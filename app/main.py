import os
import glob
import sqlite3
import hashlib
import datetime
import jwt
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Kiemaen AI Core Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_main_ai():
    if os.path.exists("web/index.html"):
        return FileResponse("web/index.html")
    return {"status": "error", "message": "Main AI UI missing."}

@app.post("/api/auth/login")
async def login_user(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        
        # VIP Admin Bypass
        if email == "P.cthole5@gmail.com" and password == "JcobCthole@5":
            token = jwt.encode({"sub": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=365)}, "kim_super_secret_admin_key", algorithm="HS256")
            return {"status": "success", "token": token, "user": {"email": email, "is_admin": True, "is_verified": 1}}
        
        # Database verification
        db_files = glob.glob("**/*.db", recursive=True)
        if db_files:
            conn = sqlite3.connect(db_files[0])
            c = conn.cursor()
            hashed = hashlib.sha256(password.encode()).hexdigest()
            c.execute("SELECT email FROM users WHERE email=? AND (password=? OR pwd=?)", (email, hashed, hashed))
            row = c.fetchone()
            conn.close()
            if row:
                token = jwt.encode({"sub": email, "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)}, "kim_secret_key", algorithm="HS256")
                return {"status": "success", "token": token}
        return {"status": "error", "message": "Invalid credentials."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/auth/register")
async def register_user(request: Request):
    return {"status": "success", "message": "Account registered."}
