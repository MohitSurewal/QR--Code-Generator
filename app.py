import base64
import io
import json
import os
from datetime import datetime, time, timezone
import time
import cloudinary
import cloudinary.uploader
import firebase_admin
import qrcode
from dotenv import load_dotenv
from firebase_admin import credentials, firestore
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash


load_dotenv()

app = Flask(__name__)


app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-fallback-secret-change-me")
max_mb = int(os.environ.get("MAX_UPLOAD_MB", "100"))
app.config["MAX_CONTENT_LENGTH"] = max_mb * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"

csrf = CSRFProtect(app)


ADMIN_USERNAME = (os.environ.get("ADMIN_USERNAME") or "admin").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "Admin@12345"
ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)


CLOUDINARY_CLOUD_NAME = (os.environ.get("CLOUDINARY_CLOUD_NAME") or "").strip()
CLOUDINARY_API_KEY = (os.environ.get("CLOUDINARY_API_KEY") or "").strip()
CLOUDINARY_API_SECRET = (os.environ.get("CLOUDINARY_API_SECRET") or "").strip()

cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)




LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 120


def _check_login_lock() -> int:

    locked_until = session.get("admin_locked_until", 0)
    now = time.time()
    if locked_until and now < locked_until:
        return int(locked_until - now)
    if locked_until and now >= locked_until:
        session.pop("admin_locked_until", None)
        session["admin_failed_attempts"] = 0
    return 0


def _record_failed_login() -> None:
    attempts = int(session.get("admin_failed_attempts", 0)) + 1
    session["admin_failed_attempts"] = attempts
    if attempts >= LOGIN_MAX_ATTEMPTS:
        session["admin_locked_until"] = time.time() + LOGIN_LOCK_SECONDS


def _reset_login_attempts() -> None:
    session.pop("admin_failed_attempts", None)
    session.pop("admin_locked_until", None)



def cloudinary_is_configured() -> bool:
    return bool(CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET)



db = None
if not firebase_admin._apps:
    cred_raw = (os.environ.get("FIREBASE_CREDENTIALS_JSON") or "").strip()
    if cred_raw:
        try:
            if (cred_raw.startswith("'") and cred_raw.endswith("'")) or (
                cred_raw.startswith('"') and cred_raw.endswith('"')
            ):
                cred_raw = cred_raw[1:-1]

            if not cred_raw.lstrip().startswith("{"):
                cred_raw = base64.b64decode(cred_raw).decode("utf-8")

            cred_dict = json.loads(cred_raw)

            if isinstance(cred_dict.get("private_key"), str):
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as exc:
            print(f"[Firebase Init Error] {exc}")

if firebase_admin._apps:
    try:
        db = firestore.client()
    except Exception as exc:
        print(f"[Firestore Client Error] {exc}")



ROOT_CLOUDINARY_DIR = "qr generator"

CLOUDINARY_FOLDERS = {
    ("public", "photo"): f"{ROOT_CLOUDINARY_DIR}/public/photos",
    ("public", "video"): f"{ROOT_CLOUDINARY_DIR}/public/videos",
    ("public", "doc"): f"{ROOT_CLOUDINARY_DIR}/public/docs",
    ("admin", "photo"): f"{ROOT_CLOUDINARY_DIR}/admin/photos",
    ("admin", "video"): f"{ROOT_CLOUDINARY_DIR}/admin/videos",
    ("admin", "doc"): f"{ROOT_CLOUDINARY_DIR}/admin/docs",
}

ALLOWED_DOC_EXTENSIONS = {
    ".doc",
    ".docx",
    ".pdf",
    ".xml",
    ".ppt",
    ".pptx",
}


def upload_media_to_cloudinary(file_storage, folder: str) -> dict:
    """Upload image or video into a dedicated Cloudinary folder."""
    if not cloudinary_is_configured():
        raise RuntimeError("Cloudinary environment variables are missing.")

    res = cloudinary.uploader.upload(
        file_storage,
        folder=folder,
        resource_type="auto",
    )
    return {
        "secure_url": res.get("secure_url"),
        "public_id": res.get("public_id"),
        "folder": folder,
        "resource_type": res.get("resource_type"),
        "format": res.get("format"),
        "bytes": res.get("bytes"),
    }


def upload_doc_to_cloudinary(file_storage, folder: str) -> dict:
   
    if not cloudinary_is_configured():
        raise RuntimeError("Cloudinary environment variables are missing.")

    res = cloudinary.uploader.upload(
        file_storage,
        folder=folder,
        resource_type="raw",
        use_filename=True,
        unique_filename=True,
    )
    return {
        "secure_url": res.get("secure_url"),
        "public_id": res.get("public_id"),
        "folder": folder,
        "resource_type": res.get("resource_type"),
        "bytes": res.get("bytes"),
    }


