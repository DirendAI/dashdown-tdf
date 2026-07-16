#!/usr/bin/env python3
"""
Fetch REAL Tour de France data from Wikipedia.

Wikipedia's Tour de France articles are updated within hours of each stage
finishing and carry machine-parseable wikitext templates ({{Cyclingresult}},
stage characteristics tables, classification tables, the startlist). This
script parses them into the Parquet files the dashboard queries.

Why Wikipedia? The sources this project originally targeted are not usable
from CI: cqranking.com has no public JSON API and procyclingstats.com blocks
scrapers (HTTP 403). Wikipedia is reliable, fast, CC-licensed, and cites the
official Tissot/letour.fr timing for every table it carries.

Outputs
-------
data/
  race_overview.parquet        one-row summary of the current race state
  data_freshness.parquet       per-source refresh audit
  live/
    stages.parquet             2026 route (21 stages) + winners so far
    stage_results.parquet      top-10 of every completed 2026 stage
    gc_standings.parquet       GC top-10 after the latest completed stage
    gc_evolution.parquet       GC top-10 after EVERY completed stage
    classifications.parquet    points/mountains/youth/team standings
    riders.parquet             full startlist (number, team, age, nationality)
    teams.parquet              the 23 participating teams
  historical/
    results.parquet            2020-2025: top-10 of every stage + GC evolution
    stages.parquet             2020-2025 stage characteristics
    final_classifications.parquet  final GC/points/KOM/youth top-10 per year
  metadata.json

Usage
-----
    python scripts/fetch_tdf_data.py --all --output data
    python scripts/fetch_tdf_data.py --year 2026 --output data
    python scripts/fetch_tdf_data.py --historical --output data
    python scripts/fetch_tdf_data.py --all --cache-dir .wikicache   # reuse downloads
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pandas as pd

USER_AGENT = (
    "TDF-Analytics-Bot/2.0 (https://github.com/DirendAI/dashdown-tdf; "
    "dashboard data refresh; contact via GitHub issues)"
)
WIKI_RAW = "https://en.wikipedia.org/w/index.php"
WIKI_API = "https://en.wikipedia.org/w/api.php"
REQUEST_DELAY = 0.3  # be polite

CURRENT_YEAR = 2026
HISTORICAL_YEARS = list(range(2020, 2026))

# Month name -> number, for stage dates like "4 July"
MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"])}

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "a": 1, "an": 1,
}


# ----------------------------------------------------------------------------
# Fetching
# ----------------------------------------------------------------------------

class WikiClient:
    def __init__(self, cache_dir: Path | None = None):
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True
        )
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, title: str) -> Path | None:
        if not self.cache_dir:
            return None
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", title)
        return self.cache_dir / f"{safe}.wiki"

    def wikitext(self, title: str, retries: int = 4) -> str:
        """Fetch raw wikitext for an article (cached if --cache-dir given)."""
        cp = self._cache_path(title)
        if cp and cp.exists() and cp.stat().st_size > 500:
            return cp.read_text(encoding="utf-8")

        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                r = self.client.get(WIKI_RAW, params={"title": title, "action": "raw"})
                # Wikimedia intermittently serves an HTML error page with 200
                if r.status_code == 200 and not r.text.lstrip().startswith("<!DOCTYPE"):
                    if cp:
                        cp.write_text(r.text, encoding="utf-8")
                    time.sleep(REQUEST_DELAY)
                    return r.text
                last_err = RuntimeError(f"HTTP {r.status_code} / error page for {title}")
            except Exception as e:  # noqa: BLE001
                last_err = e
            time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"Failed to fetch wikitext for {title!r}: {last_err}")

    def expand_team_codes(self, pairs: set[tuple[str, str]]) -> dict[tuple[str, str], str]:
        """Resolve {{UCI team code|CODE|YEAR}} templates to display names."""
        mapping: dict[tuple[str, str], str] = {}
        pairs = sorted(pairs)
        BATCH = 40
        for i in range(0, len(pairs), BATCH):
            chunk = pairs[i:i + BATCH]
            text = "@@".join(
                "{{UCI team code|%s|%s}}" % (code, year) for code, year in chunk
            )
            r = self.client.get(WIKI_API, params={
                "action": "expandtemplates", "format": "json",
                "prop": "wikitext", "text": text,
            })
            r.raise_for_status()
            expanded = r.json()["expandtemplates"]["wikitext"].split("@@")
            if len(expanded) != len(chunk):
                raise RuntimeError("expandtemplates returned unexpected batch size")
            for (code, year), exp in zip(chunk, expanded):
                mapping[(code, year)] = strip_wiki_markup(exp)
            time.sleep(REQUEST_DELAY)
        return mapping


# ----------------------------------------------------------------------------
# Wikitext helpers
# ----------------------------------------------------------------------------

def strip_wiki_markup(text: str) -> str:
    """[[A|B]] -> B, [[A]] -> A, drop templates/refs/bold, collapse spaces."""
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]*)\]\]", r"\1", text)
    # drop any remaining templates ({{...}} possibly nested one level)
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = text.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", text).strip()


def split_template_args(body: str) -> list[str]:
    """Split template body on top-level '|' (ignores '|' inside {{ }} / [[ ]])."""
    args, depth_c, depth_s, cur = [], 0, 0, []
    i = 0
    while i < len(body):
        ch = body[i]
        pair = body[i:i + 2]
        if pair == "{{":
            depth_c += 1; cur.append(pair); i += 2; continue
        if pair == "}}":
            depth_c -= 1; cur.append(pair); i += 2; continue
        if pair == "[[":
            depth_s += 1; cur.append(pair); i += 2; continue
        if pair == "]]":
            depth_s -= 1; cur.append(pair); i += 2; continue
        if ch == "|" and depth_c == 0 and depth_s == 0:
            args.append("".join(cur)); cur = []
        else:
            cur.append(ch)
        i += 1
    args.append("".join(cur))
    return args


def parse_time_to_seconds(raw: str) -> float | None:
    """Parse `28h 49' 07"`, `+ 2' 42"`, `21' 47"`, `+ 0"` -> seconds."""
    if raw is None:
        return None
    s = raw.replace("&nbsp;", " ").strip()
    s = s.lstrip("+").strip()
    if s in {"", "—", "-", "s.t."}:
        return 0.0
    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*'", s)
    sec = re.search(r'(\d+)\s*"', s)
    if not (h or m or sec):
        return None
    total = 0.0
    if h:
        total += int(h.group(1)) * 3600
    if m:
        total += int(m.group(1)) * 60
    if sec:
        total += int(sec.group(1))
    return total


TEAM_CODE_RE = re.compile(r"\{\{UCI team code\|([^|}]+)\|([^|}]+?)(?:\|[^}]*)?\}\}")


def extract_team(cell: str) -> tuple[str | None, str | None]:
    """Return (code, year) from a {{UCI team code|CODE|YEAR}} occurrence."""
    m = TEAM_CODE_RE.search(cell)
    if not m:
        return None, None
    return m.group(1).strip(), m.group(2).strip()


def extract_rider(cell: str) -> str | None:
    """Rider name from `[[Name]]` / `[[Article|Name]]` / {{Flag athlete|...}}."""
    m = re.search(r"\[\[(?:[^\[\]|]*\|)?([^\[\]|]+)\]\]", cell)
    return m.group(1).strip() if m else None


def extract_nationality(cell: str) -> str | None:
    m = re.search(r"\{\{[Ff]lag ?athlete\|[^|]*\|([A-Z]{3})[^}]*\}\}", cell)
    if m:
        return m.group(1)
    m = re.search(r"\{\{flagicon\|([A-Z]{3})\}\}", cell)
    return m.group(1) if m else None


def extract_jerseys(cell: str) -> str:
    jerseys = re.findall(r"\{\{cjersey\|([a-z ]+)", cell)
    if re.search(r"Jersey beige number", cell):
        jerseys.append("combativity")
    return ",".join(j.strip() for j in jerseys)


# ----------------------------------------------------------------------------
# Parsers
# ----------------------------------------------------------------------------

STAGE_TYPE_CANON = {
    "team time trial": "Team time trial",
    "individual time trial": "Individual time trial",
    "flat stage": "Flat",
    "plain stage": "Flat",
    "hilly stage": "Hilly",
    "mountain stage": "Mountain",
    "mountain time trial": "Individual time trial",
    "medium mountain stage": "Hilly",
    "medium-mountain stage": "Hilly",
    "flat cobblestone stage": "Flat",
    "gravel stage": "Hilly",
    "hilly stage with gravel sectors": "Hilly",
}


def parse_stage_table(wikitext: str, year: int) -> pd.DataFrame:
    """Parse the `Stage characteristics` wikitable of a year article."""
    m = re.search(r"\|\+ ?Stage characteristics.*?\n(.*?)\n\|\}", wikitext, flags=re.S)
    if not m:
        raise RuntimeError(f"No stage characteristics table found ({year})")
    table = m.group(1)
    rows = re.split(r"\n\|-\s*", table)
    out = []
    for row in rows:
        if "Rest day" in row or "sortbottom" in row or "Total" in row:
            continue
        header = re.search(r"!\s*scope=\"row\"\s*\|(.*)", row)
        if not header:
            continue
        stage_no_m = re.search(r"(\d+)\s*\]\]|^\s*(\d+)\s*$", header.group(1).strip())
        if not stage_no_m:
            continue
        stage_no = int(stage_no_m.group(1) or stage_no_m.group(2))
        cells = [c.strip() for c in re.split(r"\n\|(?!\|)", row)[1:]]
        if len(cells) < 5:
            continue
        date_txt = strip_wiki_markup(re.sub(r"style=[^|]*\|", "", cells[0]))
        dm = re.search(r"(\d+)\s+([A-Z][a-z]+)", date_txt)
        date_iso = None
        if dm and dm.group(2) in MONTHS:
            date_iso = f"{year}-{MONTHS[dm.group(2)]:02d}-{int(dm.group(1)):02d}"
        course = strip_wiki_markup(cells[1])
        course = re.sub(r"\s*\((?:Spain|France|Italy|Belgium|Denmark|Netherlands|Germany|Switzerland|Monaco)\)", "", course)
        parts = re.split(r"\s+to\s+", course, maxsplit=1)
        start = parts[0].strip()
        end = parts[1].strip() if len(parts) > 1 else start
        dist_m = re.search(r"\{\{convert\|([\d.]+)\|km", cells[2])
        distance_km = float(dist_m.group(1)) if dist_m else None
        type_cell = next(
            (c for c in cells[3:]
             if strip_wiki_markup(c).lower().strip() in STAGE_TYPE_CANON), None)
        stage_type = STAGE_TYPE_CANON[strip_wiki_markup(type_cell).lower().strip()] if type_cell else None
        winner_cell = cells[-1] if len(cells) >= 5 else ""
        winner = extract_rider(re.sub(TEAM_CODE_RE, "", winner_cell))
        wcode, wyear = extract_team(winner_cell)
        out.append({
            "year": year, "stage": stage_no, "date": date_iso,
            "start_location": start, "end_location": end,
            "distance_km": distance_km, "stage_type": stage_type,
            "winner": winner, "winner_team_code": wcode,
            "winner_team_year": wyear,
        })
    df = pd.DataFrame(out).sort_values("stage").reset_index(drop=True)
    if len(df) != 21:
        raise RuntimeError(f"Expected 21 stages for {year}, parsed {len(df)}")
    missing_type = df[df["stage_type"].isna()]
    if not missing_type.empty:
        raise RuntimeError(
            f"Unrecognised stage type(s) for {year} stages "
            f"{missing_type['stage'].tolist()} — extend STAGE_TYPE_CANON")
    return df


def extract_template(text: str, start_idx: int) -> tuple[str, int]:
    """text[start_idx:] starts with '{{'; return (template_text, end_index)."""
    depth, i = 0, start_idx
    n = len(text)
    while i < n:
        two = text[i:i + 2]
        if two == "{{":
            depth += 1
            i += 2
        elif two == "}}":
            depth -= 1
            i += 2
            if depth == 0:
                return text[start_idx:i], i
        else:
            i += 1
    raise ValueError("unbalanced template braces")


CYCLING_START_RE = re.compile(r"\{\{[Cc]yclingresult ?start(?=\s*[|}])")
CYCLING_ROW_RE = re.compile(r"\{\{[Cc]yclingresult\|")


def parse_cyclingresult_blocks(wikitext: str) -> list[dict]:
    """Parse all {{Cyclingresult ...}} blocks -> [{title, rows:[...]}, ...].

    Uses brace matching (templates may span lines and nest {{cite ...}}).
    Each block runs from its `start` template to the next one (or EOF).
    """
    starts = [m.start() for m in CYCLING_START_RE.finditer(wikitext)]
    blocks: list[dict] = []
    for i, s in enumerate(starts):
        tmpl, body_from = extract_template(wikitext, s)
        args = split_template_args(tmpl[2:-2])
        title = ""
        for a in args[1:]:
            a = a.strip()
            if a.startswith("title="):
                title = strip_wiki_markup(
                    re.sub(r"<ref.*", "", a[len("title="):], flags=re.S))
        region_end = starts[i + 1] if i + 1 < len(starts) else len(wikitext)
        region = wikitext[body_from:region_end]
        rows = []
        pos_in_region = 0
        while True:
            m = CYCLING_ROW_RE.search(region, pos_in_region)
            if not m:
                break
            row_tmpl, row_end = extract_template(region, m.start())
            pos_in_region = row_end
            args = split_template_args(row_tmpl[2:-2])[1:]
            # {{Cyclingresult|pos|rider|nat|team|time|jerseys...}}
            pos = args[0].strip() if args else ""
            if not pos.isdigit():
                continue
            rider = extract_rider(args[1]) if len(args) > 1 else None
            nat = (args[2].strip()
                   if len(args) > 2 and re.fullmatch(r"[A-Z]{3}", args[2].strip())
                   else None)
            team_cell = args[3] if len(args) > 3 else ""
            code, tyear = extract_team(team_cell)
            if nat is None and len(args) > 3:
                nat = extract_nationality(team_cell)
            time_raw = args[4].strip() if len(args) > 4 else None
            jerseys = extract_jerseys("|".join(args[5:])) if len(args) > 5 else ""
            rows.append({
                "position": int(pos),
                "rider": rider,
                "nationality": nat,
                "team_code": code, "team_year": tyear,
                "time_raw": time_raw,
                "jerseys": jerseys,
            })
        if rows:
            blocks.append({"title": title, "rows": rows})
    return blocks


def blocks_to_frames(blocks: list[dict], year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split blocks into stage results and GC-after-stage frames."""
    stage_rows, gc_rows = [], []
    for b in blocks:
        title = b["title"]
        m_res = re.search(r"^Stage (\d+)[ab]? result", title, flags=re.I)
        m_gc = re.search(r"General classification after stage (\d+)", title, flags=re.I)
        for r in b["rows"]:
            rec = dict(r, year=year)
            if m_res:
                rec["stage"] = int(m_res.group(1))
                stage_rows.append(rec)
            elif m_gc:
                rec["stage"] = int(m_gc.group(1))
                gc_rows.append(rec)
    to_df = lambda rows: pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["year", "stage", "position", "rider", "nationality",
                 "team_code", "team_year", "time_raw", "jerseys"])
    return to_df(stage_rows), to_df(gc_rows)


