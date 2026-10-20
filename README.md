<!-- mcp-name: io.github.sepehr071/iran-quake-mcp -->

# iran-quake-mcp: Iran earthquakes MCP server for AI agents

Unofficial, read-only MCP server for earthquakes in Iran (زلزله ایران): latest quakes, history search, the strongest
events, one event in full, and activity statistics, from the public USGS, EMSC and IRSC feeds. Works in Claude, Cursor and Copilot.

## For AI agents

- **What:** earthquake data for Iran from USGS ComCat (`source="usgs"`, default), EMSC via SeismicPortal (`source="emsc"`) and the Iranian Seismological Center (`source="irsc"`, only its latest ~20 events, with province names). Sources are not merged; ids differ.
- **Install:** `uvx iran-quake-mcp` or `claude mcp add iran-quake -- uvx iran-quake-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none. Optional `IRAN_QUAKE_MCP_PROXY` (HTTP proxy URL, comma list allowed); system proxy settings are ignored.
- **Access:** read-only, no confirmation needed.
- **Units:** `time_utc` (UTC) and `time_tehran` (UTC+03:30, no daylight saving); search dates are UTC; `depth_km` in kilometres; `mag_type` (mb, ml, mw...) says which magnitude it is.
- **Replies:** at most 50 events per call (`limit` 1-50), about 11 KB at the maximum.
- **Places:** USGS and EMSC have no province field (USGS gives the nearest town, EMSC a region). `place` accepts a province name (Tehran, Kerman, Hormozgan, Khuzestan, Fars, Sistan and Baluchestan, Kermanshah, Razavi Khorasan, East Azerbaijan, West Azerbaijan, Bushehr, Mazandaran), which selects an approximate box that overlaps its neighbours; other text is matched against the place text. IRSC places are `Town, Province`.
- **IRSC:** read from `http://irsc.ut.ac.ir/events_list.xml` (plain HTTP, its https is closed). It holds only the latest ~20 events, so `more` is true when the dates reach further back; the data is licensed for non-commercial, humanitarian use and must cite the Iranian Seismological Center (University of Tehran). Not a warning service.

## Tools

| Tool | What it does |
|---|---|
| `eq_latest` | Most recent earthquakes (min magnitude, hours back, source), newest first |
| `eq_search` | Search by UTC date range, magnitude range, bounding box and place text |
| `eq_significant` | Strongest earthquakes of the last N days, largest first |
| `eq_detail` | One event in full by id (USGS: review status, felt/shaking, tsunami flag, quality; EMSC: agency, update time; IRSC: nearest towns) |
| `eq_stats` | Counts for a window: by magnitude band, top places, strongest event |

By default only events inside a coarse Iran outline (about 0.3 degrees on land borders; includes the Iranian Persian Gulf, Gulf of Oman and south Caspian) whose place text names Iran, Persian Gulf, Gulf of Oman or Caspian Sea are returned, so border-region rows across the border are dropped (`iran_only=false` returns everything in the bounding box 24-40 N, 43.5-64 E).

## Development

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q          # offline
uv run python -m pytest -m live -q  # real USGS/EMSC
uv build
```

Data: USGS Earthquake Hazards Program and EMSC; see their terms of use. MIT licensed.