def save_metadata_firestore(collection_name: str, data: dict) -> bool:
    
    if db is None:
        print(f"[Firestore Warning] db is None; skipped saving to '{collection_name}'.")
        return False
    try:
        payload = dict(data)
        payload["created_at"] = datetime.now(timezone.utc)
        db.collection(collection_name).add(payload)
        return True
    except Exception as exc:
        print(f"[Firestore Write Error] collection='{collection_name}': {exc}")
        return False
    
    
    
def _format_created_at(val) -> str:
    if not val:
        return "—"
    try:
        if hasattr(val, "to_datetime"):
            val = val.to_datetime()
        if isinstance(val, datetime):
            if val.tzinfo is None:
                val = val.replace(tzinfo=timezone.utc)
            return val.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return str(val)
    except Exception:
        return "—"


def get_photo_qr_metadata(limit: int = 50) -> list[dict]:

    if db is None:
        return []

    records: list[dict] = []

    sources = [
        ("public_qr_logs", "Public User"),
        ("admin_qr_items", "Admin"),
    ]

    for col_name, default_actor in sources:
        try:
            docs = (
                db.collection(col_name)
                .where("type", "==", "photo")
                .limit(limit)
                .stream()
            )
            for doc in docs:
                item = doc.to_dict() or {}
                url = item.get("media_url") or item.get("url") or ""
                records.append({
                    "id": doc.id,
                    "source_label": default_actor if item.get("source") != "admin" else "Admin",
                    "title": item.get("title") or "Photo QR",
                    "url": url,
                    "folder": item.get("folder") or "—",
                    "public_id": item.get("cloudinary_public_id") or item.get("public_id") or "—",
                    "format": (item.get("format") or "—").upper(),
                    "bytes": item.get("bytes"),
                    "created_by": item.get("created_by") or default_actor,
                    "created_at_str": _format_created_at(item.get("created_at")),
                    "_sort_ts": item.get("created_at"),
                })
        except Exception as exc:
            print(f"[Firestore Read Error] collection='{col_name}': {exc}")


    records.sort(
        key=lambda r: (
            r["_sort_ts"].to_datetime()
            if hasattr(r["_sort_ts"], "to_datetime")
            else (r["_sort_ts"] if isinstance(r["_sort_ts"], datetime) else datetime.min.replace(tzinfo=timezone.utc))
        ),
        reverse=True,
    )
    return records[:limit]



def delete_photo_qr_record(collection_name: str, doc_id: str) -> tuple[bool, str]:
    """Delete a photo QR record from Firestore and its asset from Cloudinary if present."""
    if db is None:
        return False, "Firestore is not connected."
    if collection_name not in ("public_qr_logs", "admin_qr_items"):
        return False, "Invalid metadata collection."

    try:
        doc_ref = db.collection(collection_name).document(doc_id)
        snap = doc_ref.get()
        if not snap.exists:
            return False, "Record not found."

        data = snap.to_dict() or {}
        public_id = data.get("cloudinary_public_id") or data.get("public_id")
        folder = data.get("folder") or ""

        if public_id and cloudinary_is_configured():
            resource_type = "video" if "videos" in folder else "image"
            try:
                cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            except Exception as c_exc:
                print(f"[Cloudinary Delete Warning] {c_exc}")

        doc_ref.delete()
        return True, "Photo QR metadata and associated media removed."
    except Exception as exc:
        print(f"[Firestore Delete Error] {exc}")
        return False, f"Failed to delete record: {exc}"


def make_qr_data_uri(payload: str) -> str:
    
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def is_admin() -> bool:
    return (
        session.get("is_admin") is True
        and session.get("admin_user") == ADMIN_USERNAME
    )


def require_admin():
    if not is_admin():
        session.clear()
        flash("Please sign in as admin to access this page.", "error")
        return redirect(url_for("admin_login"))
    return None


@app.after_request
def add_security_headers(response):
    
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response



@app.route("/", methods=["GET", "POST"])
def index():
    qr_uri = None
    target_url = None

    if request.method == "POST":
        link = (request.form.get("url") or "").strip()
        if not (link.startswith("http://") or link.startswith("https://")):
            flash("Please enter a valid URL starting with http:// or https://", "error")
        else:
            target_url = link
            qr_uri = make_qr_data_uri(link)
            save_metadata_firestore(
                "public_qr_logs",
                {
                    "source": "public",
                    "type": "link",
                    "folder": "none",
                    "target_url": link,
                },
            )

    return render_template("index.html", qr_uri=qr_uri, target_url=target_url)


