"""Scrape character voice files from wiki.biligame.com/blhx (Azur Lane).

Used to build training corpus for GPT-SoVITS-V2.

Example:
    uv run --project Open-LLM-VTuber python scripts/scrape_biligame_voice.py \\
        --character 利托里奥 \\
        --output "D:/GPT-SoVITS/training_source/littorio"

Outputs in --output:
    <skin_idx>_<skin_name>_<scene_key>_<text_prefix>.mp3   (one per line)
    list.txt          # SoVITS manifest, each line: filename|zh|full_text
    scrape_log.txt    # download/skip/dup/fail log
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

WIKI_BASE = "https://wiki.biligame.com/blhx"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/121.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA}
SLEEP_BETWEEN = 0.3
TIMEOUT_PAGE = 30
TIMEOUT_AUDIO = 60
TEXT_PREFIX_LEN = 6
INVALID_CHARS = re.compile(r'[\\/:*?"<>|\s.,!?！？，。、~～:：;；()（）\[\]【】]+')


def fetch_page(character: str) -> BeautifulSoup:
    url = f"{WIKI_BASE}/{quote(character)}"
    print(f"GET {url}")
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_PAGE)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def parse_voice_table(table, skin_idx: int, skin_name: str) -> list[dict]:
    out = []
    for tr in table.select("tr[data-key]"):
        scene_key = tr.get("data-key", "").strip()
        th = tr.find("th")
        scene_name = th.get_text(strip=True) if th else ""
        line_p = tr.select_one("p.ship_word_line[data-lang='zh']")
        audio_a = tr.select_one("div.sm-audio-src a")
        if not line_p or not audio_a or not audio_a.get("href"):
            continue
        text = line_p.get_text(strip=True)
        if not text:
            continue
        out.append(
            {
                "skin_idx": skin_idx,
                "skin_name": skin_name,
                "scene_key": scene_key,
                "scene_name": scene_name,
                "text": text,
                "url": audio_a["href"],
            }
        )
    return out


def discover_skin_tables(soup: BeautifulSoup) -> list[tuple[str, object]]:
    """Map each voice table to its real skin name.

    Logic:
      - Table with `data-title` attribute -> skin name = data-title
        (used for changed-outfit / rebuild skins).
      - Table without `data-title` BUT containing >=1 `tr[data-key]`
        with a `p.ship_word_line` -> default skin "通常".
      - Tables without any `tr[data-key]` (e.g. Valentine's-day specials,
        wedding gift trivia, etc.) are skipped entirely.

    Order: default skin first, then data-title skins in DOM order.
    """
    default_table = None
    titled = []  # list of (data_title, table)
    for tbl in soup.select("table.table-ShipWordsTable"):
        if not tbl.select_one("tr[data-key] p.ship_word_line[data-lang='zh']"):
            continue  # skip non-voice scratch tables (e.g. 情人节礼物)
        title = tbl.get("data-title", "").strip()
        if title:
            titled.append((title, tbl))
        elif default_table is None:
            default_table = tbl
        else:
            titled.append(("额外台词", tbl))

    pairs: list[tuple[str, object]] = []
    if default_table is not None:
        pairs.append(("通常", default_table))
    pairs.extend(titled)
    return pairs


def safe_filename(skin_idx: int, skin: str, scene: str, text: str) -> str:
    skin_clean = INVALID_CHARS.sub("_", skin).strip("_")
    scene_clean = INVALID_CHARS.sub("_", scene).strip("_")
    prefix = INVALID_CHARS.sub("_", text)[:TEXT_PREFIX_LEN].strip("_")
    if not prefix:
        prefix = "audio"
    return f"{skin_idx:02d}_{skin_clean}_{scene_clean}_{prefix}.mp3"


def download(url: str, dst: Path, log) -> bool:
    if dst.exists() and dst.stat().st_size > 0:
        log(f"SKIP existing  {dst.name}")
        return True
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_AUDIO)
    except requests.RequestException as exc:
        log(f"FAIL exception {exc} {url}")
        return False
    if r.status_code != 200:
        log(f"FAIL HTTP {r.status_code} {url}")
        return False
    if len(r.content) < 1024:
        log(f"FAIL too small ({len(r.content)} bytes) {url}")
        return False
    dst.write_bytes(r.content)
    return True


def deduplicate_filename(out: Path, fname: str) -> str:
    """If fname collides with a different URL's file, append _2/_3/... suffix."""
    if not (out / fname).exists():
        return fname
    stem = Path(fname).stem
    suffix = Path(fname).suffix
    n = 2
    while (out / f"{stem}_{n}{suffix}").exists():
        n += 1
    return f"{stem}_{n}{suffix}"


def scrape(character: str, out_dir: str) -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    soup = fetch_page(character)
    pairs = discover_skin_tables(soup)
    print(f"Found {len(pairs)} voice tables (after filtering non-voice scratch tables)")

    if not pairs:
        print("ERROR: no voice tables found. wiki HTML may have changed.", file=sys.stderr)
        return 0

    all_records: list[dict] = []
    for idx, (skin, tbl) in enumerate(pairs):
        recs = parse_voice_table(tbl, idx, skin)
        print(f"  [{idx:02d}] {skin}: {len(recs)} records")
        all_records += recs

    log_lines: list[str] = []
    list_lines: list[str] = []
    seen_urls: set[str] = set()
    download_count = 0

    for rec in tqdm(all_records, desc=character, ncols=80):
        if rec["url"] in seen_urls:
            log_lines.append(f"DUP            {rec['url']}")
            continue
        seen_urls.add(rec["url"])

        fname = safe_filename(
            rec["skin_idx"], rec["skin_name"], rec["scene_key"], rec["text"]
        )
        fname = deduplicate_filename(out, fname)
        ok = download(rec["url"], out / fname, log_lines.append)
        if ok:
            list_lines.append(f"{fname}|zh|{rec['text']}")
            download_count += 1
        time.sleep(SLEEP_BETWEEN)

    (out / "list.txt").write_text(
        "\n".join(list_lines) + "\n", encoding="utf-8"
    )
    (out / "scrape_log.txt").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )

    print(
        f"\nDONE: {download_count} files written to {out}\n"
        f"  list.txt        ({len(list_lines)} lines)\n"
        f"  scrape_log.txt  ({len(log_lines)} lines)"
    )
    return download_count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--character", required=True, help="角色名(中文,如 利托里奥)")
    ap.add_argument("--output", required=True, help="输出目录绝对路径")
    args = ap.parse_args()
    n = scrape(args.character, args.output)
    return 0 if n > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
