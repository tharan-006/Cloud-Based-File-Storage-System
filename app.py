import os
import uuid
import mimetypes
from functools import wraps
from pathlib import Path
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_file, jsonify, abort, Response
)
from werkzeug.utils import secure_filename

from config import Config
from database import init_db
from models import UserModel, StoredFileModel
from storage import get_storage_provider, LocalStorageProvider, S3StorageProvider

app = Flask(__name__)
app.config.from_object(Config)

# Ensure database and local storage folders exist
init_db()
Config.UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Authentication Helper & Decorator
# ============================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_global_context():
    """Inject current_user and storage provider info into all templates."""
    current_user = None
    if "user_id" in session:
        current_user = UserModel.get_by_id(session["user_id"])
    
    storage_provider = get_storage_provider()
    storage_info = storage_provider.check_status()
    
    return {
        "current_user": current_user,
        "storage_info": storage_info,
        "max_upload_mb": Config.MAX_CONTENT_LENGTH_MB,
        "quota_mb": Config.USER_STORAGE_QUOTA_MB
    }


# ============================================================================
# Authentication Routes
# ============================================================================
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        if not username or not email or not password:
            flash("All required fields must be filled.", "danger")
            return render_template("register.html", username=username, email=email, full_name=full_name)

        if len(username) < 3 or len(username) > 30:
            flash("Username must be between 3 and 30 characters.", "danger")
            return render_template("register.html", username=username, email=email, full_name=full_name)

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template("register.html", username=username, email=email, full_name=full_name)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", username=username, email=email, full_name=full_name)

        if UserModel.get_by_username_or_email(username):
            flash("Username is already registered. Please choose another.", "danger")
            return render_template("register.html", username=username, email=email, full_name=full_name)

        if UserModel.get_by_username_or_email(email):
            flash("Email address is already in use.", "danger")
            return render_template("register.html", username=username, email=email, full_name=full_name)

        user_id = UserModel.create(username, email, password, full_name)
        if user_id:
            flash("Account registered successfully! You can now log in.", "success")
            return redirect(url_for("login"))
        else:
            flash("Registration failed due to a system error. Please try again.", "danger")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("Please enter both username/email and password.", "danger")
            return render_template("login.html")

        user = UserModel.get_by_username_or_email(identifier)
        if user and UserModel.verify_password(user["password_hash"], password):
            # Establish session
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"] or user["username"]
            
            flash(f"Welcome back, {user['full_name'] or user['username']}!", "success")
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials. Please verify your username/email and password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("login"))


# ============================================================================
# Dashboard & Core File Storage Routes
# ============================================================================
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    search_query = request.args.get("search", "").strip()
    category = request.args.get("category", "all").strip().lower()
    sort_by = request.args.get("sort", "date_desc")

    files = StoredFileModel.get_user_files(
        user_id=user_id,
        search=search_query if search_query else None,
        category=category if category != "all" else None,
        sort_by=sort_by
    )

    stats = UserModel.get_storage_stats(user_id)

    return render_template(
        "dashboard.html",
        files=files,
        stats=stats,
        search_query=search_query,
        active_category=category,
        active_sort=sort_by
    )


