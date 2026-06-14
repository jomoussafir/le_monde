"""
Streamlit dashboard for the Le Monde pipeline.

Run with:
    /Users/msfr/.venv/bin/streamlit run pipeline_app.py
"""
import datetime as dt
import subprocess
import time
from pathlib import Path

import pandas as pd
import streamlit as st

PYTHON   = Path("/Users/msfr/.venv/bin/python")
PIPELINE = Path(__file__).with_name("run_pipeline.py")
ARCHIVE_ROOT = Path("/Users/msfr/le_monde_archive")
URL_ROOT = ARCHIVE_ROOT / "url"
TXT_ROOT = ARCHIVE_ROOT / "txt"
TEMP_ROOT = ARCHIVE_ROOT / "temp"
URL_CACHE_PATH = TEMP_ROOT / "url_counts_cache.parquet"
TXT_CACHE_PATH = TEMP_ROOT / "txt_counts_cache.parquet"

TEMP_ROOT.mkdir(parents=True, exist_ok=True)

# Must be the first Streamlit page command.
st.set_page_config(page_title="Le Monde Pipeline", layout="wide")

# ── session state ─────────────────────────────────────────────────────────────
for key, default in [("proc", None), ("running", False),
                     ("run_start_time", None), ("run_start_txt", 0),
                     ("run_start_range_txt", 0),
                     ("run_start", None), ("run_end", None),
                     ("range_pick_start", None),
                     ("last_data_refresh", None),
                     ("refresh_reason", "auto")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── helpers ───────────────────────────────────────────────────────────────────

def _read_parquet_or_empty(path, columns):
    if not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame(columns=columns)


def _write_parquet_if_possible(df, path):
    try:
        df.to_parquet(path, index=False)
    except Exception:
        # Keep app functional even if a parquet engine is not available.
        pass


@st.cache_data(ttl=10, show_spinner=False)
def count_urls():
    cache_columns = ["path", "date", "count", "mtime_ns", "size"]
    cache_df = _read_parquet_or_empty(URL_CACHE_PATH, cache_columns)
    if not cache_df.empty:
        cache_df["path"] = cache_df["path"].astype(str)
        cache_df = cache_df.set_index("path", drop=False)

    records = []
    for url_file in sorted(URL_ROOT.glob("*/*.txt")):
        try:
            date = pd.Timestamp(url_file.stem)  # YYYYMMDD
        except Exception:
            continue

        stat = url_file.stat()
        path_str = str(url_file)
        mtime_ns = int(stat.st_mtime_ns)
        size = int(stat.st_size)

        if (not cache_df.empty) and (path_str in cache_df.index):
            old = cache_df.loc[path_str]
            if int(old["mtime_ns"]) == mtime_ns and int(old["size"]) == size:
                records.append(
                    {
                        "path": path_str,
                        "date": old["date"],
                        "count": int(old["count"]),
                        "mtime_ns": mtime_ns,
                        "size": size,
                    }
                )
                continue

        lines = url_file.read_text(encoding="utf-8", errors="replace").splitlines()
        count = sum(1 for l in lines if l.strip() and not l.startswith("#"))
        records.append(
            {
                "path": path_str,
                "date": date,
                "count": count,
                "mtime_ns": mtime_ns,
                "size": size,
            }
        )

    if not records:
        return pd.DataFrame(columns=["date", "count"])

    refreshed = pd.DataFrame(records)
    refreshed["date"] = pd.to_datetime(refreshed["date"])
    _write_parquet_if_possible(refreshed, URL_CACHE_PATH)
    return refreshed[["date", "count"]].sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=10, show_spinner=False)
