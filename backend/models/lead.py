from sqlalchemy import Column, Integer, String, DateTime, Float, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from .campaign import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    place_id = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    category = Column(String(255), nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    website_uri = Column(String(500), nullable=True)
    maps_url = Column(Text, nullable=True)
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
            "category": self.category,
            "rating": self.rating,
            "review_count": self.review_count,
            "website_uri": self.website_uri,
            "maps_url": self.maps_url or (
                f"https://www.google.com/maps/search/?api=1&query_place_id={self.place_id}"
                if self.place_id else None
            ),
            "has_website": self.has_website,
            "email_subject": self.email_subject,
            "email_body": self.email_body,
            "angle_used": self.angle_used,
            "email_status": self.email_status,
            "sent_at": str(self.sent_at) if self.sent_at else None,
        }