CLASSIFICATION_TABLE_RE = re.compile(
    r"\|\+ ?(Final )?([A-Za-z ]+?) classification(?: after Stage (\d+))? \(1[–-]",
    flags=re.I,
)


def parse_classification_tables(wikitext: str, year: int) -> pd.DataFrame:
    """Parse GC/points/mountains/young rider/team classification wikitables."""
    out = []
    for m in CLASSIFICATION_TABLE_RE.finditer(wikitext):
        name = m.group(2).strip().lower()
        after_stage = int(m.group(3)) if m.group(3) else None
        tail = wikitext[m.end():]
        end = tail.find("|}")
        table = tail[: end if end > 0 else len(tail)]
        rows = re.split(r"\n\|-\s*", table)
        for row in rows:
            rk = re.search(r"!\s*scope=\"row\"\s*\|\s*(\d+)", row)
            if not rk:
                continue
            cells = [c.strip() for c in re.split(r"\n\|(?!\|)", row)[1:]]
            if not cells:
                continue
            rider = extract_rider(re.sub(TEAM_CODE_RE, "", cells[0]))
            nat = extract_nationality(cells[0])
            code = tyear = None
            for c in cells:
                code, tyear = extract_team(c)
                if code:
                    break
            value_cell = strip_wiki_markup(re.sub(r".*\|", "", cells[-1]))
            points_m = re.fullmatch(r"\d+", value_cell)
            out.append({
                "year": year,
                "classification": name,
                "after_stage": after_stage,
                "rank": int(rk.group(1)),
                "rider": rider,
                "nationality": nat,
                "team_code": code, "team_year": tyear,
                "value_raw": value_cell,
                "points": int(value_cell) if points_m else None,
                "jerseys": extract_jerseys(cells[0]),
            })
    return pd.DataFrame(out)


