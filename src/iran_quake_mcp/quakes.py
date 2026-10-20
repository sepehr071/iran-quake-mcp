"""Earthquake tools for Iran: latest, search, significant, detail and statistics (USGS or EMSC)."""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from pydantic import Field

from .http import EMSC_BASE, USGS_BASE, ApiError, fetch
from .registry import tool

USGS_URL = f"{USGS_BASE}/fdsnws/event/1/query"
EMSC_URL = f"{EMSC_BASE}/fdsnws/event/1/query"
IRAN_BBOX = (24.0, 43.5, 40.0, 64.0)  # min_lat, min_lon, max_lat, max_lon; also covers parts of neighbours
TEHRAN = timedelta(hours=3, minutes=30)  # Iran has had no daylight saving since 2022
IRSC_URL = (
    "http://irsc.ut.ac.ir/events_list.xml"  # the site's https is closed; this plain-http feed holds ~20 latest events
)
STATS_LIMIT = 3000
POST_FILTER_LIMIT = 500  # rows fetched before the iran_only / place filter
MAX_LIMIT = 50  # 50 events are about 12 KB of JSON

# Coarse Iran outline (lat, lon), land borders to about 0.3 degrees plus the Iranian side of the Persian Gulf,
# Gulf of Oman and southern Caspian. Used by iran_only together with the place text.
IRAN_POLYGON = [
    (37.17, 44.79), (37.6, 44.55), (38.0, 44.3), (38.5, 44.25), (39.0, 44.2), (39.45, 44.15), (39.4, 44.5),
    (39.0, 45.4), (38.9, 46.0), (38.85, 46.55), (39.15, 47.0), (39.65, 47.6), (39.75, 48.0), (39.4, 48.3),
    (38.9, 48.6), (38.4, 48.9), (38.3, 49.7), (38.0, 51.0), (37.7, 52.5), (37.45, 53.9), (37.45, 54.7),
    (38.2, 55.4), (38.35, 56.3), (37.95, 57.2), (37.7, 58.4), (37.1, 59.2), (36.65, 60.0), (36.55, 61.2),
    (35.63, 61.27), (34.7, 60.8), (33.7, 60.55), (32.5, 60.8), (31.5, 61.7), (30.8, 61.8), (29.85, 60.87),
    (29.5, 61.65), (28.3, 62.5), (27.2, 63.3), (26.4, 62.7), (25.2, 61.6), (24.7, 60.5), (24.8, 58.0),
    (25.4, 57.2), (26.2, 56.6), (25.7, 55.0), (26.0, 54.2), (26.4, 53.2), (26.6, 52.2), (27.0, 51.2), (27.0, 50.4),
    (27.9, 49.8), (28.6, 49.4), (29.4, 49.0), (29.95, 48.8), (30.4, 47.9), (31.0, 47.7), (32.0, 47.6), (32.8, 46.6),
    (33.1, 46.05), (34.0, 45.7), (34.5, 45.5), (35.1, 45.8), (35.6, 45.95), (36.0, 45.7), (36.6, 45.05),
]  # fmt: skip
OFFSHORE = ("persian gulf", "gulf of oman", "caspian sea")  # region names of Iranian waters (no 'Iran' in them)

# Approximate province boxes (min_lat, min_lon, max_lat, max_lon) so `place` works by province name; they overlap neighbours.
PROVINCES = {
    "tehran": (34.4, 50.3, 36.0, 52.6),
    "kerman": (26.5, 54.4, 31.9, 59.6),
    "hormozgan": (25.4, 52.7, 28.9, 59.3),
    "khuzestan": (29.9, 47.7, 33.0, 50.6),
    "fars": (27.0, 50.6, 31.7, 55.6),
    "sistan and baluchestan": (25.0, 58.8, 31.4, 63.3),
    "kermanshah": (33.6, 45.4, 35.3, 48.0),
    "razavi khorasan": (33.8, 56.2, 37.5, 61.3),
    "east azerbaijan": (36.7, 45.0, 39.4, 48.5),
    "west azerbaijan": (36.5, 44.0, 39.5, 46.2),
    "bushehr": (27.0, 50.1, 30.3, 52.5),
    "mazandaran": (35.8, 50.3, 36.9, 54.2),
}
PROVINCES |= {"sistan": PROVINCES["sistan and baluchestan"], "khorasan": PROVINCES["razavi khorasan"]}

