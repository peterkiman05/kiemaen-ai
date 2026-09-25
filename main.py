import os
import difflib
from fastapi import FastAPI, Form, File, UploadFile, Header, Cookie, Response
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from core.brain import ask_kiemaen
from core.auth import (init_auth_db, ensure_admin_exists, create_user, verify_user,
                        create_session, get_session_user, delete_session,
                        create_pending_verification, verify_and_create_user)
from core.mailer import send_verification_email
from core.auth import (get_pending_code_admin, create_login_code, verify_login_code,
    get_user_email, get_user_by_username, log_admin_alert, get_admin_alerts,
    add_pin, get_pins, remove_pin, revoke_all_sessions)
from core.security import (firewall_middleware, is_path_safe, is_locked_file,
                            propose_edit, confirm_edit, reject_edit, rollback_edit,
                            validate_python_syntax, LOCKED_FILES)
from tools.coder import read_file, write_file, extract_code, run_script
# In utils/email.py
import smtplib, asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

async def send_login_email(to_email: str, username: str):
    msg = MIMEMultipart()
    msg['From'] = os.getenv('SMTP_USER')
    msg['To'] = to_email
    msg['Subject'] = "Kiemaen Login Alert"
    msg.attach(MIMEText(f"Hello {username}, your account was just accessed.", 'plain'))
    
    # Use a thread executor to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _send_sync, msg)

def _send_sync(msg):
    with smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT'))) as s:
        s.starttls()
        s.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASS'))
        s.send_message(msg)
load_dotenv()

DOCS_ENABLED = os.environ.get("ENABLE_API_DOCS", "false").lower() == "true"
app = FastAPI(
    docs_url="/docs" if DOCS_ENABLED else None,
    redoc_url="/redoc" if DOCS_ENABLED else None,
    openapi_url="/openapi.json" if DOCS_ENABLED else None,
)
app.middleware("http")(firewall_middleware)

init_auth_db()
ensure_admin_exists()

def issue_session_cookie(response: Response, user_id, username, is_admin):
    token = create_session(user_id)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=86400,
        path="/"
    )
    return {"status": "ok", "username": username, "is_admin": is_admin}

def get_user(token):
    if not token:
        return {"id": 0, "username": "guest", "is_admin": False}
    user = get_session_user(token)
    if not user:
        return {"id": 0, "username": "guest", "is_admin": False}
    return user

@app.get("/")
async def home():
    return FileResponse("web/index.html")

@app.get("/admin/pending-code")
async def admin_pending_code(email: str, x_session_token: str = Cookie(default=None, alias="session_token")):
    user = get_user(x_session_token)
    if not user["is_admin"]:
        return JSONResponse(status_code=403, content={"status": "error", "message": "Admin access required."})
    result = get_pending_code_admin(email)
    if not result:
        return JSONResponse(status_code=404, content={"status": "error", "message": "No pending verification found for this email."})
    return {"status": "ok", "data": result}
# In main.py
from fastapi import UploadFile, File
import base64

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    contents = await file.read()
    base64_image = base64.b64encode(contents).decode("utf-8")
    # Return base64 to client, or pass directly to LLM if you want server-side processing
    return {"image_base64": base64_image}
