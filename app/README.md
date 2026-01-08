# WAEC / WASSCE Clearance Verification System

A FastAPI-based web application for uploading WAEC/WASSCE clearance CSV files, counting recommended candidates, generating QR codes, and providing secure online verification.

---

## 🚀 Features

- Upload WAEC-style or generic CSV files
- Automatically detects school details
- Normalizes remarks (e.g. fixes "recomended" typo)
- Counts **Recommended** candidates (excluding *Not Recommended*)
- Generates QR codes for verification
- Secure verification page accessible via QR scan
- SQLite database for persistence
- Environment-based configuration using `.env`

---

## 🛠️ Tech Stack

- **Backend:** FastAPI
- **Templates:** Jinja2
- **Database:** SQLite
- **QR Codes:** qrcode + Pillow
- **Environment Config:** python-dotenv
- **Server:** Uvicorn
- **Containerization:** Docker

---

## 📁 Project Structure

