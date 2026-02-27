def compute_risk_score(contact_score, timeline_score, similarity_score) -> dict:
    weighted_score = int(round((contact_score * 0.35) + (timeline_score * 0.35) + (similarity_score * 0.30)))

    if contact_score >= 40 and weighted_score < 40:
        weighted_score = 40
    if similarity_score >= 45 and weighted_score < 40:
        weighted_score = 40

    if weighted_score <= 39:
        risk_level = "LOW RISK"
    elif weighted_score <= 69:
        risk_level = "REVIEW REQUIRED"
    else:
        risk_level = "HIGH RISK"

    return {
        "risk_score": weighted_score,
        "risk_level": risk_level,
    }
