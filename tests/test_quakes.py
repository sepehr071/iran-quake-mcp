import httpx
import pytest
from conftest import FIXTURES, fixture

from iran_quake_mcp import http, quakes

pytestmark = pytest.mark.anyio

PATH = "/fdsnws/event/1/query"
TOOLS = {"eq_latest", "eq_search", "eq_significant", "eq_detail", "eq_stats"}


async def call(client, name, args=None):
    result = await client.call_tool(name, args or {})
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def test_list_tools(client):
    assert {t.name for t in (await client.list_tools()).tools} == TOOLS


async def test_latest_usgs(client, api):
    api[PATH] = fixture("usgs_query.json")
    data = await call(client, "eq_latest", {"min_magnitude": 4, "hours": 48, "limit": 2})
    first = data["events"][0]
    assert data["count"] == 2 and data["more"] is True
    assert first["id"] == "us6000u2w9" and first["magnitude"] == 4.5 and first["mag_type"] == "mb"
    assert first["time_utc"] == "2026-10-16T21:30:26" and first["time_tehran"] == "2026-10-17T01:00:26"
    assert first["depth_km"] == 10 and "Iran" in first["place"] and "url" not in first
    q = api.calls[0].url.params
    assert q["minmagnitude"] == "4.0" and q["orderby"] == "time" and q["minlatitude"] == "24.0"


async def test_latest_emsc(client, api):
    api[PATH] = fixture("emsc_query.json")
    data = await call(client, "eq_latest", {"source": "emsc"})
    e = data["events"][0]
    assert e["source"] == "emsc" and e["depth_km"] == 10.0 and e["place"] == "SOUTHERN IRAN"
    assert e["time_tehran"] == "2026-10-17T01:00:26"
    q = api.calls[0].url.params
    assert q["minmag"] == "3.0" and "minmagnitude" not in q


async def test_search_filters(client, api):
    body = fixture("usgs_query.json")
    body["features"][1]["properties"]["place"] = "10 km N of Herat, Afghanistan"
    api[PATH] = body
    data = await call(client, "eq_search", {"start_date": "2026-10-01", "place": "minab", "order": "magnitude"})
    assert (
        all("Mīnāb" in e["place"] for e in data["events"]) and data["count"] == 2
    )  # accents ignored, Afghanistan dropped
    assert api.calls[0].url.params["orderby"] == "magnitude"
    data = await call(client, "eq_search", {"start_date": "2026-10-01", "iran_only": False, "place": "herat"})
    assert data["count"] == 1


async def test_search_bad_input(client):
    for args in (
        {"start_date": "yesterday"},
        {"start_date": "2026-13-45"},
        {"start_date": "2026-10-01", "end_date": "2026-02-30T10:00"},
        {"start_date": "2026-10-01", "bbox": "1,2,3"},
        {"start_date": "2026-10-01", "bbox": "36,50,35,52"},
    ):
        result = await client.call_tool("eq_search", args)
        assert result.is_error


async def test_search_rules(client, api):
    api[PATH] = fixture("usgs_query.json")
    for args, msg in (
        ({"start_date": "2026-10-10", "end_date": "2026-10-01"}, "end_date must be after start_date"),
        ({"start_date": "2026-10-01", "min_magnitude": 5, "max_magnitude": 4}, "min_magnitude must not be above"),
    ):
        result = await client.call_tool("eq_search", args)
        assert result.is_error and msg in result.content[0].text
    await call(client, "eq_search", {"start_date": "2026-10-01", "end_date": "2026-10-16", "place": " "})
    assert api.calls[0].url.params["endtime"] == "2026-10-17"  # date-only end includes the whole day
    assert (await client.call_tool("eq_detail", {"event_id": "../../etc"})).is_error


async def test_more_when_scan_full(client, api):
    api[PATH] = fixture("usgs_query.json")
    n = len(fixture("usgs_query.json")["features"])
    api.calls.clear()
    data = await call(client, "eq_latest", {"limit": 50, "iran_only": False})
    assert data["more"] is (n >= 50)  # fetch of `limit` rows came back full only if n >= limit
    data = await call(client, "eq_latest", {"limit": n, "iran_only": False})
    assert data["more"] is True


