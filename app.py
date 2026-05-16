import os
from unittest import result
from flask import Flask, render_template, request, send_file
import qrcode
from werkzeug.utils import secure_filename
import random
from flask import session
import cloudinary
import cloudinary.uploader
import cloudinary.utils

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

cloudinary.config(
    cloud_name="dpqxrl31h",
    api_key="651978524442419",
    api_secret="fnRUMMB-sXVZTizMiJwjR6__95c"
)
app.secret_key = 'supersecretkey'  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QR_FOLDER = os.path.join(BASE_DIR, 'static/qr_codes')

os.makedirs(QR_FOLDER, exist_ok=True)




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
    except:
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
    except:
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


@app.route('/generate', methods=['POST'])
def generate_qr():

    text = request.form.get('text')

    file = request.files.get('file')

    data = ""

    if file and file.filename != "":

        filename = file.filename.lower()

      
        if filename.endswith(".pdf"):

            result = cloudinary.uploader.upload(
                file,
                resource_type="image"
            )

        
        elif filename.endswith((".mp4", ".mov", ".avi")):

            result = cloudinary.uploader.upload(
                file,
                resource_type="video"
            )

        
        else:

            result = cloudinary.uploader.upload(
                file,
                resource_type="image"
            )

        data = result['secure_url']

    elif text:

        data = text

    else:

        return "No input provided"

    qr = qrcode.make(data)

    qr_path = os.path.join(
        QR_FOLDER,
        "qr.png"
    )

    qr.save(qr_path)

    return render_template(
        'index.html',
        qr_image="qr.png",
        data=data
    )





if __name__ == "__main__":
    app.run(debug=True)
    
