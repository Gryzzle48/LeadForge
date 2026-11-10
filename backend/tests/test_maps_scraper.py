from backend.workers.grid_search import parse_scraper_csv


def test_parse_gosom_csv_fields_and_email():
    content = (
        "input_id,link,title,category,address,website,phone,review_count,"
        "review_rating,place_id,emails\n"
        'q1,https://maps.google.com/example,Bluebird Cafe,Cafe,'
        '1 Main St\, Miami,,+1 305 555 0100,125,4.6,ChIJ123,'
        '"hello@bluebird.example, team@bluebird.example"\n'
    )

    rows = parse_scraper_csv(content)

    assert len(rows) == 1
    assert rows[0]["name"] == "Bluebird Cafe"
    assert rows[0]["category"] == "Cafe"
    assert rows[0]["phone"] == "+1 305 555 0100"
    assert rows[0]["place_id"] == "ChIJ123"
    assert rows[0]["google_maps_url"] == "https://maps.google.com/example"
    assert rows[0]["email"] == "hello@bluebird.example"
    assert rows[0]["website_uri"] is None


def test_scraper_csv_uses_stable_id_when_place_id_missing():
    content = (
        "input_id,link,title,category,address,website,phone,review_count,"
        "review_rating,place_id,emails\n"
        "q1,,Local Shop,Store,99 Broad St,,,,,,\n"
    )

    first = parse_scraper_csv(content)[0]
    second = parse_scraper_csv(content)[0]

    assert first["place_id"].startswith("gosom:")
    assert first["place_id"] == second["place_id"]


def test_scraper_csv_keeps_website_value_for_filtering():
    content = (
        "title,address,website,place_id\n"
        "Business,10 Main St,https://business.example,ChIJ456\n"
    )

    row = parse_scraper_csv(content)[0]
    assert row["website_uri"] == "https://business.example"
