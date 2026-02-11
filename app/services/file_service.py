import os
from fastapi import HTTPException, status, UploadFile
from app.core.config import settings


ALLOWED_EXTENSIONS = {ext.strip().lower() for ext in settings.allowed_extensions.split(",")}


def save_upload_file(upload_file: UploadFile, destination_dir: str) -> str:
    """Save an uploaded file to a destination directory and return the full path.

    This helper is reusable for other services.
    """

    os.makedirs(destination_dir, exist_ok=True)

    # Basic extension validation
    _, ext = os.path.splitext(upload_file.filename or "")
    ext = ext.lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: .{ext}",
        )

    safe_name = upload_file.filename or "uploaded_file"
    dest_path = os.path.join(destination_dir, safe_name)

    with open(dest_path, "wb") as out_file:
        out_file.write(upload_file.file.read())

    return dest_path
