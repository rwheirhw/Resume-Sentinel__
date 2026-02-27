from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExperienceItem(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None


class ResumeProfile(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    education: List[str] = Field(default_factory=list)
    experience: List[ExperienceItem] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    jd_text: Optional[str] = None


class RiskReport(BaseModel):
    risk_score: int
    contact_score: int
    timeline_score: int
    similarity_score: int
    risk_level: str
    llm_explanation: str
    signal_details: Dict