def count_txts():
    cache_columns = ["path", "date", "count", "mtime_ns"]
    cache_df = _read_parquet_or_empty(TXT_CACHE_PATH, cache_columns)
    if not cache_df.empty:
        cache_df["path"] = cache_df["path"].astype(str)
        cache_df = cache_df.set_index("path", drop=False)

    rows = []
    for day_dir in sorted(TXT_ROOT.glob("*/*/*")):
        if not day_dir.is_dir():
            continue

        parts = day_dir.parts[-3:]
        if len(parts) != 3:
            continue

        try:
            date = pd.Timestamp(f"{parts[0]}-{parts[1]}-{parts[2]}")
        except Exception:
            continue

        stat = day_dir.stat()
        path_str = str(day_dir)
        mtime_ns = int(stat.st_mtime_ns)

        if (not cache_df.empty) and (path_str in cache_df.index):
            old = cache_df.loc[path_str]
            if int(old["mtime_ns"]) == mtime_ns:
                rows.append({
                    "path": path_str,
                    "date": old["date"],
                    "count": int(old["count"]),
                    "mtime_ns": mtime_ns,
                })
                continue

        rows.append({
            "path": path_str,
            "date": date,
            "count": sum(1 for _ in day_dir.glob("*.txt")),
            "mtime_ns": mtime_ns,
        })

    if not rows:
        return pd.DataFrame(columns=["date", "count"])

    refreshed = pd.DataFrame(rows)
    refreshed["date"] = pd.to_datetime(refreshed["date"])
    _write_parquet_if_possible(refreshed, TXT_CACHE_PATH)
    return refreshed[["date", "count"]].sort_values("date").reset_index(drop=True)


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def build_matrix(url_df, txt_df):
    """Return a DataFrame with years as rows and months as columns.
    Each cell contains 'txt / url' counts for that month."""
    def agg(df):
        if df.empty:
            return pd.Series(dtype=int)
        d = df.copy()
        d["year"]  = d["date"].dt.year
        d["month"] = d["date"].dt.month
        return d.groupby(["year", "month"])["count"].sum()

    url_s = agg(url_df)
    txt_s = agg(txt_df)

    all_idx = url_s.index.union(txt_s.index)
    if len(all_idx) == 0:
        return pd.DataFrame()

    years = sorted({y for y, _ in all_idx})
    rows = {}
    for year in years:
        cells = {}
        for m_idx, m_name in enumerate(MONTH_NAMES, start=1):
            u = int(url_s.get((year, m_idx), 0))
            t = int(txt_s.get((year, m_idx), 0))
            cells[m_name] = f"{t}\n{u}" if (u > 0 or t > 0) else ""
        rows[year] = cells

    return pd.DataFrame(rows, index=MONTH_NAMES).T


def month_bounds(year, month):
    start = dt.date(year, month, 1)
    if month == 12:
        end = dt.date(year, 12, 31)
    else:
        end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    return start, end


# ── data (computed once per rerun) ───────────────────────────────────────────

url_df    = count_urls()
txt_df    = count_txts()
if st.session_state.refresh_reason != "manual":
    st.session_state.refresh_reason = "auto"
st.session_state.last_data_refresh = dt.datetime.now()
total_url = int(url_df["count"].sum()) if not url_df.empty else 0
total_txt = int(txt_df["count"].sum()) if not txt_df.empty else 0

# ── sidebar ───────────────────────────────────────────────────────────────────