@app.route("/photo", methods=["GET", "POST"])
def photo_qr():
    qr_uri = None
    media_url = None

    if request.method == "POST":
        file = request.files.get("photo")
        if not file or not file.filename:
            flash("Please select a photo file.", "error")
        elif not (file.mimetype or "").startswith("image/"):
            flash("Only image files are allowed on the Photo QR page.", "error")
        else:
            try:
                folder = CLOUDINARY_FOLDERS[("public", "photo")]
                uploaded = upload_media_to_cloudinary(file, folder=folder)
                media_url = uploaded["secure_url"]
                qr_uri = make_qr_data_uri(media_url)
                save_metadata_firestore(
                    "public_qr_logs",
                    {
                        "source": "public",
                        "type": "photo",
                        "folder": folder,
                        "media_url": media_url,
                        "cloudinary_public_id": uploaded["public_id"],
                        "format": uploaded["format"],
                        "bytes": uploaded["bytes"],
                    },
                )
            except Exception as exc:
                flash(f"Upload failed: {exc}", "error")

    return render_template("photo_qr.html", qr_uri=qr_uri, media_url=media_url)


@app.route("/video", methods=["GET", "POST"])
def video_qr():
    qr_uri = None
    media_url = None

    if request.method == "POST":
        file = request.files.get("video")
        if not file or not file.filename:
            flash("Please select a video file.", "error")
        elif not (file.mimetype or "").startswith("video/"):
            flash("Only video files are allowed on the Video QR page.", "error")
        else:
            folder = CLOUDINARY_FOLDERS[("public", "video")]
            uploaded = upload_media_to_cloudinary(file, folder=folder)
            media_url = uploaded["secure_url"]
            qr_uri = make_qr_data_uri(media_url)
            save_metadata_firestore(
                "public_qr_logs",
                {
                    "source": "public",
                    "type": "video",
                    "folder": folder,
                    "media_url": media_url,
                    "cloudinary_public_id": uploaded["public_id"],
                    "format": uploaded["format"],
                    "bytes": uploaded["bytes"],
                },
            )

    return render_template("video_qr.html", qr_uri=qr_uri, media_url=media_url)


@app.route("/doc", methods=["GET", "POST"])
def doc_qr():
    qr_uri = None
    doc_url = None
    doc_ext = None

    if request.method == "POST":
        file = request.files.get("document")
        if not file or not file.filename:
            flash("Please select a Word, PDF, XML, or PowerPoint file.", "error")
        else:
            ext = os.path.splitext(file.filename.lower())[1]
            if ext not in ALLOWED_DOC_EXTENSIONS:
                flash(
                    "Unsupported file format. Allowed: Word (.doc, .docx), PDF (.pdf), XML (.xml), PowerPoint (.ppt, .pptx).",
                    "error",
                )
            else:
                folder = CLOUDINARY_FOLDERS[("public", "doc")]
                uploaded = upload_doc_to_cloudinary(file, folder=folder)
                doc_url = uploaded["secure_url"]
                doc_ext = ext.lstrip(".").upper()
                qr_uri = make_qr_data_uri(doc_url)
                save_metadata_firestore(
                    "public_qr_logs",
                    {
                        "source": "public",
                        "type": "document",
                        "folder": folder,
                        "format": doc_ext,
                        "doc_url": doc_url,
                        "cloudinary_public_id": uploaded["public_id"],
                        "bytes": uploaded["bytes"],
                    },
                )

    return render_template(
        "doc_qr.html",
        qr_uri=qr_uri,
        doc_url=doc_url,
        doc_ext=doc_ext,
    )


@app.route("/about")
def about():
    return render_template("about.html")





