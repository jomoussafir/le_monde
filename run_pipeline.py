"""
Le Monde archive pipeline orchestrator.
Runs for each day in the range:
  1. [url]  Extract article URLs from archive pages → url/YYYY/YYYYMMDD.txt
  2. [html] Fetch each article in headless Chrome, convert to TXT in-memory
            → txt/YYYY/MM/DD/<title>.txt  (HTML is never saved to disk)

URL extraction uses urllib with automatic headless-Playwright fallback on
challenge pages.  Article fetching always uses a headless Chrome/Chromium
session via Playwright.  Progress bars are displayed on the console.
"""
import argparse
import asyncio
import datetime as dt
import logging
from importlib import import_module
from pathlib import Path
from urllib.error import HTTPError, URLError


from extract_archive_urls import (
    build_archive_url, date_range,
    extract_article_links, extract_max_page_hint,
)
from fetch_articles_html import read_daily_urls, output_path_for_url
from html_to_txt import extract_best_html_segment, TextExtractor
from fetch_test import (
    DEFAULT_USER_AGENT,
    fetch_url,
    is_client_challenge_html,
    fetch_url_with_playwright,
)

LOG_FILE = Path(__file__).with_name("pipeline.log")

# Headers a real Chrome browser sends — required by Le Monde's archive backend.
_BROWSER_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;"
        "q=0.8,application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Upgrade-Insecure-Requests": "1",
}

# Resource types to block in the browser (not needed for article text).
BLOCKED_RESOURCE_TYPES = {"image", "stylesheet", "font", "media",
                           "other", "eventsource", "websocket"}


def _print(msg, *args):
    """Timestamped print for pipeline progress."""
    print(dt.datetime.now().strftime("%H:%M:%S"), msg % args if args else msg, flush=True)


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


def _fetch_archive(url, cookie_file):
    """urllib first; headless Playwright fallback on challenge page."""
    html = fetch_url(url, cookie_file=cookie_file)
    if is_client_challenge_html(html):
        html = fetch_url_with_playwright(url, headless=True)
    return html


# ── pipeline steps ────────────────────────────────────────────────────────────

def step_urls(target_date, args):
    url_dir = Path(args.url_dir) / target_date.strftime("%Y")
    url_dir.mkdir(parents=True, exist_ok=True)
    url_file = url_dir / f"{target_date.strftime('%Y%m%d')}.txt"

    if url_file.exists() and url_file.stat().st_size > 0:
        log_info("[url] %s already present, skipping", target_date)
        return url_file

    _print("[url] %s extracting URLs", target_date)
    original_urls = []
    page_index = 1
    max_page = 1

    while page_index <= max_page:
        page_url = build_archive_url(target_date, page_index)
        try:
            html = _fetch_archive(page_url, args.cookie_file)
        except (HTTPError, URLError, RuntimeError) as exc:
            if page_index == 1:
                raise
            log_error("[url] %s page %d failed: %s", target_date, page_index, exc)
            break

        original_urls.extend(extract_article_links(html, page_url, target_date))

        hint = extract_max_page_hint(html, target_date)
        if hint > max_page:
            max_page = hint

        page_index += 1

    urls = sorted(set(original_urls))
    url_file.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
    log_info("[url] %s saved %d URLs → %s", target_date, len(urls), url_file)
    return url_file


def _html_to_txt_string(html):
    """Convert an HTML string to plain text in-memory."""
    segment = extract_best_html_segment(html)
    parser = TextExtractor()
    parser.feed(segment)
    parser.close()
    return parser.get_text()


async def _fetch_articles_async(target_date, pending, user_data_dir, workers, delay):
    """Fetch *pending* articles in parallel using `workers` concurrent browser pages.

    pending: list of (article_url, txt_out_path) already filtered for existence.
    Returns (fetched, failed) counts.
    """
    try:
        async_playwright = import_module("playwright.async_api").async_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is required. Install with: "
            "pip install playwright && playwright install chromium"
        ) from exc

    fetched = failed = 0
    sem = asyncio.Semaphore(workers)

    async def handle_route(route):
        if route.request.resource_type in BLOCKED_RESOURCE_TYPES:
            await route.abort()
        else:
            await route.continue_()

    async def fetch_one(article_url, txt_out):
        nonlocal fetched, failed
        async with sem:
            if delay > 0:
                await asyncio.sleep(delay)
            page = await context.new_page()
            try:
                response = await page.goto(
                    article_url, wait_until="domcontentloaded", timeout=90_000
                )
                if response is not None and not response.ok:
                    raise RuntimeError(f"HTTP {response.status}")

                html = await page.content()
                if is_client_challenge_html(html):
                    raise RuntimeError("Client challenge page returned")

                txt_out.parent.mkdir(parents=True, exist_ok=True)
                txt_out.write_text(_html_to_txt_string(html), encoding="utf-8")
                fetched += 1
            except Exception as exc:
                log_error("[html] %s failed: %s", article_url, exc)
                failed += 1
            finally:
                await page.close()

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=True,
            channel="chrome",
            user_agent=DEFAULT_USER_AGENT,
            extra_http_headers=_BROWSER_HEADERS,
        )
        await context.route("**/*", handle_route)
        try:
            await asyncio.gather(*[fetch_one(url, txt) for url, txt in pending])
        finally:
            await context.close()

    return fetched, failed


