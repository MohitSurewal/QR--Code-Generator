# 🚀 QR Code Generator Web App

A Flask-based web application that allows users to generate QR codes for text, links, and files (PDF, images, videos, documents). It also includes a contact system and admin dashboard.

---

## 🌟 Features

* 🔗 Generate QR codes for text and URLs
* 📁 Upload files and generate QR codes
* 📩 Contact form with captcha verification
* 🧑‍💻 Admin panel to view messages
* 📂 Admin panel to view uploaded files
* 🗑 Delete messages functionality
* 🎨 Clean UI with animations

---

## 🧠 How It Works

1. User enters text or uploads a file
2. Flask processes the request
3. QR code is generated using `qrcode` library
4. Files are stored in `uploads/`
5. Messages are stored in `data.txt`
6. Admin panel displays stored data

---

## 📁 Project Structure

```
qr_app/
│
├── app.py
├── requirements.txt
├── Procfile
├── data.txt
│
├── static/
│   ├── style.css
│   └── qr_codes/
│
├── uploads/
│
└── templates/
    ├── base.html
    ├── index.html
    ├── contact.html
    ├── messages.html
    └── files.html

⚙️ Installation

```bash
git clone https://github.com/yourusername/qr-app.git
cd qr-app
pip install -r requirements.txt
python app.py
```


## SCREENSHOT:-

<img width="1918" height="800" alt="Screenshot 2026-04-16 210946" src="https://github.com/user-attachments/assets/4f751d06-b1f8-4d37-9a7a-592f32e1ae06" />


## 🌐 Deployment

Deployed using Render.

## ⚠️ Limitations

* Files are stored temporarily (Render free plan)
* Data in `data.txt` is not permanent
* Basic security (URL key-based access)

## 🛠 Tech Stack

* Python (Flask)
* HTML, CSS
* qrcode library

---

## 👨‍💻 Author

Mohit Surewal

---

## 📃 License

This project is open-source.

