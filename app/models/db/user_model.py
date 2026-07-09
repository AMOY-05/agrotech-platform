from sqlalchemy import Column, String, Boolean, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, unique=True, index=True, default=lambda: f"farmer_{uuid.uuid4().hex[:8]}")
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)  # Null for OAuth users
    auth_provider = Column(String, default="email")  # "email" or "google"
    google_id = Column(String, nullable=True, unique=True)
    preferred_language = Column(String, default="english")
    region = Column(String, nullable=True)
    crop_type = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User {self.email} ({self.farmer_id})>"