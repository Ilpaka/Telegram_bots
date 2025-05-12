import logging
import sqlite3
from datetime import datetime, timedelta
import hashlib

from fastapi import FastAPI, Request, HTTPException

def adapt_datetime(dt_obj: datetime) -> str:
    return dt_obj.isoformat()

def convert_datetime(s: bytes) -> datetime:
    return datetime.fromisoformat(s.decode())

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("timestamp", convert_datetime)

# ====== Настройки (должны совпадать с bot.py) ======
ROBOKASSA_LOGIN = ""
ROBOKASSA_PASSWORD2 = ""

app = FastAPI()

def get_db_connection():
    conn = sqlite3.connect(
        'subscriptions.db',
        detect_types=sqlite3.PARSE_DECLTYPES,
        timeout=30  # задаем таймаут в 10 секунд
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # включаем режим WAL для лучшей конкурентности
    return conn

def generate_robokassa_signature_result(out_sum: str, inv_id: str, password: str) -> str:
    signature_string = f"{out_sum}:{inv_id}:{password}"
    return hashlib.md5(signature_string.encode('utf-8')).hexdigest()

def create_subscription(user_id: int, invoice_id: str, days: int = 30):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM subscriptions WHERE invoice_id = ?", (invoice_id,))
    if cursor.fetchone() is not None:
        # Запись уже существует — ничего не делаем, чтобы не создавать дубликат
        conn.close()
        return
    
    start_date = datetime.now()
    end_date = start_date + timedelta(days=days)
    cursor.execute("""
        INSERT INTO subscriptions (user_id, invoice_id, start_date, end_date, is_active)
        VALUES (?, ?, ?, ?, 1)
    """, (user_id, invoice_id, start_date, end_date))
    conn.commit()
    conn.close()

@app.post("/robokassa/callback")
async def robokassa_result(request: Request):
    form = await request.form()
    out_sum = form.get("OutSum")
    inv_id = form.get("InvId")
    robokassa_signature = form.get("SignatureValue")

    if not out_sum or not inv_id or not robokassa_signature:
        raise HTTPException(status_code=400, detail="Missing params")

    my_signature = generate_robokassa_signature_result(out_sum, inv_id, ROBOKASSA_PASSWORD2)
    if my_signature.lower() != robokassa_signature.lower():
        raise HTTPException(status_code=400, detail="Invalid signature")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM invoices WHERE invoice_id = ?", (inv_id,))
    invoice_row = cursor.fetchone()
    if not invoice_row:
        raise HTTPException(status_code=400, detail="Invoice not found")

    expected_amount = float(invoice_row["amount"])
    if float(out_sum) != expected_amount:
        raise HTTPException(status_code=400, detail="Amount mismatch")

    cursor.execute("""
        UPDATE invoices 
        SET status='paid', updated_at=?
        WHERE invoice_id=?
    """, (datetime.now(), inv_id))
    user_id = invoice_row["user_id"]
    conn.commit()
    conn.close()

    create_subscription(user_id, inv_id, days=30)

    return "OK"

@app.get("/robokassa/success")
async def robokassa_success():
    return {"status": "success", "message": "Оплата прошла успешно!"}

@app.get("/robokassa/fail")
async def robokassa_fail():
    return {"status": "fail", "message": "Оплата не удалась или отменена."}

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
