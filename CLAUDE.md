# iran-quake-mcp

Unofficial, read-only MCP server for earthquakes in Iran, built on the USGS FDSN event API, the EMSC SeismicPortal
FDSN API and the IRSC `events_list.xml` feed. On GitHub (`sepehr071/iran-quake-mcp`, public), not yet released (no tag or PyPI release). Sibling of `../snapp-mcp`; keep layout and idioms in step.
API map: `../iran-earthquakes/`.

## Layout

- `src/iran_quake_mcp/http.py`: the only HTTP code. One shared `httpx.AsyncClient` (`trust_env=False`) on a Chrome-impersonating
  curl_cffi transport, proxy only from `IRAN_QUAKE_MCP_PROXY`, concurrency 2, jitter, 60 s GET cache, GET retries (4, timeout/5xx/429;
  USGS answers a sporadic 502), 5 MB body cap, host allowlist (earthquake.usgs.gov, www.seismicportal.eu, irsc.ut.ac.ir), HTTP 204 -> `None`, `text=True` for the IRSC XML.
- `registry.py`, `server.py`: as in snapp-mcp. `quakes.py`: the 5 tools (`eq_latest`, `eq_search`, `eq_significant`, `eq_detail`, `eq_stats`).
- `tests/`: `test_quakes.py` offline (MockTransport + real trimmed fixtures), `test_live_quakes.py` (`@pytest.mark.live`).

## Commands

```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q            # offline
uv run python -m pytest -m live -q    # real USGS/EMSC
uv build
```

## Quirks (keep them)

- Source is explicit (`usgs` default, `emsc`, `irsc`); results are not merged or deduped, ids differ (EMSC ids match `\d{8}_\d+`, which `eq_detail` uses to pick the source).
- Times are UTC in the feeds; tools add `time_tehran` = UTC+03:30 (no DST since 2022). Depth is km, positive; EMSC geometry depth is negative, so use `properties.depth`.
- `iran_only` filters after fetching (up to 500 rows are fetched before cutting to `limit`): the point must be inside `IRAN_POLYGON` (coarse outline, ~0.3 degrees on land, plus Iranian waters; spot-checked against OSM/Nominatim) and the text must contain "iran", "persian gulf", "gulf of oman" or "caspian sea" (IRSC rows need no text). 'BORDER REGION' rows are decided by position (EMSC 20261014_0000009 at 37.69 N 44.81 E is in West Azerbaijan, Iran, so it stays). USGS names the nearest Iranian town even for events across the border (e.g. 38 km W of Sarpol-e Zahab is in Iraq); those are dropped by position.
- No province field exists in the USGS/EMSC feeds. `place` is an accent-insensitive substring on the place/region text, English only, except an exact province name in `PROVINCES` (12 provinces, rough boxes that overlap neighbours), which queries that box and filters by lat/lon. IRSC text is `Town, Province`, so the substring match is used for it.
- Reply size: `limit` max is 50 (`MAX_LIMIT`), ~11 KB; list events carry no `url` (only `eq_detail` for USGS does). `eq_stats` `truncated` is true when the raw fetch (before the Iran filter) came back full at 3000 rows.
- Live tests: USGS cold queries take ~10 s each, so keep calls few and concurrent; each live call is retried once.
- EMSC returns HTTP 204 (empty body) for no match; USGS returns an empty collection, and 404 for an unknown `eventid`.
- IRSC (irsc.ut.ac.ir, the official Iranian center): https is closed (TLS handshake failure) but plain `http://irsc.ut.ac.ir/events_list.xml` answers (curl, proxy off, 2026-10-19/20; Chrome timed out on it). It lists only the latest ~20 events (UTC; `Town, Province` x3 with km, mag, depth, `lat N`/`long E`), no magnitude type, no history. The POST search form `bulletin.php` is not wired. `earthquake.ut.ac.ir` does not resolve. The XML licence: non-commercial, humanitarian use, cite the center.
- Read-only only. Magnitude types differ per event (mb, ml, mw); do not compare blindly.

## Release

Bump `version` in `pyproject.toml` and both versions in `server.json`, commit, then `git tag vX.Y.Z && git push --tags`;
`.github/workflows/publish.yml` publishes to PyPI, the GitHub Release and the MCP Registry.