def step_html(target_date, url_file, args):
    """Fetch article URLs in headless Chrome (parallel pages), convert to TXT, save TXT only."""
    if not url_file.exists() or url_file.stat().st_size == 0:
        _print("[html] %s no URL file, skipping", target_date)
        return

    urls = read_daily_urls(url_file)
    user_data_dir = Path(__file__).with_name("user_data")

    # Pre-filter: skip URLs with no parseable path or an existing TXT file.
    pending = []
    skipped = 0
    for article_url in urls:
        html_path = output_path_for_url(args.txt_dir, article_url)
        if html_path is None:
            skipped += 1
            continue
        txt_out = html_path.with_suffix(".txt")
        if txt_out.exists():
            skipped += 1
            continue
        pending.append((article_url, txt_out))

    _print("[html] %s  total=%d  pending=%d  already_done=%d  workers=%d",
           target_date, len(urls), len(pending), skipped, args.workers)

    if not pending:
        return

    fetched, failed = asyncio.run(
        _fetch_articles_async(target_date, pending, user_data_dir, args.workers, args.delay)
    )
    log_info("[html] %s fetched=%d skipped=%d failed=%d",
             target_date, fetched, skipped, failed)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    today = dt.date.today()
    yesterday = today - dt.timedelta(days=1)

    parser = argparse.ArgumentParser(
        description="Le Monde pipeline: URLs → TXT via headless Chrome (HTML never saved)"
    )
    parser.add_argument(
        "start_date", nargs="?", type=parse_input_date,
        default=str(yesterday),
        help="Start date (default: yesterday). DD-MM-YYYY / YYYYMMDD / YYYY-MM-DD",
    )
    parser.add_argument(
        "end_date", nargs="?", type=parse_input_date,
        default=None,
        help="Inclusive end date (default: same as start_date)",
    )

    _archive = Path("/Users/msfr/le_monde_archive")
    parser.add_argument("--url-dir", default=str(_archive / "url"),
                        help="Directory containing daily URL files (default: le_monde_archive/url)")
    parser.add_argument("--txt-dir", default=str(_archive / "txt"),
                        help="Output directory for TXT files (default: le_monde_archive/txt)")
    parser.add_argument("--cookie-file", default=None,
                        help="Optional Netscape cookie file for URL extraction requests")
    parser.add_argument(
        "--mode",
        choices=("all", "urls", "html"),
        default="all",
        help=(
            "Phase to run: "
            "urls (extract URL files only), "
            "html (fetch articles and save TXT, requires URL files), "
            "all (both phases, default)"
        ),
    )
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose logging to pipeline.log")
    parser.add_argument("--workers", type=int, default=8,
                        help="Parallel browser pages for article fetching (default: 8)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to wait between page requests per worker (default: 0). "
                             "Increase to 1–2 if getting 406/429 errors.")
    args = parser.parse_args()

    setup_logging(args.verbose)

    end_date = args.end_date or args.start_date
    if end_date < args.start_date:
        parser.error("end_date must be >= start_date")

    days = list(date_range(args.start_date, end_date))

    _print("Pipeline: %s → %s  (%d day(s))  mode=%s", args.start_date, end_date, len(days), args.mode)
    _print("Log: %s", LOG_FILE)

    def collect_url_files_for_days():
        _print("URL phase: extracting URL files")
        collected = {}
        for target_date in days:
            try:
                collected[target_date] = step_urls(target_date, args)
            except Exception as exc:
                collected[target_date] = None
                log_error("URL phase failed on %s: %s", target_date, exc)
                _print("  ERROR [url] %s: %s", target_date, exc)
        return collected

    if args.mode == "urls":
        collect_url_files_for_days()

    elif args.mode == "html":
        _print("HTML phase: fetching articles and converting to TXT (URL files must exist)")
        for target_date in days:
            url_file = (
                Path(args.url_dir)
                / target_date.strftime("%Y")
                / f"{target_date.strftime('%Y%m%d')}.txt"
            )
            try:
                step_html(target_date, url_file, args)
            except Exception as exc:
                log_error("HTML phase failed on %s: %s", target_date, exc)
                _print("  ERROR [html] %s: %s", target_date, exc)

    else:  # all
        _print("Phase 1/2: extracting URL files for all dates")
        url_files = collect_url_files_for_days()

        _print("Phase 2/2: fetching articles and converting to TXT")
        for target_date in days:
            url_file = url_files.get(target_date)
            if url_file is None:
                _print("  [content] %s: skipped (url phase failed)", target_date)
                continue
            try:
                step_html(target_date, url_file, args)
            except Exception as exc:
                log_error("Content phase failed on %s: %s", target_date, exc)
                _print("  ERROR [content] %s: %s", target_date, exc)

    _print("Pipeline complete.")


if __name__ == "__main__":
    main()
