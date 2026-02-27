import hashlib
import json
import math

from sentence_transformers import SentenceTransformer

from db import ResumeRecord

try:
    MODEL = SentenceTransformer("all-MiniLM-L6-v2")
except Exception:
    MODEL = None


def _cosine_similarity(vec_a, vec_b) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def similarity_signals(jd_text: str, db_session) -> dict:
    normalized = (jd_text or "").lower().strip()
    jd_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    hash_collision_count = db_session.query(ResumeRecord).filter(ResumeRecord.jd_hash == jd_hash).count()

    if MODEL is not None:
        encoded = MODEL.encode(jd_text or "")
        embedding = encoded.tolist() if hasattr(encoded, "tolist") else list(encoded)
    else:
        embedding = []

    max_similarity = 0.0
    similar_count = 0

    stored_rows = db_session.query(ResumeRecord.embedding).filter(ResumeRecord.embedding.is_not(None)).all()
    for (stored_blob,) in stored_rows:
        if not stored_blob:
            continue
        try:
            stored_embedding = json.loads(stored_blob)
            if not isinstance(stored_embedding, list):
                continue
            similarity = _cosine_similarity(embedding, stored_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
            if similarity > 0.85:
                similar_count += 1
        except Exception:
            continue

    similarity_score = (hash_collision_count * 30) + (similar_count * 15)
    if max_similarity > 0.7:
        similarity_score += int(max_similarity * 20)
    similarity_score = min(similarity_score, 60)

    return {
        "jd_hash": jd_hash,
        "hash_collision_count": int(hash_collision_count),
        "max_similarity": float(max_similarity),
        "similar_count": int(similar_count),
        "embedding": embedding,
        "similarity_score": int(similarity_score),
    }