async def test_significant(client, api):
    api[PATH] = fixture("usgs_query.json")
    data = await call(client, "eq_significant", {"days": 30, "min_magnitude": 4.4})
    assert data["count"] == 3 and api.calls[0].url.params["orderby"] == "magnitude"


async def test_detail_usgs(client, api):
    api[PATH] = fixture("usgs_detail.json")
    data = await call(client, "eq_detail", {"event_id": "us6000u2w9"})
    assert data["status"] == "reviewed" and data["sig"] == 312 and data["nst"] == 45 and data["updated_utc"]
    assert api.calls[0].url.params["eventid"] == "us6000u2w9" and "earthquake.usgs.gov" in str(api.calls[0].url)


async def test_detail_emsc(client, api):
    api[PATH] = fixture("emsc_detail.json")
    data = await call(client, "eq_detail", {"event_id": "20261016_0000282"})
    assert data["source"] == "emsc" and data["catalog"] == "EMSC" and data["magnitude"] == 4.5
    assert "seismicportal.eu" in str(api.calls[0].url)


async def test_detail_unknown(client, api):
    api[PATH] = lambda request: httpx.Response(204)
    result = await client.call_tool("eq_detail", {"event_id": "20260101_0000001"})
    assert result.is_error and "No EMSC event" in result.content[0].text


def irsc(api):
    xml = (FIXTURES / "irsc_events.xml").read_bytes()
    api["/events_list.xml"] = lambda request: httpx.Response(200, content=xml)


async def test_iran_only_border_and_offshore(client, api):
    api[PATH] = fixture("emsc_border.json")
    data = await call(client, "eq_search", {"start_date": "2020-01-01", "source": "emsc"})
    # Persian Gulf, NE Iran near the Turkmen border and SOUTHERN IRAN stay; Turkey/Iraq/Azerbaijan/Caspian-north go.
    # 20261014_0000009 is a 'BORDER REGION' row that lies inside Iran (OSM: West Azerbaijan Province), so it stays.
    assert {e["id"] for e in data["events"]} == {
        "20240817_0000268",
        "20250422_0000054",
        "20260806_0000373",
        "20261014_0000009",
    }
    data = await call(client, "eq_search", {"start_date": "2020-01-01", "source": "emsc", "iran_only": False})
    assert data["count"] == 9


async def test_iran_only_usgs_nearest_town_across_border(client, api):
    api[PATH] = fixture("usgs_border.json")
    data = await call(client, "eq_search", {"start_date": "2020-01-01"})
    # 'Sarpol-e Zahab' (38 km W) and 'Mehran' (35 km SE) lie in Iraq, the Gorgan one in Turkmenistan (OSM); Iraq/Saudi/Azerbaijan texts go.
    assert {e["id"] for e in data["events"]} == {"us6000rnxv", "us6000tjyv"}


async def test_limit_max_reply_under_15kb(client, api):
    body = fixture("usgs_query.json")
    body["features"] = [dict(body["features"][i % 3], id=f"us7000{i:04d}") for i in range(120)]
    for f in body["features"]:
        f["properties"]["place"] = "117 km NNW of Bandar-e Khamir, Hormozgan Province, Iran"
    api[PATH] = body
    result = await client.call_tool("eq_latest", {"limit": 50})
    assert result.structured_content["count"] == 50 and len(result.content[0].text.encode()) < 15_000
    for args in ({"limit": 51}, {"limit": 0}):
        assert (await client.call_tool("eq_latest", args)).is_error
    assert (await client.call_tool("eq_significant", {"limit": 51})).is_error