@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    user_id = session["user_id"]
    
    if "files" not in request.files and "file" not in request.files:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": "No file part in request."}), 400
        flash("No file was selected for upload.", "danger")
        return redirect(url_for("dashboard"))

    uploaded_files = request.files.getlist("files")
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ""):
        uploaded_files = [request.files.get("file")]

    uploaded_files = [f for f in uploaded_files if f and f.filename.strip() != ""]
    if not uploaded_files:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": "No files selected."}), 400
        flash("No valid files were selected.", "danger")
        return redirect(url_for("dashboard"))

    stats = UserModel.get_storage_stats(user_id)
    current_used = stats["total_bytes"]
    quota_limit = Config.USER_STORAGE_QUOTA_BYTES
    storage_provider = get_storage_provider()

    success_count = 0
    errors = []

    for file_obj in uploaded_files:
        original_name = file_obj.filename
        safe_name = secure_filename(original_name)
        if not safe_name:
            safe_name = f"file_{uuid.uuid4().hex[:8]}"

        ext = safe_name.rsplit(".", 1)[1].lower() if "." in safe_name else ""
        if ext not in Config.ALLOWED_EXTENSIONS:
            errors.append(f"'{original_name}': File extension '.{ext}' is not permitted.")
            continue

        # Check file size by seeking stream
        file_obj.seek(0, os.SEEK_END)
        size = file_obj.tell()
        file_obj.seek(0)

        if size > Config.MAX_CONTENT_LENGTH:
            errors.append(f"'{original_name}': Exceeds max allowed size of {Config.MAX_CONTENT_LENGTH_MB} MB.")
            continue

        if current_used + size > quota_limit:
            errors.append(f"'{original_name}': Upload exceeds your allocated {Config.USER_STORAGE_QUOTA_MB} MB storage quota.")
            continue

        # Generate unique storage key to prevent collisions and directory traversal
        unique_key = f"{uuid.uuid4().hex}_{safe_name}"
        category = Config.get_file_category(safe_name)
        mime_type, _ = mimetypes.guess_type(safe_name)
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            saved_size = storage_provider.save_file(file_obj, unique_key, user_id)
            backend_name = "s3" if isinstance(storage_provider, S3StorageProvider) else "local"
            s3_bucket = Config.AWS_BUCKET_NAME if backend_name == "s3" else None

            StoredFileModel.create(
                user_id=user_id,
                filename=original_name,
                storage_key=unique_key,
                file_size=saved_size,
                file_type=ext,
                mime_type=mime_type,
                category=category,
                storage_backend=backend_name,
                s3_bucket=s3_bucket
            )
            current_used += saved_size
            success_count += 1
        except Exception as e:
            errors.append(f"'{original_name}': Storage error ({str(e)})")

    # Respond appropriately for AJAX or regular form submit
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_ajax:
        return jsonify({
            "success": success_count > 0,
            "uploaded": success_count,
            "errors": errors
        })

    if success_count > 0:
        flash(f"Successfully uploaded {success_count} file(s)!", "success")
    if errors:
        for err in errors:
            flash(err, "danger")

    return redirect(url_for("dashboard"))


@app.route("/download/<int:file_id>")
@login_required
def download_file(file_id: int):
    user_id = session["user_id"]
    # Access Control: strict multi-tenancy verification
    file_record = StoredFileModel.get_by_id_and_user(file_id, user_id)
    if not file_record:
        abort(404, description="File not found or access denied.")

    storage_provider = get_storage_provider()

    # If backend is S3 and presigned URL generation is supported
    if file_record["storage_backend"] == "s3" and isinstance(storage_provider, S3StorageProvider):
        presigned_url = storage_provider.generate_presigned_download_url(
            file_record["storage_key"], user_id, file_record["filename"]
        )
        if presigned_url:
            return redirect(presigned_url)
        # Fallback to streaming through Flask
        stream = storage_provider.get_download_stream(file_record["storage_key"], user_id)
        if stream:
            return Response(
                stream.read(),
                mimetype=file_record["mime_type"],
                headers={"Content-Disposition": f'attachment; filename="{file_record["filename"]}"'}
            )

    # Local storage download
    local_path = storage_provider.get_file_path(file_record["storage_key"], user_id)
    if not local_path or not local_path.exists():
        abort(404, description="Physical file not found on storage server.")

    return send_file(
        str(local_path),
        as_attachment=True,
        download_name=file_record["filename"],
        mimetype=file_record["mime_type"]
    )


