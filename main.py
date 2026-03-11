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

THEMES_KEYWORD    = "theme"       # matches "Apollo Themes 25-26"
LEADERSHIP_KEYWORD = "leadership"  # matches "Leadership"


@st.cache_data(ttl=86_400, show_spinner=False)
def fetch_category_groups() -> list:
    resp = requests.get(CATS_URL, headers=HEADERS, timeout=20)
    if not resp.ok:
        st.error(f"Categories API {resp.status_code}: {resp.text[:300]}")
        return []
    data = resp.json()
    return data.get("results", data.get("categories", []))


def parse_category_tree(groups: list) -> dict:
    """
    Returns group_children: { group_name_lower: {child_id: child_name} }
    Walks the full tree so nested children are captured under their root group.
    """
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

        data  = resp.json()
        batch = data.get("results", [])
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
    dom_col = next((c for c in ["domain", "site", "sourceName"] if c in df.columns), None)
    df = df.copy()
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


def render_heatmap(matrix: pd.DataFrame, title: str, x_title: str, y_title: str,
                   height: int = 540) -> go.Figure:
    z = matrix.values.tolist()
    x = list(matrix.columns)
    y = list(matrix.index)
    text = [[str(v) if v > 0 else "" for v in row] for row in z]

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
        textfont={"size": 11, "color": "white", "family": "Arial Black"},
        colorscale=GOR_SCALE, showscale=True, hoverongaps=False,
        hovertemplate=(
            f"<b>{y_title}:</b> %{{y}}<br>"
            f"<b>{x_title}:</b> %{{x}}<br>"
            "<b>Mentions:</b> %{z}<extra></extra>"
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
    )
    return fig

def styled_table(matrix: pd.DataFrame):
    """
    Color cells: low = green, mid = orange, high = red. Zero cells = dark.
    No matplotlib required.
    """
    max_val = matrix.values.max() if matrix.values.max() > 0 else 1

    palette = [
        "#1a1a1a",  # 0  — zero / empty (dark)
        "#1a4d2e",  # 1  — very low (dark green)
        "#2d7a3a",  # 2  — low (green)
        "#52b44b",  # 3  — low-mid (bright green)
        "#a8c84a",  # 4  — mid (yellow-green)
        "#f5a623",  # 5  — mid-high (orange)
        "#e8732a",  # 6  — high (dark orange)
        "#d63b1f",  # 7  — very high (red-orange)
        "#b01010",  # 8  — max (deep red)
    ]

    def cell_color(val):
        if val == 0:
            return "background-color: #1a1a1a; color: #444444; font-weight:400;"
        ratio = val / max_val
        idx = 1 + min(int(ratio * 7.99), 7)
        bg  = palette[idx]
        fg  = "#ffffff"
        return f"background-color: {bg}; color: {fg}; font-weight: 700;"

    return matrix.style.applymap(cell_color).format("{:,.0f}")


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

