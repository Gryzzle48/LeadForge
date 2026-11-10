from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from .campaign import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    # A global unique constraint prevents the same business being stored twice
    # across different searches and cities/campaigns.
    place_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    instagram_url = Column(String(500), nullable=True)
    google_maps_url = Column(String(1000), nullable=True)
    category = Column(String(255), nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    website_uri = Column(String(500), nullable=True)
    has_website = Column(Boolean, default=False)
    email_subject = Column(Text, nullable=True)
    email_body = Column(Text, nullable=True)
    angle_used = Column(String(100), nullable=True)
    email_status = Column(String(50), default="draft")
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "campaign_id": self.campaign_id,
            "place_id": self.place_id,
            "name": self.name,
            "address": self.address,
            "phone": self.phone,
            "email": self.email,
            "instagram_url": self.instagram_url,
            "google_maps_url": self.google_maps_url,
            "category": self.category,
            "rating": self.rating,
            "review_count": self.review_count,
            "has_website": self.has_website,
            "website_uri": self.website_uri,
            "email_subject": self.email_subject,
            "email_body": self.email_body,
            "angle_used": self.angle_used,
            "email_status": self.email_status,
            "sent_at": str(self.sent_at) if self.sent_at else None,
            "created_at": str(self.created_at) if self.created_at else None,
        }
