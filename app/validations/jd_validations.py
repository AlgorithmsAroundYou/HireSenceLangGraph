from fastapi import HTTPException, status, UploadFile
from pathlib import Path
from app.core.config import settings


def validate_jd_upload(file: UploadFile) -> None:
    """Validate JD upload: extension and size.

    Raises HTTPException with 400 if invalid.
    """

    filename = file.filename or ""
    ext = Path(filename).suffix.lower()

    allowed_exts = {e.strip().lower() for e in settings.allowed_jd_extensions.split(",") if e.strip()}

    if ext not in allowed_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed_exts))}",
        )

    max_size_bytes = settings.max_jd_file_size_bytes

    file.file.seek(0, 2)  # move to end
    size = file.file.tell()
    file.file.seek(0)

    if size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum allowed size is {max_size_bytes // (1024 * 1024)} MB.",
        )
