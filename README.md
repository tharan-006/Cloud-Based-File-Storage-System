# Cloud-Based File Storage System (CloudVault)

A secure, multi-tenant web application developed for the **Cloud Computing** subject. The system enables users to register, log in, upload, view, search, download, and delete files through a modern, responsive web dashboard with storage quota tracking and strict tenant isolation.

---

## Table of Contents
1. [Objective & Key Features](#objective--key-features)
2. [Technology Stack](#technology-stack)
3. [Academic Distinction: Local Storage vs. AWS S3 Cloud Storage](#academic-distinction-local-storage-vs-aws-s3-cloud-storage)
4. [System Architecture](#system-architecture)
5. [Project Folder Structure](#project-folder-structure)
6. [Getting Started (Run Locally)](#getting-started-run-locally)
7. [Configuring AWS S3 Cloud Storage](#configuring-aws-s3-cloud-storage)
8. [Automated Testing](#automated-testing)
9. [Security & Access Control](#security--access-control)
10. [REST API Endpoints](#rest-api-endpoints)

---

## Objective & Key Features

### Objective
To build a scalable, secure cloud-ready file storage service demonstrating cloud computing principles, including:
- Multi-tenancy and data isolation.
- Decoupled storage abstraction using the Strategy Design Pattern.
- Elastic quota tracking and file categorization.
- Real-time cloud object management.

### Key Features
1. **User Authentication & Session Management**: Secure user registration and login with salted password hashing (Werkzeug PBKDF2/scrypt).
2. **File Uploads with Validation**: Drag-and-drop zone and file picker supporting documents (PDF, DOCX, TXT), images (PNG, JPG, SVG), archives (ZIP, TAR), media (MP4, MP3), and code/data files (JSON, CSV, PY).
3. **Multi-Tenant Access Control**: Strict database and filesystem isolation. Users can only access, view, download, or delete their own files.
4. **Interactive Dashboard**: Real-time storage meter, quota percentage bar, free space calculation, and category breakdown.
5. **Live Search & Category Filtering**: Instant real-time filtering by filename and category pills (All, Documents, Images, Media, Archives, Code, Others).
6. **File Preview Modal**: In-browser preview for images, PDFs, code, and text files without requiring downloads.
7. **Dual-Mode Storage Engine**: Runs locally out-of-the-box (zero cloud fees) and seamlessly toggles to production **AWS S3** via environment variables.
8. **Responsive UI**: Custom dark blue and white theme built with Bootstrap 5, fully optimized for laptops, tablets, and smartphones.

---

## Technology Stack

| Layer | Technologies Used |
| :--- | :--- |
| **Frontend** | HTML5, Vanilla CSS3 (custom dark blue & white theme), JavaScript (ES6+), Bootstrap 5.3, Bootstrap Icons |
| **Backend** | Python 3, Flask 3.x, Werkzeug |
| **Database** | SQLite 3 with Foreign Key enforcement and index optimization |
| **Storage Engine** | Strategy Pattern: `LocalStorageProvider` (default) & `S3StorageProvider` (boto3) |
| **Testing** | Pytest (13 automated test suites) |

---

## Academic Distinction: Local Storage vs. AWS S3 Cloud Storage

> **Important Academic Note:**
> Storing files on a local disk or server filesystem is **not** cloud storage. Local storage writes bytes into POSIX filesystem blocks on a single machine, creating a single point of failure (SPOF) limited to disk size.
> 
> Genuine cloud storage (such as **Amazon Web Services S3**) uses **Object Storage**, which stores data as discrete objects in flat namespaces referenced by unique keys, distributed across multiple availability zones (AZs) with **99.999999999% (11 9's)** durability, automatic scaling, and RESTful API access.

### Comparison Table

| Feature | Local File System (Prototype) | Amazon Web Services (AWS) S3 |
| :--- | :--- | :--- |
| **Storage Architecture** | Hierarchical directory tree on local OS disk | Flat Object Storage (Buckets and Keys) |
| **Scalability** | Bound by physical server disk capacity | Virtually limitless elastic scaling |
| **Durability** | Vulnerable to disk failure or host corruption | 11 9's durability with multi-AZ replication |
| **Access Protocol** | Local OS file descriptors (`open()`, `read()`) | HTTPS REST API, AWS SDK (`boto3`), Presigned URLs |
| **Operational Cost** | $0 (Free for academic evaluation) | Pay-as-you-go based on storage and bandwidth |
| **Isolation** | Software directory partitioning (`user_<id>`) | Cloud IAM Policies, Bucket ACLs, KMS encryption |

---

## System Architecture

```
+-------------------------------------------------------------+
|                      Client Web Browser                     |
|           (HTML5 / Custom CSS / Bootstrap 5 / JS)           |
+------------------------------+------------------------------+
                               | HTTPS / REST
+------------------------------v------------------------------+
|                         Flask Server                        |
|  - Auth & Session Management (@login_required)              |
|  - Route Controllers & Quota Enforcer                       |
|  - Input Sanitization & Access Control Verification         |
+--------------+------------------------------+---------------+
               |                              |
+--------------v---------------+ +------------v---------------+
|     SQLite Database File     | | BaseStorageProvider (Layer) |
|  - Users (Credentials/Quota) | +------+---------------+------+
|  - Files (Metadata/Keys)     |        |               |
+------------------------------+ +------v------+ +------v------+
                                 | Local Disk  | |   AWS S3    |
                                 |  Provider   | |  Provider   |
                                 +-------------+ +-------------+
```

---

## Project Folder Structure

```
cloud-file-storage/
├── app.py                 # Main Flask application and HTTP route handlers
├── config.py              # Central application configuration & quota settings
├── database.py            # SQLite database manager & schema initialization
├── models.py              # UserModel & StoredFileModel business logic
├── storage.py             # Storage abstraction layer (Local & AWS S3 providers)
├── test_app.py            # 13 automated test cases covering all requirements
├── requirements.txt       # Project dependencies
├── .env.example           # Environment template for local & AWS S3 setup
├── .gitignore             # Git ignore file for Python, DB, and uploads
├── README.md              # Project documentation and evaluation guide
├── instance/
│   └── cloud_storage.db   # SQLite database file (created automatically)
├── static/
│   ├── css/
│   │   └── style.css      # Dark blue & crisp white responsive stylesheet
│   ├── js/
│   │   ├── app.js         # Dropzone, search filter, view toggle, modals
│   │   └── auth.js        # Password toggle & live strength meter
│   └── uploads/           # Local storage directory (partitioned by user_id)
│       └── .gitkeep
└── templates/
    ├── base.html          # Base layout with navbar, storage badge & footer
    ├── login.html         # Login page with security badges
    ├── register.html      # Registration page with strength meter
    ├── dashboard.html     # Main dashboard with meters, dropzone, table & grid
    ├── profile.html       # User profile & storage allocation breakdown
    ├── cloud_info.html    # Academic cloud architecture & S3 guide
    └── 404.html           # Custom error page (403, 404, 500)
```

---

## Getting Started (Run Locally)

### Prerequisites
- Python 3.9 or higher installed on your computer.

### Step 1: Install Dependencies
Open a terminal in the project directory and install the required packages:
```bash
pip install -r requirements.txt
```

### Step 2: Initialize Configuration
Copy `.env.example` to `.env`:
```bash
# On Windows PowerShell:
Copy-Item .env.example .env

# On Linux / macOS:
cp .env.example .env
```
*(By default, `STORAGE_BACKEND=local` is set, allowing immediate offline testing without AWS credentials).*

### Step 3: Run the Application
Start the Flask development server:
```bash
python app.py
```

### Step 4: Open in Your Browser
Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

### Step 5: Test the Application
1. Click **Register Free** and create an account (e.g., `student1`, password: `Password123!`).
2. Log in with your new credentials.
3. Drag and drop any document, image, or text file into the upload zone and click **Start Upload**.
4. Test **Search**, **Category Filters**, **Table vs Grid View**, **Preview**, **Download**, and **Delete**.

---

## Configuring AWS S3 Cloud Storage

To switch from the local prototype to production Amazon S3 cloud storage:

### Step 1: Create an S3 Bucket on AWS
1. Log in to the [AWS Management Console](https://aws.amazon.com/).
2. Open **Amazon S3** and click **Create bucket**.
3. Choose a bucket name (e.g., `my-cloud-storage-vault`) and your region (e.g., `us-east-1`).
4. Keep **Block all public access** enabled.

### Step 2: Create an IAM User
1. Go to **AWS IAM** &rarr; **Users** &rarr; **Create user**.
2. Attach policy: `AmazonS3FullAccess` (or create a restricted policy for your bucket).
3. Under **Security credentials**, generate an **Access Key ID** and **Secret Access Key**.

### Step 3: Update `.env` File
Update your `.env` configuration file:
```env
STORAGE_BACKEND=s3
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_BUCKET_NAME=my-cloud-storage-vault
AWS_REGION=us-east-1
```

### Step 4: Restart the Server
Restart `python app.py`. The top navbar will display an **AWS S3 Cloud** badge, and all future uploads, downloads, and deletions will interact directly with your Amazon S3 bucket!

---

## Automated Testing

The project includes 13 automated tests verifying all core functional and security requirements.

### Running the Test Suite
Run pytest from the project root:
```bash
pytest test_app.py -v
```

### Test Coverage Summary
- `test_user_registration_success`: Validates account creation.
- `test_user_duplicate_username_fails`: Ensures unique username constraints.
- `test_user_password_too_short_fails`: Validates minimum password length.
- `test_user_login_success_and_logout`: Tests session establishment and termination.
- `test_user_login_invalid_password`: Tests authentication failure handling.
- `test_file_upload_and_listing`: Tests multipart file upload and metadata insertion.
- `test_file_search_and_filter`: Tests query search and category filtering.
- `test_file_download_and_preview`: Tests download headers and inline preview delivery.
- `test_access_control_cross_tenant_isolation`: Verifies that User B **cannot** access or delete User A's files.
- `test_file_deletion`: Tests file removal from database and physical disk.
- `test_disallowed_file_extension`: Tests whitelisting and rejection of unsafe extensions.
- `test_storage_quota_enforcement`: Tests quota limit enforcement when uploads exceed capacity.
- `test_api_storage_stats_and_files`: Tests JSON API endpoints.

---

## Security & Access Control

1. **Authentication**: Uses Werkzeug's secure hashing (`generate_password_hash` with PBKDF2/scrypt). Plaintext passwords are never stored.
2. **Access Control (Multi-Tenancy)**: All file queries enforce `WHERE user_id = session['user_id']`. If an unauthenticated or unauthorized user attempts to download or delete a file, the server returns an HTTP 403/404 error.
3. **Collision Resistance**: Uploaded files are assigned unique UUID prefixes (`uuid4().hex + '_' + secure_filename`), preventing filename collisions and path traversal attacks (`../`).
4. **Quota Protection**: Server-side checks verify total user usage before writing files to disk or cloud storage.

---

## REST API Endpoints

| Method | Endpoint | Description | Access |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | Redirects to `/dashboard` or `/login` | Public |
| `GET, POST`| `/register` | User registration | Public |
| `GET, POST`| `/login` | User authentication | Public |
| `GET` | `/logout` | Terminates session | Authenticated |
| `GET` | `/dashboard` | Main file storage dashboard | Authenticated |
| `POST` | `/upload` | Upload one or multiple files | Authenticated |
| `GET` | `/download/<file_id>`| Download stored file | Authenticated (Owner only) |
| `GET` | `/preview/<file_id>` | Stream inline preview | Authenticated (Owner only) |
| `POST` | `/delete/<file_id>` | Permanently delete file | Authenticated (Owner only) |
| `GET` | `/profile` | Account overview & quota stats | Authenticated |
| `GET` | `/cloud-info` | Academic architecture & S3 guide | Public |
| `GET` | `/api/storage-stats` | Storage metrics in JSON format | Authenticated |
| `GET` | `/api/files` | File list in JSON format | Authenticated |

---

## Academic Submission Details
- **Subject**: Cloud Computing
- **Project Name**: Cloud-Based File Storage System (CloudVault)
- **Evaluation Notice**: This project provides full offline local evaluation capability as well as complete AWS S3 production integration.
