import argparse
import datetime as dt
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

from fetch_test import fetch_url_auto

ARCHIVE_BASE = "https://www.lemonde.fr/archives-du-monde/"
HREF_PATTERN = re.compile(r"href=[\"']([^\"']+)[\"']", re.IGNORECASE)


def parse_input_date(value):
    for fmt in ("%d-%m-%Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        "Date must be one of: DD-MM-YYYY, YYYYMMDD, YYYY-MM-DD"
    )


def build_archive_url(target_date, page_index=1):
    date_str = target_date.strftime("%d-%m-%Y")
    if page_index == 1:
        return f"{ARCHIVE_BASE}{date_str}/"
    return f"{ARCHIVE_BASE}{date_str}/{page_index}/"


def normalize_link(base_url, href):
    full_url = urljoin(base_url, href)
    full_url = full_url.split("#", 1)[0].split("?", 1)[0]
    return full_url


def extract_article_links(html, base_url, target_date):
    article_pattern = re.compile(
        rf"^https://www\.lemonde\.fr/.*/article/{target_date.strftime('%Y/%m/%d')}/[^/]+\.html$"
    )

    links = set()
    for raw_href in HREF_PATTERN.findall(html):
        href = normalize_link(base_url, raw_href)
        if article_pattern.match(href):
            links.add(href)
    return links


def extract_max_page_hint(html, target_date):
    date_part = target_date.strftime("%d-%m-%Y")
    page_pattern = re.compile(rf"/archives-du-monde/{date_part}/(\d+)/")
    pages = [int(match) for match in page_pattern.findall(html)]
    return max(pages, default=1)


def collect_daily_article_urls(
    target_date,
    cookie_file=None,
    prefer_playwright=False,
    interactive_challenge=False,
):
    collected = set()
    page_index = 1
    max_page_hint = 1

    while page_index <= max_page_hint:
        page_url = build_archive_url(target_date, page_index)
        print(f"Reading archive page: {page_url}")
        try:
            html = fetch_url_auto(
                page_url,
                cookie_file=cookie_file,
                prefer_playwright=prefer_playwright,
                interactive_challenge=interactive_challenge,
            )
        except (HTTPError, URLError, RuntimeError) as exc:
            if page_index == 1:
                raise RuntimeError(f"Failed to read archive page {page_url}: {exc}") from exc
            print(f"Stopping at page {page_index}: {exc}")
            break

        found_links = extract_article_links(html, page_url, target_date)
        collected.update(found_links)

        page_hint = extract_max_page_hint(html, target_date)
        if page_hint > max_page_hint:
            max_page_hint = page_hint

        page_index += 1

    return sorted(collected)


def date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += dt.timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(
        description="Extract Le Monde article URLs and save them to url/YYYYMMDD.txt"
    )
    parser.add_argument(
        "start_date", type=parse_input_date, help="Start date: DD-MM-YYYY, YYYYMMDD, or YYYY-MM-DD"
    )
    parser.add_argument(
        "end_date",
        nargs="?",
        type=parse_input_date,
        help="Optional inclusive end date in the same accepted formats",
    )
    parser.add_argument(
        "--cookie-file",
        default=None,
        help="Optional Netscape cookie file for authenticated requests",
    )
    parser.add_argument(
        "--url-dir",
        default="url",
        help="Directory where daily URL files are written",
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Force browser-based fetch for every page",
    )
    parser.add_argument(
        "--interactive-browser",
        action="store_true",
        help="Open visible browser and allow manual challenge solve when needed",
    )
    args = parser.parse_args()

    url_dir = Path(args.url_dir)
    url_dir.mkdir(parents=True, exist_ok=True)

    end_date = args.end_date or args.start_date
    if end_date < args.start_date:
        raise ValueError("end_date must be greater than or equal to start_date")

    total_urls = 0
    for target_date in date_range(args.start_date, end_date):
        urls = collect_daily_article_urls(
            target_date,
            cookie_file=args.cookie_file,
            prefer_playwright=args.use_playwright,
            interactive_challenge=args.interactive_browser,
        )
        output_file = url_dir / f"{target_date.strftime('%Y%m%d')}.txt"
        output_file.write_text("\n".join(urls) + ("\n" if urls else ""), encoding="utf-8")
        total_urls += len(urls)
        print(f"Saved {len(urls)} URL(s) to {output_file}")

    day_count = (end_date - args.start_date).days + 1
    print(f"Completed {day_count} day(s). Total URLs saved: {total_urls}")


if __name__ == "__main__":
    main()