@app.post("/register/request-code")
async def register_request_code(username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    if len(username) < 3 or len(password) < 4:
        return {"status": "error", "message": "Username or password too short."}
    if "@" not in email or "." not in email:
        return {"status": "error", "message": "Please enter a valid email address."}

    code, error = create_pending_verification(username, email, password)
    if error:
        return {"status": "error", "message": error}

    sent, msg = send_verification_email(email, code, username)
    if not sent:
        return {"status": "error", "message": msg}

    return {"status": "ok", "message": f"Verification code sent to {email}."}

@app.post("/register/verify")
async def register_verify(response: Response, email: str = Form(...), code: str = Form(...)):
    user, error = verify_and_create_user(email, code)
    if error:
        return {"status": "error", "message": error}
    return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

@app.post("/register")
async def register(response: Response, username: str = Form(...), password: str = Form(...)):
    if len(username) < 3 or len(password) < 4:
        return {"status": "error", "message": "Username or password too short."}
    ok = create_user(username, password)
    if not ok:
        return {"status": "error", "message": "Username already taken."}
    user = verify_user(username, password)
    return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

@app.post("/login")
async def login(response: Response, username: str = Form(...), password: str = Form(...)):
    user = verify_user(username, password)
    if not user:
        return {"status": "error", "message": "Invalid username or password."}

    if user["is_admin"]:
        return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

    email = get_user_email(username)
    if not email:
        return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

    code = create_login_code(username)
    sent, msg = send_verification_email(email, code, username)
    if not sent:
        log_admin_alert(f"Login code email FAILED for user '{username}' ({email}): {msg}. User was let in with password-only fallback.")
        return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

    return {"status": "verification_required", "username": username}

@app.post("/login/verify")
async def login_verify(response: Response, username: str = Form(...), code: str = Form(...)):
    ok, msg = verify_login_code(username, code)
    if not ok:
        return {"status": "error", "message": msg}
    user = get_user_by_username(username)
    if not user:
        return {"status": "error", "message": "User not found."}
    return issue_session_cookie(response, user["id"], user["username"], user["is_admin"])

@app.post("/logout")
async def logout(response: Response, x_session_token: str = Cookie(default=None, alias="session_token")):
    if x_session_token:
        delete_session(x_session_token)
    response.delete_cookie("session_token", path="/")
    return {"status": "ok"}

@app.get("/me")
async def me(x_session_token: str = Cookie(default=None, alias="session_token")):
    user = get_user(x_session_token)
    return {"username": user["username"], "is_admin": user["is_admin"]}

def detect_edit_target(text: str):
    """Returns a locked file path if the admin's message appears to target one for editing."""
    lowered = text.lower()
    if not any(k in lowered for k in ["modify", "edit", "update", "change", "rewrite", "patch"]):
        return None
    for locked_path in LOCKED_FILES:
        filename = os.path.basename(locked_path)
        if locked_path.lower() in lowered or filename.lower() in lowered:
            return locked_path
    return None

def make_diff(old_content: str, new_content: str, file_path: str) -> str:
    diff_lines = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"{file_path} (current)",
        tofile=f"{file_path} (proposed)",
    ))
    if not diff_lines:
        return "(No differences detected between current and proposed content.)"
    return "".join(diff_lines)