@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if is_admin():
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        remaining = _check_login_lock()
        if remaining > 0:
            flash(f"Too many failed attempts. Try again in {remaining} seconds.", "error")
            return render_template("admin_login.html"), 429

        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            _reset_login_attempts()
            session.clear()
            session["is_admin"] = True
            session["admin_user"] = username
            return redirect(url_for("admin_dashboard"))

        _record_failed_login()
        flash("Invalid admin username or password.", "error")

    return render_template("admin_login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("admin_login"))


@app.route("/admin", methods=["GET", "POST"])
def admin_dashboard():
    guard = require_admin()
    if guard:
        return guard

    qr_uri = None
    result_url = None

    if request.method == "POST":
        upload_type = request.form.get("upload_type")
        title = (request.form.get("title") or "").strip()

        if upload_type == "link":
            link = (request.form.get("url") or "").strip()
            if not (link.startswith("http://") or link.startswith("https://")):
                flash("Please enter a valid URL starting with http:// or https://", "error")
            else:
                result_url = link
                qr_uri = make_qr_data_uri(link)
                save_metadata_firestore(
                    "admin_qr_items",
                    {
                        "source": "admin",
                        "title": title,
                        "type": "link",
                        "folder": "none",
                        "url": link,
                        "created_by": session.get("admin_user"),
                    },
                )
                flash("Link QR generated and metadata saved to Firestore.", "success")

        elif upload_type in ("photo", "video"):
            file = request.files.get("media_file")
            if not file or not file.filename:
                flash(f"Please select a {upload_type} file.", "error")
            else:
                try:
                    folder = CLOUDINARY_FOLDERS[("admin", upload_type)]
                    uploaded = upload_media_to_cloudinary(file, folder=folder)
                    result_url = uploaded["secure_url"]
                    qr_uri = make_qr_data_uri(result_url)
                    save_metadata_firestore(
                        "admin_qr_items",
                        {
                            "source": "admin",
                            "title": title,
                            "type": upload_type,
                            "folder": folder,
                            "url": result_url,
                            "cloudinary_public_id": uploaded["public_id"],
                            "format": uploaded["format"],
                            "bytes": uploaded["bytes"],
                            "created_by": session.get("admin_user"),
                        },
                    )
                    flash(
                        f"{upload_type.capitalize()} uploaded to Cloudinary and metadata saved to Firestore.",
                        "success",
                    )
                except Exception as exc:
                    flash(f"Upload failed: {exc}", "error")

        elif upload_type == "doc":
            file = request.files.get("doc_file")
            if not file or not file.filename:
                flash("Please select a Word, PDF, XML, or PowerPoint file.", "error")
            else:
                ext = os.path.splitext(file.filename.lower())[1]
                if ext not in ALLOWED_DOC_EXTENSIONS:
                    flash(
                        "Unsupported file format. Allowed: Word (.doc, .docx), PDF (.pdf), XML (.xml), PowerPoint (.ppt, .pptx).",
                        "error",
                    )
                else:
                    try:
                        folder = CLOUDINARY_FOLDERS[("admin", "doc")]
                        uploaded = upload_doc_to_cloudinary(file, folder=folder)
                        result_url = uploaded["secure_url"]
                        doc_ext = ext.lstrip(".").upper()
                        qr_uri = make_qr_data_uri(result_url)
                        save_metadata_firestore(
                            "admin_qr_items",
                            {
                                "source": "admin",
                                "title": title,
                                "type": "document",
                                "folder": folder,
                                "format": doc_ext,
                                "url": result_url,
                                "cloudinary_public_id": uploaded["public_id"],
                                "bytes": uploaded["bytes"],
                                "created_by": session.get("admin_user"),
                            },
                        )
                        flash(
                            "Document uploaded to Cloudinary and metadata saved to Firestore.",
                            "success",
                        )
                    except Exception as exc:
                        flash(f"Upload failed: {exc}", "error")

        else:
            flash("Please choose a valid upload type.", "error")

    photo_metadata = get_photo_qr_metadata(limit=50)
    return render_template(
        "admin_dashboard.html",
        qr_uri=qr_uri,
        result_url=result_url,
        photo_metadata=photo_metadata,
    )


@app.route("/admin/delete-photo", methods=["POST"])
def admin_delete_photo():
    guard = require_admin()
    if guard:
        return guard

    collection_name = (request.form.get("collection") or "").strip()
    doc_id = (request.form.get("doc_id") or "").strip()
    if not collection_name or not doc_id:
        flash("Missing record details for removal.", "error")
        return redirect(url_for("admin_dashboard"))

    ok, msg = delete_photo_qr_record(collection_name, doc_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("admin_dashboard"))




@app.errorhandler(413)
def file_too_large(_err):
    flash(f"Uploaded file exceeds the {max_mb} MB limit.", "error")
    return redirect(request.referrer or url_for("index"))



@app.route("/privacy")
def privacy():
    contact_email = (os.environ.get("CONTACT_EMAIL") or "support@example.com").strip()
    return render_template("privacy.html", contact_email=contact_email)

@app.route("/terms")
def terms():
    contact_email = (os.environ.get("CONTACT_EMAIL") or "support@example.com").strip()
    return render_template("terms.html", contact_email=contact_email)




@app.errorhandler(400)
def bad_request_or_csrf(err):
    flash(str(getattr(err, "description", "Invalid request or expired CSRF token.")), "error")
    return redirect(request.referrer or url_for("index"))

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_ENV") != "production")
    
