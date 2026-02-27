"""
🛡️ ResumeGuard — AI-Based Resume Fraud Detection Engine
Main FastAPI Application

Hybrid Architecture: Python (ML/NLP) service
Endpoints: /validate_resume, /batch_validate, /compare_resumes, /health
"""
import os
import sys
import json
import logging
import hashlib
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
import uvicorn
from dotenv import load_dotenv

load_dotenv(override=True)

# ─── Setup Logging ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("resumeguard")

# ─── Add parent to path ─────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Imports ─────────────────────────────────────────────
from parsers.pdf_parser import extract_text_from_pdf
from parsers.docx_parser import extract_text_from_docx
from extractors.entity_extractor import extract_entities
from signals.timeline_overlap import check_timeline_overlap
from signals.email_validator import validate_emails
from signals.phone_dedup import validate_phones
from signals.jd_plagiarism import check_jd_plagiarism
from signals.semantic_similarity import check_semantic_similarity
from signals.skills_mismatch import check_skills_mismatch
from scoring.risk_engine import calculate_risk_score, get_risk_color, get_risk_label
from scoring.explainer import generate_explanation, generate_signal_summary

# ─── In-Memory Store (for hackathon demo) ───────────────
# In production, this would be backed by the Spring Boot service + DB
resume_store = {
    "resumes": [],        # List of processed resume records
    "emails_seen": [],     # All emails across submissions
    "phones_seen": [],     # All phones across submissions
    "experiences_seen": [],  # All experiences for JD plagiarism
    "embeddings": [],      # All embeddings for similarity
}

