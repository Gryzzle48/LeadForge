import json
import tempfile
import os
from backend.workers.email_writer import load_templates, match_category, generate_email

SAMPLE_TEMPLATES = {
    "restaurant": {
        "category": "restaurant",
        "matches": ["restaurant", "cafe", "bistro", "pizzeria"],
        "angles": [
            {
                "name": "lost_traffic",
                "template": "Hi {business_name}, noticed you're missing online orders in {location}."
            }
        ]
    },
    "generic": {
        "category": "generic",
        "matches": [],
        "angles": [
            {
                "name": "missed_opportunity",
                "template": "Hi {business_name}, you're missing customers in {location}."
            }
        ]
    }
}

def test_match_category_restaurant():
    assert match_category("pizzeria", SAMPLE_TEMPLATES) == "restaurant"
    assert match_category("cafe", SAMPLE_TEMPLATES) == "restaurant"

def test_match_category_generic():
    assert match_category("hardware store", SAMPLE_TEMPLATES) == "generic"
    assert match_category("", SAMPLE_TEMPLATES) == "generic"

def test_generate_email_returns_subject_body_angle():
    subject, body, angle = generate_email("Test Biz", "pizzeria", "NYC", 4.5, 100, SAMPLE_TEMPLATES)
    assert isinstance(subject, str)
    assert len(subject) > 0
    assert "Test Biz" in body
    assert isinstance(angle, str)

def test_braces_in_business_name_do_not_drop_the_draft():
    subject, body, angle = generate_email("Cafe {Downtown}", "pizzeria", "Austin, TX", 4.2, 10, SAMPLE_TEMPLATES)
    assert "Cafe (Downtown)" in body
    assert subject
    assert angle

def test_barber_uses_the_clinic_template_not_the_bar_keyword():
    from backend.workers.email_writer import load_templates
    templates = load_templates()
    assert match_category("barber", templates) == "clinic"
    assert match_category("hair salon", templates) == "clinic"
    assert match_category("hardware store", templates) == "retail"
    assert match_category("italian restaurant", templates) == "restaurant"
