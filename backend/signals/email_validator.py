"""
Signal 2: Email Validator & Disposable Email Detector
Checks for fake/disposable email domains, validates format,
flags duplicate emails across submissions, and verifies
deliverability via ZeroBounce API.
"""
import os
import re
import logging
import httpx

logger = logging.getLogger(__name__)

ZEROBOUNCE_API_KEY = os.environ.get("ZEROBOUNCE_API_KEY", "")
ZEROBOUNCE_VALIDATE_URL = "https://api.zerobounce.net/v2/validate"

# Comprehensive list of 100+ known disposable email domains
DISPOSABLE_DOMAINS = {
    # Major disposable services
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com", "grr.la",
    "dispostable.com", "mailnesia.com", "maildrop.cc", "discard.email",
    "fakeinbox.com", "temp-mail.org", "getnada.com", "trashmail.com",
    "mohmal.com", "tempail.com", "emailondeck.com", "10minutemail.com",
    "guerrillamail.info", "guerrillamail.net", "guerrillamail.org",
    "guerrillamail.de", "tempinbox.com", "trash-mail.com", "jetable.org",
    "throwam.com", "mytemp.email", "tempmailaddress.com", "burnermail.io",
    "inboxbear.com", "mailsac.com", "harakirimail.com", "crazymailing.com",
    "tmail.ws", "tempmailo.com", "tmpmail.net", "tmpmail.org",
    "bupmail.com", "mailcatch.com", "mailexpire.com", "mailmoat.com",
    "mintemail.com", "mt2015.com", "nobulk.com", "nospamfor.us",
    "pookmail.com", "spamfree24.org", "spamgourmet.com", "tempomail.fr",
    # Additional
    "mailnull.com", "spamhereplease.com", "safetypost.de", "trashymail.com",
    "uggsrock.com", "wegwerfmail.de", "wegwerfmail.net", "wh4f.org",
    "whyspam.me", "wuzup.net", "xagloo.com", "yepmail.net", "zetmail.com",
    "zippymail.info", "zoaxe.com", "33mail.com", "maildrop.gq",
    "getairmail.com", "filzmail.com", "inboxalias.com", "koszmail.pl",
    "trbvm.com", "kurzepost.de", "objectmail.com", "proxymail.eu",
    "rcpt.at", "reallymymail.com", "recode.me", "regbypass.com",
    "rejectmail.com", "rhyta.com", "rklips.com", "s0ny.net",
    "safe-mail.net", "saynotospams.com", "scbox.one.pl",
    "shieldedmail.com", "sofimail.com", "sogetthis.com",
    "soodonims.com", "spambox.us", "spambog.com", "spambog.de",
    "spambog.ru", "spamcannon.com", "spamcannon.net", "spamcero.com",
    "spamcon.org", "spamcorptastic.com", "spamcowboy.com",
}

# Suspicious but not necessarily disposable
SUSPICIOUS_PATTERNS = [
    r"^test\d*@",
    r"^fake\d*@",
    r"^dummy\d*@",
    r"^temp\d*@",
    r"^noreply@",
    r"^no-reply@",
    r"^asdf",
    r"^qwerty",
    r"\d{6,}@",  # Too many consecutive digits
]

# Professional email domains (positive signal)
PROFESSIONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com",
    "icloud.com", "protonmail.com", "zoho.com", "aol.com",
}


