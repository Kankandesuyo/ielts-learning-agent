from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.document_service import (
    delete_document,
    document_path,
    document_to_dict,
    get_document,
    list_documents,
    save_document,
)
from app.services.profile_service import get_profile

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{user_id}")
def get_documents(user_id: int, db: Session = Depends(get_db)):
    _require_profile(db, user_id)
    documents = list_documents(db, user_id)
    return {
        "user_id": user_id,
        "items": [document_to_dict(item) for item in documents],
        "next_step": "上传雅思资料后，可以在后续版本把它们接入 RAG 检索。",
    }


@router.post("/upload")
async def upload_document(
    user_id: int = Form(...),
    category: str = Form(default="general"),
    notes: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _require_profile(db, user_id)
    document = await save_document(db, user_id, file, category, notes)
    return {"item": document_to_dict(document), "next_step": "文件已保存到资料库。下一步可以把资料内容接入 RAG。"}


@router.get("/{user_id}/{document_id}/download")
def download_document(user_id: int, document_id: int, db: Session = Depends(get_db)):
    _require_profile(db, user_id)
    document = get_document(db, document_id, user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文件不存在。")
    path = document_path(document)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件记录存在，但本地文件已丢失。")
    return FileResponse(path, filename=document.original_filename, media_type=document.content_type)


@router.delete("/{user_id}/{document_id}")
def remove_document(user_id: int, document_id: int, db: Session = Depends(get_db)):
    _require_profile(db, user_id)
    document = get_document(db, document_id, user_id)
    if document is None:
        raise HTTPException(status_code=404, detail="文件不存在。")
    delete_document(db, document)
    return {"deleted": True, "document_id": document_id}


def _require_profile(db: Session, user_id: int) -> None:
    if get_profile(db, user_id) is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
