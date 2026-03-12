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

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os 

PROJECT_ID   = 1998348013
QUERY_ID     = 2003868554
BASE_URL     = f"https://api.brandwatch.com/projects/{PROJECT_ID}"
MENTIONS_URL = f"{BASE_URL}/data/mentions/"
CATS_URL     = f"{BASE_URL}/rulecategories"

BW_TOKEN = st.secrets.get("BRANDWATCH_TOKEN", "")
GROQ_KEY = st.secrets.get("GROQ_API_KEY", "")

HEADERS = {"Authorization": f"Bearer {BW_TOKEN}", "Accept": "application/json"}

THEMES_KEYWORD     = "theme"
LEADERSHIP_KEYWORD = "leadership"


@st.cache_data(ttl=86_400, show_spinner=False)
def fetch_category_groups() -> list:
    resp = requests.get(CATS_URL, headers=HEADERS, timeout=20)
    if not resp.ok:
        st.error(f"Categories API {resp.status_code}: {resp.text[:300]}")
        return []
    data = resp.json()
    return data.get("results", data.get("categories", []))


def parse_category_tree(groups: list) -> dict:
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

    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=y,
        text=text, texttemplate="%{text}",
        colorscale=[
            [0.000, "#1a1a1a"],
            [0.001, "#1a4d2e"],
            [0.143, "#2d7a3a"],
            [0.286, "#52b44b"],
            [0.429, "#a8c84a"],
            [0.571, "#f5a623"],
            [0.714, "#e8732a"],
            [0.857, "#d63b1f"],
            [1.000, "#b01010"],
        ], showscale=True, hoverongaps=False,
        hovertemplate=(
            f"<b>{y_title}:</b> %{{y}}<br>"
            f"<b>{x_title}:</b> %{{x}}<br>"
            "<b>Mentions:</b> %{z}<extra></extra>"
        ),
    ))
    fig.update_layout(
        title=title,
        xaxis=dict(title=x_title, tickangle=-38, side="bottom"),
        yaxis=dict(title=y_title, autorange="reversed"),
        height=height,
        margin=dict(l=250, r=90, t=65, b=185),
    )
    return fig


# --- App layout ---

st.set_page_config(
    page_title="Apollo",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Apollo Hospitals")
st.caption("Themes × Leadership & Themes × Publishers")

with st.sidebar:
    st.header("Date Range")
    start_date = st.date_input("Start Date", value=datetime(2025, 3, 10).date())
    end_date   = st.date_input("End Date",   value=datetime(2025, 3, 11).date())

    st.header("Options")
    top_n_pubs     = st.slider("Top N Publishers", 5, 40, 15, 5)
    hide_zero_rows = st.checkbox("Hide zero-count theme rows", value=True)

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

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Mentions", f"{total_mentions:,}")
col2.metric("Theme-Tagged", f"{themed_count:,}")
col3.metric("Leadership-Tagged", f"{leader_count:,}")
col4.metric("Unique Publishers", f"{unique_pubs:,}")

with st.spinner("Building pivot matrices…"):
    tl_matrix = build_cross_pivot(df, themes_cats, leader_cats)
    tp_matrix = build_theme_publisher_pivot(df, themes_cats, top_n=top_n_pubs)

if hide_zero_rows:
    tl_matrix = tl_matrix.loc[tl_matrix.sum(axis=1) > 0]
    tp_matrix = tp_matrix.loc[tp_matrix.sum(axis=1) > 0]

st.subheader("Themes × Leadership")

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
        st.dataframe(tl_matrix, use_container_width=True)

st.subheader(f"Themes × Publishers — Top {top_n_pubs}")

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
        st.dataframe(tp_matrix, use_container_width=True)

if dom_col:
    st.subheader("Top Publishers by Total Mention Volume")
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
        text=top_pub_df["Mentions"],
        textposition="outside",
    ))
    fig_bar.update_layout(
        height=480,
        margin=dict(l=170, r=80, t=30, b=40),
        yaxis=dict(autorange="reversed"),
        xaxis=dict(title="Mentions"),
    )
    st.plotly_chart(fig_bar, use_container_width=True)
