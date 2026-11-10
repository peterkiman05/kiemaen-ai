"""Bounded, type-checked upload handling for Kiemaen's chat endpoint."""
from __future__ import annotations
import io
import zipfile
from fastapi import HTTPException

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_BYTES = 12 * 1024 * 1024
MAX_DOCX_EXPANDED_BYTES = 30 * 1024 * 1024
MAX_DOCX_ENTRIES = 2000

async def read_limited_upload(upload, max_bytes: int, label: str) -> bytes:
    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"{label} is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.")
    return data

def detect_image_mime(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None

def validate_image_bytes(data: bytes, declared_content_type: str = "") -> str:
    mime = detect_image_mime(data)
    if not mime:
        raise HTTPException(status_code=415, detail="Unsupported or invalid image. Upload a valid JPEG, PNG, or WebP image.")
    declared = (declared_content_type or "").lower().split(";", 1)[0].strip()
    if declared.startswith("image/") and declared != mime:
        raise HTTPException(status_code=415, detail="The image content type does not match its file contents.")
    return mime

def validate_document_upload(filename: str, content_type: str, data: bytes) -> str:
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    extension = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    allowed = {".pdf", ".docx", ".txt", ".md", ".csv", ".json", ".py", ".js"}
    if extension not in allowed:
        raise HTTPException(status_code=415, detail="Unsupported document type.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded document is empty.")
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The PDF file signature is invalid.")
    if extension == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                expanded_size = sum(item.file_size for item in entries)
                names = set(archive.namelist())
                if len(entries) > MAX_DOCX_ENTRIES or expanded_size > MAX_DOCX_EXPANDED_BYTES:
                    raise HTTPException(status_code=413, detail="The DOCX archive expands beyond the allowed size.")
                if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                    raise HTTPException(status_code=415, detail="The DOCX file structure is invalid.")
        except zipfile.BadZipFile:
            raise HTTPException(status_code=415, detail="The DOCX archive is invalid.")
    else:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="Text documents must use UTF-8 encoding.")
        if b"\x00" in data:
            raise HTTPException(status_code=415, detail="Binary content is not allowed in text documents.")
    return extension