def parse_startlist(wikitext: str) -> pd.DataFrame:
    """Parse the `By starting number` table of the startlist article."""
    m = re.search(r"=== ?By starting number ?===\s*(.*?)\n\|\}", wikitext, flags=re.S)
    if not m:
        raise RuntimeError("No startlist table found")
    rows = re.split(r"\n\|-\s*", m.group(1))
    out = []
    for row in rows:
        num_m = re.search(r'\|\s*style="text-align:center;?"\s*\|\s*(\d+)', row)
        name_m = re.search(r'!\s*scope="row"[^|]*\|\s*(.*)', row)
        if not (num_m and name_m):
            continue
        name_cell = name_m.group(1)
        rider = extract_rider(name_cell)
        young = "‡" in name_cell
        country_m = re.search(r"\{\{[Ff]lagu\|([^}|]+)", row)
        code, tyear = extract_team(row)
        age_m = re.search(r"\{\{age\|(\d+)\|(\d+)\|(\d+)\|", row)
        birth_date = age = None
        if age_m:
            y_, mo, d = (int(g) for g in age_m.groups())
            birth_date = f"{y_:04d}-{mo:02d}-{d:02d}"
            race_start = datetime(CURRENT_YEAR, 7, 4)
            age = (race_start - datetime(y_, mo, d)).days // 365
        status = "active"
        sm = re.search(r"\b(DNS|DNF|DSQ|OTL)[-–]?\s*(\d+)?", row)
        if sm:
            status = sm.group(1) + (f"-{sm.group(2)}" if sm.group(2) else "")
        out.append({
            "number": int(num_m.group(1)),
            "rider": rider,
            "country": country_m.group(1) if country_m else None,
            "team_code": code, "team_year": tyear,
            "birth_date": birth_date, "age": age,
            "young_rider_eligible": young,
            "status": status,
        })
    df = pd.DataFrame(out).drop_duplicates(subset="number").sort_values("number")
    if not (150 <= len(df) <= 200):
        raise RuntimeError(f"Startlist parse suspicious: {len(df)} riders")
    return df.reset_index(drop=True)


