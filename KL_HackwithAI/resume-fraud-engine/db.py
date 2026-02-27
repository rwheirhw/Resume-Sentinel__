from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./resume_fraud.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class ResumeRecord(Base):
    __tablename__ = "resumes"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True, index=True)
    jd_text = Column(Text, nullable=True)
    jd_hash = Column(String, nullable=True, index=True)
    embedding = Column(Text, nullable=True)
    risk_score = Column(Integer, nullable=False, default=0)
    contact_score = Column(Integer, nullable=False, default=0)
    timeline_score = Column(Integer, nullable=False, default=0)
    similarity_score = Column(Integer, nullable=False, default=0)
    risk_level = Column(String, nullable=False, default="LOW RISK")
    llm_explanation = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=False)
    signals_json = Column(Text, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
