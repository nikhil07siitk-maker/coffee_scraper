"""SQLAlchemy / SQLite session manager."""

from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid
from datetime import datetime

Base = declarative_base()

class CoffeeEstate(Base):
    __tablename__ = "coffee_estates"

    estate_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    estate_name = Column(String, nullable=False, index=True)
    estate_name_raw = Column(String)
    state = Column(String, nullable=False, index=True)
    district = Column(String, nullable=False, index=True)
    village_taluka = Column(String)
    altitude_meters = Column(Float)
    rating = Column(Float)
    user_ratings_total = Column(Float)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geo_accuracy = Column(String)
    primary_phone = Column(String)
    secondary_contact = Column(String)
    email = Column(String)
    website = Column(String)
    instagram_handle = Column(String)
    address_raw = Column(String)
    varietals_grown = Column(JSON)
    processing_methods = Column(JSON)
    certifications = Column(JSON)
    farm_size_acres = Column(Float)
    contact_person_name = Column(String)
    export_readiness = Column(String, default="unknown")
    rcmc_verified = Column(Boolean, default=False)
    apeda_registered = Column(Boolean, default=False)
    quality_flag = Column(JSON, default=list)
    discovery_sources = Column(JSON, nullable=False)
    bhuvan_verified = Column(Boolean)
    llm_confidence_score = Column(Float)
    record_status = Column(String, nullable=False, default="pending_verification")
    last_enriched_at = Column(DateTime, default=datetime.utcnow)

engine = None
SessionLocal = None

def init_db(database_url: str = "sqlite:///./data/indian_coffee_intel.db"):
    global engine, SessionLocal
    engine = create_engine(database_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

def get_session():
    if not SessionLocal:
        init_db()
    return SessionLocal()