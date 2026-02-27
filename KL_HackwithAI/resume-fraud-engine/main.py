import json
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from db import ResumeRecord, SessionLocal, init_db
from explainer import generate_explanation
from extractor import extract_text, parse_profile
from models import RiskReport
from scorer import compute_risk_score
from signals.contact import contact_signals
from signals.similarity import similarity_signals
from signals.timeline import timeline_signals

app = FastAPI(title="Resume Fraud Detection Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


@app.post("/validate_resume")
async def validate_resume(file: UploadFile = File(...), jd_text: str = Form("")):
    db_session = SessionLocal()
    try:
        file_bytes = await file.read()
        raw_text = extract_text(file_bytes=file_bytes, filename=file.filename or "")
        if not raw_text:
            raise HTTPException(status_code=400, detail="Unable to extract text from uploaded file")

        profile = parse_profile(raw_text)

        contact = contact_signals(profile.get("email", ""), profile.get("phone", ""), db_session)
        timeline = timeline_signals(raw_text)

        jd_for_similarity = (jd_text or "").strip() or profile.get("raw_text", "")
        similarity = similarity_signals(jd_for_similarity, db_session)

        scoring = compute_risk_score(
            contact_score=contact["contact_score"],
            timeline_score=timeline["timeline_score"],
            similarity_score=similarity["similarity_score"],
        )

        signal_details = {
            "contact": contact,
            "timeline": timeline,
            "similarity": {
                key: value for key, value in similarity.items() if key != "embedding"
            },
            "profile": {
                "name": profile.get("name", ""),
                "email": profile.get("email", ""),
                "phone": profile.get("phone", ""),
            },
        }

        explanation = generate_explanation(
            signals_dict=signal_details,
            risk_score=scoring["risk_score"],
            risk_level=scoring["risk_level"],
        )

        embedding_value = similarity.get("embedding", [])
        if hasattr(embedding_value, "tolist"):
            embedding_value = embedding_value.tolist()

        record = ResumeRecord(
            id=str(uuid4()),
            name=profile.get("name", "") or "Unknown Candidate",
            email=(profile.get("email", "") or "").lower(),
            phone=profile.get("phone", "") or "",
            jd_text=jd_for_similarity,
            jd_hash=similarity.get("jd_hash", ""),
            embedding=json.dumps(embedding_value),
            risk_score=scoring["risk_score"],
            contact_score=contact["contact_score"],
            timeline_score=timeline["timeline_score"],
            similarity_score=similarity["similarity_score"],
            risk_level=scoring["risk_level"],
            llm_explanation=explanation,
            submitted_at=datetime.utcnow(),
            signals_json=json.dumps(signal_details),
        )

        db_session.add(record)
        db_session.commit()

        response = RiskReport(
            risk_score=scoring["risk_score"],
            contact_score=contact["contact_score"],
            timeline_score=timeline["timeline_score"],
            similarity_score=similarity["similarity_score"],
            risk_level=scoring["risk_level"],
            llm_explanation=explanation,
            signal_details=signal_details,
        )
        return response.model_dump()

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal server error: {exc}")
    finally:
        db_session.close()


@app.get("/risk_report/{resume_id}")
async def get_risk_report(resume_id: str):
    db_session = SessionLocal()
    try:
        record = db_session.query(ResumeRecord).filter(ResumeRecord.id == resume_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Report not found")

        signal_details = {}
        if record.signals_json:
            try:
                signal_details = json.loads(record.signals_json)
            except Exception:
                signal_details = {}

        response = RiskReport(
            risk_score=record.risk_score,
            contact_score=record.contact_score,
            timeline_score=record.timeline_score,
            similarity_score=record.similarity_score,
            risk_level=record.risk_level,
            llm_explanation=record.llm_explanation or "",
            signal_details=signal_details,
        )
        return response.model_dump()
    finally:
        db_session.close()


@app.get("/all_reports")
async def all_reports():
    db_session = SessionLocal()
    try:
        rows = db_session.query(ResumeRecord).order_by(ResumeRecord.submitted_at.desc()).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "risk_score": row.risk_score,
                "risk_level": row.risk_level,
                "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
            }
            for row in rows
        ]
    finally:
        db_session.close()