CLIMB_WORD_RE = re.compile(
    r"(?:(\w+)\s+)?(hors[ -]catégorie|first-category|second-category|"
    r"third-category|fourth-category)",
    flags=re.I,
)
CLIMB_COLS = {
    "hors catégorie": "climbs_hc", "hors-catégorie": "climbs_hc",
    "first-category": "climbs_cat1", "second-category": "climbs_cat2",
    "third-category": "climbs_cat3", "fourth-category": "climbs_cat4",
}


def parse_stage_previews(subarticle_text: str) -> dict[int, dict]:
    """Per `== Stage N ==` section: climb counts + the distance stated in the
    stage header line (used to cross-check route-table typos)."""
    sections = re.split(r"\n== ?Stage (\d+) ?==\n", subarticle_text)
    out: dict[int, dict] = {}
    for i in range(1, len(sections), 2):
        stage_no = int(sections[i])
        body = sections[i + 1]
        intro = body.split("{{Cyclingresult", 1)[0]
        rec: dict = {c: 0 for c in set(CLIMB_COLS.values())}
        for word, cat in CLIMB_WORD_RE.findall(intro):
            col = CLIMB_COLS[cat.lower()]
            rec[col] += WORD_NUMBERS.get(word.lower(), 1) if word else 1
        # header line: `;4 July 2026 – A to B, {{convert|180.4|km|abbr=on}}`
        hm = re.search(r"^;.*?\{\{convert\|([\d.]+)\|km", intro, flags=re.M)
        rec["distance_km_preview"] = float(hm.group(1)) if hm else None
        # every km figure mentioned in the intro (for total reconciliation)
        rec["distance_candidates"] = [
            float(x) for x in re.findall(r"\{\{convert\|([\d.]+)\|km", intro)
        ]
        out[stage_no] = rec
    return out


