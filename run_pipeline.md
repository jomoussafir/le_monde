# run_pipeline.py

## Purpose

`run_pipeline.py` orchestrates the Le Monde ingestion pipeline over a date or date range:

1. URL extraction from archive pages into `url/YYYYMMDD.txt`
2. HTML download for each article URL into `html/YYYY/MM/DD/*.html`
3. HTML to text conversion into `txt/YYYY/MM/DD/*.txt`

The script supports running all steps or only one step (`urls`, `html`, `txt`).

## Fetch strategy

Network fetching uses this strategy by default:

- Try urllib first
- If a client challenge page is detected, fallback to Playwright automatically
- If `--interactive-browser` is set, Playwright opens a visible browser so a challenge can be solved manually

## Execution modes

Use `--mode` to choose what to run:

- `all` (default): full pipeline in 2 phases
  - Phase 1: extract URL files for all dates
  - Phase 2: fetch HTML and convert TXT for all dates
- `urls`: extract URL files only
- `html`: fetch HTML only (uses existing URL files, does not extract URLs)
- `txt`: convert HTML to TXT only (uses existing HTML files)

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

- `--url-dir` (default: `url`)
- `--html-dir` (default: `html`)
- `--txt-dir` (default: `txt`)

### Fetch behavior

- `--interactive-browser`
  - Show browser window when Playwright fallback is triggered
- `--cookie-file PATH`
  - Optional cookie file used by urllib requests
- `--workers N` (default: `8`)
  - Parallel workers for HTML fetch and TXT conversion

### Force behavior

- `--force-urls`
  - Rebuild URL files even if non-empty files already exist
- `--force-html`
  - Re-download HTML files even if they already exist
- `--force-txt`
  - Regenerate TXT files even if they already exist
- `--force`
  - Enables all force flags above

### Other

- `--mode {all,urls,html,txt}` (default: `all`)
- `--verbose`
  - Enable verbose logging

## Logging and progress

- Console output uses tqdm progress bars
- Logs are written to `pipeline.log` in the same folder as `run_pipeline.py`

## Common examples

### Full pipeline for one day

```bash
python run_pipeline.py 14-05-2026
```

### Full pipeline for a date range

```bash
python run_pipeline.py 01-05-2026 14-05-2026
```

### URLs only

```bash
python run_pipeline.py 01-05-2026 14-05-2026 --mode urls
```

### HTML only (requires URL files already present)

```bash
python run_pipeline.py 01-05-2026 14-05-2026 --mode html
```

### TXT only (requires HTML files already present)

```bash
python run_pipeline.py 01-05-2026 14-05-2026 --mode txt
```

### Rebuild text outputs only

```bash
python run_pipeline.py 01-05-2026 14-05-2026 --mode txt --force-txt
```

### Increase concurrency

```bash
python run_pipeline.py 01-05-2026 14-05-2026 --workers 16
```

## Notes

- In `html` mode, missing URL files will cause that day to be skipped for HTML fetch.
- In `txt` mode, missing HTML day folders will cause that day to be skipped for TXT conversion.
- If the site starts challenging heavily, lowering `--workers` can improve stability.