/* Main area and sidebar backgrounds */
.stApp                                      { background: #000000 !important; }
section[data-testid="stSidebar"]            { background: #0a0a0a !important; border-right: 1px solid #ffffff; }
section[data-testid="stSidebar"] *          { color: #ffffff !important; }

/* All text white */
p, span, label, div, li, h1, h2, h3, h4   { color: #ffffff !important; }
.stMarkdown, .stCaption, .stText           { color: #ffffff !important; }

/* Inputs / widgets */
.stDateInput input, .stSlider, .stCheckbox { color: #ffffff !important filter: invert(1) hue-rotate(180deg); }
.stButton > button {
    background: black !important;
    color: #000000 !important;
    font-weight: 700;
    border: 2px solid #ffffff !important;
    border-radius: 0 !important;
    letter-spacing: .05em;
    font-family: 'Space Mono', monospace !important;
}
.stButton > button:hover {
    background: #000000 !important;
    color: #ffffff !important;
}

/* Expander */
details, summary                            { background: #000000 !important; color: #ffffff !important; border: 1px solid #ffffff !important; }
summary:hover                               { background: #111111 !important; }

/* Info / warning boxes */
.stInfo, .stWarning, .stError, .stSuccess  { filter: invert(1) hue-rotate(180deg); }

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

/* Dataframe / table */
.stDataFrame, iframe                        { background:#000000 !important; border:1px solid #ffffff; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<h1 style='color:#ffffff; margin-bottom:2px; margin-top:6px; font-family:"Space Mono",monospace; letter-spacing:.03em;'>
  APOLLO HOSPITALS
</h1>
<p style='color:#ffffff; font-size:.85rem; margin:0 0 8px; opacity:.55; letter-spacing:.1em; text-transform:uppercase; font-family:"Space Mono",monospace;'>
  Themes × Leadership &amp; Themes × Publishers
</p>
<hr style='border:1px solid #ffffff; margin-bottom:4px;'>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Date Range")
    start_date = st.date_input("Start Date", value=datetime(2025, 3, 10).date())
    end_date   = st.date_input("End Date",   value=datetime(2025, 3, 11).date())

    st.markdown("### Options")
    top_n_pubs    = st.slider("Top N Publishers", 5, 40, 15, 5)
    hide_zero_rows = st.checkbox("Hide zero-count theme rows", value=True)
    # show_ai       = st.checkbox("Generate AI Insights (Groq)", value=bool(GROQ_KEY))

    st.markdown("---")
    load_btn = st.button("Load Data", use_container_width=True, type="primary")

if start_date > end_date:
    st.error("Start date must be before end date.")
    st.stop()

if not load_btn:
    st.info("Select a date range and click **Load Data** to fetch live Brandwatch data.")
    st.stop()

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

# with st.expander("✅ Detected category groups", expanded=False):
#     c1, c2 = st.columns(2)
#     with c1:
#         st.markdown("**Themes**")
#         st.markdown(
#             " ".join(f'<span class="tag">{v}</span>' for v in themes_cats.values()),
#             unsafe_allow_html=True,
#         )
#     with c2:
#         st.markdown("**Leadership**")
#         st.markdown(
#             " ".join(f'<span class="tag">{v}</span>' for v in leader_cats.values()),
#             unsafe_allow_html=True,
#         )

start_str = start_date.strftime("%Y-%m-%d")
end_str   = end_date.strftime("%Y-%m-%d")

with st.spinner(f"Fetching mentions {start_str} → {end_str}…"):
    df = fetch_all_mentions(start_str, end_str)

if df.empty:
    st.warning("No mentions found for this date range.")
    st.stop()

if "categories" not in df.columns:
    df["categories"] = [[] for _ in range(len(df))]

tid_set = set(themes_cats.keys())
lid_set = set(leader_cats.keys())

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

with st.spinner("Building pivot matrices…"):
    tl_matrix = build_cross_pivot(df, themes_cats, leader_cats)
    tp_matrix = build_theme_publisher_pivot(df, themes_cats, top_n=top_n_pubs)

if hide_zero_rows:
    tl_matrix = tl_matrix.loc[tl_matrix.sum(axis=1) > 0]
    tp_matrix = tp_matrix.loc[tp_matrix.sum(axis=1) > 0]

st.markdown('<div class="sec-hdr">Themes × Leadership</div>', unsafe_allow_html=True)

if tl_matrix.empty or tl_matrix.values.sum() == 0:
    st.info("No co-tagged Themes × Leadership mentions found in this period.")
else:
    fig_tl = render_heatmap(
        tl_matrix,
        title="Themes × Leadership",
        x_title="Leadership",
        y_title="Theme",
        height=max(400, len(tl_matrix) * 38 + 220),
    )
    st.plotly_chart(fig_tl, use_container_width=True)
    with st.expander("Raw table — Themes × Leadership"):
        st.dataframe(styled_table(tl_matrix), use_container_width=True)

st.markdown(
    f'<div class="sec-hdr">Themes × Publishers — Top {top_n_pubs}</div>',
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
    )
    st.plotly_chart(fig_tp, use_container_width=True)
    with st.expander("Raw table — Themes × Publishers"):
        st.dataframe(styled_table(tp_matrix), use_container_width=True)

if dom_col:
    st.markdown('<div class="sec-hdr">Top Publishers by Total Mention Volume</div>', unsafe_allow_html=True)
    top_pub_df = (
        df[dom_col].fillna("Unknown").value_counts().head(20)
        .reset_index().rename(columns={dom_col: "Publisher", "count": "Mentions"})
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
        yaxis=dict(autorange="reversed", tickfont=dict(size=11, color="#ffffff"),
                   linecolor="#ffffff", gridcolor="#222222"),
        xaxis=dict(title=dict(text="Mentions", font=dict(color="#ffffff")),
                   tickfont=dict(color="#ffffff"), linecolor="#ffffff", gridcolor="#222222"),
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        font=dict(color="#ffffff"),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