def reconcile_total_distance(stages: pd.DataFrame, previews: dict[int, dict],
                             infobox_total: float | None, year: int) -> pd.DataFrame:
    """If the stage distances don't add up to the official race total, look
    for a single stage whose article text contains a distance that closes the
    gap exactly (catches route-table typos like 2026 stage 9: 155.5 vs the
    real 185.5 km confirmed by letour.fr)."""
    if not infobox_total:
        return stages
    gap = infobox_total - stages["distance_km"].sum()
    if abs(gap) <= 1.0:
        return stages
    for stage_no, rec in previews.items():
        mask = stages["stage"] == stage_no
        if not mask.any():
            continue
        current = stages.loc[mask, "distance_km"].iloc[0]
        for cand in rec.get("distance_candidates", []):
            if cand > 20 and abs((cand - current) - gap) < 1.0:
                print(f"  note: {year} stage {stage_no} distance corrected "
                      f"{current} -> {cand} km (reconciles official total "
                      f"{infobox_total} km)")
                stages.loc[mask, "distance_km"] = cand
                return stages
    print(f"  warning: {year} stage distances sum to "
          f"{stages['distance_km'].sum():.1f} km, official total {infobox_total}")
    return stages


def cross_check_distances(stages: pd.DataFrame, previews: dict[int, dict],
                          year: int) -> pd.DataFrame:
    """Wikipedia's route table occasionally has a typo'd distance; the stage
    subarticle header is written per stage and has proven more reliable
    (e.g. 2026 stage 9: table said 155.5 km, letour.fr and the stage article
    say 185.5 km). Prefer the stage-article value when the two disagree."""
    for stage_no, rec in previews.items():
        d = rec.get("distance_km_preview")
        if d is None:
            continue
        mask = stages["stage"] == stage_no
        table_d = stages.loc[mask, "distance_km"]
        if not table_d.empty and pd.notna(table_d.iloc[0]) and abs(table_d.iloc[0] - d) > 0.05:
            print(f"  note: {year} stage {stage_no} distance mismatch "
                  f"(route table {table_d.iloc[0]} km vs stage article {d} km) "
                  f"-> using stage article")
            stages.loc[mask, "distance_km"] = d
    return stages


def parse_infobox_distance(wikitext: str) -> float | None:
    m = re.search(r"\|\s*distance\s*=\s*([\d.]+)", wikitext)
    return float(m.group(1)) if m else None


# ----------------------------------------------------------------------------
# Assembly
# ----------------------------------------------------------------------------

def resolve_teams(client: WikiClient, *frames: pd.DataFrame) -> dict[tuple[str, str], str]:
    pairs = set()
    for f in frames:
        if f is None or f.empty:
            continue
        for col_c, col_y in (("team_code", "team_year"),
                             ("winner_team_code", "winner_team_year")):
            if col_c in f.columns:
                sub = f[[col_c, col_y]].dropna()
                pairs.update((str(c), str(y)) for c, y in sub.itertuples(index=False))
    return client.expand_team_codes(pairs)


def apply_team_names(df: pd.DataFrame, names: dict[tuple[str, str], str],
                     code_col="team_code", year_col="team_year",
                     out_col="team") -> pd.DataFrame:
    if df.empty or code_col not in df.columns:
        return df
    df[out_col] = [
        names.get((str(c), str(y))) if pd.notna(c) else None
        for c, y in zip(df[code_col], df[year_col])
    ]
    return df


