import io
import unittest
import zipfile
from fastapi import HTTPException
from core.upload_safety import (
    MAX_IMAGE_BYTES, read_limited_upload, validate_document_upload, validate_image_bytes,
)
class FakeUpload:
    def __init__(self, data): self.data = data
    async def read(self, size=-1): return self.data[:size] if size >= 0 else self.data
class UploadSafetyTests(unittest.TestCase):
    def test_supported_image_signatures(self):
        self.assertEqual(validate_image_bytes(b"\xff\xd8\xffjpeg", "image/jpeg"), "image/jpeg")
        self.assertEqual(validate_image_bytes(b"\x89PNG\r\n\x1a\nimage", "image/png"), "image/png")
        self.assertEqual(validate_image_bytes(b"RIFFxxxxWEBPdata", "image/webp"), "image/webp")
    def test_rejects_invalid_or_mismatched_images(self):
        for data, mime in ((b"not image", "image/png"), (b"\xff\xd8\xffjpeg", "image/png")):
            with self.subTest(mime=mime), self.assertRaises(HTTPException): validate_image_bytes(data, mime)
    def test_text_and_pdf(self):
        self.assertEqual(validate_document_upload("notes.md", "", b"hello"), ".md")
        self.assertEqual(validate_document_upload("report.pdf", "", b"%PDF-1.7"), ".pdf")
    def test_rejects_unsupported_and_invalid_documents(self):
        for name, data in (("payload.exe", b"x"), ("report.pdf", b"not pdf"), ("notes.txt", b"\xff\xfe")):
            with self.subTest(name=name), self.assertRaises(HTTPException): validate_document_upload(name, "", data)
    def test_valid_docx_structure(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,"w") as archive:
            archive.writestr("[Content_Types].xml","<Types/>")
            archive.writestr("word/document.xml","<document/>")
        self.assertEqual(validate_document_upload("report.docx","",stream.getvalue()),".docx")
    def test_invalid_docx(self):
        with self.assertRaises(HTTPException): validate_document_upload("report.docx","",b"PK-invalid")
    def test_oversized_upload(self):
        import asyncio
        async def run():
            with self.assertRaises(HTTPException) as caught:
                await read_limited_upload(FakeUpload(b"x"*(MAX_IMAGE_BYTES+1)),MAX_IMAGE_BYTES,"Image")
            self.assertEqual(caught.exception.status_code,413)
        asyncio.run(run())
if __name__ == "__main__": unittest.main()
