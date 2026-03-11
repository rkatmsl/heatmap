"""
Apollo Hospitals — Media Intelligence Dashboard
------------------------------------------------
Fetches live data from:
  GET /projects/1998348013/rulecategories          → category tree
  GET /projects/1998348013/data/mentions/          → paginated mentions

Renders:
  1. Themes × Leadership heatmap  (co-occurrence)
  2. Themes × Publishers heatmap  (top-N publishers)
  3. Top publishers bar chart

Hover on heatmap cells to preview top mentions.
Click on a cell to expand article links below the chart.
"""

import os
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

PROJECT_ID   = 1998348013
QUERY_ID     = 2003868554
BASE_URL     = f"https://api.brandwatch.com/projects/{PROJECT_ID}"
MENTIONS_URL = f"{BASE_URL}/data/mentions/"
CATS_URL     = f"{BASE_URL}/rulecategories"

BW_TOKEN = st.secrets.get("BRANDWATCH_TOKEN", "")
GROQ_KEY = st.secrets.get("GROQ_API_KEY", "")


GROQ_MODEL = "llama-3.3-70b-versatile"

HEADERS = {"Authorization": f"Bearer {BW_TOKEN}", "Accept": "application/json"}

THEMES_KEYWORD     = "theme"
LEADERSHIP_KEYWORD = "leadership"


# ─────────────────────────────────────────────
# DATA FETCHING
# ─────────────────────────────────────────────

@st.cache_data(ttl=86_400, show_spinner=False)
def fetch_category_groups() -> list:
    resp = requests.get(CATS_URL, headers=HEADERS, timeout=20)
    if not resp.ok:
        st.error(f"Categories API {resp.status_code}: {resp.text[:300]}")
        return []
    data = resp.json()
    return data.get("results", data.get("categories", []))


def parse_category_tree(groups: list) -> dict:
    """Returns group_children: { group_name_lower: {child_id: child_name} }"""
    group_children: dict[str, dict[int, str]] = {}

    def collect_descendants(node: dict) -> dict[int, str]:
        result = {}
        for child in node.get("children", []):
            cid = child.get("id")
            cname = child.get("name", "")
            if cid:
                result[int(cid)] = cname
            result.update(collect_descendants(child))
        return result

    for group in groups:
        gname = group.get("name", "").lower()
        group_children[gname] = collect_descendants(group)

    return group_children


def find_group(group_children: dict, keyword: str) -> dict:
    """Return first group whose name contains keyword (case-insensitive)."""
    kw = keyword.lower()
    for gname, children in group_children.items():
        if kw in gname:
            return children
    return {}


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_all_mentions(start: str, end: str, page_size: int = 5000) -> pd.DataFrame:
    all_rows = []
    page = 0
    progress = st.progress(0, text="Fetching mentions…")

    while True:
        params = {
            "queryId":   QUERY_ID,
            "startDate": start,
            "endDate":   end,
            "pageSize":  page_size,
            "page":      page,
        }
        resp = requests.get(MENTIONS_URL, headers=HEADERS, params=params, timeout=30)
        if not resp.ok:
            st.error(f"Mentions API {resp.status_code}: {resp.text[:300]}")
            break

        data    = resp.json()
        batch   = data.get("results", [])
        total_r = data.get("totalResults", data.get("resultsTotal", None))
        all_rows.extend(batch)
        fetched = len(all_rows)

        if total_r and total_r > 0:
            progress.progress(
                min(fetched / total_r, 1.0),
                text=f"Fetched {fetched:,} / {total_r:,} mentions…"
            )

        if len(batch) < page_size:
            break
        page += 1
        if page > 40:
            st.warning("Reached page cap (40 pages). Results may be incomplete.")
            break

    progress.empty()
    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()


# ─────────────────────────────────────────────
# CATEGORY HELPERS
# ─────────────────────────────────────────────

