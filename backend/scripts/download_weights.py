"""Fetch the PANNs CNN14 weights + AudioSet label CSV into ~/panns_data (no wget needed).

Valid existing files are detected and skipped. Downloads go to <file>.part and
RESUME from wherever they stopped (HTTP Range / 206), with retries; partial files
are never deleted. If the server ignores the Range header (200), the bytes we
already have are skipped in the stream instead of being thrown away.

  python scripts/download_weights.py          # verify, download only what is missing
  python scripts/download_weights.py --check  # verify only; exit code 1 if anything is missing/invalid
"""

import argparse
import csv
import sys
import time
import urllib.request
from pathlib import Path

import _bootstrap  # noqa: F401
from echotrace import config

CHUNK = 1 << 20


def check_weights(path: Path) -> tuple[bool, str]:
    if not path.exists():
        part = path.with_name(path.name + ".part")
        extra = f" (partial: {part.stat().st_size:,} bytes)" if part.exists() else ""
        return False, f"missing{extra}"
    size = path.stat().st_size
    if size != config.WEIGHTS_SIZE:
        return False, f"wrong size {size:,} (expected {config.WEIGHTS_SIZE:,})"
    return True, f"ok ({size:,} bytes)"


def check_labels(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        header, body = rows[0], rows[1:]
        if header[:3] != ["index", "mid", "display_name"]:
            return False, f"unexpected header {header}"
        if len(body) != config.LABELS_COUNT:
            return False, f"{len(body)} classes (expected {config.LABELS_COUNT})"
    except Exception as e:
        return False, f"unreadable: {e}"
    return True, f"ok ({path.stat().st_size:,} bytes, {len(body)} classes)"


def download(url: str, dest: Path, expected_size: int | None, retries: int = 50) -> None:
    """Resumable download to dest.part, then rename to dest. Never deletes the partial file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    if dest.exists() and not part.exists():
        # an invalid "final" file is treated as a partial to resume from, not deleted
        dest.rename(part)
    for attempt in range(1, retries + 1):
        have = part.stat().st_size if part.exists() else 0
        if expected_size and have == expected_size:
            break
        if expected_size and have > expected_size:
            raise RuntimeError(f"{part} is larger than expected ({have:,} > {expected_size:,}); inspect it manually")
        req = urllib.request.Request(url, headers={"User-Agent": "echotrace-downloader/1.0"})
        if have:
            req.add_header("Range", f"bytes={have}-")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                status = resp.status
                skip = have if (have and status == 200) else 0  # server ignored Range
                total = expected_size or (have + int(resp.headers.get("Content-Length", 0)))
                print(f"  attempt {attempt}: HTTP {status}, resuming at {have:,} / {total:,} bytes")
                done, t0 = have, time.time()
                with open(part, "ab") as f:
                    while True:
                        buf = resp.read(CHUNK)
                        if not buf:
                            break
                        if skip:
                            cut = min(skip, len(buf))
                            buf, skip = buf[cut:], skip - cut
                            if not buf:
                                continue
                        f.write(buf)
                        done += len(buf)
                        rate = (done - have) / max(time.time() - t0, 1e-6) / 1e6
                        pct = 100 * done / total if total else 0
                        print(f"\r  {done:,} bytes ({pct:5.1f}%)  {rate:5.1f} MB/s   ", end="", flush=True)
                print()
            if not expected_size:
                break
        except Exception as e:
            print(f"\n  attempt {attempt} interrupted: {e}; partial file kept, retrying in {min(2 * attempt, 30)} s")
            time.sleep(min(2 * attempt, 30))
    have = part.stat().st_size if part.exists() else 0
    if expected_size and have != expected_size:
        raise RuntimeError(f"download incomplete: {have:,} / {expected_size:,} bytes kept in {part}; rerun to resume")
    part.replace(dest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="verify only, do not download")
    args = ap.parse_args()

    items = [
        ("weights", config.WEIGHTS_FILE, config.WEIGHTS_URL, config.WEIGHTS_SIZE, check_weights),
        ("labels ", config.LABELS_FILE, config.LABELS_URL, None, check_labels),
    ]
    all_ok = True
    print(f"PANNs data dir: {config.PANNS_DATA_DIR}")
    for name, path, url, size, check in items:
        ok, msg = check(path)
        print(f"  {name} {path.name}: {msg}")
        if ok:
            continue
        if args.check:
            all_ok = False
            continue
        print(f"  downloading {url}")
        download(url, path, size)
        ok, msg = check(path)
        print(f"  {name} {path.name}: {msg}")
        all_ok &= ok
    print("ALL OK" if all_ok else "PROBLEMS FOUND (run without --check to download/resume)")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
