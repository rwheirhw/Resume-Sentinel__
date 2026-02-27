"""
Signal 3: Phone Number Deduplication & Validation
Normalizes phone numbers, checks for duplicates across submissions,
and verifies validity/carrier/line-type via NumVerify API.
"""
import os
import re
import logging
import httpx

logger = logging.getLogger(__name__)

NUMVERIFY_API_KEY = os.environ.get("NUMVERIFY_API_KEY", "")
NUMVERIFY_VALIDATE_URL = "http://apilayer.net/api/validate"


def normalize_phone(phone: str) -> str:
    """Normalize a phone number to digits only, stripping country code if India (+91)."""
    digits = re.sub(r"\D", "", phone)

    # Handle Indian phone numbers
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]

    return digits


def _verify_phone_numverify(phone_digits: str) -> dict:
    """Call NumVerify API to verify a single phone number. Returns result dict or None on failure."""
    if not NUMVERIFY_API_KEY:
        return None
    # NumVerify expects digits; for 10-digit numbers default to India (+91)
    clean = phone_digits
    country_code = ""
    if len(clean) == 10:
        clean = "91" + clean
        country_code = "IN"
    try:
        params = {"access_key": NUMVERIFY_API_KEY, "number": clean}
        if country_code:
            params["country_code"] = country_code
        response = httpx.get(NUMVERIFY_VALIDATE_URL, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        if data.get("success") is False:
            logger.warning(f"NumVerify error for '{phone_digits}': {data.get('error', {}).get('info', '')}")
            return None
        return {
            "phone": phone_digits,
            "is_valid": data.get("valid", False),
            "line_type": data.get("line_type") or None,
            "state": data.get("location") or None,
            "country": data.get("country_name") or None,
        }
    except Exception as e:
        logger.warning(f"NumVerify API call failed for '{phone_digits}': {e}")
        return None


def validate_phones(phones: list, known_phones: list = None) -> dict:
    """
    Validate phone numbers for fraud signals.
    Combines local heuristic checks with NumVerify API verification.

    Args:
        phones: list of phone numbers from current resume
        known_phones: list of previously seen phone numbers (for dedup)

    Returns:
        dict with score (0-15), flags, details, and API verification results
    """
    if known_phones is None:
        known_phones = []

    result = {
        "signal_name": "phone_validation",
        "score": 0,
        "flags": [],
        "details": [],
        "severity": "NONE",
        "explanation": "",
        "duplicate_found": False,
        "normalized_phones": [],
        "verified_phones": [],
    }

    if not phones:
        result["flags"].append("NO_PHONE")
        result["score"] = 5
        result["severity"] = "LOW"
        result["explanation"] = "No phone number found in resume."
        return result

    score = 0
    normalized = [normalize_phone(p) for p in phones]
    result["normalized_phones"] = normalized

    # Check for duplicate phones within the same resume (multiple numbers)
    if len(set(normalized)) < len(normalized):
        result["flags"].append("INTERNAL_DUPLICATE")
        result["details"].append("Same phone number appears multiple times in resume")
        score += 3

    # Check for invalid phone numbers
    for phone in normalized:
        if len(phone) < 10:
            result["flags"].append(f"INVALID_LENGTH: {phone}")
            result["details"].append(f"Phone number '{phone}' has fewer than 10 digits")
            score += 3
        elif len(phone) > 15:
            result["flags"].append(f"TOO_LONG: {phone}")
            result["details"].append(f"Phone number '{phone}' exceeds 15 digits")
            score += 2

    # Check for known fake patterns
    for phone in normalized:
        if re.match(r"^(\d)\1{9}$", phone):  # All same digit: 1111111111
            result["flags"].append(f"FAKE_PATTERN: {phone}")
            result["details"].append(f"Phone '{phone}' appears to be fake (repeating digits)")
            score += 10
        elif phone in ("1234567890", "0987654321", "9876543210"):
            result["flags"].append(f"SEQUENTIAL: {phone}")
            result["details"].append(f"Phone '{phone}' is a sequential number")
            score += 8

    # Check against known submissions
    known_normalized = [normalize_phone(p) for p in known_phones]
    for phone in normalized:
        if phone in known_normalized:
            result["duplicate_found"] = True
            result["flags"].append(f"CROSS_DUPLICATE: {phone}")
            result["details"].append(f"Phone '{phone}' found in another submission")
            score += 10

    # ── NumVerify API verification ──
    already_verified = set()
    for phone in normalized:
        if phone in already_verified:
            continue
        already_verified.add(phone)

        api_result = _verify_phone_numverify(phone)
        if api_result:
            result["verified_phones"].append(api_result)

            if not api_result["is_valid"]:
                result["flags"].append(f"API_INVALID: {phone}")
                result["details"].append(f"NumVerify: '{phone}' is INVALID (not in service)")
                score += 8

            line_type = (api_result.get("line_type") or "").lower()
            if line_type == "voip":
                result["flags"].append(f"API_VOIP: {phone}")
                result["details"].append(
                    f"NumVerify: '{phone}' is a VoIP number"
                )
                score += 4
            elif line_type == "toll_free":
                result["flags"].append(f"API_TOLL_FREE: {phone}")
                result["details"].append(f"NumVerify: '{phone}' is toll-free — unusual for a resume")
                score += 5
        else:
            result["verified_phones"].append({
                "phone": phone, "is_valid": None,
                "line_type": None, "state": None, "country": None,
            })

    result["score"] = min(score, 15)

    # Severity
    if result["score"] >= 10:
        result["severity"] = "HIGH"
        result["explanation"] = f"Phone validation flagged issues: " + "; ".join(result["details"][:3])
    elif result["score"] >= 5:
        result["severity"] = "MEDIUM"
        result["explanation"] = f"Phone has concerns: " + "; ".join(result["details"][:2])
    elif result["score"] > 0:
        result["severity"] = "LOW"
        result["explanation"] = "Minor phone concerns detected."
    else:
        result["explanation"] = "Phone validation passed — no concerns."

    return result