@app.post("/chat")
async def chat(
    prompt: str = Form(default=""),
    msg: str = Form(default=""),
    image: UploadFile = File(default=None),
    x_session_token: str = Cookie(default=None, alias="session_token")
):
    user = get_user(x_session_token)
    user_key = f"user_{user['id']}" if user["id"] else "guest"
    is_admin = user["is_admin"]

    text = prompt or msg
    image_bytes = await image.read() if image else None

    try:
        stripped_cmd = text.strip()

        if stripped_cmd.upper() == "LOGOUT_ALL_DEVICES":
            revoke_all_sessions(user["id"])
            return {"status": "ok", "response": "All your active sessions have been revoked. You will need to log in again on all devices.", "category": "meta"}

        if stripped_cmd.upper().startswith("REVOKE_USER") and is_admin:
            parts = stripped_cmd.split()
            if len(parts) < 2:
                return {"status": "ok", "response": "Usage: REVOKE_USER <username>", "category": "meta"}
            target = get_user_by_username(parts[1])
            if not target:
                return {"status": "ok", "response": f"User '{parts[1]}' not found.", "category": "meta"}
            revoke_all_sessions(target["id"])
            return {"status": "ok", "response": f"All sessions for '{parts[1]}' have been revoked.", "category": "meta"}

        if stripped_cmd.upper() == "SHOW_ALERTS" and is_admin:
            alerts = get_admin_alerts()
            if not alerts:
                return {"status": "ok", "response": "No new admin alerts.", "category": "meta"}
            lines = [f"[{a['created_at']}] {a['message']}" for a in alerts]
            return {"status": "ok", "response": "**Admin Alerts:**\n\n" + "\n".join(lines), "category": "meta"}

        if stripped_cmd.upper().startswith("PIN:"):
            fact = stripped_cmd[4:].strip()
            if not fact:
                return {"status": "ok", "response": "Usage: PIN: <fact to remember>", "category": "meta"}
            add_pin(user["id"], fact)
            return {"status": "ok", "response": f"Pinned: \"{fact}\". I will remember this going forward.", "category": "meta"}

        if stripped_cmd.upper() == "SHOW_PINS":
            pins = get_pins(user["id"])
            if not pins:
                return {"status": "ok", "response": "You have no pinned facts yet. Use PIN: <fact> to add one.", "category": "meta"}
            lines = [f"[{p['id']}] {p['text']}" for p in pins]
            return {"status": "ok", "response": "**Your Pinned Facts:**\n\n" + "\n".join(lines), "category": "meta"}

        if stripped_cmd.upper().startswith("UNPIN"):
            parts = stripped_cmd.split()
            if len(parts) < 2 or not parts[1].isdigit():
                return {"status": "ok", "response": "Usage: UNPIN <id>", "category": "meta"}
            remove_pin(user["id"], int(parts[1]))
            return {"status": "ok", "response": f"Removed pin {parts[1]}.", "category": "meta"}

        # ===== ADMIN CORE-EDIT SYSTEM =====
        if is_admin:
            stripped = text.strip()

            if stripped.upper().startswith("CONFIRM_EDIT"):
                parts = stripped.split()
                if len(parts) < 2:
                    return {"status": "ok", "response": "Usage: CONFIRM_EDIT <edit_id>", "category": "meta"}
                edit_id = parts[1]
                success, result = confirm_edit(edit_id, user["username"])
                if not success:
                    return {"status": "ok", "response": f"Could not confirm edit: {result}", "category": "meta"}

                from core.security import PENDING_EDITS
                edited_file = PENDING_EDITS[edit_id]["file"]
                valid, reason = validate_python_syntax(edited_file)
                if not valid:
                    rollback_edit(edit_id)
                    return {"status": "ok", "response": f"Edit applied but FAILED validation ({reason}). Automatically rolled back to the previous working version. Please revise your request and try again.", "category": "meta"}

                return {"status": "ok", "response": f"Edit confirmed and applied to {edited_file}.\nValidation: {reason}\nBackup saved at: {result}", "category": "meta"}

            if stripped.upper().startswith("REJECT_EDIT"):
                parts = stripped.split()
                if len(parts) < 2:
                    return {"status": "ok", "response": "Usage: REJECT_EDIT <edit_id>", "category": "meta"}
                edit_id = parts[1]
                success, result = reject_edit(edit_id)
                return {"status": "ok", "response": result, "category": "meta"}

            target_file = detect_edit_target(text)
            if target_file:
                current_content = read_file(target_file)
                if current_content.startswith("[ERROR]"):
                    return {"status": "ok", "response": f"Could not read {target_file}: {current_content}", "category": "meta"}

                edit_prompt = (
                    f"You are editing the file '{target_file}'. Here is its CURRENT full content:\n\n"
                    f"```\n{current_content}\n```\n\n"
                    f"Requested change: {text}\n\n"
                    f"Return ONLY the complete new file content for '{target_file}', fully rewritten with the requested change applied. "
                    f"Do not include explanations, do not omit any existing code that should remain, output the full file in a single code block."
                )
                edit_reply, _ = await ask_kiemaen(edit_prompt, user_key=user_key, is_admin=is_admin)
                new_content = extract_code(edit_reply)

                diff_preview = make_diff(current_content, new_content, target_file)
                edit_id = propose_edit(target_file, new_content, user["username"], diff_preview)

                response_text = (
                    f"**Proposed edit to `{target_file}`** (edit_id: `{edit_id}`)\n\n"
                    f"```diff\n{diff_preview}\n```\n\n"
                    f"Reply **CONFIRM_EDIT {edit_id}** to apply this change, or **REJECT_EDIT {edit_id}** to cancel."
                )
                return {"status": "ok", "response": response_text, "category": "meta"}
        # ===== END ADMIN CORE-EDIT SYSTEM =====

        if image_bytes:
            reply, category = await ask_kiemaen(text, image_bytes, user_key=user_key, is_admin=is_admin, user_id=user["id"])
        else:
            reply, category = await ask_kiemaen(text, user_key=user_key, is_admin=is_admin, user_id=user["id"])

        if "```" in reply and any(k in text.lower() for k in ["run", "execute", "test this", "debug"]):
            file_name = "sandbox_script.py"
            if is_path_safe(file_name):
                code = extract_code(reply)
                write_file(file_name, code)
                out, success = run_script(file_name)
                if not success:
                    reply += f"\n\n**(Execution Failed - Initiating Autonomous Fix)**:\n```\n{out}\n```"
                    fix_prompt = f"The code you just wrote in {file_name} failed with this error:\n{out}\nPlease output ONLY the fully corrected code."
                    fix_reply, _ = await ask_kiemaen(fix_prompt, user_key=user_key, is_admin=is_admin)
                    fixed_code = extract_code(fix_reply)
                    write_file(file_name, fixed_code)
                    out2, success2 = run_script(file_name)
                    reply += f"\n\n**(Agentic Fix Applied)**: {'Success' if success2 else 'Failed'}.\n```\n{out2}\n```"

        return {"status": "ok", "response": reply, "category": category}

    except Exception as e:
        err_str = str(e)
        if is_admin:
            return JSONResponse(status_code=200, content={"status": "error", "message": f"[ADMIN DEBUG] {err_str}"})
        else:
            if "too large" in err_str.lower() or "413" in err_str:
                friendly = "Your message or file is too large. Please shorten it and try again."
            elif "rate" in err_str.lower() or "429" in err_str:
                friendly = "Kiemaen is a bit busy right now. Please try again in a few seconds."
            else:
                friendly = "Something went wrong on my end. Please try rephrasing your message."
            return JSONResponse(status_code=200, content={"status": "error", "message": friendly})
