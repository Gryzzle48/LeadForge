from backend.workers.city_search import (
    CityBounds,
    CoverProgress,
    clear_geocode_cache,
    finish_reason,
    note_tile,
    parse_nominatim,
    plan_tiles,
    should_stop_before_tile,
    geocode_city,
)


AUSTIN = {
    "lat": "30.2672",
    "lon": "-97.7431",
    "display_name": "Austin, Texas, USA",
    "boundingbox": ["30.0986", "30.5169", "-97.9384", "-97.5615"],
}


def test_nominatim_box_is_parsed():
    bounds = parse_nominatim([AUSTIN])
    assert bounds is not None
    assert bounds.south < bounds.north
    assert bounds.west < bounds.east
    assert bounds.label.startswith("Austin")
    assert parse_nominatim([]) is None


def test_tiles_cover_the_city_and_respect_the_cap():
    bounds = parse_nominatim([AUSTIN])
    tiles, truncated = plan_tiles(bounds, tile_km=8, max_tiles=100)
    assert truncated is False
    assert len(tiles) >= 4
    assert tiles[0].lat < tiles[-1].lat or tiles[0].lng != tiles[-1].lng
    assert all(tile.radius_m >= 400 for tile in tiles)
    assert all(tile.zoom >= 1 for tile in tiles)
    limited, cut = plan_tiles(bounds, tile_km=1, max_tiles=4)
    assert len(limited) <= 4
    assert cut is False
    huge, huge_cut = plan_tiles(CityBounds(-40, 40, -40, 40, 0, 0, "Huge"), tile_km=1, max_tiles=4)
    assert len(huge) == 4
    assert huge_cut is True


def test_stop_when_the_target_is_reached():
    progress = CoverProgress()
    assert note_tile(progress, new_places=6, new_leads=2, checked=8, target=3, empty_limit=3, tiles_total=10) is None
    reason = note_tile(progress, new_places=4, new_leads=2, checked=5, target=3, empty_limit=3, tiles_total=10)
    assert reason == "target"
    assert progress.leads == 4
    assert progress.places_checked == 13
    assert progress.tiles_done == 2


def test_stop_when_the_city_is_exhausted():
    progress = CoverProgress()
    assert note_tile(progress, new_places=0, new_leads=0, checked=3, target=None, empty_limit=3, tiles_total=8) is None
    assert note_tile(progress, new_places=0, new_leads=0, checked=1, target=None, empty_limit=3, tiles_total=8) is None
    reason = note_tile(progress, new_places=0, new_leads=0, checked=0, target=None, empty_limit=3, tiles_total=8)
    assert reason == "exhausted"
    assert progress.tiles_done == 3
    assert progress.tiles_done < 8


def test_blank_target_finishes_the_tiles():
    progress = CoverProgress()
    assert note_tile(progress, new_places=2, new_leads=1, checked=4, target=None, empty_limit=3, tiles_total=2) is None
    assert note_tile(progress, new_places=1, new_leads=0, checked=2, target=None, empty_limit=3, tiles_total=2) == "tiles_done"


def test_time_cap_and_tile_cap_stop_before_another_tile():
    progress = CoverProgress(tiles_done=2, leads=1)
    assert should_stop_before_tile(progress, elapsed=100, max_seconds=90, max_tiles=10, cancelled=False) == "time_cap"
    assert should_stop_before_tile(progress, elapsed=10, max_seconds=90, max_tiles=2, cancelled=False) == "tile_cap"
    assert should_stop_before_tile(progress, elapsed=10, max_seconds=90, max_tiles=10, cancelled=True) == "cancelled"
    assert finish_reason("tiles_done", truncated=True) == "tile_cap"
    assert finish_reason("tiles_done", truncated=False) == "tiles_done"


def test_new_places_reset_the_empty_streak():
    progress = CoverProgress()
    note_tile(progress, new_places=0, new_leads=0, checked=1, target=None, empty_limit=3, tiles_total=9)
    note_tile(progress, new_places=0, new_leads=0, checked=1, target=None, empty_limit=3, tiles_total=9)
    reason = note_tile(progress, new_places=3, new_leads=0, checked=3, target=None, empty_limit=3, tiles_total=9)
    assert reason is None
    assert progress.empty_streak == 0


async def test_geocode_uses_nominatim_and_caches():
    clear_geocode_cache()
    calls = []

    class Response:
        status = 200

        async def json(self, content_type=None):
            return [AUSTIN]

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class Session:
        def get(self, url, params=None, headers=None):
            calls.append({"url": url, "params": params, "headers": headers})
            return Response()

    session = Session()
    first = await geocode_city(session, "Austin, TX", "LeadForge/1.0 (local business search)")
    second = await geocode_city(session, "austin,  tx", "LeadForge/1.0 (local business search)")
    assert first.label.startswith("Austin")
    assert second is first
    assert len(calls) == 1
    assert calls[0]["url"].startswith("https://nominatim.openstreetmap.org/")
    assert "LeadForge" in calls[0]["headers"]["User-Agent"]
    clear_geocode_cache()
