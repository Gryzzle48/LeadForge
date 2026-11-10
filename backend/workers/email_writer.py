import json
import logging
import random
import os
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import async_session
from ..models.lead import Lead
from ..models.campaign import Campaign

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

def load_templates():
    templates = {}
    for fname in os.listdir(TEMPLATES_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(TEMPLATES_DIR, fname)) as f:
                data = json.load(f)
                templates[data["category"]] = data
    return templates

def match_category(category: str, templates: dict) -> str:
    """Pick the template whose keyword match is longest.

    File order used to win, so "barber" could match the restaurant keyword
    "bar" and get the wrong draft.
    """
    if not category:
        return "generic"
    cat_lower = category.lower()
    best_key = "generic"
    best_len = 0
    for key, tmpl in templates.items():
        for kw in tmpl.get("matches", []):
            if kw and kw in cat_lower and len(kw) > best_len:
                best_key = key
                best_len = len(kw)
    return best_key

class _SafeFormat(dict):
    def __missing__(self, key):
        return ""

def render_template(template: str, values: dict) -> str:
    safe = {}
    for key, value in values.items():
        text = "N/A" if value is None else str(value)
        safe[key] = text.replace("{", "(").replace("}", ")")
    return template.format_map(_SafeFormat(safe))

def generate_email(lead_name: str, category: str, location: str, rating: float, review_count: int, templates: dict):
    cat_key = match_category(category, templates)
    tmpl_data = templates.get(cat_key) or templates.get("generic")
    if not tmpl_data or not tmpl_data.get("angles"):
        raise ValueError("No email templates are installed")
    angle = random.choice(tmpl_data["angles"])
    body = render_template(angle["template"], {
        "business_name": lead_name or "your business",
        "category": category or "local",
        "location": location or "your area",
        "rating": rating if rating else "N/A",
        "review_count": review_count if review_count else "many",
    })
    subjects = [
        f"Quick question about {lead_name}",
        f"Question about {lead_name}",
        f"Hi from a local customer of {lead_name}",
        f"Quick question: {lead_name}",
        f"{lead_name} — a quick thought",
        f"Regarding {lead_name}",
    ]
    subject = random.choice(subjects)
    return subject, body, angle["name"]

async def generate_emails_for_campaign(campaign_id: int):
    async with async_session() as db:
        result = await db.execute(
            select(Lead).where(Lead.campaign_id == campaign_id, Lead.email_body == None)
        )
        leads = result.scalars().all()

        if not leads:
            return

        templates = load_templates()
        campaign_result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
        campaign = campaign_result.scalar_one_or_none()
        location = campaign.location if campaign else "your area"

        for lead in leads:
            try:
                subject, body, angle = generate_email(
                    lead.name,
                    lead.category or "",
                    location,
                    lead.rating or 0,
                    lead.review_count or 0,
                    templates,
                )
            except Exception:
                logger.exception("Could not draft an email for lead %s", lead.id)
                continue
            lead.email_subject = subject
            lead.email_body = body
            lead.angle_used = angle
            lead.email_status = "draft"

        await db.commit()
