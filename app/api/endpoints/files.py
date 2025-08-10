from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from typing import List
from sqlmodel import Session, select

from app.database import get_session
from app.api.endpoints.auth import get_current_user
from app.models.user import User
from app.models.sample_file import SampleFile
from app.models.sample_requirement import SampleRequirement
from app.schemas.sample_file import SampleFileRead

router = APIRouter()


@router.post("/upload", response_model=SampleFileRead, status_code=status.HTTP_201_CREATED)
def upload_sample_file(
    uploaded_file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not uploaded_file.filename.lower().endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are allowed")

    existing_files = session.exec(
        select(SampleFile).where(SampleFile.owner_id == current_user.id)
    ).all()
    if len(existing_files) >= 5:
        raise HTTPException(status_code=400, detail="Maximum number of files reached")

    file_record = SampleFile(filename=uploaded_file.filename, owner_id=current_user.id)
    session.add(file_record)
    session.commit()
    session.refresh(file_record)

    content = uploaded_file.file.read().decode("utf-8")
    for line in content.splitlines():
        line = line.strip()
        if line:
            session.add(SampleRequirement(text=line, file_id=file_record.id))
    session.commit()

    return file_record


@router.get("/", response_model=List[SampleFileRead])
def list_sample_files(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    files = session.exec(
        select(SampleFile).where(SampleFile.owner_id == current_user.id)
    ).all()
    return files


@router.get("/{file_id}/requirements", response_model=List[str])
def get_sample_requirements(
    file_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    file_record = session.get(SampleFile, file_id)
    if not file_record or file_record.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")

    reqs = session.exec(
        select(SampleRequirement).where(SampleRequirement.file_id == file_id)
    ).all()
    return [r.text for r in reqs]
