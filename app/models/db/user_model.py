from sqlalchemy import (
    Column, String, Boolean, DateTime, Integer, Float, Numeric, Text, Index
)
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
import uuid

Base = declarative_base()


def utcnow():
    """Timezone-aware replacement for the deprecated datetime.utcnow."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(
        String,
        unique=True,
        index=True,
        default=lambda: f"farmer_{uuid.uuid4().hex[:8]}"
    )
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    auth_provider = Column(String, default="email")
    google_id = Column(String, nullable=True, unique=True)
    preferred_language = Column(String, default="english")
    region = Column(String, nullable=True, index=True)
    crop_type = Column(String, nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    last_login = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<User {self.email} ({self.farmer_id})>"


class PasswordResetToken(Base):
    """One-time password reset links.

    Only a SHA-256 hash of the token is stored — the raw value exists solely
    in the email we send. A database leak therefore yields nothing usable.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    def __repr__(self):
        return f"<PasswordResetToken {self.farmer_id} used={self.used_at is not None}>"


class PriceReport(Base):
    __tablename__ = "price_reports"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, nullable=True, index=True)
    crop_type = Column(String, nullable=False, index=True)
    region = Column(String, nullable=False, index=True)
    # Numeric, not String — so you can average, sort and aggregate.
    price_ngn_per_kg = Column(Numeric(10, 2), nullable=False)
    notes = Column(Text, nullable=True)
    reported_at = Column(DateTime(timezone=True), default=utcnow, index=True)
    is_verified = Column(Boolean, default=False)

    __table_args__ = (
        Index("ix_price_crop_region_date", "crop_type", "region", "reported_at"),
    )

    def __repr__(self):
        return f"<PriceReport {self.crop_type} ₦{self.price_ngn_per_kg}/kg @ {self.region}>"


class Detection(Base):
    """Every pest/disease detection the model makes. Log every call, including
    ones the farmer ignores — this is the record that proves model accuracy."""

    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, nullable=True, index=True)

    crop_type = Column(String, nullable=True, index=True)
    predicted_label = Column(String, nullable=False, index=True)
    confidence = Column(Float, nullable=True)
    model_version = Column(String, nullable=True)

    region = Column(String, nullable=True, index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    image_path = Column(String, nullable=True)     # object-storage key, not the blob
    inference_ms = Column(Integer, nullable=True)

    # Feedback loop — lets you measure real accuracy later.
    farmer_confirmed = Column(Boolean, nullable=True)
    corrected_label = Column(String, nullable=True)

    # Referral tracking for the agro-dealer path.
    recommended_input = Column(String, nullable=True)
    referral_code = Column(String, nullable=True, index=True)
    referral_redeemed = Column(Boolean, default=False)

    detected_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    __table_args__ = (
        Index("ix_detect_region_label_date", "region", "predicted_label", "detected_at"),
    )

    def __repr__(self):
        return f"<Detection {self.predicted_label} @ {self.region}>"


class YieldPrediction(Base):
    """Every yield forecast, plus the actual harvest once reported.
    Predicted vs actual is what proves the model works."""

    __tablename__ = "yield_predictions"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, nullable=True, index=True)

    crop_type = Column(String, nullable=False, index=True)
    region = Column(String, nullable=True, index=True)
    farm_size_hectares = Column(Float, nullable=True)

    predicted_yield_kg_per_ha = Column(Float, nullable=False)
    model_version = Column(String, nullable=True)
    season = Column(String, nullable=True, index=True)

    actual_yield_kg_per_ha = Column(Float, nullable=True)
    actual_reported_at = Column(DateTime(timezone=True), nullable=True)

    predicted_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    def __repr__(self):
        return f"<YieldPrediction {self.crop_type} {self.predicted_yield_kg_per_ha}kg/ha>"


class StoreReferral(Base):
    """Agro-store lookups and whether they converted — the table you show an
    agro-dealer or input company when asking them to pay you."""

    __tablename__ = "store_referrals"

    id = Column(Integer, primary_key=True, index=True)
    farmer_id = Column(String, nullable=True, index=True)
    store_name = Column(String, nullable=False, index=True)
    region = Column(String, nullable=True, index=True)

    triggered_by = Column(String, nullable=True)   # e.g. "detection", "search"
    detection_id = Column(Integer, nullable=True, index=True)
    recommended_input = Column(String, nullable=True)

    referral_code = Column(String, nullable=True, unique=True, index=True)
    redeemed = Column(Boolean, default=False, index=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    def __repr__(self):
        return f"<StoreReferral {self.store_name} redeemed={self.redeemed}>"