def extract_cat_ids(cell) -> set:
    """
    Brandwatch categories field is a list of dicts {"id":…} or plain ints.
    Handle both.
    """
    if not isinstance(cell, list):
        return set()
    ids = set()
    for item in cell:
        if isinstance(item, dict):
            cid = item.get("id") or item.get("categoryId")
            if cid is not None:
                ids.add(int(cid))
        elif isinstance(item, (int, float)):
            ids.add(int(item))
    return ids


# ─────────────────────────────────────────────
# PIVOT BUILDERS
# ─────────────────────────────────────────────

def build_cross_pivot(df: pd.DataFrame, row_cats: dict, col_cats: dict) -> pd.DataFrame:
    """Co-occurrence: cell[r][c] = # mentions tagged with BOTH r AND c."""
    matrix = pd.DataFrame(0, index=list(row_cats.values()), columns=list(col_cats.values()))
    for cell in df["categories"]:
        ids = extract_cat_ids(cell)
        row_hits = [row_cats[i] for i in ids if i in row_cats]
        col_hits = [col_cats[i] for i in ids if i in col_cats]
        for r in row_hits:
            for c in col_hits:
                matrix.loc[r, c] += 1
    return matrix


def build_theme_publisher_pivot(df: pd.DataFrame, theme_cats: dict, top_n: int = 20) -> pd.DataFrame:
    """Themes × publisher domain, top-N publishers by total mentions."""
    dom_col  = next((c for c in ["domain", "site", "sourceName"] if c in df.columns), None)
    df       = df.copy()
    df["_pub"] = df[dom_col].fillna("Unknown") if dom_col else "Unknown"
    top_pubs = df["_pub"].value_counts().head(top_n).index.tolist()
    matrix   = pd.DataFrame(0, index=list(theme_cats.values()), columns=top_pubs)
    tid_set  = set(theme_cats.keys())
    for _, row in df.iterrows():
        pub = row["_pub"]
        if pub not in top_pubs:
            continue
        ids = extract_cat_ids(row.get("categories", []))
        for i in ids:
            if i in tid_set:
                matrix.loc[theme_cats[i], pub] += 1
    return matrix


# ─────────────────────────────────────────────
# MENTION LOOKUP BUILDERS (for hover/click)
# ─────────────────────────────────────────────

def _mention_record(row) -> dict:
    url     = row.get("originalUrl") or row.get("url") or ""
    title   = (row.get("title") or "").strip()
    snippet = (row.get("snippet") or "").strip()
    domain  = row.get("domain") or row.get("site") or row.get("sourceName") or ""
    date    = str(row.get("date") or "")[:10]
    pub     = row.get("publicationName") or row.get("unifiedSourceName") or domain
    sentiment = row.get("sentiment") or ""
    return dict(title=title, snippet=snippet, url=url, domain=domain,
                date=date, pub=pub, sentiment=sentiment)


def build_mention_lookup(df: pd.DataFrame, row_cats: dict, col_cats: dict) -> dict:
    """(row_label, col_label) → list of mention records (for Themes × Leadership)."""
    lookup: dict[tuple, list] = {}
    for _, row in df.iterrows():
        ids      = extract_cat_ids(row.get("categories", []))
        row_hits = [row_cats[i] for i in ids if i in row_cats]
        col_hits = [col_cats[i] for i in ids if i in col_cats]
        rec      = _mention_record(row)
        for r in row_hits:
            for c in col_hits:
                lookup.setdefault((r, c), []).append(rec)
    return lookup


def build_mention_lookup_pub(df: pd.DataFrame, theme_cats: dict, top_pubs: list) -> dict:
    """(theme_label, publisher) → list of mention records (for Themes × Publishers)."""
    top_pub_set = set(top_pubs)
    dom_col     = next((c for c in ["domain", "site", "sourceName"] if c in df.columns), None)
    lookup: dict[tuple, list] = {}
    for _, row in df.iterrows():
        pub = (row.get(dom_col) if dom_col else None) or "Unknown"
        if pub not in top_pub_set:
            continue
        ids = extract_cat_ids(row.get("categories", []))
        rec = _mention_record(row)
        for i in ids:
            if i in theme_cats:
                lookup.setdefault((theme_cats[i], pub), []).append(rec)
    return lookup


