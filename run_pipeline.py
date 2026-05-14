"""
Le Monde archive pipeline orchestrator.
Runs for each day in the range:
  1. [url]  Extract article URLs from archive pages → url/YYYYMMDD.txt
  2. [html] Fetch HTML for each URL              → html/YYYY/MM/DD/<title>.html
  3. [txt]  Convert HTML to plain text            → txt/YYYY/MM/DD/<title>.txt

HTTP fetching uses urllib by default, with automatic Playwright fallback when
a client-challenge page is detected. Progress bars are displayed on the console.
"""
import argparse
import datetime as dt
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError

try:
    from tqdm import tqdm
except ModuleNotFoundError as exc:
    raise RuntimeError("tqdm is required. Install it with: pip install tqdm") from exc

from extract_archive_urls import (
    build_archive_url, date_range,
    extract_article_links, extract_max_page_hint,
)
from fetch_articles_html import read_daily_urls, output_path_for_url
from fetch_test import fetch_url, is_client_challenge_html, fetch_url_with_playwright
from html_to_txt import html_file_to_txt

LOG_FILE = Path(__file__).with_name("pipeline.log")

# Playwright is not thread-safe. Serialize all fallback calls across workers.
_playwright_lock = threading.Lock()


def setup_logging(verbose=False):
    fmt = "%(asctime)s  %(levelname)-7s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=[handler])


def log_info(msg, *args):
    logging.getLogger(__name__).info(msg, *args)


def log_error(msg, *args):
    logging.getLogger(__name__).error(msg, *args)


# ── helpers ──────────────────────────────────────────────────────────────────

def parse_input_date(value):
    for fmt in ("%d-%m-%Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        "Date must be one of: DD-MM-YYYY, YYYYMMDD, YYYY-MM-DD"
    )


def _bar(total, desc, position=1, unit=""):
    return tqdm(
        total=total,
        desc=desc,
        position=position,
        leave=False,
        unit=unit,
        dynamic_ncols=True,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} {unit} [{elapsed}]",
    )


def _fetch(url, args):
    """urllib first; Playwright fallback on challenge page (lock-serialized)."""
    html = fetch_url(url, cookie_file=args.cookie_file)
    if is_client_challenge_html(html):
        with _playwright_lock:
            html = fetch_url_with_playwright(
                url,
                headless=not args.interactive_browser,
                interactive_challenge=args.interactive_browser,
            )
    return html


# ── pipeline steps ────────────────────────────────────────────────────────────

def step_urls(target_date, args):
    url_dir = Path(args.url_dir)
    url_dir.mkdir(parents=True, exist_ok=True)
    url_file = url_dir / f"{target_date.strftime('%Y%m%d')}.txt"

    if url_file.exists() and url_file.stat().st_size > 0 and not args.force_urls:
        log_info("[url] %s already present, skipping", target_date)
        return url_file

    with _bar(total=None, desc=f"[url] {target_date} scraping pages", unit="page") as bar:
        original_urls = []
        page_index = 1
        max_page = 1

        while page_index <= max_page:
            page_url = build_archive_url(target_date, page_index)
            try:
                html = _fetch(page_url, args)
            except (HTTPError, URLError, RuntimeError) as exc:
                if page_index == 1:
                    raise
                log_error("[url] %s page %d failed: %s", target_date, page_index, exc)
                break

            original_urls.extend(extract_article_links(html, page_url, target_date))

            hint = extract_max_page_hint(html, target_date)
            if hint > max_page:
                max_page = hint
                bar.total = max_page
                bar.refresh()

            bar.update(1)
            page_index += 1

    urls = sorted(set(original_urls))
    url_file.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    log_info("[url] %s saved %d URLs → %s", target_date, len(urls), url_file)
    return url_file


def _fetch_article(article_url, html_dir, force, args):
    """Worker: fetch one article HTML. Returns fetched / skip_exists / skip_unmatched."""
    out = output_path_for_url(html_dir, article_url)
    if out is None:
        return "skip_unmatched"
    if out.exists() and not force:
        return "skip_exists"
    out.parent.mkdir(parents=True, exist_ok=True)
    html = _fetch(article_url, args)
    out.write_text(html, encoding="utf-8")
    return "fetched"


def step_html(target_date, url_file, args):
    if not url_file.exists() or url_file.stat().st_size == 0:
        tqdm.write(f"  [html] {target_date}: no URL file, skipping")
        return

    urls = read_daily_urls(url_file)
    fetched = skipped = failed = 0

    with _bar(total=len(urls), desc=f"[html] {target_date}", unit="art") as bar:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(_fetch_article, u, args.html_dir, args.force_html, args): u
                for u in urls
            }
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                    if result == "fetched":
                        fetched += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    log_error("[html] %s failed: %s", futures[fut], exc)
                    failed += 1
                bar.update(1)
                bar.set_postfix(fetched=fetched, skip=skipped, fail=failed)

    log_info("[html] %s fetched=%d skipped=%d failed=%d", target_date, fetched, skipped, failed)


def _convert_article(html_file, txt_file, force):
    """Worker: convert one HTML file to TXT."""
    return html_file_to_txt(html_file, txt_file, force=force)


