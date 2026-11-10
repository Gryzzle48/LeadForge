from backend.workers.contact_finder import _extract_contacts


def test_extracts_public_email_instagram_and_sources():
    result = _extract_contacts([
        {
            "title": "Sunrise Coffee - Contact",
            "link": "https://sunrisecoffee.example/contact",
            "snippet": "Email <hello@sunrisecoffee.example> or follow https://www.instagram.com/sunrisecoffee/",
        }
    ])

    assert result["email"] == "hello@sunrisecoffee.example"
    assert result["instagram_url"] == "https://www.instagram.com/sunrisecoffee"
    assert result["sources"] == ["https://sunrisecoffee.example/contact"]


def test_ignores_instagram_content_urls_and_example_emails():
    result = _extract_contacts([
        {
            "title": "Contact",
            "link": "https://www.instagram.com/p/ABC123/",
            "snippet": "test@example.com",
        }
    ])

    assert result["email"] is None
    assert result["instagram_url"] is None


def test_deduplicates_contacts():
    result = _extract_contacts([
        {
            "title": "Business",
            "link": "https://business.example/contact",
            "snippet": "hello@business.example",
        },
        {
            "title": "Business Instagram",
            "link": "https://www.instagram.com/business/",
            "snippet": "hello@business.example",
        },
    ])

    assert result["email"] == "hello@business.example"
    assert result["instagram_url"] == "https://www.instagram.com/business"
    assert len(result["sources"]) == 2


def test_ignores_malformed_results_and_normalizes_wrapped_email():
    result = _extract_contacts([
        None,
        {"title": "Contact", "link": "", "snippet": "(Team@Business.example)."},
    ])

    assert result["email"] == "team@business.example"