Source = Annotated[
    Literal["usgs", "emsc", "irsc"],
    Field(
        description="Data source: 'usgs' (USGS ComCat, default), 'emsc' (EMSC via SeismicPortal) or 'irsc' (Iranian "
        "Seismological Center, only its latest ~20 events, with province names). Magnitudes and locations differ "
        "slightly between them; ids are not interchangeable."
    ),
]
IranOnly = Annotated[
    bool,
    Field(
        description="True (default): keep only events inside a coarse Iran outline (lat/lon, includes Iranian waters) "
        "whose place text names Iran (or Persian Gulf, Gulf of Oman, Caspian Sea); neighbours across the border "
        "are dropped. False: everything in the bounding box."
    ),
]
Limit = Annotated[
    int,
    Field(ge=1, le=MAX_LIMIT, description=f"Max events to return, 1-{MAX_LIMIT} (a reply stays under 15 KB), e.g. 20."),
]


def _utc(ms_or_iso: int | float | str) -> datetime:
    if isinstance(ms_or_iso, str):
        head, _, frac = ms_or_iso.rstrip("Z").partition(".")
        s = f"{head}.{frac.ljust(6, '0')[:6]}" if frac else head
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    return datetime.fromtimestamp(ms_or_iso / 1000, timezone.utc)


def _fmt(dt: datetime, shift: timedelta = timedelta(0)) -> str:
    return (dt + shift).strftime("%Y-%m-%dT%H:%M:%S")


def _event(source: str, f: dict[str, Any]) -> dict[str, Any]:
    """One feature as a flat event. USGS and EMSC are mapped to the same fields."""
    p = f["properties"]
    if source == "usgs":
        lon, lat, depth = f["geometry"]["coordinates"][:3]
        t, mag_type, place = _utc(p["time"]), p.get("magType"), p.get("place")
    else:
        lon, lat, depth = p["lon"], p["lat"], p.get("depth")
        t, mag_type, place = _utc(p["time"]), p.get("magtype"), p.get("flynn_region")
    return {
        "id": f["id"],
        "source": source,
        "time_utc": _fmt(t),
        "time_tehran": _fmt(t, TEHRAN),
        "magnitude": p.get("mag"),
        "mag_type": mag_type,
        "depth_km": depth,
        "lat": lat,
        "lon": lon,
        "place": place,
    }


def _plain(s: str) -> str:
    """Lowercase without diacritics, so 'Minab' matches USGS 'Mīnāb'."""
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def _inside(lat: float, lon: float, poly: list[tuple[float, float]] = IRAN_POLYGON) -> bool:
    """Ray casting point-in-polygon on (lat, lon) vertices."""
    hit = False
    for (la, lo), (lb, lb_lon) in zip(poly, poly[-1:] + poly, strict=False):
        if (la > lat) != (lb > lat) and lon < (lb_lon - lo) * (lat - la) / (lb - la) + lo:
            hit = not hit
    return hit


def _in_iran(r: dict[str, Any]) -> bool:
    """iran_only rule: inside the Iran outline, and the place text names Iran or Iranian waters (IRSC lists only Iran)."""
    text = (r["place"] or "").lower()
    named = r["source"] == "irsc" or "iran" in text or any(k in text for k in OFFSHORE)
    return named and _inside(r["lat"], r["lon"])


def _irsc_events(xml: str) -> list[dict[str, Any]]:
    """Flatten the IRSC events_list.xml items (time is UTC, regions are 'Town, Province')."""
    out = []
    for it in ET.fromstring(xml).iter("item"):
        v = {c.tag: (c.text or "").strip() for c in it}
        if "mag" not in v:  # the first item is the licence text
            continue
        t = _utc(v["date"].replace(" ", "T"))
        out.append({
            "id": v["id"], "source": "irsc", "time_utc": _fmt(t), "time_tehran": _fmt(t, TEHRAN),
            "magnitude": float(v["mag"]), "mag_type": None, "depth_km": float(v["dep"]),
            "lat": float(v["lat"].split()[0]), "lon": float(v["long"].split()[0]), "place": v["reg1"],
            "nearby": [{"place": v[f"reg{i}"], "km": float(v[f"dis{i}"])} for i in (2, 3) if f"reg{i}" in v],
        })  # fmt: skip
    return out


