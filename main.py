import os
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import urllib.request
import urllib.parse

app = FastAPI(title="Real Estate Lead System V2")

# Allow CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Setup
DB_FILE = "leads.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            phone TEXT,
            interest TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Telegram Notification Function
def send_telegram_notification(name: str, email: str, phone: str, interest: str, message: str):
    # Render environment variable names matched correctly here
    bot_token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHAT_ID")
    
    if not bot_token or not chat_id:
        print("Telegram configuration missing. Skipping telegram alert.")
        return

    text = f"🚨 **New Real Estate Lead!** 🚨\n\n👤 **Name:** {name}\n📧 **Email:** {email}\n📞 **Phone:** {phone}\n🏠 **Interest:** {interest}\n💬 **Message:** {message}"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req)
        print("Telegram notification sent successfully.")
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

# Email Auto-Reply Function
def send_auto_reply_email(to_email: str, user_name: str):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")

    if not sender_email or not sender_password:
        print("Email configuration missing. Skipping auto-reply email.")
        return

    subject = "Thank you for contacting PrimeEstates!"
    
    body = f"""Hello {user_name},

Thank you for reaching out to us! We have received your inquiry regarding our real estate properties.

Our representative will review your request and get back to you shortly.

Best regards,
PrimeEstates Team
"""

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect to Gmail SMTP Server using TLS (Port 587)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        # Clean space from sender password just in case
        clean_password = sender_password.replace(" ", "")
        server.login(sender_email, clean_password)
        server.send_message(msg)
        server.quit()
        print(f"Auto-reply email sent successfully to {to_email}")
    except Exception as e:
        print(f"Failed to send auto-reply email: {e}")

# Lead Pydantic Model for JSON requests
class LeadRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str = ""
    interest: str = "General Inquiry"
    message: str = ""

@app.get("/")
def read_root():
    return {"status": "Active", "message": "Real Estate Backend V2 is running successfully!"}

@app.post("/api/submit")
async def submit_lead(
    background_tasks: BackgroundTasks,
    name: str = Form(None),
    email: str = Form(None),
    phone: str = Form(None),
    interest: str = Form(None),
    message: str = Form(None),
    payload: LeadRequest = None
):
    # Support both Form Data and JSON Payload
    if payload:
        lead_name = payload.name
        lead_email = payload.email
        lead_phone = payload.phone
        lead_interest = payload.interest
        lead_message = payload.message
    else:
        lead_name = name
        lead_email = email
        lead_phone = phone or ""
        lead_interest = interest or "General Inquiry"
        lead_message = message or ""

    if not lead_name or not lead_email:
        raise HTTPException(status_code=400, detail="Name and Email are required.")

    # 1. Save to Database
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO leads (name, email, phone, interest, message) VALUES (?, ?, ?, ?, ?)",
            (lead_name, lead_email, lead_phone, lead_interest, lead_message)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database error: {e}")

    # 2. Trigger Background Tasks (Telegram & Email)
    background_tasks.add_task(send_telegram_notification, lead_name, lead_email, lead_phone, lead_interest, lead_message)
    background_tasks.add_task(send_auto_reply_email, lead_email, lead_name)

    return {"status": "success", "message": "Lead received! Notification & Auto-reply queued."}
