import os
from flask import Flask, render_template, request, send_file
import qrcode
from werkzeug.utils import secure_filename
import random
from flask import session

app = Flask(__name__)
app.secret_key = 'supersecretkey'  

UPLOAD_FOLDER = 'uploads'
QR_FOLDER = 'static/qr_codes'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QR_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/services')
def services():
    return render_template('services.html')




@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        print("POST HIT")  

        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        user_answer = request.form.get("captcha")
        real_answer = session.get("captcha_answer")

        print("USER:", user_answer, "REAL:", real_answer)  \

       
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

        
        with open("data.txt", "a", encoding="utf-8") as f:
            f.write(f"\nName: {name}\nEmail: {email}\nMessage: {message}\n")

        
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        session["captcha_answer"] = num1 + num2

        return render_template(
            "contact.html",
            success="Message saved ✅",
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
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        data = f"http://192.168.1.5:5000/uploads/{filename}"

    elif text:
        data = text
    else:
        return "No input provided"

    qr = qrcode.make(data)

    qr_filename = "qr.png"
    qr_path = os.path.join(QR_FOLDER, qr_filename)
    qr.save(qr_path)

    return render_template('index.html', qr_image=qr_filename, data=data)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(
        os.path.join(app.config['UPLOAD_FOLDER'], filename),
        as_attachment=False
    )


if __name__ == "__main__":
    app.run()
    
try:
    from flask import send_from_directory

    @app.route('/static/<path:filename>')
    def custom_static(filename):
        return send_from_directory('static', filename)
except ImportError:
    pass