def add_gap_columns(df: pd.DataFrame, pos_col: str = "position") -> pd.DataFrame:
    """time_raw of the leader is a total; others are gaps. Add seconds cols."""
    if df.empty:
        return df
    df["time_seconds"] = df["time_raw"].map(parse_time_to_seconds)
    def gap(group: pd.DataFrame) -> pd.DataFrame:
        group = group.sort_values(pos_col).copy()
        leader = group["time_seconds"].iloc[0]
        gaps = [0.0] + [t if t is not None else None
                        for t in group["time_seconds"].iloc[1:]]
        group["gap_seconds"] = gaps
        group["total_seconds"] = [
            (leader + g) if (leader is not None and g is not None) else None
            for g in gaps
        ]
        return group
    keys = [k for k in ("year", "stage", "classification") if k in df.columns]
    return df.groupby(keys, group_keys=False)[df.columns].apply(gap).reset_index(drop=True)


def fmt_gap(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return ""
    seconds = int(seconds)
    if seconds == 0:
        return "—"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"+ {h}h {m:02d}' {s:02d}\"" if h else f"+ {m}' {s:02d}\""


def fmt_total(seconds: float | None) -> str:
    if seconds is None or pd.isna(seconds):
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}' {s:02d}\""


def build_2026(client: WikiClient, out: Path) -> dict:
    print("Fetching 2026 Tour de France data from Wikipedia...")
    main_wt = client.wikitext("2026 Tour de France")
    sub1_wt = client.wikitext("2026 Tour de France, Stage 1 to Stage 11")
    sub2_wt = client.wikitext("2026 Tour de France, Stage 12 to Stage 21")
    startlist_wt = client.wikitext("List of teams and cyclists in the 2026 Tour de France")

    stages = parse_stage_table(main_wt, CURRENT_YEAR)
    blocks = parse_cyclingresult_blocks(sub1_wt) + parse_cyclingresult_blocks(sub2_wt)
    results, gc_evo = blocks_to_frames(blocks, CURRENT_YEAR)
    classifications = parse_classification_tables(main_wt, CURRENT_YEAR)
    riders = parse_startlist(startlist_wt)

    previews = parse_stage_previews(sub1_wt)
    previews.update(parse_stage_previews(sub2_wt))
    stages = cross_check_distances(stages, previews, CURRENT_YEAR)
    stages = reconcile_total_distance(
        stages, previews, parse_infobox_distance(main_wt), CURRENT_YEAR)
    for col in sorted(set(CLIMB_COLS.values())):
        stages[col] = stages["stage"].map(lambda s: previews.get(s, {}).get(col, 0))

    names = resolve_teams(client, stages, results, gc_evo, classifications, riders)

    stages = apply_team_names(stages, names, "winner_team_code",
                              "winner_team_year", "winner_team")
    # a TTT winner is a team, not a rider
    ttt = stages["stage_type"] == "Team time trial"
    stages.loc[ttt & stages["winner"].isna(), "winner"] = stages.loc[ttt, "winner_team"]
    # rider winners carry no team template in the route table — fill from startlist
    riders = apply_team_names(riders, names)
    rider_team = riders.set_index("rider")["team"]
    fill = stages["winner_team"].isna() & stages["winner"].notna()
    stages.loc[fill, "winner_team"] = stages.loc[fill, "winner"].map(rider_team)
    results = apply_team_names(results, names)
    gc_evo = apply_team_names(gc_evo, names)
    classifications = apply_team_names(classifications, names)

    stages["completed"] = stages["winner"].notna()
    stages["is_tt"] = stages["stage_type"].str.contains("time trial", case=False)
    stages["is_mountain"] = stages["stage_type"] == "Mountain"
    last_completed = int(stages.loc[stages["completed"], "stage"].max())

    results = add_gap_columns(results)
    gc_evo = add_gap_columns(gc_evo)

    # enrich stage results with stage metadata
    results = results.merge(
        stages[["stage", "date", "start_location", "end_location",
                "distance_km", "stage_type"]],
        on="stage", how="left",
    )

    # GC standings after the latest completed stage, enriched from startlist.
    # During the race a stage result is often published on Wikipedia before its
    # GC table, so fall back to the latest stage that actually has GC data.
    gc_stages = gc_evo.loc[gc_evo["stage"] <= last_completed, "stage"]
    gc_stage = int(gc_stages.max()) if not gc_stages.empty else last_completed
    gc_now = gc_evo[gc_evo["stage"] == gc_stage].copy()
    rider_info = riders[["rider", "age", "country", "young_rider_eligible"]]
    gc_now = gc_now.merge(rider_info, on="rider", how="left")
    gc_now["time"] = [
        fmt_total(t) if p == 1 else fmt_gap(g)
        for p, t, g in zip(gc_now["position"], gc_now["total_seconds"],
                           gc_now["gap_seconds"])
    ]
    gc_now["gap"] = gc_now["gap_seconds"].map(fmt_gap).replace("—", "0")
    gc_now["gap_minutes"] = (gc_now["gap_seconds"] / 60).round(2)

    # classification standings (after latest stage) with formatted values
    classifications = add_gap_columns(
        classifications.rename(columns={"value_raw": "time_raw"}), pos_col="rank"
    ).rename(columns={"time_raw": "value_raw"})
    classifications["value"] = [
        (str(int(p)) if pd.notna(p) else
         (fmt_total(t) if r == 1 else fmt_gap(g)))
        for p, r, t, g in zip(classifications["points"], classifications["rank"],
                              classifications["total_seconds"],
                              classifications["gap_seconds"])
    ]

    live = out / "live"
    live.mkdir(parents=True, exist_ok=True)
    stages.drop(columns=["winner_team_code", "winner_team_year"]).to_parquet(live / "stages.parquet", index=False)
    results.drop(columns=["team_code", "team_year"]).to_parquet(live / "stage_results.parquet", index=False)
    gc_now.drop(columns=["team_code", "team_year"]).to_parquet(live / "gc_standings.parquet", index=False)
    gc_evo.drop(columns=["team_code", "team_year"]).to_parquet(live / "gc_evolution.parquet", index=False)
    classifications.drop(columns=["team_code", "team_year"]).to_parquet(live / "classifications.parquet", index=False)
    riders.drop(columns=["team_year"]).to_parquet(live / "riders.parquet", index=False)

    teams = (riders.groupby(["team_code", "team"], as_index=False)
             .agg(riders_started=("rider", "count"),
                  avg_age=("age", "mean")))
    teams["avg_age"] = teams["avg_age"].round(1)
    teams.to_parquet(live / "teams.parquet", index=False)

    for name, df in [("stages", stages), ("stage_results", results),
                     ("gc_standings", gc_now), ("riders", riders)]:
        print(f"  live/{name}: {len(df)} rows")

    jersey = lambda cls: (classifications.query(
        f"classification == '{cls}' and rank == 1")["rider"].iloc[0]
        if not classifications.query(f"classification == '{cls}'").empty else None)
    state = {
        "stages_completed": last_completed,
        "next_stage": last_completed + 1 if last_completed < 21 else None,
        "yellow_jersey": (yj.iloc[0] if not (yj := gc_now.loc[
            gc_now["position"] == 1, "rider"]).empty else None),
        "green_jersey": jersey("points"),
        "polka_dot_jersey": jersey("mountains"),
        "white_jersey": jersey("young rider"),
        "total_distance_km": parse_infobox_distance(main_wt)
                             or round(float(stages["distance_km"].sum()), 1),
        "num_riders": int(len(riders)),
        "num_riders_active": int((riders["status"] == "active").sum()),
        "num_teams": int(riders["team"].nunique()),
        "last_stage_winner": stages.loc[stages["stage"] == last_completed, "winner"].iloc[0],
    }
    return state