def _verify_email_zerobounce(email: str) -> dict:
    """Call ZeroBounce API to verify a single email. Returns raw result dict or None on failure."""
    if not ZEROBOUNCE_API_KEY:
        return None
    try:
        response = httpx.get(
            ZEROBOUNCE_VALIDATE_URL,
            params={"api_key": ZEROBOUNCE_API_KEY, "email": email},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        status = data.get("status", "unknown").lower()
        sub_status = data.get("sub_status", "").lower()
        return {
            "email": email,
            "status": status,
            "sub_status": data.get("sub_status", ""),
            "is_valid": status == "valid",
            "is_disposable": sub_status in ("disposable", "toxic"),
            "is_free": data.get("free_email", False),
            "did_you_mean": data.get("did_you_mean") or None,
        }
    except Exception as e:
        logger.warning(f"ZeroBounce API call failed for '{email}': {e}")
        return None


def validate_emails(emails: list, known_emails: list = None) -> dict:
    """
    Validate email addresses for fraud signals.
    Combines local heuristic checks with ZeroBounce API verification.

    Args:
        emails: list of email addresses from current resume
        known_emails: list of previously seen emails (for dedup)

    Returns:
        dict with score (0-20), flags, details, and API verification results
    """
    if known_emails is None:
        known_emails = []

    result = {
        "signal_name": "email_validation",
        "score": 0,
        "flags": [],
        "details": [],
        "severity": "NONE",
        "explanation": "",
        "disposable_found": False,
        "duplicate_found": False,
        "verified_emails": [],
    }

    if not emails:
        result["flags"].append("NO_EMAIL")
        result["score"] = 10
        result["severity"] = "MEDIUM"
        result["explanation"] = "No email address found in resume. This is unusual and may indicate the resume was fabricated or heavily edited."
        return result

    score = 0
    for email in emails:
        email = email.lower().strip()
        domain = email.split("@")[-1] if "@" in email else ""

        # ── Local heuristic checks ──

        # Check disposable domain
        if domain in DISPOSABLE_DOMAINS:
            result["disposable_found"] = True
            result["flags"].append(f"DISPOSABLE_EMAIL: {email}")
            result["details"].append(f"'{email}' uses disposable domain '{domain}'")
            score += 15

        # Check suspicious patterns
        for pattern in SUSPICIOUS_PATTERNS:
            if re.match(pattern, email, re.IGNORECASE):
                result["flags"].append(f"SUSPICIOUS_PATTERN: {email}")
                result["details"].append(f"'{email}' matches suspicious pattern")
                score += 5
                break

        # Check for duplicates against known submissions
        known_lower = [e.lower().strip() for e in known_emails]
        if email in known_lower:
            result["duplicate_found"] = True
            result["flags"].append(f"DUPLICATE_EMAIL: {email}")
            result["details"].append(f"'{email}' was found in another submission")
            score += 10

        # Check for very short local part (e.g., a@b.com)
        local_part = email.split("@")[0]
        if len(local_part) < 3:
            result["flags"].append(f"SHORT_LOCAL: {email}")
            score += 3

        # ── ZeroBounce API verification ──
        api_result = _verify_email_zerobounce(email)
        if api_result:
            result["verified_emails"].append(api_result)

            if not api_result["is_valid"]:
                status_upper = api_result["status"].upper()
                if api_result["status"] == "invalid":
                    result["flags"].append(f"API_INVALID: {email}")
                    result["details"].append(f"ZeroBounce: '{email}' is INVALID (undeliverable)")
                    score += 10
                elif api_result["status"] == "spamtrap":
                    result["flags"].append(f"API_SPAMTRAP: {email}")
                    result["details"].append(f"ZeroBounce: '{email}' is a known spam trap")
                    score += 12
                elif api_result["status"] == "abuse":
                    result["flags"].append(f"API_ABUSE: {email}")
                    result["details"].append(f"ZeroBounce: '{email}' is a known abuse address")
                    score += 8
                elif api_result["status"] == "do_not_mail":
                    result["flags"].append(f"API_DO_NOT_MAIL: {email}")
                    result["details"].append(f"ZeroBounce: '{email}' flagged as do-not-mail")
                    score += 6
                elif api_result["status"] == "catch-all":
                    result["flags"].append(f"API_CATCH_ALL: {email}")
                    result["details"].append(f"ZeroBounce: '{email}' is a catch-all domain")
                    score += 2

            if api_result["is_disposable"]:
                result["disposable_found"] = True
                result["flags"].append(f"API_DISPOSABLE: {email}")
                result["details"].append(f"ZeroBounce: '{email}' confirmed disposable")
                score += 8

            if api_result.get("did_you_mean"):
                result["flags"].append(f"API_TYPO: {email}")
                result["details"].append(f"ZeroBounce: did you mean '{api_result['did_you_mean']}'?")
                score += 3
        else:
            # API unavailable — note it but don't penalize
            result["verified_emails"].append({
                "email": email, "status": "api_unavailable",
                "sub_status": "", "is_valid": None,
                "is_disposable": None, "is_free": None, "did_you_mean": None,
            })

    result["score"] = min(score, 20)

    # Severity
    if result["score"] >= 15:
        result["severity"] = "HIGH"
        result["explanation"] = f"Email analysis flagged {len(result['flags'])} issue(s): " + "; ".join(result["details"][:3])
    elif result["score"] >= 8:
        result["severity"] = "MEDIUM"
        result["explanation"] = f"Email has some concerns: " + "; ".join(result["details"][:2])
    elif result["score"] > 0:
        result["severity"] = "LOW"
        result["explanation"] = "Minor email concerns detected."
    else:
        result["explanation"] = "Email validation passed — no concerns."

    return result
