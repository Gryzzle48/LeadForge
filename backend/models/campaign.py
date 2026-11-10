from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, Text, Enum as SAEnum
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
import enum

class Base(DeclarativeBase):
    pass

class CampaignStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    radius = Column(Integer, nullable=True)
    min_rating = Column(Float, nullable=True)
    min_reviews = Column(Integer, nullable=True)
    max_reviews = Column(Integer, nullable=True)
    target_leads = Column(Integer, nullable=True)
    tiles_done = Column(Integer, nullable=True)
    tiles_total = Column(Integer, nullable=True)
    places_checked = Column(Integer, nullable=True)
    cancel_requested = Column(Boolean, nullable=True, default=False)
    status = Column(String(20), default=CampaignStatus.PENDING.value)
    status_detail = Column(Text, nullable=True)
    sheet_url = Column(String(500), nullable=True)
    total_leads = Column(Integer, default=0)
    emailed_leads = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.query,
            "location": self.location,
            "lat": self.lat,
            "lng": self.lng,
            "radius": self.radius,
            "min_rating": self.min_rating,
            "min_reviews": self.min_reviews,
            "max_reviews": self.max_reviews,
            "target_leads": self.target_leads,
            "tiles_done": self.tiles_done or 0,
            "tiles_total": self.tiles_total or 0,
            "places_checked": self.places_checked or 0,
            "cancel_requested": bool(self.cancel_requested),
            "status": self.status,
            "status_detail": self.status_detail,
            "sheet_url": self.sheet_url,
            "total_leads": self.total_leads,
            "emailed_leads": self.emailed_leads,
            "created_at": str(self.created_at) if self.created_at else None,
        }