def build_historical(client: WikiClient, out: Path) -> None:
    print("Fetching historical Tour de France data (2020-2025)...")
    all_stages, all_results, all_gc, all_finals = [], [], [], []
    for year in HISTORICAL_YEARS:
        main_wt = client.wikitext(f"{year} Tour de France")
        recaps = re.search(
            r"\{\{Cycling stage recaps\|%d Tour de France\|(\d+)\|(\d+)\|(\d+)\|(\d+)\}\}" % year,
            main_wt,
        )
        a, b, c, d = (recaps.group(i) for i in range(1, 5)) if recaps else (1, 11, 12, 21)
        sub1 = client.wikitext(f"{year} Tour de France, Stage {a} to Stage {b}")
        sub2 = client.wikitext(f"{year} Tour de France, Stage {c} to Stage {d}")

        stages = parse_stage_table(main_wt, year)
        previews = parse_stage_previews(sub1)
        previews.update(parse_stage_previews(sub2))
        stages = cross_check_distances(stages, previews, year)
        blocks = parse_cyclingresult_blocks(sub1) + parse_cyclingresult_blocks(sub2)
        results, gc_evo = blocks_to_frames(blocks, year)
        finals = parse_classification_tables(main_wt, year)
        finals = finals[finals["after_stage"].isna()]
        print(f"  {year}: {len(stages)} stages, {len(results)} result rows, "
              f"{len(gc_evo)} GC rows, {len(finals)} final classification rows")
        all_stages.append(stages)
        all_results.append(results)
        all_gc.append(gc_evo)
        all_finals.append(finals)

    stages = pd.concat(all_stages, ignore_index=True)
    results = pd.concat(all_results, ignore_index=True)
    gc_evo = pd.concat(all_gc, ignore_index=True)
    finals = pd.concat(all_finals, ignore_index=True)

    names = resolve_teams(client, stages, results, gc_evo, finals)
    stages = apply_team_names(stages, names, "winner_team_code",
                              "winner_team_year", "winner_team")
    ttt = stages["stage_type"] == "Team time trial"
    stages.loc[ttt & stages["winner"].isna(), "winner"] = stages.loc[ttt, "winner_team"]
    results = apply_team_names(results, names)
    gc_evo = apply_team_names(gc_evo, names)
    finals = apply_team_names(finals, names)

    results = add_gap_columns(results)
    gc_evo = add_gap_columns(gc_evo)
    finals = add_gap_columns(
        finals.rename(columns={"value_raw": "time_raw"}), pos_col="rank"
    ).rename(columns={"time_raw": "value_raw"})
    results = results.merge(
        stages[["year", "stage", "date", "distance_km", "stage_type"]],
        on=["year", "stage"], how="left",
    )
    results["won_stage"] = (results["position"] == 1).astype(int)
    gc_evo["record"] = "gc_after_stage"
    results["record"] = "stage_result"
    combined = pd.concat([results, gc_evo], ignore_index=True)

    hist = out / "historical"
    hist.mkdir(parents=True, exist_ok=True)
    combined.drop(columns=["team_code", "team_year"]).to_parquet(hist / "results.parquet", index=False)
    stages.drop(columns=["winner_team_code", "winner_team_year"]).to_parquet(hist / "stages.parquet", index=False)
    finals.drop(columns=["team_code", "team_year", "after_stage"]).to_parquet(
        hist / "final_classifications.parquet", index=False)
    print(f"  historical/results: {len(combined)} rows, "
          f"stages: {len(stages)}, finals: {len(finals)}")