def step_txt(target_date, args):
    html_day = (
        Path(args.html_dir)
        / target_date.strftime("%Y")
        / target_date.strftime("%m")
        / target_date.strftime("%d")
    )
    if not html_day.exists():
        return

    html_files = sorted(html_day.glob("*.html"))
    txt_base = (
        Path(args.txt_dir)
        / target_date.strftime("%Y")
        / target_date.strftime("%m")
        / target_date.strftime("%d")
    )
    txt_base.mkdir(parents=True, exist_ok=True)
    written = skipped = 0

    with _bar(total=len(html_files), desc=f"[txt]  {target_date}", unit="file") as bar:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(_convert_article, hf, txt_base / (hf.stem + ".txt"), args.force_txt): hf
                for hf in html_files
            }
            for fut in as_completed(futures):
                try:
                    if fut.result() == "written":
                        written += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    log_error("[txt] %s failed: %s", futures[fut], exc)
                bar.update(1)
                bar.set_postfix(written=written, skip=skipped)

    log_info("[txt] %s written=%d skipped=%d", target_date, written, skipped)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)

    parser = argparse.ArgumentParser(
        description="Full Le Monde pipeline: URLs → HTML → TXT"
    )
    parser.add_argument("start_date", nargs="?", type=parse_input_date,
                        default=str(yesterday),
                        help="Start date (default: yesterday). DD-MM-YYYY / YYYYMMDD / YYYY-MM-DD")
    parser.add_argument("end_date",   nargs="?", type=parse_input_date,
                        default=None,
                        help="Inclusive end date (default: same as start_date)")

    parser.add_argument("--url-dir",  default="url")
    parser.add_argument("--html-dir", default="html")
    parser.add_argument("--txt-dir",  default="txt")

    parser.add_argument("--interactive-browser", action="store_true",
                        help="Show browser window when Playwright fallback is triggered")
    parser.add_argument("--cookie-file", default=None)
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel workers for HTML fetch and TXT conversion (default: 8)")
    parser.add_argument(
        "--mode",
        choices=("all", "urls", "html", "txt"),
        default="all",
        help="Run only one phase: urls, html, txt, or full pipeline (default: all)",
    )

    parser.add_argument("--force-urls", action="store_true", help="Re-extract URLs even if file exists")
    parser.add_argument("--force-html", action="store_true", help="Re-download HTML even if file exists")
    parser.add_argument("--force-txt",  action="store_true", help="Regenerate txt even if file exists")
    parser.add_argument("--force",      action="store_true", help="Force all three steps")

    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.force:
        args.force_urls = args.force_html = args.force_txt = True

    setup_logging(args.verbose)

    end_date = args.end_date or args.start_date
    if end_date < args.start_date:
        parser.error("end_date must be >= start_date")

    days = list(date_range(args.start_date, end_date))

    tqdm.write(
        f"Pipeline: {args.start_date} → {end_date}  ({len(days)} day(s))  "
        f"workers={args.workers}  mode={args.mode}"
    )
    tqdm.write(f"Log: {LOG_FILE}")

    def collect_url_files_for_days():
        tqdm.write("URL phase: extracting URL files")
        collected = {}
        with tqdm(days, desc="urls", position=0, unit="day", dynamic_ncols=True) as day_bar:
            for target_date in day_bar:
                day_bar.set_description(f"urls  [{target_date}]")
                try:
                    collected[target_date] = step_urls(target_date, args)
                except Exception as exc:
                    collected[target_date] = None
                    log_error("URL phase failed on %s: %s", target_date, exc)
                    tqdm.write(f"  ERROR [url] {target_date}: {exc}")
        return collected

    if args.mode == "urls":
        collect_url_files_for_days()
    elif args.mode == "html":
        tqdm.write("HTML mode: using existing URL files (no URL extraction)")
        with tqdm(days, desc="html", position=0, unit="day", dynamic_ncols=True) as day_bar:
            for target_date in day_bar:
                day_bar.set_description(f"html  [{target_date}]")
                url_file = Path(args.url_dir) / f"{target_date.strftime('%Y%m%d')}.txt"
                try:
                    step_html(target_date, url_file, args)
                except Exception as exc:
                    log_error("HTML mode failed on %s: %s", target_date, exc)
                    tqdm.write(f"  ERROR [html] {target_date}: {exc}")
    elif args.mode == "txt":
        tqdm.write("TXT mode: converting existing HTML files (no URL/HTML fetch)")
        with tqdm(days, desc="txt", position=0, unit="day", dynamic_ncols=True) as day_bar:
            for target_date in day_bar:
                day_bar.set_description(f"txt  [{target_date}]")
                try:
                    step_txt(target_date, args)
                except Exception as exc:
                    log_error("TXT mode failed on %s: %s", target_date, exc)
                    tqdm.write(f"  ERROR [txt] {target_date}: {exc}")
    else:
        tqdm.write("Phase 1/2: extracting URL files for all dates")
        url_files = collect_url_files_for_days()

        tqdm.write("Phase 2/2: fetching HTML and converting TXT")
        with tqdm(days, desc="content", position=0, unit="day", dynamic_ncols=True) as day_bar:
            for target_date in day_bar:
                day_bar.set_description(f"content  [{target_date}]")
                url_file = url_files.get(target_date)
                if url_file is None:
                    tqdm.write(f"  [content] {target_date}: skipped (url phase failed)")
                    continue
                try:
                    step_html(target_date, url_file, args)
                    step_txt(target_date, args)
                except Exception as exc:
                    log_error("Content phase failed on %s: %s", target_date, exc)
                    tqdm.write(f"  ERROR [content] {target_date}: {exc}")

    tqdm.write("Pipeline complete.")


if __name__ == "__main__":
    main()