# ─────────────────────────────────────────────
# HEATMAP RENDERER
# ─────────────────────────────────────────────

def render_heatmap(
    matrix: pd.DataFrame,
    title: str,
    x_title: str,
    y_title: str,
    height: int = 540,
    mention_lookup: dict = None,
) -> go.Figure:
    z    = matrix.values.tolist()
    x    = list(matrix.columns)
    y    = list(matrix.index)
    text = [[str(v) if v > 0 else "" for v in row] for row in z]

    # Build customdata: top-3 snippets per cell as a single hover string
    customdata = []
    for row_label in y:
        row_data = []
        for col_label in x:
            if mention_lookup:
                mentions = mention_lookup.get((row_label, col_label), [])[:3]
                parts = []
                for m in mentions:
                    t   = (m["title"] or m["snippet"] or "(no title)")[:70]
                    pub = m["pub"] or m["domain"]
                    dt  = m["date"]
                    sent = f' · {m["sentiment"]}' if m["sentiment"] else ""
                    parts.append(f"▸ {t}  [{pub}{sent}, {dt}]")
                cell_str = "<br>".join(parts) if parts else "—"
            else:
                cell_str = ""
            row_data.append(cell_str)
        customdata.append(row_data)

    GOR_SCALE = [
        [0.000, "#1a1a1a"],
        [0.001, "#1a4d2e"],
        [0.143, "#2d7a3a"],
        [0.286, "#52b44b"],
        [0.429, "#a8c84a"],
        [0.571, "#f5a623"],
        [0.714, "#e8732a"],
        [0.857, "#d63b1f"],
        [1.000, "#b01010"],
    ]

    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=y,
        text=text, texttemplate="%{text}",
        customdata=customdata,
        textfont={"size": 11, "color": "white", "family": "Arial Black"},
        colorscale=GOR_SCALE, showscale=True, hoverongaps=False,
        hovertemplate=(
            f"<b>{y_title}:</b> %{{y}}<br>"
            f"<b>{x_title}:</b> %{{x}}<br>"
            "<b>Mentions:</b> %{z}<br>"
            "<br>%{customdata}"
            "<extra></extra>"
        ),
        colorbar=dict(
            thickness=14, len=0.85,
            title=dict(text="Count", font=dict(size=12, color="#ffffff")),
            tickfont=dict(size=11, color="#ffffff"),
            outlinecolor="#ffffff", outlinewidth=1,
        ),
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#ffffff", family="Georgia"), x=0.01),
        xaxis=dict(
            title=dict(text=x_title, font=dict(size=12, color="#ffffff")),
            tickangle=-38, tickfont=dict(size=11, color="#ffffff"),
            side="bottom", gridcolor="#333333", linecolor="#555555",
        ),
        yaxis=dict(
            title=dict(text=y_title, font=dict(size=12, color="#ffffff")),
            tickfont=dict(size=11, color="#ffffff"),
            autorange="reversed", gridcolor="#333333", linecolor="#555555",
        ),
        height=height,
        margin=dict(l=250, r=90, t=65, b=185),
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(family="'Source Sans 3', sans-serif", color="#ffffff"),
        hoverlabel=dict(
            bgcolor="#111111",
            bordercolor="#ffffff",
            font=dict(size=12, color="#ffffff", family="'Space Mono', monospace"),
        ),
    )
    return fig