@app.route("/preview/<int:file_id>")
@login_required
def preview_file(file_id: int):
    user_id = session["user_id"]
    file_record = StoredFileModel.get_by_id_and_user(file_id, user_id)
    if not file_record:
        abort(404, description="File not found or access denied.")

    storage_provider = get_storage_provider()
    
    # For local storage preview
    if file_record["storage_backend"] == "local" or isinstance(storage_provider, LocalStorageProvider):
        local_path = storage_provider.get_file_path(file_record["storage_key"], user_id)
        if not local_path or not local_path.exists():
            abort(404, description="Physical file missing.")
        return send_file(
            str(local_path),
            as_attachment=False,
            download_name=file_record["filename"],
            mimetype=file_record["mime_type"]
        )
    
    # For S3 storage preview
    stream = storage_provider.get_download_stream(file_record["storage_key"], user_id)
    if stream:
        return Response(stream.read(), mimetype=file_record["mime_type"])
    
    abort(404, description="Could not load file preview.")


@app.route("/delete/<int:file_id>", methods=["POST"])
@login_required
def delete_file(file_id: int):
    user_id = session["user_id"]
    # Access Control: ensure file belongs to user
    file_record = StoredFileModel.get_by_id_and_user(file_id, user_id)
    if not file_record:
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "error": "File not found or permission denied."}), 404
        flash("File not found or unauthorized.", "danger")
        return redirect(url_for("dashboard"))

    # Delete physical/cloud asset
    storage_provider = get_storage_provider()
    storage_provider.delete_file(file_record["storage_key"], user_id)

    # Delete database record
    StoredFileModel.delete_by_id_and_user(file_id, user_id)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        new_stats = UserModel.get_storage_stats(user_id)
        return jsonify({
            "success": True,
            "message": f"'{file_record['filename']}' deleted successfully.",
            "stats": new_stats
        })

    flash(f"File '{file_record['filename']}' has been permanently deleted.", "success")
    return redirect(url_for("dashboard"))


# ============================================================================
# User Profile & Cloud Info Pages
# ============================================================================
@app.route("/profile")
@login_required
def profile():
    user_id = session["user_id"]
    user = UserModel.get_by_id(user_id)
    stats = UserModel.get_storage_stats(user_id)
    return render_template("profile.html", user=user, stats=stats)


@app.route("/cloud-info")
def cloud_info():
    """Educational page explaining cloud storage concepts, architecture, and S3 guide."""
    storage_provider = get_storage_provider()
    storage_info = storage_provider.check_status()
    return render_template("cloud_info.html", storage_info=storage_info)


# ============================================================================
# API Endpoints
# ============================================================================
@app.route("/api/storage-stats")
@login_required
def api_storage_stats():
    user_id = session["user_id"]
    stats = UserModel.get_storage_stats(user_id)
    return jsonify(stats)


@app.route("/api/files")
@login_required
def api_files():
    user_id = session["user_id"]
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "all").strip().lower()
    sort_by = request.args.get("sort", "date_desc")
    files = StoredFileModel.get_user_files(
        user_id=user_id,
        search=search if search else None,
        category=category if category != "all" else None,
        sort_by=sort_by
    )
    return jsonify({"files": files})


# ============================================================================
# Custom Error Handlers
# ============================================================================
@app.errorhandler(413)
def request_entity_too_large(error):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({
            "success": False,
            "error": f"File is too large! Maximum allowed upload size is {Config.MAX_CONTENT_LENGTH_MB} MB."
        }), 413
    flash(f"Upload failed: File exceeds maximum allowed limit of {Config.MAX_CONTENT_LENGTH_MB} MB.", "danger")
    return redirect(url_for("dashboard"))


@app.errorhandler(403)
def forbidden_error(error):
    return render_template("404.html", error_code="403", error_message="Access Forbidden: You do not have permission to access this resource."), 403


@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html", error_code="404", error_message="Resource not found."), 404


@app.errorhandler(500)
def internal_server_error(error):
    return render_template("404.html", error_code="500", error_message="Internal Server Error: Something went wrong on the server."), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
