#!/usr/bin/env python3
import json, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

OUT_FILE = Path("lottery_data.json")
USER_AGENT = "Mozilla/5.0"

# 这里填你后面可用的上游 JSON 地址。可以放多个，脚本会按顺序尝试。
SOURCE_URLS = [
    # "https://your-json-source.example.com/latest.json",
]

FALLBACK_SAMPLE = [
    {"issue":"2026-040","date":"2026-04-08","numbers":[3,7,12,18,26,41],"special":49},
    {"issue":"2026-039","date":"2026-04-05","numbers":[1,9,14,22,31,44],"special":16},
    {"issue":"2026-038","date":"2026-04-03","numbers":[6,11,17,24,35,47],"special":29},
    {"issue":"2026-037","date":"2026-03-31","numbers":[2,8,13,20,33,45],"special":39},
    {"issue":"2026-036","date":"2026-03-29","numbers":[5,10,19,21,30,42],"special":48},
]

def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def normalize_item(item):
    issue = str(item.get("issue") or item.get("period") or item.get("draw") or item.get("no") or "").strip()
    date = str(item.get("date") or item.get("draw_date") or item.get("time") or "").strip()[:10]
    numbers = item.get("numbers") or item.get("normal") or item.get("draw_result") or []
    special = item.get("special") or item.get("specialNumber") or item.get("tm") or item.get("extra")

    if isinstance(numbers, str):
        numbers = [x for x in re.findall(r"\d{1,2}", numbers)]

    try:
        numbers = [int(x) for x in numbers][:6]
    except Exception:
        numbers = []

    try:
        special = int(special) if special is not None else None
    except Exception:
        special = None

    if len(numbers) != 6 or special is None:
        return None

    if not issue:
        issue = "unknown"
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return {"issue": issue.replace("/", "-"), "date": date, "numbers": numbers, "special": special}

def parse_json_payload(text: str):
    data = json.loads(text)
    rows = []

    if isinstance(data, list):
        for item in data:
            row = normalize_item(item)
            if row:
                rows.append(row)
    elif isinstance(data, dict):
        candidates = [data]
        for key in ("data", "results", "items", "list"):
            if isinstance(data.get(key), list):
                candidates.extend(data[key])
        for item in candidates:
            if isinstance(item, dict):
                row = normalize_item(item)
                if row:
                    rows.append(row)

    dedup = []
    seen = set()
    for row in rows:
        key = (row["issue"], row["date"])
        if key not in seen:
            seen.add(key)
            dedup.append(row)

    dedup.sort(key=lambda x: (x["date"], x["issue"]), reverse=True)
    return dedup

def load_existing():
    if OUT_FILE.exists():
        try:
            return json.loads(OUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []

def main():
    final_rows = []
    for url in SOURCE_URLS:
        try:
            text = fetch(url)
            rows = parse_json_payload(text)
            if rows:
                final_rows = rows
                print(f"Fetched {len(rows)} rows from {url}")
                break
        except Exception as e:
            print(f"Source failed: {url} -> {e}")

    if not final_rows:
        final_rows = load_existing() or FALLBACK_SAMPLE
        print("No upstream source available. Keeping existing data or fallback sample.")

    OUT_FILE.write_text(json.dumps(final_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(final_rows)} rows to {OUT_FILE}")

if __name__ == "__main__":
    main()
