from db import ResumeRecord

DISPOSABLE = [
    "mailinator.com",
    "guerrillamail.com",
    "tempmail.com",
    "throwaway.email",
    "yopmail.com",
    "sharklasers.com",
    "trashmail.com",
    "maildrop.cc",
    "dispostable.com",
    "fakeinbox.com",
]


def contact_signals(email: str, phone: str, db_session) -> dict:
    email = (email or "").strip().lower()
    phone = (phone or "").strip()

    email_dup_count = 0
    phone_dup_count = 0

    if email:
        email_dup_count = db_session.query(ResumeRecord).filter(ResumeRecord.email == email).count()

    if phone:
        phone_dup_count = db_session.query(ResumeRecord).filter(ResumeRecord.phone == phone).count()

    domain = email.split("@")[-1] if "@" in email else ""
    disposable_domain = domain in DISPOSABLE

    score = (email_dup_count * 20) + (phone_dup_count * 20) + (30 if disposable_domain else 0)
    contact_score = min(score, 60)

    return {
        "email_dup_count": int(email_dup_count),
        "phone_dup_count": int(phone_dup_count),
        "disposable_domain": bool(disposable_domain),
        "contact_score": int(contact_score),
    }
