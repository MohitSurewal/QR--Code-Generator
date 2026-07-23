import os
import random
import time
import uuid
from unittest import result
import cloudinary
import cloudinary.uploader
import cloudinary.utils
from flask import (Flask,render_template, request, send_file, send_from_directory, session)
from PIL import Image
import qrcode
from werkzeug.utils import secure_filename
import sqlite3
from datetime import datetime

app = Flask(__name__)
init_db()
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# Allowed File Types
ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", 
    "gif", "mp4", "mov", "avi"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
QR_FOLDER = os.path.join(BASE_DIR, 'static/qr_codes')
LOGO_PATH = os.path.join(BASE_DIR, "static", "images", "logo.png")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'supersecretkey'

cloudinary.config(
    cloud_name="dpqxrl31h",
    api_key="651978524442419",
    api_secret="fnRUMMB-sXVZTizMiJwjR6__95c"
)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/admin/messages')
def view_messages():
    if request.args.get("key") != "28195373":
        return "Unauthorized ❌"

    messages = []
    try:
        with open("data.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                parts = line.strip().split("|")
                if len(parts) == 3:
                    messages.append({
                        "id": i,
                        "name": parts[0],
                        "email": parts[1],
                        "message": parts[2]
                    })
    except Exception:
        pass

    return render_template("messages.html", messages=messages)


@app.route('/delete/<int:msg_id>')
def delete_message(msg_id):
    try:
        with open("data.txt", "r", encoding="utf-8") as f:
            lines = f.readlines()

        with open("data.txt", "w", encoding="utf-8") as f:
            for i, line in enumerate(lines):
                if i != msg_id:
                    f.write(line)

    except Exception as e:
        return f"Error: {e}"

    return "<h3>Deleted ✅</h3><a href='/admin/messages?key=28195373'>Go Back</a>"


@app.route('/admin/files')
def view_files():
    if request.args.get("key") != "28195373":
        return "Unauthorized ❌"

    files = []
    try:
        file_list = os.listdir(app.config['UPLOAD_FOLDER'])
        for f in file_list:
            files.append(f)
    except Exception:
        pass

    return render_template("files.html", files=files)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/services')
def services():
    return render_template('services.html')


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name") or ""
        email = request.form.get("email") or ""
        message = request.form.get("message") or ""
        user_answer = request.form.get("captcha")
        real_answer = session.get("captcha_answer")

        if not real_answer or str(user_answer) != str(real_answer):
            num1 = random.randint(1, 10)
            num2 = random.randint(1, 10)
            session["captcha_answer"] = num1 + num2

            return render_template(
                "contact.html",
                error="Wrong captcha ❌",
                num1=num1,
                num2=num2
            )

        try:
            with open("data.txt", "a", encoding="utf-8") as f:
                f.write(f"{name}|{email}|{message}\n")
        except Exception as e:
            return f"Error saving data: {e}"

        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        session["captcha_answer"] = num1 + num2

        return render_template(
            "contact.html",
            success="Message saved✅",
            num1=num1,
            num2=num2
        )

    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    session["captcha_answer"] = num1 + num2

    return render_template("contact.html", num1=num1, num2=num2)


def allowed_file(filename):
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():

    conn = sqlite3.connect("database.db")

    cursor = conn.cursor()

    cursor.execute("""

        CREATE TABLE IF NOT EXISTS qr_history(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            created_at TEXT,

            qr_type TEXT,

            qr_data TEXT,

            qr_image TEXT

        )

    """)

    conn.commit()

    conn.close()


def delete_old_files(folder, days=30):
    now = time.time()
    expiry = days * 24 * 60 * 60

    for filename in os.listdir(folder):
        filepath = os.path.join(folder, filename)
        if os.path.isfile(filepath):
            if now - os.path.getmtime(filepath) > expiry:
                try:
                    os.remove(filepath)
                except Exception:
                    pass


@app.route('/generate', methods=['POST'])
def generate_qr():
    delete_old_files(QR_FOLDER)
    delete_old_files(UPLOAD_FOLDER)

    text = request.form.get("text")
    file = request.files.get("file")
    data = ""

    if file and file.filename != "":
        if not allowed_file(file.filename):
            return render_template(
                "index.html",
                error="Unsupported file type!"
            )

        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit(".", 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{extension}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)
        file.save(filepath)

        data = request.host_url + "uploads/" + unique_filename

    elif text:
        data = text.strip()
    else:
        return "No input provided"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(
        fill_color="black",
        back_color="white"
    ).convert("RGB")

    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH)
        logo_size = 70
        logo = logo.resize((logo_size, logo_size))
        x = (img.size[0] - logo_size) // 2
        y = (img.size[1] - logo_size) // 2
        img.paste(
            logo,
            (x, y),
            mask=logo if logo.mode == "RGBA" else None
        )

    qr_filename = f"{uuid.uuid4().hex}.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)
    img.save(qr_path)
    conn = sqlite3.connect("database.db")

    cursor = conn.cursor()
    
    cursor.execute("""
    
    INSERT INTO qr_history(
    
    created_at,
    
    qr_type,
    
    qr_data,
    
    qr_image
    
    )
    
    VALUES(?,?,?,?)
    
    """,(datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    
    "text" if text else "file",
    
    data,
    
    qr_filename))
    
    conn.commit()
    
    conn.close()

    return render_template(
        "index.html",
        qr_image=qr_filename,
        data=data
    )


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if not os.path.exists(filepath):
        return "File not found", 404

    return send_file(
        filepath,
        as_attachment=False
    )
@app.route("/history")
def history():

    conn = sqlite3.connect("database.db")

    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""

    SELECT * FROM qr_history

    ORDER BY id DESC

    """)

    history = cursor.fetchall()

    conn.close()

    return render_template(

        "history.html",

        history=history

    )

if __name__ == "__main__":
    app.run(debug=True)
