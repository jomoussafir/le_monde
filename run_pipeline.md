# run_pipeline.py

## Purpose

`run_pipeline.py` orchestrates the Le Monde ingestion pipeline over a date or date range:

1. URL extraction from archive pages into `url/YYYY/YYYYMMDD.txt`
2. HTML fetch via headless Chrome, converted to plain text in-memory → `txt/YYYY/MM/DD/<title>.txt`

**HTML is never saved to disk.** Only TXT files are written.

The script supports running both steps together or one at a time (`urls`, `html`).

## Fetch strategy

### URL extraction

- Uses urllib with automatic headless-Playwright fallback when a challenge page is detected.

### Article fetching

- Always uses a persistent headless Chrome/Chromium session via Playwright.
- One Chrome context is opened per day's URL file; each article is loaded in a new page, converted to TXT in-memory, and the page is closed.
- HTML is discarded after conversion — nothing is written to `html/`.

## Execution modes

Use `--mode` to choose what to run:

- `all` (default): full pipeline in 2 phases
  - Phase 1: extract URL files for all dates
  - Phase 2: fetch articles, convert to TXT, and save
- `urls`: extract URL files only
- `html`: fetch and convert to TXT only (uses existing URL files)

## Date handling

Positional arguments:

- `start_date` (optional): default is yesterday
- `end_date` (optional): default is `start_date`

Accepted date formats:

- `DD-MM-YYYY`
- `YYYYMMDD`
- `YYYY-MM-DD`

If `end_date` is provided, it must be greater than or equal to `start_date`.

## Command line options

### Paths

- `--url-dir` (default: `le_monde_archive/url`)
- `--txt-dir` (default: `le_monde_archive/txt`)

### Other

- `--cookie-file PATH`
  - Optional Netscape cookie file used by urllib during URL extraction
- `--mode {all,urls,html}` (default: `all`)
- `--verbose`
  - Enable verbose logging to `pipeline.log`

## Logging and progress

- Console output uses tqdm progress bars
- Logs are written to `pipeline.log` in the same folder as `run_pipeline.py`

## Common examples

### Full pipeline for one day

Runs URL extraction then article fetch + TXT conversion for a single date.

```bash
python run_pipeline.py 14-05-2026
```

### Full pipeline for a date range

Runs both phases for every day from 1 May to 14 May inclusive.

```bash
python run_pipeline.py 01-05-2026 14-05-2026
```

### URLs only

Extracts article URLs from the Le Monde archive pages and writes one `url/YYYY/YYYYMMDD.txt` file per day. Does not fetch any articles.

```bash
python run_pipeline.py 01-05-2026 14-05-2026 --mode urls
```

### HTML fetch and TXT conversion only (URL files must already exist)

Opens each article URL in headless Chrome, converts HTML to TXT in-memory, and writes only `.txt` files. Skips articles already converted.

```bash
python run_pipeline.py 01-05-2026 14-05-2026 --mode html
```

## Notes

- In `html` mode, days whose URL file is missing are skipped.
- To re-process an article, delete its `.txt` file manually and re-run.
- If the site starts challenging heavily, the browser session may accumulate solved-challenge cookies in `user_data/`, which helps on subsequent runs.
