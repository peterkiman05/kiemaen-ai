with open("core/security.py", "r") as f:
    content = f.read()

if "PENDING_EDITS" in content:
    print("Already patched - skipping.")
else:
    addition = '''

# ===== ADMIN CORE-EDIT SYSTEM =====
# Allows admin to modify locked files ONLY through a confirmed propose->verify->write flow.
# Regular is_path_safe() protection remains fully intact for all normal writes.

import uuid
import shutil
import datetime

PENDING_EDITS = {}  # edit_id -> {file, old_content, new_content, admin, timestamp, diff}
EDIT_LOG = []        # audit trail of all proposed/confirmed/rejected/rolled-back edits
BACKUP_DIR = "core_backups"

def is_locked_file(path: str) -> bool:
    normalized = os.path.normpath(path).replace("\\\\", "/").lstrip("/")
    return normalized in LOCKED_FILES

def propose_edit(file_path: str, new_content: str, admin_username: str, diff_preview: str) -> str:
    """Stage a proposed edit to a locked file. Returns an edit_id. Does NOT write to disk."""
    if not is_locked_file(file_path):
        raise ValueError(f"{file_path} is not a protected core file - use normal write instead.")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"{file_path} does not exist.")

    with open(file_path, "r") as f:
        old_content = f.read()

    edit_id = str(uuid.uuid4())[:8]
    PENDING_EDITS[edit_id] = {
        "file": file_path,
        "old_content": old_content,
        "new_content": new_content,
        "admin": admin_username,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "diff": diff_preview,
        "status": "pending",
    }
    EDIT_LOG.append({**PENDING_EDITS[edit_id], "edit_id": edit_id, "action": "proposed"})
    return edit_id

def confirm_edit(edit_id: str, admin_username: str):
    """Writes the proposed edit to disk after backing up the original. Returns (success, message)."""
    edit = PENDING_EDITS.get(edit_id)
    if not edit:
        return False, "No pending edit found with that ID. It may have expired or already been resolved."
    if edit["status"] != "pending":
        return False, f"This edit was already {edit['status']}."

    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_name = f"{BACKUP_DIR}/{os.path.basename(edit['file'])}.{edit_id}.bak"
    shutil.copy(edit["file"], backup_name)

    try:
        with open(edit["file"], "w") as f:
            f.write(edit["new_content"])
        edit["status"] = "confirmed"
        edit["backup_path"] = backup_name
        EDIT_LOG.append({**edit, "edit_id": edit_id, "action": "confirmed"})
        return True, backup_name
    except Exception as e:
        return False, f"Write failed: {e}"

def rollback_edit(edit_id: str):
    """Restores the pre-edit backup if validation fails after confirm_edit."""
    edit = PENDING_EDITS.get(edit_id)
    if not edit or "backup_path" not in edit:
        return False, "No backup available to roll back to."
    shutil.copy(edit["backup_path"], edit["file"])
    edit["status"] = "rolled_back"
    EDIT_LOG.append({**edit, "edit_id": edit_id, "action": "rolled_back"})
    return True, f"Rolled back {edit['file']} to previous version."

def reject_edit(edit_id: str):
    edit = PENDING_EDITS.get(edit_id)
    if not edit:
        return False, "No pending edit found with that ID."
    edit["status"] = "rejected"
    EDIT_LOG.append({**edit, "edit_id": edit_id, "action": "rejected"})
    return True, "Edit rejected, no changes made."

def validate_python_syntax(file_path: str):
    """Basic safety check: does the new file at least parse as valid Python (if .py)?"""
    if not file_path.endswith(".py"):
        return True, "Not a Python file - skipping syntax check."
    try:
        with open(file_path, "r") as f:
            source = f.read()
        compile(source, file_path, "exec")
        return True, "Syntax OK."
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
'''
    with open("core/security.py", "w") as f:
        f.write(content + addition)
    print("Patched core/security.py with admin core-edit propose/confirm/rollback system.")
