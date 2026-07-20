from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import UploadedDocument

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx", ".pptx"}
TRUSTED_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
ALLOWED_CATEGORIES = {"general", "ielts_book", "writing_sample", "speaking_material", "reading_material", "listening_material", "notes"}


def safe_upload_dir() -> Path:
    settings = get_settings()
    path = settings.upload_path
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_documents(db: Session, user_id: int) -> list[UploadedDocument]:
    stmt = select(UploadedDocument).where(UploadedDocument.user_id == user_id).order_by(UploadedDocument.created_at.desc())
    return list(db.scalars(stmt))


def get_document(db: Session, document_id: int, user_id: int) -> UploadedDocument | None:
    stmt = select(UploadedDocument).where(UploadedDocument.id == document_id, UploadedDocument.user_id == user_id)
    return db.scalar(stmt)


async def save_document(db: Session, user_id: int, file: UploadFile, category: str, notes: str) -> UploadedDocument:
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空。")

    original = Path(file.filename).name
    if len(original) > 255:
        raise HTTPException(status_code=400, detail="文件名不能超过 255 个字符。")
    extension = Path(original).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"暂不支持 {extension or '无扩展名'} 文件。支持：pdf、txt、md、docx、pptx。")

    settings = get_settings()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    upload_dir = safe_upload_dir()
    stored_filename = f"{uuid4().hex}{extension}"
    target_path = upload_dir / stored_filename

    normalized_category = category.strip() or "general"
    if normalized_category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="文件分类不合法。")
    normalized_notes = notes.strip()
    if len(normalized_notes) > 500:
        raise HTTPException(status_code=400, detail="备注不能超过 500 个字符。")

    size = 0
    first_chunk = True
    try:
        with target_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                if first_chunk:
                    _validate_file_signature(extension, chunk)
                    first_chunk = False
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail=f"文件不能超过 {settings.max_upload_mb}MB。")
                output.write(chunk)
            if first_chunk:
                raise HTTPException(status_code=400, detail="不能上传空文件。")
    except Exception:
        if target_path.exists():
            target_path.unlink()
        raise
    finally:
        await file.close()

    document = UploadedDocument(
        user_id=user_id,
        original_filename=original,
        stored_filename=stored_filename,
        content_type=TRUSTED_CONTENT_TYPES[extension],
        file_size=size,
        category=normalized_category,
        notes=normalized_notes,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def delete_document(db: Session, document: UploadedDocument) -> None:
    file_path = safe_upload_dir() / document.stored_filename
    if file_path.exists():
        file_path.unlink()
    db.delete(document)
    db.commit()


def document_path(document: UploadedDocument) -> Path:
    return safe_upload_dir() / document.stored_filename


def document_to_dict(document: UploadedDocument) -> dict:
    return {
        "id": document.id,
        "user_id": document.user_id,
        "original_filename": document.original_filename,
        "content_type": document.content_type,
        "file_size": document.file_size,
        "category": document.category,
        "notes": document.notes,
        "created_at": document.created_at.isoformat(),
    }


def _validate_file_signature(extension: str, first_chunk: bytes) -> None:
    if not first_chunk:
        raise HTTPException(status_code=400, detail="不能上传空文件。")
    if extension == ".pdf" and not first_chunk.startswith(b"%PDF-"):
        raise HTTPException(status_code=400, detail="文件内容不是有效的 PDF。")
    if extension in {".docx", ".pptx"} and not first_chunk.startswith(b"PK"):
        raise HTTPException(status_code=400, detail="Office 文件内容与扩展名不匹配。")
    if extension in {".txt", ".md"}:
        if b"\x00" in first_chunk:
            raise HTTPException(status_code=400, detail="文本文件包含不支持的二进制内容。")
        try:
            first_chunk.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="文本文件必须使用 UTF-8 编码。") from exc