def render_click_panel(lookup: dict, row_label: str, col_label: str,
                       row_title: str, col_title: str, key_prefix: str):
    """
    Shows a styled expandable panel with linked articles for the clicked cell.
    Called after a plotly_chart click event.
    """
    mentions = lookup.get((row_label, col_label), [])
    st.markdown(
        f'<div class="click-panel">'
        f'<span class="click-hdr">{row_title}: <b>{row_label}</b> &nbsp;×&nbsp; '
        f'{col_title}: <b>{col_label}</b> &nbsp;—&nbsp; {len(mentions)} mention(s)</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not mentions:
        st.info("No mentions found for this cell.")
        return

    # Sentiment badge colours
    sent_colors = {"positive": "#2d7a3a", "negative": "#d63b1f", "neutral": "#555555"}

    for m in mentions[:15]:   # show up to 15
        title   = m["title"] or m["snippet"][:80] or "(untitled)"
        url     = m["url"]
        pub     = m["pub"] or m["domain"]
        date    = m["date"]
        snippet = m["snippet"]
        sent    = m["sentiment"]
        sc      = sent_colors.get(sent, "#555555")

        title_html = (
            f'<a href="{url}" target="_blank" style="color:#aaffaa;font-weight:700;'
            f'text-decoration:none;">{title}</a>'
            if url else
            f'<span style="color:#ffffff;font-weight:700;">{title}</span>'
        )
        sent_badge = (
            f'<span style="background:{sc};color:#fff;padding:1px 7px;'
            f'font-size:.68rem;margin-left:8px;font-family:\'Space Mono\',monospace;">'
            f'{sent}</span>'
            if sent else ""
        )
        snippet_html = (
            f'<div style="color:#aaaaaa;font-size:.78rem;margin-top:3px;">{snippet[:160]}…</div>'
            if snippet else ""
        )

        st.markdown(
            f'<div class="mention-card">'
            f'{title_html}{sent_badge}'
            f'<div style="color:#666666;font-size:.72rem;margin-top:4px;">'
            f'{pub} &nbsp;·&nbsp; {date}</div>'
            f'{snippet_html}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────
# STYLED TABLE
# ─────────────────────────────────────────────

def styled_table(matrix: pd.DataFrame):
    max_val = matrix.values.max() if matrix.values.max() > 0 else 1
    palette = [
        "#1a1a1a", "#1a4d2e", "#2d7a3a", "#52b44b",
        "#a8c84a", "#f5a623", "#e8732a", "#d63b1f", "#b01010",
    ]

    def cell_color(val):
        if val == 0:
            return "background-color: #1a1a1a; color: #444444; font-weight:400;"
        ratio = val / max_val
        idx   = 1 + min(int(ratio * 7.99), 7)
        return f"background-color: {palette[idx]}; color: #ffffff; font-weight: 700;"

    return matrix.style.applymap(cell_color).format("{:,.0f}")


# ─────────────────────────────────────────────
# PAGE CONFIG & GLOBAL CSS
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="Apollo — Media Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;600;700&family=Space+Mono:wght@400;700&display=swap');

html, body, [class*="css"], .stApp, section[data-testid="stSidebar"] {
    font-family: 'Space Grotesk', sans-serif !important;
    background-color: #000000 !important;
    color: #ffffff !important;
}

.stApp                                      { background: #000000 !important; }
section[data-testid="stSidebar"]            { background: #0a0a0a !important; border-right: 1px solid #ffffff; }
section[data-testid="stSidebar"] *          { color: #ffffff !important; }

p, span, label, div, li, h1, h2, h3, h4   { color: #ffffff !important; }
.stMarkdown, .stCaption, .stText           { color: #ffffff !important; }

.stDateInput input, .stSlider, .stCheckbox { color: #ffffff !important; }
.stButton > button {
    background: black !important;
    color: #ffffff !important;
    font-weight: 700;
    border: 2px solid #ffffff !important;
    border-radius: 0 !important;
    letter-spacing: .05em;
    font-family: 'Space Mono', monospace !important;
}
.stButton > button:hover {
    background: #ffffff !important;
    color: #000000 !important;
}

details, summary { background: #000000 !important; color: #ffffff !important; border: 1px solid #ffffff !important; }
summary:hover    { background: #111111 !important; }

.stInfo, .stWarning, .stError, .stSuccess { filter: invert(1) hue-rotate(180deg); }

/* KPI cards */
.kpi-row  { display:flex; gap:12px; margin:14px 0 20px; flex-wrap:wrap; }
.kpi-card {
    flex:1; min-width:130px;
    background:#000000;
    border:1px solid #ffffff;
    padding:15px 16px 11px;
    text-align:center;
}
.kpi-val  { font-size:2rem; font-weight:700; color:#ffffff; font-family:'Space Mono',monospace; }
.kpi-lbl  { font-size:.68rem; color:#ffffff; text-transform:uppercase; letter-spacing:.12em; margin-top:4px; opacity:.6; }

/* Section headers */
.sec-hdr {
    background:#ffffff;
    color:#000000 !important;
    padding:9px 16px;
    font-family:'Space Mono',monospace;
    font-size:.95rem;
    font-weight:700;
    margin:28px 0 8px;
    letter-spacing:.04em;
    text-transform:uppercase;
}

/* Click panel header */
.click-panel {
    background:#0d0d0d;
    border-left: 3px solid #ffffff;
    padding: 10px 16px;
    margin: 10px 0 6px;
}
.click-hdr {
    font-family:'Space Mono',monospace;
    font-size:.82rem;
    color:#cccccc !important;
    letter-spacing:.03em;
}

/* Mention cards */
.mention-card {
    background: #0a0a0a;
    border: 1px solid #2a2a2a;
    border-left: 3px solid #ffffff;
    padding: 10px 14px;
    margin: 6px 0;
    transition: border-color .15s;
}
.mention-card:hover {
    border-left-color: #52b44b;
    background: #111111;
}

/* Category pills */
.tag {
    display:inline-block;
    background:#000000;
    color:#ffffff !important;
    border:1px solid #ffffff;
    padding:2px 9px;
    font-size:.75rem;
    margin:2px;
    font-family:'Space Mono',monospace;
}

.stDataFrame, iframe { background:#000000 !important; border:1px solid #ffffff; }

/* Instruction hint */
.hint {
    font-size:.72rem;
    color:#666666 !important;
    font-family:'Space Mono',monospace;
    margin: -4px 0 12px;
    letter-spacing:.04em;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

st.markdown("""
<h1 style='color:#ffffff; margin-bottom:2px; margin-top:6px;
           font-family:"Space Mono",monospace; letter-spacing:.03em;'>
  APOLLO HOSPITALS
</h1>
<p style='color:#ffffff; font-size:.85rem; margin:0 0 8px; opacity:.55;
          letter-spacing:.1em; text-transform:uppercase; font-family:"Space Mono",monospace;'>
  Themes × Leadership &amp; Themes × Publishers
</p>
<hr style='border:1px solid #ffffff; margin-bottom:4px;'>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🗓 Date Range")
    start_date = st.date_input("Start Date", value=datetime(2025, 3, 10).date())
    end_date   = st.date_input("End Date",   value=datetime(2025, 3, 11).date())

    st.markdown("### ⚙️ Options")
    top_n_pubs     = st.slider("Top N Publishers", 5, 40, 15, 5)
    hide_zero_rows = st.checkbox("Hide zero-count theme rows", value=True)
    show_ai        = st.checkbox("Generate AI Insights (Groq)", value=bool(GROQ_KEY))
    max_click_rows = st.slider("Max articles shown on click", 5, 30, 10, 5)

    st.markdown("---")
    load_btn = st.button("Load Data", use_container_width=True, type="primary")


# ─────────────────────────────────────────────
# GUARDS
# ─────────────────────────────────────────────

if start_date > end_date:
    st.error("Start date must be before end date.")
    st.stop()

if not load_btn:
    st.info("Select a date range and click **Load Data** to fetch live Brandwatch data.")
    st.stop()


# ─────────────────────────────────────────────
# FETCH CATEGORIES
# ─────────────────────────────────────────────

with st.spinner("Fetching category tree…"):
    raw_groups = fetch_category_groups()

if not raw_groups:
    st.error("Failed to load categories. Check BRANDWATCH_TOKEN.")
    st.stop()

group_children = parse_category_tree(raw_groups)
themes_cats    = find_group(group_children, THEMES_KEYWORD)
leader_cats    = find_group(group_children, LEADERSHIP_KEYWORD)

if not themes_cats:
    st.error(f"No 'Themes' group found. Available: {list(group_children.keys())}")
    st.stop()
if not leader_cats:
    st.error(f"No 'Leadership' group found. Available: {list(group_children.keys())}")
    st.stop()


# ─────────────────────────────────────────────
# FETCH MENTIONS
# ─────────────────────────────────────────────

start_str = start_date.strftime("%Y-%m-%d")
end_str   = end_date.strftime("%Y-%m-%d")

with st.spinner(f"Fetching mentions {start_str} → {end_str}…"):
    df = fetch_all_mentions(start_str, end_str)

if df.empty:
    st.warning("No mentions found for this date range.")
    st.stop()

if "categories" not in df.columns:
    df["categories"] = [[] for _ in range(len(df))]


# ─────────────────────────────────────────────
# KPI CARDS
# ─────────────────────────────────────────────

tid_set      = set(themes_cats.keys())
lid_set      = set(leader_cats.keys())
total_mentions = len(df)
themed_count   = df["categories"].apply(lambda c: bool(extract_cat_ids(c) & tid_set)).sum()
leader_count   = df["categories"].apply(lambda c: bool(extract_cat_ids(c) & lid_set)).sum()
dom_col        = next((c for c in ["domain", "site", "sourceName"] if c in df.columns), None)
unique_pubs    = df[dom_col].nunique() if dom_col else 0

st.markdown(f"""
<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-val">{total_mentions:,}</div>
    <div class="kpi-lbl">Total Mentions</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{themed_count:,}</div>
    <div class="kpi-lbl">Theme-Tagged</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{leader_count:,}</div>
    <div class="kpi-lbl">Leadership-Tagged</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{unique_pubs:,}</div>
    <div class="kpi-lbl">Unique Publishers</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{start_str}</div>
    <div class="kpi-lbl">Start Date</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-val">{end_str}</div>
    <div class="kpi-lbl">End Date</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# BUILD PIVOTS + LOOKUPS
# ─────────────────────────────────────────────

with st.spinner("Building pivot matrices…"):
    tl_matrix = build_cross_pivot(df, themes_cats, leader_cats)
    tp_matrix = build_theme_publisher_pivot(df, themes_cats, top_n=top_n_pubs)

    # Mention lookups for hover + click
    tl_lookup = build_mention_lookup(df, themes_cats, leader_cats)

    # Publisher lookup — uses the top pub list already computed in tp_matrix
    tp_top_pubs = list(tp_matrix.columns)
    tp_lookup   = build_mention_lookup_pub(df, themes_cats, tp_top_pubs)

if hide_zero_rows:
    tl_matrix = tl_matrix.loc[tl_matrix.sum(axis=1) > 0]
    tp_matrix = tp_matrix.loc[tp_matrix.sum(axis=1) > 0]


# ─────────────────────────────────────────────
# SECTION 1 — THEMES × LEADERSHIP
# ─────────────────────────────────────────────

st.markdown('<div class="sec-hdr">Themes × Leadership</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hint">HOVER over a cell to preview top mentions &nbsp;·&nbsp; '
    'CLICK a cell to expand article links below</div>',
    unsafe_allow_html=True,
)

if tl_matrix.empty or tl_matrix.values.sum() == 0:
    st.info("No co-tagged Themes × Leadership mentions found in this period.")
else:
    fig_tl = render_heatmap(
        tl_matrix,
        title="Themes × Leadership",
        x_title="Leadership",
        y_title="Theme",
        height=max(400, len(tl_matrix) * 38 + 220),
        mention_lookup=tl_lookup,
    )

    tl_event = st.plotly_chart(
        fig_tl,
        use_container_width=True,
        on_select="rerun",
        key="tl_chart",
        selection_mode="points",
    )

    # Handle click → show article panel
    tl_pts = (tl_event or {}).get("selection", {}).get("points", [])
    if tl_pts:
        pt          = tl_pts[0]
        theme_lbl   = pt.get("y", "")
        leader_lbl  = pt.get("x", "")
        if theme_lbl and leader_lbl:
            render_click_panel(
                tl_lookup, theme_lbl, leader_lbl,
                "Theme", "Leadership", "tl",
            )

    with st.expander("Raw table — Themes × Leadership"):
        st.dataframe(styled_table(tl_matrix), use_container_width=True)


# ─────────────────────────────────────────────
# SECTION 2 — THEMES × PUBLISHERS
# ─────────────────────────────────────────────

st.markdown(
    f'<div class="sec-hdr">Themes × Publishers — Top {top_n_pubs}</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="hint">HOVER over a cell to preview top mentions &nbsp;·&nbsp; '
    'CLICK a cell to expand article links below</div>',
    unsafe_allow_html=True,
)

if tp_matrix.empty or tp_matrix.values.sum() == 0:
    st.info("No theme-tagged publisher mentions found in this period.")
else:
    fig_tp = render_heatmap(
        tp_matrix,
        title=f"Themes × Publishers (Top {top_n_pubs})",
        x_title="Publisher",
        y_title="Theme",
        height=max(420, len(tp_matrix) * 38 + 240),
        mention_lookup=tp_lookup,
    )

    tp_event = st.plotly_chart(
        fig_tp,
        use_container_width=True,
        on_select="rerun",
        key="tp_chart",
        selection_mode="points",
    )

    # Handle click → show article panel
    tp_pts = (tp_event or {}).get("selection", {}).get("points", [])
    if tp_pts:
        pt         = tp_pts[0]
        theme_lbl  = pt.get("y", "")
        pub_lbl    = pt.get("x", "")
        if theme_lbl and pub_lbl:
            render_click_panel(
                tp_lookup, theme_lbl, pub_lbl,
                "Theme", "Publisher", "tp",
            )

    with st.expander("Raw table — Themes × Publishers"):
        st.dataframe(styled_table(tp_matrix), use_container_width=True)


# ─────────────────────────────────────────────
# SECTION 3 — TOP PUBLISHERS BAR CHART
# ─────────────────────────────────────────────

if dom_col:
    st.markdown(
        '<div class="sec-hdr">Top Publishers by Total Mention Volume</div>',
        unsafe_allow_html=True,
    )
    top_pub_df = (
        df[dom_col].fillna("Unknown").value_counts().head(20)
        .reset_index()
        .rename(columns={dom_col: "Publisher", "count": "Mentions"})
    )
    if "index" in top_pub_df.columns:
        top_pub_df.columns = ["Publisher", "Mentions"]

    fig_bar = go.Figure(go.Bar(
        x=top_pub_df["Mentions"],
        y=top_pub_df["Publisher"],
        orientation="h",
        marker_color="#ffffff",
        marker_line=dict(color="#000000", width=1),
        text=top_pub_df["Mentions"],
        textposition="outside",
        textfont=dict(color="#ffffff", size=11),
    ))
    fig_bar.update_layout(
        height=480,
        margin=dict(l=170, r=80, t=30, b=40),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=11, color="#ffffff"),
            linecolor="#ffffff", gridcolor="#222222",
        ),
        xaxis=dict(
            title=dict(text="Mentions", font=dict(color="#ffffff")),
            tickfont=dict(color="#ffffff"),
            linecolor="#ffffff", gridcolor="#222222",
        ),
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#ffffff"),
        hoverlabel=dict(
            bgcolor="#111111",
            bordercolor="#ffffff",
            font=dict(size=12, color="#ffffff"),
        ),
    )
    st.plotly_chart(fig_bar, use_container_width=True)
