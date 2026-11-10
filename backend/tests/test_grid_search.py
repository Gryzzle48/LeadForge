from backend.workers.grid_search import parse_scraper_csv


def test_parse_gosom_csv_maps_business_fields():
    csv_content = """link,title,category,address,website,phone,review_count,review_rating,place_id
https://www.google.com/maps/place/Example,Example Coffee,Coffee shop,"123 Main St, Miami, FL",,+1 305-555-0100,42,4.6,ChIJexample
"""

    rows = parse_scraper_csv(csv_content)

    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "Example Coffee"
    assert row["category"] == "Coffee shop"
    assert row["address"] == "123 Main St, Miami, FL"
    assert row["phone"] == "+1 305-555-0100"
    assert row["google_maps_url"] == "https://www.google.com/maps/place/Example"
    assert row["place_id"] == "ChIJexample"
    assert row["website_uri"] is None
    assert row["rating"] == 4.6
    assert row["review_count"] == 42


def test_parse_gosom_csv_keeps_website_for_later_filtering():
    csv_content = """link,title,category,address,website,phone,review_count,review_rating,place_id
https://maps.google.com/example,Example Dental,Dentist,"2 Main St, Austin, TX",https://example.com,+1 512-555-0100,12,4.2,ChIJwebsite
"""

    rows = parse_scraper_csv(csv_content)

    assert len(rows) == 1
    assert rows[0]["website_uri"] == "https://example.com"


def test_parse_gosom_csv_uses_stable_fallback_when_place_id_is_missing():
    csv_content = """link,title,category,address,website,phone,review_count,review_rating
https://maps.google.com/example,No Place ID Shop,Shop,"4 Main St, Denver, CO",,,0,0
"""

    first = parse_scraper_csv(csv_content)[0]
    second = parse_scraper_csv(csv_content)[0]

    assert first["place_id"].startswith("gosom:")
    assert first["place_id"] == second["place_id"]
