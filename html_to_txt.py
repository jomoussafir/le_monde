import argparse
import datetime as dt
import re
from html.parser import HTMLParser
from pathlib import Path


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


# Trailing lines Le Monde appends after article content on every page.
_BOILERPLATE_LINES = {
    "Le Monde",
    "L’espace des contributions est réservé aux abonnés.",
    "Abonnez-vous pour accéder à cet espace d’échange et contribuer à la discussion.",
    "S’abonner",
    "Commenter",
    "Réutiliser ce contenu",
}


def strip_boilerplate(text):
    lines = text.splitlines()
    while lines and lines[-1].strip() in _BOILERPLATE_LINES:
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in {"p", "div", "section", "article", "h1", "h2", "h3", "li", "br"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"p", "div", "section", "article", "h1", "h2", "h3", "li"}:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._chunks.append(text)
            self._chunks.append(" ")

    def get_text(self):
        raw = "".join(self._chunks)
        raw = raw.replace("\xa0", " ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
        lines = [line for line in lines if line]

        # Remove immediate duplicate lines often produced by archive markup.
        deduped = []
        prev = None
        for line in lines:
            if line != prev:
                deduped.append(line)
            prev = line

        text = "\n".join(deduped).strip() + ("\n" if deduped else "")
        return strip_boilerplate(text)


def extract_best_html_segment(html):
    patterns = [
        re.compile(r"<article\b[\s\S]*?</article>", re.IGNORECASE),
        re.compile(r"<main\b[\s\S]*?</main>", re.IGNORECASE),
        re.compile(r"<div[^>]*id=[\"']articleBody[\"'][\s\S]*?</div>", re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(html)
        if match:
            return match.group(0)
    body_match = re.search(r"<body\b[\s\S]*?</body>", html, re.IGNORECASE)
    if body_match:
        return body_match.group(0)
    return html


def html_file_to_txt(html_file, txt_file, force=False):
    if txt_file.exists() and not force:
        return "skipped"

    html = html_file.read_text(encoding="utf-8", errors="replace")
    segment = extract_best_html_segment(html)

    parser = TextExtractor()
    parser.feed(segment)
    parser.close()
    text = parser.get_text()

    txt_file.parent.mkdir(parents=True, exist_ok=True)
    txt_file.write_text(text, encoding="utf-8")
    return "written"


def convert_day(html_dir, txt_dir, target_date, force=False):
    html_day_dir = Path(html_dir) / target_date.strftime("%Y") / target_date.strftime("%m") / target_date.strftime("%d")
    if not html_day_dir.exists():
        print(f"Skipping {target_date}: no HTML directory at {html_day_dir}")
        return 0, 0

    written = 0
    skipped = 0
    for html_file in sorted(html_day_dir.glob("*.html")):
        txt_file = Path(txt_dir) / target_date.strftime("%Y") / target_date.strftime("%m") / target_date.strftime("%d") / (html_file.stem + ".txt")
        status = html_file_to_txt(html_file, txt_file, force=force)
        if status == "written":
            written += 1
        else:
            skipped += 1

    print(f"{target_date}: written={written}, skipped_existing={skipped}")
    return written, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Convert HTML articles to plain text files in txt/YYYY/MM/DD/<title>.txt"
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
    parser.add_argument("--html-dir", default="html", help="Root directory containing html/YYYY/MM/DD")
    parser.add_argument("--txt-dir", default="txt", help="Root directory for txt/YYYY/MM/DD outputs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing .txt files")
    args = parser.parse_args()

    end_date = args.end_date or args.start_date
    if end_date < args.start_date:
        raise ValueError("end_date must be >= start_date")

    total_written = 0
    total_skipped = 0
    for target_date in date_range(args.start_date, end_date):
        written, skipped = convert_day(
            html_dir=args.html_dir,
            txt_dir=args.txt_dir,
            target_date=target_date,
            force=args.force,
        )
        total_written += written
        total_skipped += skipped

    day_count = (end_date - args.start_date).days + 1
    print(
        f"All done. {day_count} day(s). "
        f"written={total_written}, skipped_existing={total_skipped}"
    )


if __name__ == "__main__":
    main()
