from sqlalchemy import Column, Integer, String, DateTime, Float
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


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String(255), nullable=False)
    location = Column(String(255), nullable=False)
    country = Column(String(80), nullable=True, default="United States")
    state = Column(String(120), nullable=True)
    city = Column(String(120), nullable=True)
    max_results = Column(Integer, nullable=False, default=100)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    radius = Column(Integer, default=50000)
    min_rating = Column(Float, nullable=True)
    status = Column(String(20), default=CampaignStatus.PENDING.value)
    total_leads = Column(Integer, default=0)
    emailed_leads = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.query,
            "location": self.location,
            "country": self.country,
            "state": self.state,
            "city": self.city,
            "max_results": self.max_results,
            "lat": self.lat,
            "lng": self.lng,
            "radius": self.radius,
            "min_rating": self.min_rating,
            "status": self.status,
            "total_leads": self.total_leads,
            "emailed_leads": self.emailed_leads,
            "created_at": str(self.created_at) if self.created_at else None,
        }
