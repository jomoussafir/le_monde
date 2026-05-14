import argparse
import datetime as dt
import re
from pathlib import Path
from urllib.error import HTTPError, URLError

from fetch_test import fetch_url_auto

ARTICLE_PATH_RE = re.compile(
    r"^https://www\.lemonde\.fr/.*/article/(?P<year>\d{4})/(?P<month>\d{2})/(?P<day>\d{2})/(?P<title>[^/?#]+\.html)$"
)


def parse_input_date(value):
    for fmt in ("%d-%m-%Y", "%Y%m%d", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError("Date must be one of: DD-MM-YYYY, YYYYMMDD, YYYY-MM-DD")


def date_range(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += dt.timedelta(days=1)


def read_daily_urls(url_file):
    lines = url_file.read_text(encoding="utf-8").splitlines()
    urls = []
    seen = set()
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if value not in seen:
            seen.add(value)
            urls.append(value)
    return urls


def output_path_for_url(base_dir, article_url):
    clean_url = article_url.split("#", 1)[0].split("?", 1)[0]
    match = ARTICLE_PATH_RE.match(clean_url)
    if not match:
        return None

    year = match.group("year")
    month = match.group("month")
    day = match.group("day")
    title = match.group("title")

    return Path(base_dir) / year / month / day / title


def fetch_day(url_file, html_dir, cookie_file, overwrite, prefer_playwright, interactive_challenge):
    urls = read_daily_urls(url_file)
    print(f"Loaded {len(urls)} URL(s) from {url_file}")

    fetched = skipped_existing = skipped_unmatched = failed = 0

    for article_url in urls:
        output_path = output_path_for_url(html_dir, article_url)
        if output_path is None:
            print(f"Skipping unsupported URL format: {article_url}")
            skipped_unmatched += 1
            continue

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.exists() and not overwrite:
            skipped_existing += 1
            continue

        try:
            html = fetch_url_auto(
                article_url,
                cookie_file=cookie_file,
                prefer_playwright=prefer_playwright,
                interactive_challenge=interactive_challenge,
            )
        except (HTTPError, URLError, RuntimeError) as exc:
            print(f"Failed: {article_url} ({exc})")
            failed += 1
            continue

        output_path.write_text(html, encoding="utf-8")
        fetched += 1

    print(
        f"  fetched={fetched}, skipped_existing={skipped_existing}, "
        f"skipped_unmatched={skipped_unmatched}, failed={failed}"
    )
    return fetched, skipped_existing, skipped_unmatched, failed


def main():
    parser = argparse.ArgumentParser(
        description="Fetch article HTML from url/YYYYMMDD.txt into html/YYYY/MM/DD/<title>.html"
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
        "--url-dir",
        default="url",
        help="Directory containing daily URL files",
    )
    parser.add_argument(
        "--html-dir",
        default="html",
        help="Directory where HTML files are saved",
    )
    parser.add_argument(
        "--cookie-file",
        default=None,
        help="Optional Netscape cookie file for authenticated requests",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite files if they already exist",
    )
    parser.add_argument(
        "--use-playwright",
        action="store_true",
        help="Force browser-based fetch for each article",
    )
    parser.add_argument(
        "--interactive-browser",
        action="store_true",
        help="Open visible browser and allow manual challenge solve when needed",
    )
    args = parser.parse_args()

    end_date = args.end_date or args.start_date
    if end_date < args.start_date:
        raise ValueError("end_date must be >= start_date")

    url_dir = Path(args.url_dir)
    totals = {"fetched": 0, "skipped_existing": 0, "skipped_unmatched": 0, "failed": 0}

    for target_date in date_range(args.start_date, end_date):
        url_file = url_dir / f"{target_date.strftime('%Y%m%d')}.txt"
        if not url_file.exists():
            print(f"Skipping {target_date}: URL file not found ({url_file})")
            continue
        print(f"--- {target_date} ---")
        f, se, su, fa = fetch_day(
            url_file,
            args.html_dir,
            args.cookie_file,
            args.overwrite,
            args.use_playwright,
            args.interactive_browser,
        )
        totals["fetched"] += f
        totals["skipped_existing"] += se
        totals["skipped_unmatched"] += su
        totals["failed"] += fa

    day_count = (end_date - args.start_date).days + 1
    print(
        f"\nAll done. {day_count} day(s). "
        f"fetched={totals['fetched']}, skipped_existing={totals['skipped_existing']}, "
        f"skipped_unmatched={totals['skipped_unmatched']}, failed={totals['failed']}"
    )


if __name__ == "__main__":
    main()
