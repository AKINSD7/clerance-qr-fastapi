from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import csv
import uuid
import json
import sqlite3
import qrcode
from io import BytesIO
import base64

import os
from dotenv import load_dotenv

load_dotenv()




BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


# ------------------ APP SETUP ------------------

app = FastAPI()

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

DB_FILE = "uploads.db"


# ------------------ DATABASE ------------------

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            record_id TEXT PRIMARY KEY,
            school_name TEXT,
            school_code TEXT,
            principal TEXT,
            rows TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


# ------------------ HELPERS ------------------

def normalize_remark(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("recomended", "recommended")  # FIX WAEC TYPO
    return value


def count_recommended(rows: list) -> int:
    return sum(
        1 for r in rows
        if "recommended" in r.get("remark", "")
        and "not" not in r.get("remark", "")
    )

# ------------------ ROUTES ------------------

@app.get("/")
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

def get_verification_context(request: Request, record_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "SELECT school_name, school_code, principal, rows FROM uploads WHERE record_id = ?",
        (record_id,)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Record not found")

    school_name, school_code, principal, rows_json = row
    rows = json.loads(rows_json)

    recommended_count = count_recommended(rows)

    qr_data = f"{BASE_URL}/core/structure/registration/{record_id}"
    qr_img = qrcode.make(qr_data)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "request": request,
        "school_name": school_name,
        "school_code": school_code,
        "principal": principal,
        "recommended_count": recommended_count,
        "qr_code": qr_base64
    }



@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8").splitlines()

    data_rows = []
    school_name = ""
    school_code = ""
    principal = ""
    header_found = False

    # Detect WAEC-style CSV
    if any("SCHOOL NAME" in line.upper() for line in content[:10]):
        reader = csv.reader(content)
        for row in reader:
            if not row:
                continue

            if row[0].strip().upper() == "SCHOOL NAME":
                school_name = row[1].strip()
                continue

            if row[0].strip().upper() == "SCHOOL CODE":
                school_code = row[1].strip()
                continue

            if row[0].strip().upper() == "NAME OF PRINCIPAL":
                principal = row[1].strip()
                continue

            if row[0].strip() == "#":
                header_found = True
                continue

            if not header_found:
                continue

            data_rows.append({
                "passport": row[1],
                "lin": row[2],
                "lastname": row[3],
                "firstname": row[4],
                "othername": row[5],
                "sex": row[6],
                "year_2026": row[7],
                "year_2025": row[8],
                "year_2024": row[9],
                "remark": normalize_remark(row[10])
            })

    else:
        # Generic CSV
        reader = csv.DictReader(content)
        for row in reader:
            row["remark"] = normalize_remark(row.get("remark", ""))
            data_rows.append(row)

        school_name = "CLIMAX SECONDARY SCHOOL"
        school_code = "C24084"
        principal = "Tolani Ogunbamiji"

    # Unique, readable record_id
    record_id = f"{school_code}-{uuid.uuid4().hex[:6]}"

    # Store in SQLite
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO uploads (record_id, school_name, school_code, principal, rows)
        VALUES (?, ?, ?, ?, ?)
    """, (
        record_id,
        school_name,
        school_code,
        principal,
        json.dumps(data_rows)
    ))
    conn.commit()
    conn.close()

    return JSONResponse({
        "message": "Upload successful",
        "index_url": f"/clearance/{record_id}",
        "verify_url": f"/verify/{record_id}"
    })


@app.get("/clearance/{record_id}")
def clearance_page(request: Request, record_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        SELECT school_name, school_code, principal, rows
        FROM uploads WHERE record_id = ?
    """, (record_id,))
    result = c.fetchone()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Record not found")

    school_name, school_code, principal, rows_json = result
    rows = json.loads(rows_json)

    recommended_count = count_recommended(rows)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "school_name": school_name,
            "school_code": school_code,
            "principal": principal,
            "rows": rows,
            "recommended_count": count_recommended(rows)
        }
    )

# @app.get("/verify/{record_id}")
# def verify_page(request: Request, record_id: str):
#     conn = sqlite3.connect(DB_FILE)
#     c = conn.cursor()
#     c.execute(
#         "SELECT school_name, school_code, principal, rows FROM uploads WHERE record_id = ?",
#         (record_id,)
#     )
#     row = c.fetchone()
#     conn.close()

#     if not row:
#         raise HTTPException(status_code=404, detail="Record not found")

#     school_name, school_code, principal, rows_json = row
#     rows = json.loads(rows_json)


#     # ✅ CORRECT COUNT
#     recommended_count = count_recommended(rows)


#     # QR code
#     # qr_data = f"http://localhost:8000/clearance/{record_id}"
#     qr_data = f"{BASE_URL}/core/structure/registration/{record_id}"
#     qr_img = qrcode.make(qr_data)
#     buf = BytesIO()
#     qr_img.save(buf, format="PNG")
#     qr_base64 = base64.b64encode(buf.getvalue()).decode()

#     return templates.TemplateResponse(
#         "verification.html",
#         {
#             "request": request,
#             "school_name": school_name,
#             "school_code": school_code,
#             "principal": principal,
#             "recommended_count": recommended_count,
#             "qr_code": qr_base64
#         }
#     )




@app.get("/verify/{record_id}")
def verify_page(request: Request, record_id: str):
    context = get_verification_context(request, record_id)
    return templates.TemplateResponse("verification.html", context)


@app.get("/core/structure/registration/{record_id}")
def registration_verify(request: Request, record_id: str):
    context = get_verification_context(request, record_id)
    return templates.TemplateResponse("verification.html", context)