async def test_stats_truncated_counts_rows_before_iran_filter(client, api, monkeypatch):
    monkeypatch.setattr(quakes, "STATS_LIMIT", 3)
    api[PATH] = fixture("emsc_border.json")
    del api[PATH]["features"][3:]  # 3 rows come back = full; only one is in Iran
    data = await call(client, "eq_stats", {"source": "emsc", "min_magnitude": 0})
    assert data["total"] == 1 and data["truncated"] is True  # 3 raw rows, only the Persian Gulf one is Iranian
    assert api.calls[0].url.params["limit"] == "3"


async def test_province_place(client, api):
    body = fixture("usgs_query.json")
    body["features"][0]["geometry"]["coordinates"] = [51.4, 35.7, 10]  # inside the Tehran box
    api[PATH] = body
    data = await call(client, "eq_search", {"start_date": "2026-10-01", "place": "Tehran", "iran_only": False})
    assert [e["id"] for e in data["events"]] == ["us6000u2w9"]
    q = api.calls[0].url.params
    assert q["minlatitude"] == "34.4" and q["maxlongitude"] == "52.6"  # province box replaces the Iran box
    data = await call(client, "eq_search", {"start_date": "2026-10-01", "place": "khuzestan", "iran_only": False})
    assert data["count"] == 0  # box match: the Tehran-box row is not in Khuzestan


async def test_irsc_latest_and_filters(client, api):
    irsc(api)
    data = await call(client, "eq_latest", {"source": "irsc", "min_magnitude": 3.3, "hours": 720})
    assert [e["id"] for e in data["events"]][:3] == ["213536", "213530", "213529"]
    e = data["events"][0]
    assert e["source"] == "irsc" and e["place"] == "Roydar, Hormozgan" and e["time_tehran"] == "2026-10-18T10:04:25"
    assert "irsc.ut.ac.ir" in str(api.calls[0].url) and str(api.calls[0].url).startswith("http://")
    assert all("Iraq" not in e["place"] for e in data["events"])  # iran_only drops Kifri, Iraq
    data = await call(client, "eq_search", {"start_date": "2026-10-16T16:00", "source": "irsc", "place": "hormozgan"})
    assert data["count"] == 4 and data["more"] is False
    data = await call(client, "eq_search", {"start_date": "2026-10-16T16:00", "source": "irsc", "order": "magnitude"})
    assert data["events"][0]["magnitude"] == 4.3
    data = await call(client, "eq_search", {"start_date": "2020-01-01", "source": "irsc", "end_date": "2026-10-17"})
    assert data["more"] is True  # the feed holds only the latest ~20 events


async def test_irsc_detail(client, api):
    irsc(api)
    data = await call(client, "eq_detail", {"event_id": "213536"})
    assert data["magnitude"] == 3.3 and data["nearby"][0] == {"place": "Bandar khamir, Hormozgan", "km": 39}
    result = await client.call_tool("eq_detail", {"event_id": "999999"})
    assert result.is_error and "No IRSC event" in result.content[0].text


async def test_stats(client, api):
    api[PATH] = fixture("usgs_query.json")
    data = await call(client, "eq_stats", {"days": 7, "min_magnitude": 4})
    assert data["total"] == 3 and data["by_magnitude"] == {"4-5": 3}
    assert data["top_places"] == {"Mīnāb": 2, "Bandar-e Jask": 1} or sum(data["top_places"].values()) == 3
    assert data["strongest"]["magnitude"] == 4.5 and data["truncated"] is False


async def test_http_retry_and_cache(api, monkeypatch):
    async def no_sleep(_):
        pass

    monkeypatch.setattr(http.asyncio, "sleep", no_sleep)
    hits = iter([httpx.Response(502), httpx.Response(200, json={"a": 1})])
    api[PATH] = lambda request: next(hits)
    url = "https://earthquake.usgs.gov" + PATH
    assert await http.fetch(url, {"q": 1}) == {"a": 1}
    assert await http.fetch(url, {"q": 1}) == {"a": 1}  # cached
    assert len(api.calls) == 2


async def test_http_refuses_other_host():
    with pytest.raises(http.ApiError):
        await http.fetch("https://example.com/x")
