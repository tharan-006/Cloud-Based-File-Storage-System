import io
import os
import shutil
import tempfile
import pytest
from app import app
from database import init_db, get_db_connection
from models import UserModel, StoredFileModel
from config import Config

@pytest.fixture
def client():
    # Set up temporary directory for test DB and uploads
    temp_dir = tempfile.mkdtemp()
    test_db = os.path.join(temp_dir, "test_cloud.db")
    test_uploads = os.path.join(temp_dir, "uploads")
    os.makedirs(test_uploads, exist_ok=True)

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    Config.DATABASE_PATH = test_db
    Config.UPLOAD_FOLDER = test_uploads
    Config.STORAGE_BACKEND = "local"
    # Small quota for testing quota limits
    Config.USER_STORAGE_QUOTA_BYTES = 100 * 1024  # 100 KB for quick quota testing

    with app.app_context():
        # Initialize test database
        conn = get_db_connection()
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            storage_key TEXT UNIQUE NOT NULL,
            file_size INTEGER NOT NULL,
            file_type TEXT NOT NULL,
            mime_type TEXT DEFAULT 'application/octet-stream',
            category TEXT DEFAULT 'others',
            storage_backend TEXT NOT NULL DEFAULT 'local',
            s3_bucket TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """)
        conn.commit()
        conn.close()

    with app.test_client() as client:
        yield client

    # Cleanup temporary directory
    shutil.rmtree(temp_dir, ignore_errors=True)


def register_user(client, username="alice", email="alice@test.com", password="password123", full_name="Alice Wonder"):
    return client.post("/register", data={
        "username": username,
        "email": email,
        "password": password,
        "confirm_password": password,
        "full_name": full_name
    }, follow_redirects=True)


def login_user(client, identifier="alice", password="password123"):
    return client.post("/login", data={
        "identifier": identifier,
        "password": password
    }, follow_redirects=True)


# ============================================================================
# 1. User Registration & Authentication Tests
# ============================================================================
def test_user_registration_success(client):
    res = register_user(client, "testuser", "test@test.com", "secure123", "Test User")
    assert res.status_code == 200
    assert b"Account registered successfully" in res.data


def test_user_duplicate_username_fails(client):
    register_user(client, "duplicateuser", "user1@test.com", "pass1234")
    res = register_user(client, "duplicateuser", "user2@test.com", "pass1234")
    assert b"Username is already registered" in res.data


def test_user_password_too_short_fails(client):
    res = register_user(client, "shortpassuser", "short@test.com", "123")
    assert b"Password must be at least 6 characters" in res.data


def test_user_login_success_and_logout(client):
    register_user(client, "bob", "bob@test.com", "password123")
    res = login_user(client, "bob", "password123")
    assert res.status_code == 200
    assert b"Welcome back" in res.data

    # Test logout
    logout_res = client.get("/logout", follow_redirects=True)
    assert b"You have been logged out" in logout_res.data


def test_user_login_invalid_password(client):
    register_user(client, "charlie", "charlie@test.com", "password123")
    res = login_user(client, "charlie", "wrongpassword")
    assert b"Invalid credentials" in res.data


# ============================================================================
# 2. File Upload, List & Quota Tests
# ============================================================================
def test_file_upload_and_listing(client):
    register_user(client, "uploader", "uploader@test.com", "password123")
    login_user(client, "uploader", "password123")

    # Upload sample text file
    file_data = (io.BytesIO(b"Cloud Computing Final Project Test Content"), "sample_notes.txt")
    res = client.post("/upload", data={"files": file_data}, content_type="multipart/form-data", follow_redirects=True)
    assert res.status_code == 200
    assert b"Successfully uploaded 1 file(s)" in res.data
    assert b"sample_notes.txt" in res.data


def test_file_search_and_filter(client):
    register_user(client, "searcher", "searcher@test.com", "password123")
    login_user(client, "searcher", "password123")

    # Upload two files
    client.post("/upload", data={"files": (io.BytesIO(b"image data"), "vacation.png")}, content_type="multipart/form-data")
    client.post("/upload", data={"files": (io.BytesIO(b"report data"), "annual_report.pdf")}, content_type="multipart/form-data")

    # Search for report
    res_search = client.get("/dashboard?search=report")
    assert b"annual_report.pdf" in res_search.data
    assert b"vacation.png" not in res_search.data

    # Filter by category 'images'
    res_images = client.get("/dashboard?category=images")
    assert b"vacation.png" in res_images.data
    assert b"annual_report.pdf" not in res_images.data


# ============================================================================
# 3. File Download & Preview Tests
# ============================================================================
def test_file_download_and_preview(client):
    register_user(client, "downloader", "downloader@test.com", "password123")
    login_user(client, "downloader", "password123")

    test_content = b"Antigravity Secure Cloud Storage Content"
    client.post("/upload", data={"files": (io.BytesIO(test_content), "cloud_test.txt")}, content_type="multipart/form-data")

    # Retrieve file record ID
    files = StoredFileModel.get_user_files(1)
    assert len(files) == 1
    file_id = files[0]["id"]

    # Test download
    dl_res = client.get(f"/download/{file_id}")
    assert dl_res.status_code == 200
    assert dl_res.data == test_content
    assert "attachment" in dl_res.headers.get("Content-Disposition", "")

    # Test preview
    preview_res = client.get(f"/preview/{file_id}")
    assert preview_res.status_code == 200
    assert preview_res.data == test_content


# ============================================================================
# 4. Strict Access Control & Multi-Tenancy Isolation Test
# ============================================================================
def test_access_control_cross_tenant_isolation(client):
    """
    CRITICAL CLOUD SECURITY TEST:
    User B must NEVER be able to view, download, or delete User A's files.
    """
    # Register & Login User A (Alice)
    register_user(client, "user_a", "usera@test.com", "password123")
    login_user(client, "user_a", "password123")
    client.post("/upload", data={"files": (io.BytesIO(b"CONFIDENTIAL DATA FOR USER A"), "user_a_secret.txt")}, content_type="multipart/form-data")

    user_a_files = StoredFileModel.get_user_files(1)
    file_id_a = user_a_files[0]["id"]

    # Log out User A, Register & Login User B (Bob)
    client.get("/logout")
    register_user(client, "user_b", "userb@test.com", "password123")
    login_user(client, "user_b", "password123")

    # User B tries to download User A's file
    cross_download_res = client.get(f"/download/{file_id_a}")
    assert cross_download_res.status_code in [404, 403]

    # User B tries to preview User A's file
    cross_preview_res = client.get(f"/preview/{file_id_a}")
    assert cross_preview_res.status_code in [404, 403]

    # User B tries to delete User A's file
    cross_delete_res = client.post(f"/delete/{file_id_a}", follow_redirects=True)
    assert b"File not found or unauthorized" in cross_delete_res.data

    # Verify User A's file is still safe and intact in database
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM files WHERE id = ?", (file_id_a,)).fetchone()
    conn.close()
    assert row is not None


# ============================================================================
# 5. File Deletion & Quota Recalculation Test
# ============================================================================
def test_file_deletion(client):
    register_user(client, "deleter", "deleter@test.com", "password123")
    login_user(client, "deleter", "password123")

    client.post("/upload", data={"files": (io.BytesIO(b"Temporary file content"), "temp.txt")}, content_type="multipart/form-data")
    files = StoredFileModel.get_user_files(1)
    file_id = files[0]["id"]

    # Delete file
    del_res = client.post(f"/delete/{file_id}", follow_redirects=True)
    assert del_res.status_code == 200
    assert b"has been permanently deleted" in del_res.data

    # Ensure list is now empty
    files_after = StoredFileModel.get_user_files(1)
    assert len(files_after) == 0


# ============================================================================
# 6. File Validation & Quota Enforcement Tests
# ============================================================================
def test_disallowed_file_extension(client):
    register_user(client, "hacker", "hacker@test.com", "password123")
    login_user(client, "hacker", "password123")

    # Attempt to upload disallowed .exe file
    res = client.post(
        "/upload",
        data={"files": (io.BytesIO(b"binary executable"), "malicious.exe")},
        content_type="multipart/form-data",
        follow_redirects=True
    )
    assert b"is not permitted" in res.data
    files = StoredFileModel.get_user_files(1)
    assert len(files) == 0


def test_storage_quota_enforcement(client):
    register_user(client, "quotatester", "quota@test.com", "password123")
    login_user(client, "quotatester", "password123")

    # Client fixture sets USER_STORAGE_QUOTA_BYTES = 100 * 1024 (100 KB)
    # Attempt to upload 120 KB file
    big_file = io.BytesIO(b"A" * (120 * 1024))
    res = client.post(
        "/upload",
        data={"files": (big_file, "large_file.txt")},
        content_type="multipart/form-data",
        follow_redirects=True
    )
    assert b"Upload exceeds your allocated" in res.data
    files = StoredFileModel.get_user_files(1)
    assert len(files) == 0


# ============================================================================
# 7. JSON API Endpoints Tests
# ============================================================================
def test_api_storage_stats_and_files(client):
    register_user(client, "apitester", "api@test.com", "password123")
    login_user(client, "apitester", "password123")

    client.post("/upload", data={"files": (io.BytesIO(b"Data for API"), "data.json")}, content_type="multipart/form-data")

    # Test /api/storage-stats
    stats_res = client.get("/api/storage-stats")
    assert stats_res.status_code == 200
    stats_json = stats_res.get_json()
    assert stats_json["total_files"] == 1
    assert "categories" in stats_json
    assert stats_json["categories"]["code"]["count"] == 1

    # Test /api/files
    files_res = client.get("/api/files")
    assert files_res.status_code == 200
    files_json = files_res.get_json()
    assert len(files_json["files"]) == 1
    assert files_json["files"][0]["filename"] == "data.json"

