from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import csv, uuid, json, qrcode, os, base64, random, string
from io import BytesIO
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import Json, RealDictCursor

app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")





# ------------------ LOAD ENV ------------------
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

DATABASE_URL = os.getenv("DATABASE_URL")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

if not DATABASE_URL:
    raise Exception("DATABASE_URL is missing in .env")

print("DATABASE_URL loaded successfully!")

# ------------------ DATABASE ------------------
def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS uploads (
                    record_id TEXT PRIMARY KEY,
                    school_name TEXT,
                    school_code TEXT,
                    principal TEXT,
                    rows JSONB,
                    param1 TEXT,
                    param2 TEXT,
                    param3 TEXT,
                    param4 TEXT,
                    param5 TEXT
                )
            """)
init_db()


# ------------------ APP SETUP ------------------
app = FastAPI()
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ------------------ HELPERS ------------------
def generate_url_segments():
    param1 = str(random.randint(100, 999))             # e.g., 566
    param2 = ''.join(random.choices(string.ascii_lowercase, k=7))  # e.g., aprivate
    param3 = str(random.randint(1, 10))                # e.g., 4
    param4 = str(random.randint(100, 999))             # e.g., 243
    param5 = str(random.randint(10, 99))               # e.g., 32 (extra for your example)
    return param1, param2, param3, param4, param5


def normalize_remark(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("recomended", "recommended")
    return value

def count_recommended(rows: list) -> int:
    return sum(1 for r in rows if "recommended" in r.get("remark", "") and "not" not in r.get("remark", ""))


def get_verification_context(request: Request, record_id: str):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM uploads WHERE record_id = %s",
                (record_id,)
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Record not found")

    rows = row["rows"]
    recommended_count = count_recommended(rows)

    qr_data = (
        f"{BASE_URL}/wassce-list/"
        f"{row['param1']}/{row['param2']}/{row['param3']}/"
        f"{row['param4']}/{row['param5']}/{record_id}"
    )

    qr_img = qrcode.make(qr_data)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode()

    return {
        "request": request,
        "school_name": row["school_name"],
        "school_code": row["school_code"],
        "principal": row["principal"],
        "recommended_count": recommended_count,
        "qr_code": qr_base64,
        "rows": rows   # ✅ THIS WAS MISSING
    }






# ------------------ ROUTES ------------------
@app.get("/")
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})

@app.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8").splitlines()

    data_rows = []
    school_name = ""
    school_code = ""
    principal = ""
    header_found = False

    # WAEC-style CSV
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
        reader = csv.DictReader(content)
        for row in reader:
            row["remark"] = normalize_remark(row.get("remark", ""))
            data_rows.append(row)
        school_name = "CLIMAX SECONDARY SCHOOL"
        school_code = "C24084"
        principal = "Tolani Ogunbamiji"

    record_id = f"{school_code}-{uuid.uuid4().hex[:6]}"

    # Generate fixed URL segments
    param1, param2, param3, param4, param5 = generate_url_segments()

    # Insert into Postgres with URL segments
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO uploads
                (record_id, school_name, school_code, principal, rows, param1, param2, param3, param4, param5)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (record_id, school_name, school_code, principal, Json(data_rows),
                param1, param2, param3, param4, param5))

    custom_index_url = f"{BASE_URL}/wassce-list/{param1}/{param2}/{param3}/{param4}/{param5}/{record_id}"

    return JSONResponse({
        "message": "Upload successful",
        "index_url": custom_index_url,   # ✅ customised URL
        "verify_url": f"/verify/{record_id}"  # ✅ NOT customised
    })


@app.get("/verify/{record_id}")
def verify_page(request: Request, record_id: str):
    context = get_verification_context(request, record_id)
    return templates.TemplateResponse("verification.html", context)

@app.get("/wassce-list/{param1}/{param2}/{param3}/{param4}/{param5}/{record_id}")
def wassce_list_page(
    request: Request,
    param1: str,
    param2: str,
    param3: str,
    param4: str,
    param5: str,
    record_id: str
):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                        SELECT
                        record_id,
                        param1,
                        param2,
                        param3,
                        param4,
                        param5
                        FROM uploads
                        WHERE record_id = %s
            """, (record_id,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Record not found")

    # Ensure the URL matches the stored segments
    if (
        row["param1"],
        row["param2"],
        row["param3"],
        row["param4"],
        row["param5"]
    ) != (param1, param2, param3, param4, param5):
        raise HTTPException(status_code=404, detail="URL segments do not match record")




    context = get_verification_context(request, record_id)
    context.update({
        "param1": param1,
        "param2": param2,
        "param3": param3,
        "param4": param4,
        "param5": param5
        
    })
    return templates.TemplateResponse("index.html", context)

