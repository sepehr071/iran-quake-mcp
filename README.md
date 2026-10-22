<!-- mcp-name: io.github.sepehr071/iran-quake-mcp -->

<div align="center">

# iran-quake-mcp: Iran earthquakes MCP server for AI agents

**Let your AI agent check the latest earthquakes in Iran (زلزله ایران).**<br>
An unofficial, read-only MCP server for earthquake data from [USGS](https://earthquake.usgs.gov/), [EMSC](https://www.seismicportal.eu/) and the [Iranian Seismological Center](http://irsc.ut.ac.ir/):<br>
latest quakes, history search, the strongest events, one event in full and activity statistics, from Claude, Cursor or Copilot.

[![PyPI](https://img.shields.io/pypi/v/iran-quake-mcp?color=2563eb)](https://pypi.org/project/iran-quake-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/iran-quake-mcp)](https://pypi.org/project/iran-quake-mcp/)
[![CI](https://github.com/sepehr071/iran-quake-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/sepehr071/iran-quake-mcp/actions/workflows/ci.yml)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-io.github.sepehr071%2Firan--quake--mcp-7c3aed)](https://registry.modelcontextprotocol.io/?q=iran-quake-mcp)
[![License: MIT](https://img.shields.io/badge/license-MIT-16a34a)](https://github.com/sepehr071/iran-quake-mcp/blob/main/LICENSE)

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_iran--quake--mcp-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://vscode.dev/redirect/mcp/install?name=iran-quake&config=%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22iran-quake-mcp%22%5D%7D)

[For AI agents](#for-ai-agents) · [Quick start](#quick-start) · [What it can do](#what-it-can-do) · [Tools](#tools) · [FAQ](#faq) · [فارسی](#فارسی)

</div>

---

## For AI agents

- **What:** unofficial MCP server (model context protocol) for earthquakes in Iran. Sources: USGS ComCat (`source="usgs"`, default), EMSC via SeismicPortal (`source="emsc"`) and the Iranian Seismological Center (`source="irsc"`, only its latest ~20 events, with province names). Sources are not merged; their event ids differ.
- **Install:** `uvx iran-quake-mcp` or `claude mcp add iran-quake -- uvx iran-quake-mcp`. Transport: stdio. Needs [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python 3.10+).
- **Auth:** none, no API key or account. Optional `IRAN_QUAKE_MCP_PROXY` (HTTP proxy URL, or a comma-separated list); system proxy settings are ignored.
- **Access:** read-only. It cannot write or subscribe, so no confirmation is needed before calling any tool.
- **Tools:** 5, all prefixed `eq_`. Typical sequence: `eq_latest` or `eq_significant` -> `eq_detail` with an id from the list. `eq_search` for a date range, bounding box or place; `eq_stats` for counts.
- **Use when:** the user asks about recent or past earthquakes in Iran, the strongest quakes, quakes near a province or city, or how active a period was.
- **Do not use when:** the user needs an official warning or alert (this is not a warning service; see the Iranian Seismological Center, irsc.ut.ac.ir), or asks about earthquakes outside Iran and its neighbours.
- **Units:** `time_utc` (UTC) and `time_tehran` (UTC+03:30, no daylight saving); search dates are UTC; `depth_km` in kilometres; `mag_type` (mb, ml, mw...) says which magnitude it is.
- **Replies:** at most 50 events per call (`limit` 1-50), about 12 KB at the maximum, under 15 KB.
- **Machine-readable:** [`server.json`](https://github.com/sepehr071/iran-quake-mcp/blob/main/server.json) and the
  [awesome-iran-mcp catalog](https://github.com/sepehr071/awesome-iran-mcp).

## Why

Earthquake feeds are built for seismologists: different servers, different id formats, UTC timestamps, no province field.
Asking "was there a quake above 4.5 near Kerman this week, and what was the strongest one in Iran this month?" means
querying a map or a query form and converting times by hand. With `iran-quake-mcp` an agent answers it in a few calls
and returns a short summary with Tehran time and depth in kilometres.

> **You:** Were there any strong earthquakes in Iran in the last 30 days?
>
> **Agent:** *calls* `eq_significant(days=30, min_magnitude=5.0)` -> `eq_detail(...)` for the largest one
>
> It lists the events from largest to smallest with magnitude, place, depth and Tehran time, then adds the review
> status and felt reports of the biggest one.

Every reply stays under 15 KB (about 12 KB at the maximum), so it does not flood the agent's context.

## What it can do

- **Latest earthquakes** in Iran by minimum magnitude and hours back, newest first
- **Search** by UTC date range, magnitude range, bounding box and place text, ordered by time or magnitude
- **Strongest events** of the last N days, largest first
- **One event in full** by id: for USGS review status, felt/shaking, tsunami flag and quality; for EMSC the agency and update time; for IRSC the nearest towns
- **Statistics** for a window: counts by magnitude band, top places and the strongest event
- **Three sources** in one server: USGS, EMSC and the Iranian Seismological Center
- **Read-only by design**: nothing is written or subscribed to

Example prompts:

- "Show earthquakes of magnitude 4 or more in Iran in the last 48 hours."
- "What were the 10 strongest earthquakes in Iran in the last year?"
- "Any earthquakes near Kerman this month?"
- "Give me the quake statistics for Iran over the last 30 days."
- "Details of the latest quake on the Iranian Seismological Center feed, with province."
- <span dir="rtl">آخرین زلزله&zwnj;های ایران در ۲۴ ساعت گذشته کدام&zwnj;اند؟</span>
- <span dir="rtl">قوی&zwnj;ترین زلزله&zwnj;های ماه اخیر در ایران را با عمق و ساعت تهران بده.</span>
- <span dir="rtl">آیا در هفته گذشته در هرمزگان زلزله بالای ۴ ریشتر آمده؟</span>

## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). No API key or account.

<details open>
<summary><b>Claude Code</b></summary>

```bash
claude mcp add iran-quake -- uvx iran-quake-mcp
```
</details>

<details>
<summary><b>Claude Desktop</b></summary>

Settings → Developer → Edit Config, then add:

```json
{
  "mcpServers": {
    "iran-quake": { "command": "uvx", "args": ["iran-quake-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Cursor</b></summary>

Add the Claude Desktop block above to `~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project).
</details>

<details>
<summary><b>VS Code (Copilot agent mode)</b></summary>

Click **Install in VS Code** above, or add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "iran-quake": { "type": "stdio", "command": "uvx", "args": ["iran-quake-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Codex CLI</b></summary>

```bash
codex mcp add iran-quake -- uvx iran-quake-mcp
```

Or in `~/.codex/config.toml`:

```toml
[mcp_servers.iran-quake]
command = "uvx"
args = ["iran-quake-mcp"]
```
</details>

<details>
<summary><b>Gemini CLI</b></summary>

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "iran-quake": { "command": "uvx", "args": ["iran-quake-mcp"] }
  }
}
```
</details>

<details>
<summary><b>Windsurf</b></summary>

Add the Claude Desktop block to `~/.codeium/windsurf/mcp_config.json`.
</details>

<details>
<summary><b>Anything else</b></summary>

It is a standard stdio MCP server: run `uvx iran-quake-mcp`, or `pip install iran-quake-mcp` and run `iran-quake-mcp`.
</details>

## Tools

The list tools (`eq_latest`, `eq_search`, `eq_significant`, `eq_stats`) take an optional `source` (`usgs` default, `emsc`, `irsc`) and `iran_only` (default true).

| Tool | What it does |
|---|---|
| `eq_latest` | List the most recent earthquakes in Iran, newest first |
| `eq_search` | Search earthquakes in Iran by date range, magnitude, bounding box and place text |
| `eq_significant` | List the strongest recent earthquakes in Iran, largest magnitude first |
| `eq_detail` | Get one earthquake in full: location, depth_km, magnitude type and source quality fields |
| `eq_stats` | Count earthquakes in Iran over a window: by magnitude band, by place, plus the strongest event |

All 5 tools are annotated `readOnlyHint: true`.

## How it works

```text
  AI agent  (Claude, Cursor, Copilot, ...)
      │
      │  MCP over stdio
      ▼
  iran-quake-mcp  (runs on your machine)
      │
      │  HTTPS (IRSC: plain HTTP)
      ├──────▶  earthquake.usgs.gov   USGS FDSN event API
      ├──────▶  www.seismicportal.eu  EMSC FDSN event API
      └──────▶  irsc.ut.ac.ir         events_list.xml
```

`iran-quake-mcp` runs locally and calls the public feeds of USGS, EMSC and IRSC. It has no hosted server in between
and no API key. It sends at most 2 requests at a time with a little jitter, keeps answers for 60 seconds,
retries a failed GET up to 4 times (USGS sometimes answers a sporadic 502), caps a response body at 5 MB and only
talks to those three hosts. It only reads.

## Good to know

- **Times:** `time_utc` is UTC, `time_tehran` is UTC+03:30 (no daylight saving since 2022). Search dates are UTC. Depth is `depth_km`, positive.
- **Magnitudes:** the type is in `mag_type` (mb, ml, mw...). Values from different types or sources are not exactly comparable.
- **Sources are separate:** results are not merged or deduplicated and ids differ. `eq_detail` takes only an event id and detects the source from its format: EMSC `20261014_0000009`, IRSC a plain number such as `213549` (only found in its latest ~20 events), otherwise USGS.
- **Inside Iran only by default:** the event must fall inside a coarse Iran outline (about 0.3 degrees on land borders, plus Iranian waters of the Persian Gulf, Gulf of Oman and south Caspian) and its place text must name Iran, Persian Gulf, Gulf of Oman or Caspian Sea. Events just across the border are dropped. `iran_only=false` returns everything in the box 24-40 N, 43.5-64 E.
- **Places:** USGS and EMSC have no province field (USGS gives the nearest town, EMSC a region). `place` accepts a province name (Tehran, Kerman, Hormozgan, Khuzestan, Fars, Sistan and Baluchestan, Kermanshah, Razavi Khorasan, East Azerbaijan, West Azerbaijan, Bushehr, Mazandaran), which selects an approximate box that overlaps its neighbours. Other text is an English, accent-insensitive substring match. IRSC places are `Town, Province`.
- **IRSC:** read from `http://irsc.ut.ac.ir/events_list.xml` (plain HTTP; its https is closed). It lists only the latest ~20 events, with no magnitude type and no history, so `more` is true when your dates reach further back. The data is licensed for non-commercial, humanitarian use and must cite the Iranian Seismological Center (University of Tehran).
- **Reply size:** `limit` is at most 50. `eq_stats` sets `truncated` when the raw fetch came back full at 3000 rows.
- **Delays and revisions:** feeds list small events with a delay and revise values later. USGS cold queries can take about 10 seconds.
- **What it does not do:** no alerts, no push notifications, no early warning, no shaking maps, no damage estimates.
- **Network:** set `IRAN_QUAKE_MCP_PROXY` if the feeds are not reachable directly. System proxy variables are ignored on purpose.

## FAQ

<details>
<summary><b>Is there an MCP server for earthquakes in Iran?</b></summary>

Yes. `iran-quake-mcp` is an unofficial MCP server with 5 read-only tools. It reads the public USGS, EMSC and IRSC
feeds and returns compact JSON for AI agents.
</details>

<details>
<summary><b>Which data sources does it use?</b></summary>

USGS ComCat (default), EMSC through SeismicPortal, and the Iranian Seismological Center (IRSC, University of Tehran).
Pick one with the `source` argument. They are not merged.
</details>

<details>
<summary><b>How do I use it with Claude, Cursor or Copilot?</b></summary>

Add the server with `claude mcp add iran-quake -- uvx iran-quake-mcp`, or use the matching config in
[Quick start](#quick-start), then ask in plain language, in Persian or English.
</details>

<details>
<summary><b>Is it an earthquake warning service?</b></summary>

No. It reads public catalogs that list events after the fact, sometimes with a delay, and values get revised. For
official information use the Iranian Seismological Center (irsc.ut.ac.ir).
</details>

<details>
<summary><b>What times does it use?</b></summary>

Each event has `time_utc` and `time_tehran` (UTC+03:30, no daylight saving). Search dates you pass are UTC.
</details>

<details>
<summary><b>Can I search by province or city?</b></summary>

Partly. The USGS and EMSC feeds have no province field. Pass a province name from the list in
[Good to know](#good-to-know) in `place` for an approximate box that overlaps neighbouring provinces, other English
text to match the nearest town or region, or a `bbox`. IRSC rows carry `Town, Province` text.
</details>

<details>
<summary><b>Why does the IRSC source show so few events?</b></summary>

The IRSC feed lists only its latest ~20 events and has no history. Use `usgs` or `emsc` for longer ranges.
</details>

<details>
<summary><b>Why are some nearby quakes missing?</b></summary>

By default only events inside a coarse Iran outline are returned, so events across the border are dropped. Pass
`iran_only=false` to include neighbours.
</details>

<details>
<summary><b>How do I debug what the agent sees?</b></summary>

```bash
npx @modelcontextprotocol/inspector uvx iran-quake-mcp
```
</details>

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `IRAN_QUAKE_MCP_PROXY` | unset | Optional HTTP proxy URL for reaching USGS/EMSC; system proxy settings are ignored. A comma-separated list is used one at a time: the next proxy takes over when one is blocked or cannot connect |

<a id="فارسی"></a>

## فارسی: سرور MCP زلزله ایران

<div dir="rtl">

**iran-quake-mcp** یک سرور MCP غیررسمی و فقط&zwnj;خواندنی برای داده&zwnj;های زلزله ایران است. این سرور به دستیار هوش مصنوعی شما (Claude، Cursor، Copilot و ...) اجازه می&zwnj;دهد
آخرین زلزله&zwnj;ها، زلزله&zwnj;های قوی، تاریخچه و آمار لرزه&zwnj;خیزی ایران را از منابع عمومی USGS، EMSC و مرکز لرزه&zwnj;نگاری کشوری (IRSC) بخواند.

**چه کارهایی می&zwnj;کند**

- **آخرین زلزله&zwnj;ها** با حداقل بزرگا و تعداد ساعت گذشته، از جدیدترین.
- **جستجو** بر اساس بازه تاریخ (UTC)، بزرگا، محدوده جغرافیایی و نام مکان یا استان.
- **قوی&zwnj;ترین زلزله&zwnj;ها** در چند روز اخیر، از بزرگ&zwnj;ترین.
- **جزئیات یک زلزله** با شناسه: عمق، نوع بزرگا، وضعیت بازبینی و منبع.
- **آمار** یک بازه: تعداد به تفکیک بزرگا، پرتکرارترین مکان&zwnj;ها و قوی&zwnj;ترین رویداد.

**نکته&zwnj;ها**

- فقط خواندنی است و هشدار یا پیش&zwnj;آگاهی زلزله نیست؛ برای اطلاعات رسمی به مرکز لرزه&zwnj;نگاری کشوری (irsc.ut.ac.ir) مراجعه کنید.
- زمان هر رویداد هم به UTC و هم به وقت تهران (UTC+03:30) داده می&zwnj;شود؛ عمق به کیلومتر است.
- منابع با هم ادغام نمی&zwnj;شوند و شناسه&zwnj;هایشان فرق دارد. منبع IRSC فقط حدود ۲۰ رویداد آخر را دارد.
- فیلد استان در USGS و EMSC وجود ندارد؛ نام استان (به انگلیسی، مثل Kerman) محدوده تقریبی آن را انتخاب می&zwnj;کند.
- کلید API لازم نیست و روی سیستم خود شما اجرا می&zwnj;شود. در صورت نیاز متغیر `IRAN_QUAKE_MCP_PROXY` را روی یک پراکسی HTTP بگذارید.

**نصب** (اول [uv](https://docs.astral.sh/uv/getting-started/installation/) را نصب کنید). در Claude Code:

</div>

```bash
claude mcp add iran-quake -- uvx iran-quake-mcp
```

<div dir="rtl">

در Claude Desktop، Cursor و بقیه برنامه&zwnj;ها همان تنظیم بخش [Quick start](#quick-start) را بگذارید.

**نمونه پرسش&zwnj;ها**

- «آخرین زلزله&zwnj;های ایران در ۲۴ ساعت گذشته کدام&zwnj;اند؟»
- «قوی&zwnj;ترین زلزله&zwnj;های ماه اخیر در ایران را نشان بده.»
- «آیا این هفته در کرمان زلزله بالای ۴ ریشتر آمده؟»
- «آمار زلزله&zwnj;های ایران در ۳۰ روز گذشته را بده.»

</div>

## Development

```bash
git clone https://github.com/sepehr071/iran-quake-mcp && cd iran-quake-mcp
uv sync
uv run ruff check . && uv run ruff format --check .
uv run python -m pytest -q          # offline unit tests
uv run python -m pytest -m live -q  # calls the real USGS/EMSC feeds
uv build
```

All tools live in `src/iran_quake_mcp/quakes.py`; each is a typed async function with a docstring that tells the agent
when to use it. Issues and PRs are welcome.

Releases: bump the version in `pyproject.toml` and `server.json`, then push a `v*` tag. GitHub Actions publishes to PyPI.

## Related servers

- [awesome-iran-mcp](https://github.com/sepehr071/awesome-iran-mcp): catalog of all Iranian-service MCP servers
- [iran-news-mcp](https://github.com/sepehr071/iran-news-mcp) for Iranian news
- [iran-apps-mcp](https://github.com/sepehr071/iran-apps-mcp) for Iranian apps
- [iran-tax-mcp](https://github.com/sepehr071/iran-tax-mcp) for Iranian tax and Codal data
- [tgju-mcp](https://github.com/sepehr071/tgju-mcp) for dollar, gold, coin and commodity prices from TGJU

## Disclaimer

Unofficial and not affiliated with or endorsed by USGS, EMSC or the Iranian Seismological Center. It is read-only.
Earthquake data is informational, can be delayed and is revised by the sources; this is not a warning service. Check
each source's terms of use: IRSC data is licensed for non-commercial, humanitarian use and must cite the Iranian
Seismological Center (University of Tehran).

## License

[MIT](https://github.com/sepehr071/iran-quake-mcp/blob/main/LICENSE)
