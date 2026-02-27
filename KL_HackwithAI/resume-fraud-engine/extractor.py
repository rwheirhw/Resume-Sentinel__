import re
from io import BytesIO

import pdfplumber
from docx import Document


def extract_text(file_bytes: bytes, filename: str) -> str:
    try:
        lower_name = filename.lower()
        if lower_name.endswith(".pdf"):
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n".join(pages).strip()

        if lower_name.endswith(".docx"):
            document = Document(BytesIO(file_bytes))
            paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
            return "\n".join(paragraphs).strip()

        return ""
    except Exception:
        return ""


def parse_profile(raw_text: str) -> dict:
    text = raw_text or ""

    email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    email = email_match.group(0) if email_match else ""

    phone_match = re.search(r"(?:\+91[-\s]?|0)?[6-9]\d{9}\b", text)
    phone = phone_match.group(0) if phone_match else ""

    _dates = re.findall(
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
        r"Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|\b\d{1,2}/\d{4}\b|\b\d{4}\b",
        text,
        flags=re.IGNORECASE,
    )

    name = ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    name_pattern = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}$")
    for line in lines:
        candidate = re.sub(r"\s+", " ", line)
        if name_pattern.match(candidate):
            name = candidate
            break

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "raw_text": text,
    }