def build_overview(out: Path, state: dict) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    overview = pd.DataFrame([{
        "year": CURRENT_YEAR,
        "race": "Tour de France",
        "edition": 113,
        "num_stages": 21,
        "total_distance_km": state["total_distance_km"],
        "num_riders": state["num_riders"],
        "num_riders_active": state["num_riders_active"],
        "num_teams": state["num_teams"],
        "stages_completed": state["stages_completed"],
        "next_stage": state["next_stage"],
        "yellow_jersey": state["yellow_jersey"],
        "green_jersey": state["green_jersey"],
        "polka_dot_jersey": state["polka_dot_jersey"],
        "white_jersey": state["white_jersey"],
        "last_stage_winner": state["last_stage_winner"],
        "last_refreshed": now.isoformat(),
    }])
    overview.to_parquet(out / "race_overview.parquet", index=False)

    freshness = pd.DataFrame([
        {"source": "Wikipedia: 2026 Tour de France (live results)",
         "url": "https://en.wikipedia.org/wiki/2026_Tour_de_France",
         "last_fetched": now.isoformat(), "license": "CC BY-SA 4.0"},
        {"source": "Wikipedia: stage articles (per-stage top 10 + GC)",
         "url": "https://en.wikipedia.org/wiki/2026_Tour_de_France,_Stage_1_to_Stage_11",
         "last_fetched": now.isoformat(), "license": "CC BY-SA 4.0"},
        {"source": "Wikipedia: historical Tours 2020-2025",
         "url": "https://en.wikipedia.org/wiki/2025_Tour_de_France",
         "last_fetched": now.isoformat(), "license": "CC BY-SA 4.0"},
        {"source": "Underlying timing data cited by Wikipedia",
         "url": "https://www.letour.fr/en/rankings",
         "last_fetched": now.isoformat(), "license": "ASO / Tissot Timing"},
    ])
    freshness.to_parquet(out / "data_freshness.parquet", index=False)

    metadata = {
        "last_refreshed": now.isoformat(),
        "data_source": "Wikipedia (en) — parsed wikitext, cites letour.fr / Tissot Timing",
        "refresh_interval": "daily during the race",
        "current_stage_completed": state["stages_completed"],
        "next_stage": state["next_stage"],
        "total_stages": 21,
        "yellow_jersey": state["yellow_jersey"],
        "green_jersey": state["green_jersey"],
        "polka_dot_jersey": state["polka_dot_jersey"],
        "white_jersey": state["white_jersey"],
        "note": f"Live data - Tour de France 2026, stage {state['stages_completed']} completed",
    }
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"  race_overview + data_freshness + metadata.json written")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--year", type=int, default=CURRENT_YEAR)
    parser.add_argument("--historical", action="store_true",
                        help="fetch 2020-2025 data")
    parser.add_argument("--all", action="store_true",
                        help="fetch historical + current year")
    parser.add_argument("--output", type=str, default="data")
    parser.add_argument("--cache-dir", type=str, default=None,
                        help="directory to cache raw wikitext downloads")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    client = WikiClient(Path(args.cache_dir) if args.cache_dir else None)

    if args.all or args.historical:
        build_historical(client, out)
    if args.all or not args.historical:
        state = build_2026(client, out)
        build_overview(out, state)
    print("✓ Data fetch complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
