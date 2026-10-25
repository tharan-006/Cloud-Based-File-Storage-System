import datetime
import math
from typing import Optional, List, Dict, Any
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection
from config import Config

def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


class UserModel:
    @staticmethod
    def create(username: str, email: str, password: str, full_name: Optional[str] = None) -> Optional[int]:
        """Create new user with hashed password."""
        password_hash = generate_password_hash(password)
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (username, email, password_hash, full_name)
                VALUES (?, ?, ?, ?)
                """,
                (username.strip().lower(), email.strip().lower(), password_hash, full_name.strip() if full_name else username)
            )
            conn.commit()
            user_id = cursor.lastrowid
            return user_id
        except Exception:
            return None
        finally:
            conn.close()

    @staticmethod
    def get_by_id(user_id: int) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_username_or_email(identifier: str) -> Optional[Dict[str, Any]]:
        conn = get_db_connection()
        identifier_clean = identifier.strip().lower()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier_clean, identifier_clean)
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def verify_password(stored_hash: str, password: str) -> bool:
        return check_password_hash(stored_hash, password)

    @staticmethod
    def get_storage_stats(user_id: int) -> Dict[str, Any]:
        """
        Calculate user storage analytics:
        - Total file count
        - Total bytes used
        - Quota percentage used
        - Categorized usage (Documents, Images, Media, Archives, Code, Others)
        """
        conn = get_db_connection()
        cursor = conn.cursor()

        # Total usage
        totals = cursor.execute(
            """
            SELECT COUNT(id) as total_files, COALESCE(SUM(file_size), 0) as total_bytes
            FROM files
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchone()

        total_files = totals["total_files"] if totals else 0
        total_bytes = totals["total_bytes"] if totals else 0

        # Category breakdown
        category_rows = cursor.execute(
            """
            SELECT category, COUNT(id) as count, COALESCE(SUM(file_size), 0) as bytes
            FROM files
            WHERE user_id = ?
            GROUP BY category
            """,
            (user_id,)
        ).fetchall()

        conn.close()

        quota_bytes = Config.USER_STORAGE_QUOTA_BYTES
        usage_percent = min(100.0, round((total_bytes / quota_bytes) * 100, 2)) if quota_bytes > 0 else 0
        remaining_bytes = max(0, quota_bytes - total_bytes)

        categories_summary = {
            'documents': {'count': 0, 'bytes': 0, 'formatted': '0 B'},
            'images': {'count': 0, 'bytes': 0, 'formatted': '0 B'},
            'media': {'count': 0, 'bytes': 0, 'formatted': '0 B'},
            'archives': {'count': 0, 'bytes': 0, 'formatted': '0 B'},
            'code': {'count': 0, 'bytes': 0, 'formatted': '0 B'},
            'others': {'count': 0, 'bytes': 0, 'formatted': '0 B'}
        }

        for row in category_rows:
            cat = row["category"]
            if cat in categories_summary:
                categories_summary[cat] = {
                    'count': row["count"],
                    'bytes': row["bytes"],
                    'formatted': format_file_size(row["bytes"])
                }
            else:
                categories_summary['others']['count'] += row["count"]
                categories_summary['others']['bytes'] += row["bytes"]
                categories_summary['others']['formatted'] = format_file_size(categories_summary['others']['bytes'])

        return {
            'total_files': total_files,
            'total_bytes': total_bytes,
            'total_formatted': format_file_size(total_bytes),
            'quota_bytes': quota_bytes,
            'quota_formatted': format_file_size(quota_bytes),
            'remaining_bytes': remaining_bytes,
            'remaining_formatted': format_file_size(remaining_bytes),
            'usage_percent': usage_percent,
            'categories': categories_summary
        }


class StoredFileModel:
    @staticmethod
    def create(user_id: int, filename: str, storage_key: str, file_size: int,
               file_type: str, mime_type: str, category: str,
               storage_backend: str = 'local', s3_bucket: Optional[str] = None) -> int:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO files (user_id, filename, storage_key, file_size, file_type,
                               mime_type, category, storage_backend, s3_bucket)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, filename, storage_key, file_size, file_type, mime_type, category, storage_backend, s3_bucket)
        )
        conn.commit()
        file_id = cursor.lastrowid
        conn.close()
        return file_id

    @staticmethod
    def get_by_id_and_user(file_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Strict Access Control Check: ensure the file belongs to user_id."""
        conn = get_db_connection()
        row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ?",
            (file_id, user_id)
        ).fetchone()
        conn.close()
        if row:
            d = dict(row)
            d["formatted_size"] = format_file_size(d["file_size"])
            return d
        return None

    @staticmethod
    def get_user_files(user_id: int, search: Optional[str] = None,
                       category: Optional[str] = None,
                       sort_by: str = 'date_desc') -> List[Dict[str, Any]]:
        """Fetch files for a user with optional search and category filter."""
        conn = get_db_connection()
        query = "SELECT * FROM files WHERE user_id = ?"
        params: List[Any] = [user_id]

        if search:
            query += " AND filename LIKE ?"
            params.append(f"%{search.strip()}%")

        if category and category != 'all':
            query += " AND category = ?"
            params.append(category.strip().lower())

        # Sorting logic
        sort_map = {
            'date_desc': " ORDER BY uploaded_at DESC",
            'date_asc': " ORDER BY uploaded_at ASC",
            'name_asc': " ORDER BY LOWER(filename) ASC",
            'name_desc': " ORDER BY LOWER(filename) DESC",
            'size_desc': " ORDER BY file_size DESC",
            'size_asc': " ORDER BY file_size ASC"
        }
        query += sort_map.get(sort_by, " ORDER BY uploaded_at DESC")

        rows = conn.execute(query, params).fetchall()
        conn.close()

        file_list = []
        for r in rows:
            item = dict(r)
            item["formatted_size"] = format_file_size(item["file_size"])
            file_list.append(item)
        return file_list

    @staticmethod
    def delete_by_id_and_user(file_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        """Delete file record after ownership validation."""
        conn = get_db_connection()
        file_row = conn.execute(
            "SELECT * FROM files WHERE id = ? AND user_id = ?",
            (file_id, user_id)
        ).fetchone()

        if not file_row:
            conn.close()
            return None

        file_dict = dict(file_row)
        conn.execute("DELETE FROM files WHERE id = ? AND user_id = ?", (file_id, user_id))
        conn.commit()
        conn.close()
        return file_dict