# CSS overrides — compact matrix buttons (main area only) + sober typography
st.markdown("""
<style>
/* Target secondary button text nodes — Streamlit 1.3x+ data-testid */
[data-testid="stBaseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span,
[data-testid="stBaseButton-secondary"] div {
    font-size: 0.8rem !important;
    line-height: 1.25 !important;
    white-space: pre-line !important;
}
[data-testid="stBaseButton-secondary"] {
    padding: 2px 4px !important;
    min-height: 2.4rem !important;
    font-weight: 400 !important;
}
/* Fallback for older testid names */
div[data-testid="stMain"] button p {
    font-size: 0.8rem !important;
    white-space: pre-line !important;
    line-height: 1.25 !important;
}
div[data-testid="stMain"] button {
    padding: 2px 4px !important;
    min-height: 2.4rem !important;
    font-weight: 400 !important;
}
/* Suppress Streamlit's forced bold on metric labels */
[data-testid="stMetricLabel"] { font-weight: 400 !important; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("##### Le Monde Pipeline")
    st.divider()

    mode = st.radio("Mode", ["urls", "html", "all"], index=0)
    workers = st.slider("Parallel pages", min_value=1, max_value=24, value=8, step=1)
    delay   = st.slider("Delay between requests (s)", min_value=0.0, max_value=5.0, value=0.0, step=0.5)

    today = dt.date.today()
    if "start_date_input" not in st.session_state:
        st.session_state.start_date_input = today - dt.timedelta(days=7)
    if "end_date_input" not in st.session_state:
        st.session_state.end_date_input = today - dt.timedelta(days=1)

    start = st.session_state.start_date_input
    end   = st.session_state.end_date_input

    st.markdown(f"Start &nbsp;&nbsp;&nbsp;{start.strftime('%d %b %Y')}")
    st.markdown(f"End &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{end.strftime('%d %b %Y')}")

    st.divider()

    col_a, col_b = st.columns(2)
    start_clicked = col_a.button("▶ Start", type="primary",  use_container_width=True)
    stop_clicked  = col_b.button("⏹ Stop",                   use_container_width=True)
    refresh_clicked = st.button("↻ Refresh data", use_container_width=True)

    # live status
    if st.session_state.proc is not None:
        if st.session_state.proc.poll() is None:
            st.success("Running…")
            st.session_state.running = True
        else:
            code = st.session_state.proc.poll()
            st.info(f"Finished (exit {code})")
            st.session_state.running = False
    else:
        st.caption("Not started")

# ── actions ───────────────────────────────────────────────────────────────────

if refresh_clicked:
    count_urls.clear()
    count_txts.clear()
    st.session_state.last_data_refresh = dt.datetime.now()
    st.session_state.refresh_reason = "manual"
    st.rerun()

if start_clicked:
    if end < start:
        st.sidebar.error("End date must be ≥ start date")
    else:
        cmd = [
            str(PYTHON), str(PIPELINE),
            start.strftime("%d-%m-%Y"),
            end.strftime("%d-%m-%Y"),
            "--mode", mode,
            "--workers", str(workers),
            "--delay", str(delay),
        ]
        st.session_state.proc = subprocess.Popen(cmd)
        st.session_state.running = True
        st.session_state.run_start_time = time.time()
        st.session_state.run_start_txt = total_txt
        st.session_state.run_start = start
        st.session_state.run_end = end
        _rs = pd.Timestamp(start)
        _re = pd.Timestamp(end)
        _range_txt_now = int(
            txt_df[(txt_df["date"] >= _rs) & (txt_df["date"] <= _re)]["count"].sum()
        ) if not txt_df.empty else 0
        st.session_state.run_start_range_txt = _range_txt_now
        st.rerun()

if stop_clicked and st.session_state.proc is not None:
    st.session_state.proc.terminate()
    st.session_state.running = False
    st.rerun()

# ── main ──────────────────────────────────────────────────────────────────────

st.markdown("#### Le Monde Archive Monitor")

if st.session_state.last_data_refresh is None:
    st.session_state.last_data_refresh = dt.datetime.now()
    st.session_state.refresh_reason = "auto"

_refresh_ts = st.session_state.last_data_refresh.strftime("%Y-%m-%d %H:%M:%S")
_refresh_kind = st.session_state.refresh_reason
st.caption(f"Cache status: active (Parquet + Streamlit cache) · last refresh: {_refresh_ts} · source: {_refresh_kind}")

# ── progress panel ───────────────────────────────────────────────────────────────
# Scope counts to the active run's date range (or sidebar selection if idle).
_d0 = pd.Timestamp(st.session_state.run_start or start)
_d1 = pd.Timestamp(st.session_state.run_end   or end)
range_url_df = url_df[(url_df["date"] >= _d0) & (url_df["date"] <= _d1)] if not url_df.empty else url_df
range_txt_df = txt_df[(txt_df["date"] >= _d0) & (txt_df["date"] <= _d1)] if not txt_df.empty else txt_df
range_url = int(range_url_df["count"].sum()) if not range_url_df.empty else 0
range_txt = int(range_txt_df["count"].sum()) if not range_txt_df.empty else 0

if range_url > 0:
    remaining = max(0, range_url - range_txt)
    progress  = min(1.0, range_txt / range_url)

    rate_str = "—"
    eta_str  = "—"
    t0 = st.session_state.run_start_time
    if t0 is not None and st.session_state.running:
        elapsed   = time.time() - t0
        delta_txt = range_txt - st.session_state.run_start_range_txt
        if elapsed > 15 and delta_txt > 0:
            rate      = delta_txt / elapsed          # art / s
            rate_str  = f"{rate * 3600:.0f} art/h"
            if remaining > 0:
                eta_dt  = dt.datetime.now() + dt.timedelta(seconds=remaining / rate)
                eta_str = eta_dt.strftime("%Y-%m-%d %H:%M")
            else:
                eta_str = "done"
        elif elapsed > 5:
            rate_str = "waiting…"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TXT produced",   f"{range_txt:,}")
    c2.metric("Total URLs",     f"{range_url:,}")
    c3.metric("Remaining",      f"{remaining:,}")
    c4.metric("Rate",           rate_str)
    if eta_str != "—":
        st.caption(f"Estimated completion: {eta_str}")
    st.progress(progress)
    st.divider()

_elapsed_str = "—"
if st.session_state.run_start_time is not None:
    _secs = int(time.time() - st.session_state.run_start_time)
    _h, _rem = divmod(_secs, 3600)
    _m, _s   = divmod(_rem, 60)
    _elapsed_str = f"{_h:02d}:{_m:02d}:{_s:02d}"
st.caption(f"Running time: {_elapsed_str}")

st.caption(f"total txt: {total_txt:,}  ·  total urls: {total_url:,}")
matrix = build_matrix(url_df, txt_df)
if not matrix.empty:
    if st.session_state.range_pick_start is None:
        st.caption("Click a cell to set the start date")
    else:
        _py, _pm = st.session_state.range_pick_start
        st.caption(f"Start: {MONTH_NAMES[_pm-1]} {_py} — click another cell to set the end date")

    # Header row
    _hcols = st.columns([0.55] + [1] * 12)
    _hcols[0].write("")
    for _mn in MONTH_NAMES:
        _hcols[MONTH_NAMES.index(_mn) + 1].caption(_mn)

    # One button per non-empty cell; track which was clicked this run.
    _clicked_year = None
    _clicked_month_idx = None
    for _year in matrix.index:
        _rcols = st.columns([0.55] + [1] * 12)
        _rcols[0].caption(str(_year))
        for _mi, _mn in enumerate(MONTH_NAMES):
            _val = matrix.loc[_year, _mn]
            if _val:
                if _rcols[_mi + 1].button(_val, key=f"mc_{_year}_{_mn}", use_container_width=True):
                    _clicked_year = int(_year)
                    _clicked_month_idx = _mi + 1

    if _clicked_year is not None:
        _sm, _em = month_bounds(_clicked_year, _clicked_month_idx)
        if st.session_state.range_pick_start is None:
            st.session_state["start_date_input"] = _sm
            st.session_state.range_pick_start = (_clicked_year, _clicked_month_idx)
        else:
            st.session_state["end_date_input"] = _em
            st.session_state.range_pick_start = None
        st.rerun()
else:
    st.caption("No data yet.")

# ── auto-refresh while running ────────────────────────────────────────────────
if st.session_state.running:
    time.sleep(5)
    st.rerun()