def _bbox(bbox: str | None) -> tuple[float, float, float, float]:
    if not bbox:
        return IRAN_BBOX
    try:
        a, b, c, d = (float(x) for x in bbox.split(","))
    except ValueError:
        raise ApiError("bbox must be 'min_lat,min_lon,max_lat,max_lon', e.g. '35,50,36,52'.") from None
    if not (-90 <= a < c <= 90 and -180 <= b < d <= 180):
        raise ApiError("bbox needs min_lat < max_lat (within +-90) and min_lon < max_lon (within +-180).")
    return a, b, c, d


def _day(value: str, name: str) -> str:
    value = value.replace(" ", "T")
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?)?", value):
            raise ValueError
        datetime.fromisoformat(value)  # rejects impossible dates such as 2026-13-45
    except ValueError:
        raise ApiError(f"{name} must be 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS' in UTC, e.g. '2026-10-01'.") from None
    return value


async def _events(
    source: str,
    *,
    start: str,
    end: str | None = None,
    min_mag: float | None = None,
    max_mag: float | None = None,
    bbox: tuple[float, float, float, float] = IRAN_BBOX,
    order: str = "time",
    limit: int = 20,
    iran_only: bool = True,
    place: str | None = None,
    fetch_limit: int | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch, flatten, filter and cut. Returns (events, more) where more = rows may exist beyond the cut
    (more than `limit` matched, or the fetch itself was full so filtered-out rows may hide matches)."""
    n = fetch_limit or (POST_FILTER_LIMIT if iran_only or place else limit)
    prov = (
        PROVINCES.get(_plain(place.strip())) if place and place.strip() and source != "irsc" else None
    )  # IRSC text has the province
    if prov and bbox == IRAN_BBOX:
        bbox = prov  # fetch only the province box
    if source == "irsc":
        rows = _irsc_events(await fetch(IRSC_URL, text=True))
        full = not rows or min(r["time_utc"] for r in rows) > start  # the feed does not reach back to `start`
        rows = [
            r for r in rows
            if r["time_utc"] >= start and (not end or r["time_utc"] < end)
            and (min_mag is None or r["magnitude"] >= min_mag) and (max_mag is None or r["magnitude"] <= max_mag)
            and bbox[0] <= r["lat"] <= bbox[2] and bbox[1] <= r["lon"] <= bbox[3]
        ]  # fmt: skip
        rows.sort(key=lambda r: r["magnitude" if order == "magnitude" else "time_utc"], reverse=True)
    elif source == "usgs":
        params = {
            "format": "geojson", "starttime": start, "endtime": end, "minmagnitude": min_mag,
            "maxmagnitude": max_mag, "minlatitude": bbox[0], "minlongitude": bbox[1],
            "maxlatitude": bbox[2], "maxlongitude": bbox[3], "orderby": order, "limit": n,
        }  # fmt: skip
        body = await fetch(USGS_URL, params)
    else:
        params = {
            "format": "json", "starttime": start, "endtime": end, "minmag": min_mag, "maxmag": max_mag,
            "minlat": bbox[0], "minlon": bbox[1], "maxlat": bbox[2], "maxlon": bbox[3],
            "orderby": order, "limit": n,
        }  # fmt: skip
        body = await fetch(EMSC_URL, params)
    if source != "irsc":
        rows = [_event(source, f) for f in (body or {}).get("features", [])]
        full = len(rows) >= n  # the source may hold more rows than the n we asked for, counted before any filter
    rows = [r for r in rows if r["magnitude"] is not None]
    if iran_only:
        rows = [r for r in rows if _in_iran(r)]
    if prov:
        rows = [r for r in rows if prov[0] <= r["lat"] <= prov[2] and prov[1] <= r["lon"] <= prov[3]]
    elif place and place.strip():
        rows = [r for r in rows if _plain(place.strip()) in _plain(r["place"] or "")]
    return rows[:limit], len(rows) > limit or full


def _since(hours: float) -> str:
    return _fmt(datetime.now(timezone.utc) - timedelta(hours=hours))


@tool("Latest earthquakes")
async def eq_latest(
    min_magnitude: Annotated[float, Field(ge=0, le=9, description="Minimum magnitude, e.g. 3.0.")] = 3.0,
    hours: Annotated[int, Field(ge=1, le=720, description="Look back this many hours, e.g. 24.")] = 24,
    limit: Limit = 20,
    source: Source = "usgs",
    iran_only: IranOnly = True,
) -> dict[str, Any]:
    """List the most recent earthquakes in Iran, newest first.

    Use for "was there an earthquake today?". Times: time_utc and time_tehran (UTC+03:30); depth_km in km;
    magnitude type in mag_type (mb, ml, mw...). Call eq_detail with an id for more, eq_stats for counts.
    """
    events, more = await _events(source, start=_since(hours), min_mag=min_magnitude, limit=limit, iran_only=iran_only)
    return {"source": source, "count": len(events), "more": more, "events": events}


@tool("Search earthquakes")
async def eq_search(
    start_date: Annotated[
        str, Field(description="Start, UTC: 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SS', e.g. '2026-10-01'.")
    ],
    end_date: Annotated[
        str | None,
        Field(
            description="End, UTC, same format, e.g. '2026-10-15' (a date alone includes that whole day). Default: now."
        ),
    ] = None,
    min_magnitude: Annotated[float | None, Field(ge=0, le=10, description="Minimum magnitude, e.g. 4.5.")] = None,
    max_magnitude: Annotated[float | None, Field(ge=0, le=10, description="Maximum magnitude, e.g. 6.")] = None,
    bbox: Annotated[
        str | None,
        Field(
            description="Box 'min_lat,min_lon,max_lat,max_lon', e.g. '35,50,36,52' (Tehran area). Default: all Iran."
        ),
    ] = None,
    place: Annotated[
        str | None,
        Field(
            description="Text the place must contain, case and accents ignored, e.g. 'Minab' or 'southern iran' (EMSC region); IRSC places are 'Town, Province'. A province name (Tehran, Kerman, Hormozgan, Khuzestan, Fars, Sistan and Baluchestan, Kermanshah, Razavi Khorasan, East Azerbaijan, West Azerbaijan, Bushehr, Mazandaran) selects its approximate box instead. English names only."
        ),
    ] = None,
    order: Annotated[
        Literal["time", "magnitude"],
        Field(description="'time' (newest first, default) or 'magnitude' (largest first)."),
    ] = "time",
    limit: Limit = 20,
    source: Source = "usgs",
    iran_only: IranOnly = True,
) -> dict[str, Any]:
    """Search earthquakes in Iran by date range, magnitude, bounding box and place text.

    Use for history ("M5+ in 2026", "quakes near Bam"). USGS and EMSC have no province field: USGS gives the nearest
    town ('70 km NNE of Minab, Iran'), EMSC a region ('SOUTHERN IRAN'); filter by `place` (a province name works) or
    `bbox`. source='irsc' only knows its latest ~20 events, so older dates give `more`=true with few rows.
    Times: time_utc and time_tehran (UTC+03:30); depth_km in km. `more` = more results may exist beyond `limit`
    (or beyond the newest 500 events scanned when filtering by place/iran_only: narrow the dates or bbox).
    """
    start, end = _day(start_date, "start_date"), _day(end_date, "end_date") if end_date else None
    if end and len(end) == 10:  # a date-only end covers that whole day
        end = (datetime.fromisoformat(end) + timedelta(days=1)).strftime("%Y-%m-%d")
    if end and datetime.fromisoformat(end) <= datetime.fromisoformat(start):
        raise ApiError("end_date must be after start_date.")
    if None not in (min_magnitude, max_magnitude) and min_magnitude > max_magnitude:
        raise ApiError("min_magnitude must not be above max_magnitude.")
    events, more = await _events(
        source,
        start=start,
        end=end,
        min_mag=min_magnitude,
        max_mag=max_magnitude,
        bbox=_bbox(bbox),
        order=order,
        limit=limit,
        iran_only=iran_only,
        place=place,
    )
    return {"source": source, "count": len(events), "more": more, "events": events}


@tool("Significant earthquakes")
async def eq_significant(
    days: Annotated[int, Field(ge=1, le=3650, description="Look back this many days, e.g. 30.")] = 30,
    min_magnitude: Annotated[float, Field(ge=3, le=9, description="Minimum magnitude, e.g. 5.0.")] = 5.0,
    limit: Annotated[int, Field(ge=1, le=MAX_LIMIT, description=f"Max events to return, 1-{MAX_LIMIT}, e.g. 10.")] = 10,
    source: Source = "usgs",
    iran_only: IranOnly = True,
) -> dict[str, Any]:
    """List the strongest recent earthquakes in Iran, largest magnitude first.

    Use for "biggest earthquakes this month/year". Times in UTC and Tehran (UTC+03:30), depth_km in km.
    """
    events, more = await _events(
        source, start=_since(days * 24), min_mag=min_magnitude, order="magnitude", limit=limit, iran_only=iran_only
    )
    return {"source": source, "count": len(events), "more": more, "events": events}


@tool("Earthquake detail")
async def eq_detail(
    event_id: Annotated[
        str,
        Field(
            min_length=4,
            pattern=r"^[A-Za-z0-9_-]+$",
            description="Event id from another eq_ tool: USGS 'us6000u2w9', EMSC '20261016_0000282' or IRSC '213549'.",
        ),
    ],
) -> dict[str, Any]:
    """Get one earthquake in full: location, depth_km, magnitude type and source quality fields.

    The source is detected from the id format (IRSC: plain number, found only in its latest ~20 events, adds
    the nearest towns). USGS adds review status, shaking (felt reports, cdi, mmi),
    tsunami flag, sig (significance 0-1000), nst (stations), gap (degrees), rms; EMSC adds the contributing
    agency (catalog) and last update. Times in UTC and Tehran (UTC+03:30).
    """
    if re.fullmatch(r"\d{5,7}", event_id):  # IRSC ids are plain numbers; only its latest feed can be searched
        found = [r for r in _irsc_events(await fetch(IRSC_URL, text=True)) if r["id"] == event_id]
        if not found:
            raise ApiError(f"No IRSC event with id {event_id} in the latest feed (about 20 events).", 404)
        return found[0]
    if re.fullmatch(r"\d{8}_\d+", event_id):
        source, body = "emsc", await fetch(EMSC_URL, {"format": "json", "eventid": event_id})
    else:
        source, body = "usgs", await fetch(USGS_URL, {"format": "geojson", "eventid": event_id})
    if not body or "properties" not in body:
        raise ApiError(f"No {source.upper()} event with id {event_id}.", 404)
    p = body["properties"]
    out = _event(source, body)
    if source == "usgs":
        out["url"] = p.get("url")
        for k in (
            "status",
            "type",
            "felt",
            "cdi",
            "mmi",
            "alert",
            "tsunami",
            "sig",
            "net",
            "nst",
            "gap",
            "rms",
            "dmin",
        ):
            out[k] = p.get(k)
        out["updated_utc"] = _fmt(_utc(p["updated"]))
    else:
        out.update(catalog=p.get("auth"), type=p.get("evtype"), updated_utc=_fmt(_utc(p["lastupdate"])))
    return out


@tool("Earthquake statistics")
async def eq_stats(
    days: Annotated[int, Field(ge=1, le=365, description="Window length in days, ending now, e.g. 30.")] = 30,
    min_magnitude: Annotated[float, Field(ge=0, le=9, description="Minimum magnitude counted, e.g. 3.0.")] = 3.0,
    source: Source = "usgs",
    iran_only: IranOnly = True,
) -> dict[str, Any]:
    """Count earthquakes in Iran over a window: by magnitude band, by place, plus the strongest event.

    Use for "how active has Iran been this month". Places are USGS nearest towns or EMSC regions (no province
    data). `truncated` = the source returned its full 3000 rows before the Iran filter, so the count covers only the newest.
    """
    start = _since(days * 24)
    rows, truncated = await _events(
        source, start=start, min_mag=min_magnitude, limit=STATS_LIMIT, iran_only=iran_only, fetch_limit=STATS_LIMIT
    )
    bands = Counter()
    places = Counter()
    for r in rows:
        m = r["magnitude"]
        bands["<3" if m < 3 else "3-4" if m < 4 else "4-5" if m < 5 else "5-6" if m < 6 else "6+"] += 1
        pl = r["place"] or "unknown"
        places[(re.search(r" of (.+?)(?:,|$)", pl) or [None, pl])[1]] += 1
    return {
        "source": source,
        "window_start_utc": start,
        "min_magnitude": min_magnitude,
        "total": len(rows),
        "truncated": truncated,
        "by_magnitude": {k: bands[k] for k in ("<3", "3-4", "4-5", "5-6", "6+") if bands[k]},
        "top_places": dict(places.most_common(10)),
        "strongest": max(rows, key=lambda r: r["magnitude"], default=None),
    }
