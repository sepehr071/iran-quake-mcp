import asyncio

import pytest

pytestmark = [pytest.mark.anyio, pytest.mark.live]


async def call(client, name, args):
    # USGS answers a sporadic 502 that outlasts the client's own retries: retry the whole call once.
    for attempt in range(2):
        result = await client.call_tool(name, args)
        if not result.is_error or attempt:
            break
        await asyncio.sleep(3)
    assert not result.is_error, result.content[0].text
    return result.structured_content


async def test_usgs(client):
    # One cold USGS query takes ~10 s, so keep the count low and run them two at a time (the client's limit).
    latest, search, sig = await asyncio.gather(
        call(client, "eq_latest", {"min_magnitude": 3, "hours": 720, "limit": 5}),
        call(
            client, "eq_search", {"start_date": "2023-01-27", "end_date": "2023-01-30", "min_magnitude": 5, "limit": 5}
        ),
        call(client, "eq_significant", {"days": 365, "min_magnitude": 5, "limit": 3}),
    )
    assert latest["events"] and latest["events"][0]["time_utc"] >= latest["events"][-1]["time_utc"]
    assert search["events"] and all(e["magnitude"] >= 5 for e in search["events"])
    mags = [e["magnitude"] for e in sig["events"]]
    assert mags and mags == sorted(mags, reverse=True)
    event = latest["events"][0]
    data = await call(client, "eq_detail", {"event_id": event["id"]})
    assert data["id"] == event["id"] and data["magnitude"] == event["magnitude"] and data["url"]


async def test_stats_usgs(client):
    data = await call(client, "eq_stats", {"days": 7, "min_magnitude": 4})
    assert sum(data["by_magnitude"].values()) == data["total"] and data["truncated"] is False


async def test_emsc(client):
    latest, stats = await asyncio.gather(
        call(client, "eq_latest", {"min_magnitude": 3, "hours": 720, "limit": 5, "source": "emsc"}),
        call(client, "eq_stats", {"days": 30, "min_magnitude": 3, "source": "emsc"}),
    )
    assert latest["events"] and latest["events"][0]["time_utc"] >= latest["events"][-1]["time_utc"]
    assert stats["total"] > 0 and sum(stats["by_magnitude"].values()) == stats["total"]
    data = await call(client, "eq_detail", {"event_id": latest["events"][0]["id"]})
    assert data["source"] == "emsc" and data["magnitude"] == latest["events"][0]["magnitude"]


async def test_irsc(client):
    latest = await call(client, "eq_latest", {"min_magnitude": 0, "hours": 720, "source": "irsc"})
    assert latest["events"] and all(e["source"] == "irsc" for e in latest["events"])
    data = await call(client, "eq_detail", {"event_id": latest["events"][0]["id"]})
    assert data["id"] == latest["events"][0]["id"] and data["nearby"]
