from django.core.exceptions import ValidationError

MAX_RESUME_BYTES = 5 * 1024 * 1024
PDF_MAGIC = b"%PDF-"


def validate_resume(upload) -> None:
    """Accept only real PDF files up to 5 MB.

    The file signature is checked rather than trusting the extension or the
    browser-supplied content type, both of which are client controlled.
    """
    if upload.size > MAX_RESUME_BYTES:
        raise ValidationError("Resumes must be 5 MB or smaller.")
    if not upload.name.lower().endswith(".pdf"):
        raise ValidationError("Please upload your resume as a PDF.")

    position = upload.tell() if hasattr(upload, "tell") else 0
    upload.seek(0)
    header = upload.read(len(PDF_MAGIC))
    upload.seek(position)
    if header != PDF_MAGIC:
        raise ValidationError("This file does not look like a valid PDF.")