# ─── FastAPI App ─────────────────────────────────────────
app = FastAPI(
    title="🛡️ ResumeGuard — Fraud Detection Engine",
    description="AI-powered resume fraud detection with 6-signal analysis pipeline",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helper Functions ────────────────────────────────────

def parse_file(file_bytes: bytes, filename: str) -> dict:
    """Parse uploaded file and return extracted text."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return extract_text_from_docx(file_bytes)
    elif ext == "txt":
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            return {"text": text, "success": True, "error": None}
        except Exception as e:
            return {"text": "", "success": False, "error": str(e)}
    else:
        return {"text": "", "success": False, "error": f"Unsupported file type: .{ext}"}


def run_analysis(text: str, filename: str) -> dict:
    """Run the complete 6-signal fraud analysis pipeline."""

    # Step 1: Extract entities
    logger.info(f"Extracting entities from '{filename}'...")
    entities = extract_entities(text)

    # Step 2: Run all 6 signals
    logger.info("Running fraud detection signals...")

    signal_results = {}

    # Signal 1: Timeline Overlap
    try:
        signal_results["timeline_overlap"] = check_timeline_overlap(
            entities.get("experiences", [])
        )
    except Exception as e:
        logger.error(f"Timeline signal failed: {e}")
        signal_results["timeline_overlap"] = {"score": 0, "severity": "NONE", "explanation": f"Error: {e}"}

    # Signal 2: Email Validation
    try:
        signal_results["email_validation"] = validate_emails(
            entities.get("emails", []),
            known_emails=resume_store["emails_seen"]
        )
    except Exception as e:
        logger.error(f"Email signal failed: {e}")
        signal_results["email_validation"] = {"score": 0, "severity": "NONE", "explanation": f"Error: {e}"}

    # Signal 3: Phone Dedup
    try:
        signal_results["phone_validation"] = validate_phones(
            entities.get("phones", []),
            known_phones=resume_store["phones_seen"]
        )
    except Exception as e:
        logger.error(f"Phone signal failed: {e}")
        signal_results["phone_validation"] = {"score": 0, "severity": "NONE", "explanation": f"Error: {e}"}

    # Signal 4: JD Plagiarism
    try:
        signal_results["jd_plagiarism"] = check_jd_plagiarism(
            entities.get("experiences", []),
            known_experiences=resume_store["experiences_seen"]
        )
    except Exception as e:
        logger.error(f"JD plagiarism signal failed: {e}")
        signal_results["jd_plagiarism"] = {"score": 0, "severity": "NONE", "explanation": f"Error: {e}"}

    # Signal 5: Semantic Similarity
    try:
        signal_results["semantic_similarity"] = check_semantic_similarity(
            text,
            known_resumes=resume_store["embeddings"]
        )
    except Exception as e:
        logger.error(f"Semantic similarity signal failed: {e}")
        signal_results["semantic_similarity"] = {"score": 0, "severity": "NONE", "explanation": f"Error: {e}"}

    # Signal 6: Skills Mismatch
    try:
        signal_results["skills_mismatch"] = check_skills_mismatch(
            entities.get("skills", {}),
            entities.get("experiences", []),
            text
        )
    except Exception as e:
        logger.error(f"Skills mismatch signal failed: {e}")
        signal_results["skills_mismatch"] = {"score": 0, "severity": "NONE", "explanation": f"Error: {e}"}

    # Step 3: Calculate composite risk score
    logger.info("Calculating risk score...")
    risk_score = calculate_risk_score(signal_results)

    # Step 4: Generate explanation
    explanation = generate_explanation(signal_results, risk_score, entities)
    signal_summary = generate_signal_summary(signal_results)

    # Step 5: Store data for future comparisons
    _store_resume_data(filename, entities, signal_results, text)

    # Build response
    return {
        "filename": filename,
        "analyzed_at": datetime.now().isoformat(),
        "name": entities.get("name", "Unknown"),
        "emails": entities.get("emails", []),
        "phones": entities.get("phones", []),
        "skills": entities.get("skills", {}),
        "experience_count": len(entities.get("experiences", [])),
        "word_count": entities.get("word_count", 0),
        "risk_score": risk_score["composite_score"],
        "risk_level": risk_score["risk_level"],
        "risk_label": get_risk_label(risk_score["composite_score"]),
        "risk_color": get_risk_color(risk_score["composite_score"]),
        "alert": risk_score["alert"],
        "active_signals": risk_score["active_signals"],
        "most_critical_signal": risk_score["most_critical_signal"],
        "signals": {
            "timeline_score": signal_results.get("timeline_overlap", {}).get("score", 0),
            "email_score": signal_results.get("email_validation", {}).get("score", 0),
            "phone_score": signal_results.get("phone_validation", {}).get("score", 0),
            "plagiarism_score": signal_results.get("jd_plagiarism", {}).get("score", 0),
            "similarity_score": signal_results.get("semantic_similarity", {}).get("score", 0),
            "mismatch_score": signal_results.get("skills_mismatch", {}).get("score", 0),
        },
        "email_verification": signal_results.get("email_validation", {}).get("verified_emails", []),
        "phone_verification": signal_results.get("phone_validation", {}).get("verified_phones", []),
        "signal_details": signal_summary,
        "breakdown": risk_score["breakdown"],
        "llm_explanation": explanation,
        "entities": {
            "name": entities.get("name"),
            "emails": entities.get("emails", []),
            "phones": entities.get("phones", []),
            "skills_count": entities.get("skills", {}).get("total_count", 0),
            "experiences": [
                {
                    "company": e.get("company", ""),
                    "role": e.get("role", ""),
                    "start": e.get("start", ""),
                    "end": e.get("end", ""),
                }
                for e in entities.get("experiences", [])
            ],
            "education": entities.get("education", []),
        },
    }


def _store_resume_data(filename: str, entities: dict, signal_results: dict, text: str):
    """Store processed resume data for cross-resume comparison."""
    # Store emails
    resume_store["emails_seen"].extend(entities.get("emails", []))

    # Store phones
    resume_store["phones_seen"].extend(entities.get("phones", []))

    # Store experiences for JD plagiarism
    for exp in entities.get("experiences", []):
        exp_copy = dict(exp)
        exp_copy["source_resume"] = filename
        resume_store["experiences_seen"].append(exp_copy)

    # Store embedding for semantic similarity
    semantic = signal_results.get("semantic_similarity", {})
    if semantic.get("embedding"):
        resume_store["embeddings"].append({
            "filename": filename,
            "text": text[:1000],  # Store truncated text
            "embedding": semantic["embedding"],
        })

    # Store full record
    resume_store["resumes"].append({
        "filename": filename,
        "analyzed_at": datetime.now().isoformat(),
        "name": entities.get("name", "Unknown"),
        "emails": entities.get("emails", []),
        "phones": entities.get("phones", []),
        "text_hash": hashlib.sha256(text.encode()).hexdigest(),
    })


# ─── API Endpoints ───────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint — API info."""
    return {
        "name": "🛡️ ResumeGuard — Fraud Detection Engine",
        "version": "1.0.0",
        "status": "running",
        "signals": ["timeline_overlap", "email_validation", "phone_validation",
                     "jd_plagiarism", "semantic_similarity", "skills_mismatch"],
        "resumes_analyzed": len(resume_store["resumes"]),
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/validate_resume")
async def validate_resume(file: UploadFile = File(...)):
    """
    Analyze a single resume for fraud signals.
    Accepts PDF, DOCX, or TXT files.
    """
    logger.info(f"Received resume: {file.filename}")

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ("pdf", "docx", "doc", "txt"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Accepted: PDF, DOCX, TXT"
        )

    # Read file bytes
    try:
        file_bytes = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded")

    # Size limit: 10MB
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Parse file
    parse_result = parse_file(file_bytes, file.filename)
    if not parse_result.get("success") and not parse_result.get("text"):
        raise HTTPException(
            status_code=422,
            detail=f"Could not extract text from file: {parse_result.get('error', 'Unknown error')}"
        )

    text = parse_result["text"]

    # Run analysis
    try:
        analysis = await run_in_threadpool(run_analysis, text, file.filename)
        return JSONResponse(content=analysis)
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/batch_validate")
async def batch_validate(files: list[UploadFile] = File(...)):
    """
    Analyze multiple resumes in batch.
    Returns individual results + cross-resume analysis.
    """
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per batch")

    results = []
    errors = []

    for file in files:
        try:
            file_bytes = await file.read()
            ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""

            if ext not in ("pdf", "docx", "doc", "txt"):
                errors.append({"filename": file.filename, "error": f"Unsupported type: .{ext}"})
                continue

            parse_result = parse_file(file_bytes, file.filename)
            if not parse_result.get("text"):
                errors.append({"filename": file.filename, "error": parse_result.get("error", "No text")})
                continue

            analysis = await run_in_threadpool(run_analysis, parse_result["text"], file.filename)
            results.append(analysis)

        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    # Summary stats
    scores = [r["risk_score"] for r in results]
    summary = {
        "total_analyzed": len(results),
        "total_errors": len(errors),
        "avg_risk_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "max_risk_score": max(scores) if scores else 0,
        "high_risk_count": sum(1 for s in scores if s >= 65),
        "medium_risk_count": sum(1 for s in scores if 40 <= s < 65),
        "low_risk_count": sum(1 for s in scores if s < 40),
    }

    return JSONResponse(content={
        "summary": summary,
        "results": results,
        "errors": errors,
    })


@app.post("/compare_resumes")
async def compare_resumes(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    """Compare two resumes side-by-side for similarity."""
    results = []
    for f in [file1, file2]:
        file_bytes = await f.read()
        parse_result = parse_file(file_bytes, f.filename)
        if not parse_result.get("text"):
            raise HTTPException(status_code=422, detail=f"Cannot parse {f.filename}")
        entities = extract_entities(parse_result["text"])
        results.append({
            "filename": f.filename,
            "text": parse_result["text"],
            "entities": entities,
        })

    # Compute direct similarity
    from signals.semantic_similarity import get_embedding, cosine_similarity
    emb1 = get_embedding(results[0]["text"])
    emb2 = get_embedding(results[1]["text"])
    import numpy as np
    similarity = cosine_similarity(emb1, emb2) if emb1 is not None and emb2 is not None else 0

    # Check shared contact info
    shared_emails = set(results[0]["entities"]["emails"]) & set(results[1]["entities"]["emails"])
    shared_phones = set(results[0]["entities"]["phones"]) & set(results[1]["entities"]["phones"])

    return JSONResponse(content={
        "file1": results[0]["filename"],
        "file2": results[1]["filename"],
        "similarity_score": round(similarity * 100, 1),
        "shared_emails": list(shared_emails),
        "shared_phones": list(shared_phones),
        "name1": results[0]["entities"].get("name"),
        "name2": results[1]["entities"].get("name"),
        "skills_overlap": list(
            set(results[0]["entities"]["skills"].get("technical", [])) &
            set(results[1]["entities"]["skills"].get("technical", []))
        ),
        "fraud_indicators": {
            "same_contact": bool(shared_emails or shared_phones),
            "high_similarity": similarity >= 0.85,
            "possible_duplicate": similarity >= 0.95,
        }
    })


@app.get("/history")
async def get_history():
    """Get analysis history."""
    return JSONResponse(content={
        "total_resumes": len(resume_store["resumes"]),
        "resumes": resume_store["resumes"][-50:],  # Last 50
    })


@app.get("/stats")
async def get_stats():
    """Get overall system statistics."""
    return JSONResponse(content={
        "total_resumes_analyzed": len(resume_store["resumes"]),
        "unique_emails": len(set(resume_store["emails_seen"])),
        "unique_phones": len(set(resume_store["phones_seen"])),
        "embeddings_stored": len(resume_store["embeddings"]),
        "experiences_indexed": len(resume_store["experiences_seen"]),
    })


@app.delete("/reset")
async def reset_store():
    """Reset the in-memory store (for demo purposes)."""
    resume_store["resumes"] = []
    resume_store["emails_seen"] = []
    resume_store["phones_seen"] = []
    resume_store["experiences_seen"] = []
    resume_store["embeddings"] = []
    return {"status": "reset", "message": "All stored data cleared"}


# ─── Main ────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
