from flask import Flask, render_template, request, send_file
import qrcode
import os

app = Flask(__name__)

QR_FOLDER = "static/qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    qr_image = None

    if request.method == "POST":
        data = request.form.get("data")

        if data:
            img = qrcode.make(data)

            file_path = os.path.join(QR_FOLDER, "qr.png")
            img.save(file_path)

            qr_image = file_path

    return render_template("index.html", qr_image=qr_image)


@app.route("/download")
def download():
    file_path = os.path.join(QR_FOLDER, "qr.png")

    if os.path.exists(file_path):
        return send_file(os.path.abspath(file_path), as_attachment=True)
    else:
        return "QR code not generated yet!"


if __name__ == "__main__":
    app.run(debug=True)
