"""
Media Intelligence Dashboard — Apollo, Indigo & Cred
Install: pip install streamlit streamlit-plotly-events plotly requests pandas openai
"""

import os
import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, date as _date, timedelta as _td
from streamlit_plotly_events import plotly_events

# ── Client Configs ───────────────────────────────────────────────────────────
CLIENTS = {
    "Apollo Hospitals": {
        "PROJECT_ID":          1998348013,
        "QUERY_ID":            2003868554,
        "THEMES_KEYWORD":      "BWHM_Key Themes",
        "LEADERSHIP_KEYWORD":  "BWHM_Leadership",
        "ACCENT":              "#e63946",
        "BADGE_BG":            "#3a1a1a",
        "LOGO_EMOJI":          "",
        "PUBLISHERS": [
            "financialexpress.com",
            "thehindu.com",
            "news18.com",
            "newindianexpress.com",
            "theweek.in",
            "hindustantimes.com",
            "businesstoday.in",
            "indiatoday.in",
            "ndtvprofit.com",
            "deccanchronicle.com",
            "indianexpress.com",
            "indiatimes.com",
            "livemint.com",
            "moneycontrol.com",
            "timesnownews.com",
            "business-standard.com",
            "aninews.in",
            "thehindubusinessline.com",
            "ndtv.com",
            "republicworld.com"
        ]
    },
    "Indigo": {
        "PROJECT_ID":          1998400453,
        "QUERY_ID":            2003736894,
        "THEMES_KEYWORD":      "BWHM_Key Themes",
        "LEADERSHIP_KEYWORD":  "BWHM_Leadership",
        "ACCENT":              "#4a9eff",
        "BADGE_BG":            "#0d1f3a",
        "LOGO_EMOJI":          "",
        "PUBLISHERS": [
            "hindustantimes.com",
            "ndtv.com",
            "moneycontrol.com",
            "indiatimes.com",
            "indianexpress.com",
            "thehindu.com",
            "indiatoday.in",
            "livemint.com",
            "news18.com",
            "timesnownews.com",
            "india.com",
            "financialexpress.com",
            "business-standard.com",
            "cnbctv18.com",
            "newindianexpress.com",
            "tribuneindia.com",
            "telegraphindia.com",
            "travelandtourworld.com",
            "businesstoday.in",
            "thehindubusinessline.com",
            "republicworld.com",
            "mathrubhumi.com",
            "theweek.in",
            "latestly.com"
        ]
    },
    "Cred": {
        "PROJECT_ID":          1998394120,
        "QUERY_ID":            2003727092,
        "THEMES_KEYWORD":      "BWHM_Key Themes",
        "LEADERSHIP_KEYWORD":  "BWHM_Leadership",
        "ACCENT":              "#a259f7",
        "BADGE_BG":            "#1e0d3a",
        "LOGO_EMOJI":          "",
        "PUBLISHERS": [
            "financialexpress.com",
            "inc42.com",
            "thehindu.com",
            "etnownews.com",
            "forbesindia.com",
            "fortuneindia.com",
            "theprint.in",
            "ndtvprofit.com",
            "thewire.in",
            "exchange4media.com",
            "firstpost.com",
            "india.com",
            "business-standard.com",
            "techstory.in",
            "news18.com",
            "yourstory.com",
            "indiatoday.in",
            "businessworld.in",
            "indiatv.in",
            "afaqs.com",
            "ptinews.com",
            "timesnownews.com",
            "storyboard18.com",
            "telegraphindia.com",
            "socialsamosa.com",
            "ianslive.in",
            "investing.com",
            "medianews4u.com",
            "theweek.in",
            "rbi.org.in",
            "hindustantimes.com",
            "abplive.com",
            "dnaindia.com",
            "tribuneindia.com",
            "deccanchronicle.com",
            "cxodigitalpulse.com",
            "the-ken.com",
            "indianexpress.com",
            "cnbctv18.com",
            "moneycontrol.com",
            "aninews.in",
            "thehindubusinessline.com",
            "ians.in",
            "cxotoday.com",
            "entrackr.com",
            "businesstoday.in",
            "indiatimes.com",
            "livemint.com",
            "ndtv.com",
            "themorningcontext.com",
            "republicworld.com"
        ]
    },
}

SOCIAL_DOMAINS = {
    "youtube.com", "facebook.com", "instagram.com",
    "twitter.com", "linkedin.com", "reddit.com", "x.com",
}

BW_TOKEN = st.secrets.get("BRANDWATCH_TOKEN", "")
GROQ_KEY = st.secrets.get("GROQ_API_KEY", "")

HEADERS  = {"Authorization": f"Bearer {BW_TOKEN}", "Accept": "application/json"}

OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o-mini"

BG           = "#0f1117"
CARD_BG      = "#1a1d27"
BORDER       = "#2a2d3e"
TEXT_PRIMARY = "#f0f2f5"
TEXT_MUTED   = "#8b8fa8"
GREEN        = "#2dc653"
ORANGE       = "#f4a261"
RED          = "#e63946"

HEATMAP_SCALE = [
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

st.set_page_config(
    page_title="Media Intelligence Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0f1117 !important;
    color: #f0f2f5 !important;
}
.stApp { background: #0f1117 !important; }

section[data-testid="stSidebar"] {
    background: #13151f !important;
    border-right: 1px solid #2a2d3e !important;
}
section[data-testid="stSidebar"] * { color: #f0f2f5 !important; }
section[data-testid="stSidebar"] .stMarkdown h3 {
    font-size: 0.7rem !important;
    letter-spacing: 0.12em !important;
    text-transform: uppercase !important;
    color: #8b8fa8 !important;
    margin-top: 1.4rem !important;
    margin-bottom: 0.5rem !important;
    font-weight: 600 !important;
}

.stButton > button[kind="primary"] {
    background: var(--accent, #e63946) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.55rem 1.2rem !important;
    letter-spacing: 0.03em !important;
    transition: opacity 0.15s !important;
}
.stButton > button[kind="primary"]:hover { opacity: 0.85 !important; }

.stButton > button:not([kind="primary"]) {
    background: #1a1d27 !important;
    color: #8b8fa8 !important;
    border: 1px solid #2a2d3e !important;
    border-radius: 6px !important;
    font-size: 0.78rem !important;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #8b8fa8 !important;
    color: #f0f2f5 !important;
}

[data-testid="metric-container"] {
    background: #1a1d27 !important;
    border: 1px solid #2a2d3e !important;
    border-radius: 12px !important;
    padding: 1rem 1.2rem !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #f0f2f5 !important;
    font-family: 'DM Mono', monospace !important;
}
[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: #8b8fa8 !important;
}

.section-label {
    display: flex; align-items: center; gap: 10px; margin: 2rem 0 0.25rem;
}
.section-label-text {
    font-size: 0.72rem; font-weight: 600; letter-spacing: 0.14em;
    text-transform: uppercase; color: #8b8fa8;
}
.section-label-line { flex: 1; height: 1px; background: #2a2d3e; }

.section-title {
    font-size: 1.25rem; font-weight: 700; color: #f0f2f5;
    margin: 0 0 0.2rem; line-height: 1.3;
}
.section-sub { font-size: 0.8rem; color: #8b8fa8; margin: 0 0 1rem; }

.panel-placeholder {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; height: 320px; background: #1a1d27;
    border: 1.5px dashed #2a2d3e; border-radius: 12px;
    color: #4a4e66; font-size: 0.85rem; text-align: center; gap: 10px;
}
.panel-placeholder .icon { font-size: 2rem; opacity: 0.4; }

/* ── AI Insights Card ── */
.ai-insights-card {
    background: linear-gradient(135deg, #1a1d27 0%, #151824 100%);
    border: 1px solid #2a2d3e;
    border-left: 3px solid #a259f7;
    border-radius: 12px;
    padding: 1.2rem 1.4rem;
    margin: 1rem 0;
    position: relative;
}
.ai-insights-card::before {
    content: "✦ AI INSIGHTS";
    position: absolute;
    top: -0.55rem;
    left: 1rem;
    background: #0f1117;
    padding: 0 8px;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: #a259f7;
    font-family: 'DM Mono', monospace;
}
.ai-insights-bullet {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 7px;
}
.ai-insights-bullet-dot {
    color: #a259f7;
    font-size: 0.7rem;
    margin-top: 5px;
    flex-shrink: 0;
}
.ai-insights-text {
    font-size: 0.875rem;
    color: #c8cde0;
    line-height: 1.7;
    margin: 0;
}

hr { border-color: #2a2d3e !important; margin: 1.5rem 0 !important; }
.stDataFrame { border: 1px solid #2a2d3e !important; border-radius: 8px !important; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0f1117; }
::-webkit-scrollbar-thumb { background: #2a2d3e; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4a4e66; }
.stAlert { background: #1a1d27 !important; border-color: #2a2d3e !important; }
.streamlit-expanderHeader {
    background: #1a1d27 !important; border: 1px solid #2a2d3e !important;
    border-radius: 8px !important; color: #8b8fa8 !important; font-size: 0.78rem !important;
}
</style>
""", unsafe_allow_html=True)

def call_openai(system_prompt: str, user_prompt: str, max_tokens: int = 600) -> str:
    """Call OpenAI Chat Completions and return the assistant text."""
    if not OPENAI_API_KEY:
        return "⚠️ Set OPENAI_API_KEY environment variable to enable AI insights."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"AI insight unavailable: {e}"


@st.cache_data(ttl=3_600, show_spinner=False)
def generate_dashboard_insights(
    client_name: str,
    total_mentions: int,
    themed_count: int,
    leader_count: int,
    unique_pubs: int,
    top_themes: str,
    top_leaders: str,
    date_range: str,
) -> str:
    system = (
        "You are a senior media intelligence analyst. "
        "Your output must be plain text only — no markdown, no asterisks, no headers. "
        "Return exactly 5 bullet points, each on its own line, starting with a dash (-)."
    )
    user = f"""Summarise the following media monitoring data for {client_name} over {date_range}.

Numbers:
- Total mentions: {total_mentions:,}
- Theme-tagged: {themed_count:,} ({themed_count / max(total_mentions, 1) * 100:.1f}% of total)
- Leadership-tagged: {leader_count:,} ({leader_count / max(total_mentions, 1) * 100:.1f}% of total)
- Unique publishers: {unique_pubs:,}
- Top themes: {top_themes}
- Top leaders: {top_leaders}

Write exactly 5 bullet points (each starting with -) covering:
1. Overall media volume and what it signals
2. Dominant narrative themes in coverage
3. Leadership visibility — who is driving attention and why
4. Publisher diversity and reach quality
5. One sharp, actionable strategic recommendation for the comms team

Keep every bullet under 30 words. Plain text only."""

    return call_openai(system, user, max_tokens=500)


@st.cache_data(ttl=3_600, show_spinner=False)
def generate_cell_summary(
    client_name: str,
    row_label: str,
    col_label: str,
    row_type: str,
    col_type: str,
    titles_and_snippets: str,
    mention_count: int,
) -> str:
    system = (
        "You are a media intelligence analyst. "
        "Write in plain prose — no bullet points, no markdown, no asterisks. "
        "Be concise and direct."
    )
    user = f"""A PR professional clicked on a heatmap cell for {client_name}.

Cell: {row_type} = "{row_label}"  x  {col_type} = "{col_label}"
Total articles in cell: {mention_count}

Article titles and snippets (sample of up to 15):
{titles_and_snippets}

Write a 3-4 sentence plain-text summary (max 90 words) that explains:
- What story or narrative connects these articles
- Any common event, angle, or sentiment driving this coverage
- What a PR/comms professional should know or watch

Plain prose only. No lists. No markdown."""

    return call_openai(system, user, max_tokens=220)

@st.cache_data(ttl=86_400, show_spinner=False)
def fetch_category_groups(project_id: int) -> list:
    url  = f"https://api.brandwatch.com/projects/{project_id}/rulecategories"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    if not resp.ok:
        st.error(f"Categories API {resp.status_code}: {resp.text[:300]}")
        return []
    data = resp.json()
    return data.get("results", data.get("categories", []))


def parse_category_tree(groups: list) -> dict:
    def collect_descendants(node: dict) -> dict:
        result = {}
        for child in node.get("children", []):
            cid   = child.get("id")
            cname = child.get("name", "")
            if cid:
                result[int(cid)] = cname
            result.update(collect_descendants(child))
        return result

    group_children: dict[str, dict[int, str]] = {}
    for group in groups:
        gname = group.get("name", "").lower()
        group_children[gname] = collect_descendants(group)
    return group_children


def find_group(group_children: dict, keyword: str) -> dict:
    kw = keyword.lower()
    if kw in group_children:
        return group_children[kw]
    for gname, children in group_children.items():
        if kw in gname:
            return children
    return {}

@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_all_mentions(
    project_id: int, query_id: int, start: str, end: str, page_size: int = 2500
) -> pd.DataFrame:
    import time

    mentions_url = f"https://api.brandwatch.com/projects/{project_id}/data/mentions/"
    all_rows     = []
    page         = 0
    nextCursor   = ""
    progress     = st.progress(0, text="Fetching mentions…")

    MAX_RETRIES = 3
    TIMEOUT     = 120  # seconds

    session = requests.Session()
    session.headers.update(HEADERS)

    while True:
        params = {
            "queryId":        query_id,
            "startDate":      start,
            "endDate":        end,
            "pageSize":       page_size,
            "pageType":       "news",
            "orderBy":        "date",
            "orderDirection": "asc",
            "cursor":         nextCursor,
        }

        # ── Retry loop ────────────────────────────────────────────────────
        resp = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = session.get(mentions_url, params=params, timeout=TIMEOUT)
                break  # success
            except requests.exceptions.ReadTimeout:
                if attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt  # 1s → 2s → 4s
                    progress.progress(
                        min(len(all_rows) / max(len(all_rows) + 1, 1), 1.0),
                        text=f"Timeout on page {page + 1}, retrying in {wait}s… "
                             f"(attempt {attempt + 2}/{MAX_RETRIES})",
                    )
                    time.sleep(wait)
                else:
                    progress.empty()
                    st.error(
                        f"Brandwatch API timed out after {MAX_RETRIES} attempts "
                        f"on page {page + 1}. Returning {len(all_rows):,} mentions fetched so far."
                    )
                    return pd.DataFrame(all_rows) if all_rows else pd.DataFrame()

        if resp is None or not resp.ok:
            st.error(f"Mentions API {resp.status_code}: {resp.text[:300]}")
            break

        data       = resp.json()
        batch      = data.get("results", [])
        total_r    = data.get("totalResults", data.get("resultsTotal", None))
        nextCursor = data.get("nextCursor", "")
        all_rows.extend(batch)
        fetched = len(all_rows)

        if total_r and total_r > 0:
            progress.progress(
                min(fetched / total_r, 1.0),
                text=f"Fetching {fetched:,} / {total_r:,}…",
            )

        if len(batch) < page_size or not nextCursor:
            break

        page += 1
        if page > 40:
            st.warning("Page cap reached (40). Results may be incomplete.")
            break

    progress.empty()
    session.close()
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


def get_dom_col(df):
    return next((c for c in ["domain", "site", "sourceName"] if c in df.columns), None)


def _is_social(pub: str) -> bool:
    pl = pub.lower()
    return any(s in pl for s in SOCIAL_DOMAINS)


def build_cross_pivot(df, row_cats, col_cats):
    matrix = pd.DataFrame(
        0, index=list(row_cats.values()), columns=list(col_cats.values())
    )
    for cell in df["categories"]:
        ids = extract_cat_ids(cell)
        for r in [row_cats[i] for i in ids if i in row_cats]:
            for c in [col_cats[i] for i in ids if i in col_cats]:
                matrix.loc[r, c] += 1
    return matrix


def build_theme_publisher_pivot(df, theme_cats, allowed_pubs):
    dom_col = get_dom_col(df)
    df = df.copy()
    df["_pub"] = df[dom_col].fillna("Unknown") if dom_col else "Unknown"
    allowed_set = set(allowed_pubs)
    matrix      = pd.DataFrame(0, index=list(theme_cats.values()), columns=allowed_pubs)
    tid_set     = set(theme_cats.keys())
    for _, row in df.iterrows():
        pub = row["_pub"]
        if pub not in allowed_set:
            continue
        for i in extract_cat_ids(row.get("categories", [])):
            if i in tid_set:
                matrix.loc[theme_cats[i], pub] += 1
    return matrix


def _rec(row) -> dict:
    dom = row.get("domain") or row.get("site") or row.get("sourceName") or ""
    dom = str(dom) if dom and not isinstance(dom, float) else ""
    return dict(
        title     = str(row.get("title") or "").strip(),
        snippet   = str(row.get("snippet") or "").strip(),
        url       = str(row.get("originalUrl") or row.get("url") or ""),
        domain    = dom,
        date      = str(row.get("date") or "")[:10],
        pub       = str(row.get("publicationName") or row.get("unifiedSourceName") or dom or ""),
        sentiment = str(row.get("sentiment") or ""),
    )


def build_mention_lookup(df, row_cats, col_cats):
    lookup: dict = {}
    for _, row in df.iterrows():
        ids = extract_cat_ids(row.get("categories", []))
        rec = _rec(row)
        for r in [row_cats[i] for i in ids if i in row_cats]:
            for c in [col_cats[i] for i in ids if i in col_cats]:
                lookup.setdefault((r, c), []).append(rec)
    return lookup


def build_mention_lookup_pub(df, theme_cats, allowed_pubs):
    dom_col     = get_dom_col(df)
    allowed_set = set(allowed_pubs)
    lookup: dict = {}
    for _, row in df.iterrows():
        pub = (row.get(dom_col) if dom_col else None) or "Unknown"
        if pub not in allowed_set:
            continue
        rec = _rec(row)
        for i in extract_cat_ids(row.get("categories", [])):
            if i in theme_cats:
                lookup.setdefault((theme_cats[i], pub), []).append(rec)
    return lookup


def styled_table(matrix):
    stops  = [0.000, 0.001, 0.143, 0.286, 0.429, 0.571, 0.714, 0.857, 1.000]
    colors = [
        "#1a1a1a", "#1a4d2e", "#2d7a3a", "#52b44b",
        "#a8c84a", "#f5a623", "#e8732a", "#d63b1f", "#b01010",
    ]
    text_colors = [
        "#888888", "#ffffff", "#ffffff", "#ffffff",
        "#1a1a1a", "#1a1a1a", "#ffffff", "#ffffff", "#ffffff",
    ]
    max_val = matrix.values.max() if matrix.values.max() > 0 else 1

    def style_cell(val):
        n   = val / max_val
        idx = 0
        for i, s in enumerate(stops):
            if n >= s:
                idx = i
        bg = colors[idx]; tc = text_colors[idx]
        fw = "400" if val == 0 else "700"
        return f"background-color:{bg}; color:{tc}; font-weight:{fw}; text-align:center;"

    return matrix.style.applymap(style_cell).format("{:,.0f}")


def build_heatmap(matrix, title, x_title, y_title, height=500):
    z   = matrix.values.tolist()
    x   = list(matrix.columns)
    y   = list(matrix.index)
    arr = matrix.values.astype(float)
    max_val = arr.max() if arr.max() > 0 else 1
    norm    = arr / max_val

    annotations = []
    for ri, row_label in enumerate(y):
        for ci, col_label in enumerate(x):
            val   = z[ri][ci]
            n     = norm[ri][ci]
            color = "#1a1a1a" if 0.30 <= n <= 0.75 else "#ffffff"
            annotations.append(dict(
                x=col_label, y=row_label,
                text=f"<b>{val}</b>",
                showarrow=False,
                font=dict(size=12, color=color, family="Arial Black"),
                xref="x", yref="y",
            ))

    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=y,
        colorscale=HEATMAP_SCALE,
        showscale=True,
        hoverongaps=False,
        hovertemplate=(
            f"<b>{y_title}:</b> %{{y}}<br>"
            f"<b>{x_title}:</b> %{{x}}<br>"
            "<b>Mentions:</b> %{z}<extra></extra>"
        ),
        colorbar=dict(
            thickness=14, len=0.85,
            title=dict(text="Count", font=dict(size=11, color="#8b8fa8")),
            tickfont=dict(size=10, color="#8b8fa8"),
            outlinewidth=0, bgcolor="rgba(0,0,0,0)",
        ),
    ))
    fig.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family="DM Sans, sans-serif", color=TEXT_PRIMARY),
        title=dict(
            text=title,
            font=dict(size=14, color=TEXT_MUTED, family="DM Sans"),
            x=0.0, xanchor="left",
        ),
        xaxis=dict(
            title=dict(text=x_title, font=dict(size=11, color=TEXT_MUTED)),
            tickangle=-35, tickfont=dict(size=10, color=TEXT_MUTED),
            side="bottom", gridcolor=BORDER, linecolor=BORDER,
        ),
        yaxis=dict(
            title=dict(text=y_title, font=dict(size=11, color=TEXT_MUTED)),
            tickfont=dict(size=10, color=TEXT_MUTED),
            autorange="reversed", gridcolor=BORDER, linecolor=BORDER,
        ),
        height=height,
        margin=dict(l=220, r=60, t=55, b=160),
        annotations=annotations,
        hoverlabel=dict(
            bgcolor="#1a1d27", bordercolor=BORDER,
            font=dict(size=11, color=TEXT_PRIMARY, family="DM Mono"),
        ),
    )
    return fig


def render_panel(
    lookup, row_label, col_label, row_title, col_title,
    client_name, max_rows=30, panel_height=640,
):
    import html as hlib
    import streamlit.components.v1 as components

    mentions = lookup.get((row_label, col_label), [])
    count    = len(mentions)

    sent_map = {
        "positive": ("#0d2818", "#4ade80", "#166534"),
        "negative": ("#2d0f0f", "#f87171", "#7f1d1d"),
        "neutral":  ("#1e2030", "#94a3b8", "#334155"),
    }

    # ── OpenAI summary of the clicked cell ──────────────────────────────────
    summary_html = ""
    if mentions and OPENAI_API_KEY:
        sample = mentions[:15]
        titles_and_snippets = "\n".join(
            f"- {m['title'] or '(no title)'}: {(m['snippet'] or '')[:120]}"
            for m in sample
        )
        cache_key = f"cell_summary__{client_name}__{row_label}__{col_label}"
        if cache_key not in st.session_state:
            with st.spinner("Generating AI summary…"):
                st.session_state[cache_key] = generate_cell_summary(
                    client_name=client_name,
                    row_label=row_label,
                    col_label=col_label,
                    row_type=row_title,
                    col_type=col_title,
                    titles_and_snippets=titles_and_snippets,
                    mention_count=count,
                )
        ai_text = st.session_state[cache_key]
        summary_html = (
            f'<div style="background:linear-gradient(135deg,#161a2a,#12151f);'
            f'border:1px solid #252a3a;border-left:3px solid #4a9eff;'
            f'border-radius:10px;padding:14px 16px;margin-bottom:14px;">'
            f'<div style="font-size:0.6rem;font-weight:700;letter-spacing:0.18em;'
            f'color:#4a9eff;text-transform:uppercase;font-family:DM Mono,monospace;'
            f'margin-bottom:8px;">✦ AI SUMMARY</div>'
            f'<div style="font-size:0.8rem;color:#94a3b8;line-height:1.65;">'
            f'{hlib.escape(ai_text)}</div></div>'
        )

    # ── Article cards ────────────────────────────────────────────────────────
    cards_html = ""
    for m in mentions[:max_rows]:
        pub     = hlib.escape(str(m["pub"] or m["domain"] or "Unknown"))
        title   = hlib.escape(str(m["title"] or m["snippet"][:90] or "(untitled)").strip())
        snippet = hlib.escape(str(m["snippet"] or "")[:200])
        url     = m["url"] or ""
        date    = hlib.escape(m["date"] or "")
        sent    = m["sentiment"] or ""
        sbg, sc, sbd = sent_map.get(sent, sent_map["neutral"])

        badge = (
            f'<span style="display:inline-block;font-size:0.6rem;font-weight:700;padding:2px 8px;'
            f'border-radius:20px;margin-left:8px;vertical-align:middle;text-transform:uppercase;'
            f'letter-spacing:0.07em;font-family:DM Mono,monospace;background:{sbg};color:{sc};'
            f'border:1px solid {sbd};">{hlib.escape(sent)}</span>'
        ) if sent else ""

        if url:
            title_el = (
                f'<a href="{hlib.escape(url)}" target="_blank" rel="noopener"'
                f' style="font-weight:600;font-size:0.87rem;color:#e2e8f0;text-decoration:none;line-height:1.45;"'
                f' onmouseover="this.style.color=\'#f4a261\'"'
                f' onmouseout="this.style.color=\'#e2e8f0\'">{title}</a>'
            )
        else:
            title_el = (
                f'<span style="font-weight:600;font-size:0.87rem;color:#e2e8f0;">{title}</span>'
            )

        snippet_el = (
            f'<div style="font-size:0.77rem;color:#64748b;margin-top:6px;line-height:1.55;">'
            f'{snippet}...</div>'
        ) if snippet else ""

        card = (
            f'<div style="background:#161925;border:1px solid #252a3a;border-left:3px solid #e07040;'
            f'border-radius:0 10px 10px 0;padding:13px 16px;margin-bottom:10px;"'
            f' onmouseover="this.style.background=\'#1c2235\';this.style.borderLeftColor=\'#f4d160\'"'
            f' onmouseout="this.style.background=\'#161925\';this.style.borderLeftColor=\'#e07040\'">'
            f'<div>{title_el}{badge}</div>'
            f'<div style="font-size:0.7rem;color:#475569;margin-top:5px;font-family:DM Mono,monospace;">'
            f'{pub} &nbsp;&middot;&nbsp; {date}</div>'
            f'{snippet_el}</div>'
        )
        cards_html += card

    no_data = (
        '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;'
        'height:180px;color:#334155;font-size:0.85rem;gap:8px;">'
        '<span style="font-size:1.8rem;opacity:0.35;">&#x1F50D;</span>No mentions for this cell.</div>'
    ) if not mentions else ""

    hdr = (
        f'<div style="background:#161925;border:1px solid #252a3a;border-radius:10px;'
        f'padding:12px 16px;margin-bottom:12px;position:sticky;top:0;z-index:10;">'
        f'<div style="font-size:0.98rem;font-weight:700;color:#f1f5f9;">{hlib.escape(row_label)}</div>'
        f'<div style="font-size:0.7rem;color:#64748b;margin-top:3px;font-family:DM Mono,monospace;">'
        f'{hlib.escape(col_title)}: <strong style="color:#94a3b8;">{hlib.escape(col_label)}</strong>'
        f' &nbsp;&middot;&nbsp; {count} mention{"s" if count != 1 else ""}</div></div>'
    )

    html = f"""<!DOCTYPE html><html><head>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ background:#0f1117; font-family:'DM Sans',sans-serif; padding:4px 4px 4px 2px; }}
::-webkit-scrollbar {{ width:5px; }}
::-webkit-scrollbar-track {{ background:#0f1117; }}
::-webkit-scrollbar-thumb {{ background:#252a3a; border-radius:3px; }}
</style></head>
<body>{hdr}{summary_html}{cards_html}{no_data}</body></html>"""

    components.html(html, height=panel_height, scrolling=True)


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — CLIENT SELECTOR + CONTROLS
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("### Client")

    client_names = list(CLIENTS.keys())
    if "selected_client" not in st.session_state:
        st.session_state["selected_client"] = client_names[0]

    prev_client = st.session_state["selected_client"]

    chosen = st.selectbox(
        label="Select client",
        options=client_names,
        index=client_names.index(st.session_state["selected_client"]),
        format_func=lambda n: f"{CLIENTS[n]['LOGO_EMOJI']}  {n}",
        label_visibility="collapsed",
    )

    if chosen != prev_client:
        st.session_state["selected_client"] = chosen
        st.session_state["data_loaded"]      = False
        st.session_state["tl_click"]         = None
        st.session_state["tp_click"]         = None

    selected_client = st.session_state["selected_client"]
    client_cfg      = CLIENTS[selected_client]

    st.markdown("### Date Range")
    start_date = _date.today() - _td(days=30)
    end_date   = _date.today()
    st.markdown(
        f'<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:8px;'
        f'padding:10px 14px;margin-bottom:6px;">'
        f'<div style="font-size:0.68rem;color:#8b8fa8;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:4px;">Start Date</div>'
        f'<div style="font-size:0.95rem;font-weight:600;color:#f0f2f5;">'
        f'{start_date.strftime("%d %b %Y")}</div></div>'
        f'<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:8px;'
        f'padding:10px 14px;">'
        f'<div style="font-size:0.68rem;color:#8b8fa8;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:4px;">End Date</div>'
        f'<div style="font-size:0.95rem;font-weight:600;color:#f0f2f5;">'
        f'{end_date.strftime("%d %b %Y")}</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("Showing last 30 days")

    st.markdown("### Options")
    hide_zero_rows = st.checkbox("Hide zero rows", value=True)
    max_click_rows = st.slider("Articles per click", 5, 30, 10, 5)

    st.markdown("---")
    load_btn = st.button("⟳  Load Data", use_container_width=True, type="primary")


# ═══════════════════════════════════════════════════════════════════════════
# HEADER — dynamic per client
# ═══════════════════════════════════════════════════════════════════════════

accent     = client_cfg["ACCENT"]
badge_bg   = client_cfg["BADGE_BG"]
logo_emoji = client_cfg["LOGO_EMOJI"]

st.markdown(f"""
<div style="display:flex; align-items:baseline; gap:14px; padding: 0.5rem 0 0.25rem;">
    <span style="font-size:1.6rem; font-weight:800; color:#f0f2f5; letter-spacing:-0.02em;">
        {logo_emoji} {selected_client}
    </span>
    <span style="font-size:0.72rem; font-weight:600; letter-spacing:0.14em;
                 text-transform:uppercase; color:{accent}; background:{badge_bg};
                 padding:3px 10px; border-radius:20px;">
        Media Intelligence
    </span>
</div>
<div style="font-size:0.82rem; color:#8b8fa8; margin-bottom:1rem;">
    Themes x Leadership &nbsp;·&nbsp; Themes x Publishers
</div>
<hr>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# GUARDS
# ═══════════════════════════════════════════════════════════════════════════

if load_btn:
    st.session_state.update({
        "data_loaded":       True,
        "load_start":        start_date.strftime("%Y-%m-%d"),
        "load_end":          end_date.strftime("%Y-%m-%d"),
        "load_hide_z":       hide_zero_rows,
        "load_client":       selected_client,
        "tl_click":          None,
        "tp_click":          None,
        "dashboard_insight": None,   # reset on fresh load
    })

if not st.session_state.get("data_loaded"):
    st.markdown("""
    <div class="panel-placeholder" style="height:420px; border-radius:16px; margin-top:2rem;">
        <div class="icon">📡</div>
        <div style="font-size:1rem; font-weight:600; color:#4a4e66;">No data loaded</div>
        <div>Select a client and click <b style="color:#e63946;">Load Data</b></div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Use the client that was active at load time (not current selection)
loaded_client = st.session_state.get("load_client", selected_client)
loaded_cfg    = CLIENTS.get(loaded_client, client_cfg)

start_str      = st.session_state["load_start"]
end_str        = st.session_state["load_end"]
hide_zero_rows = st.session_state["load_hide_z"]

project_id         = loaded_cfg["PROJECT_ID"]
query_id           = loaded_cfg["QUERY_ID"]
themes_keyword     = loaded_cfg["THEMES_KEYWORD"]
leadership_keyword = loaded_cfg["LEADERSHIP_KEYWORD"]

if loaded_client != selected_client:
    st.info(
        f"Showing data for **{loaded_client}**. "
        f"Click **Load Data** to switch to {selected_client}."
    )


# ═══════════════════════════════════════════════════════════════════════════
# FETCH
# ═══════════════════════════════════════════════════════════════════════════

with st.spinner("Loading categories…"):
    raw_groups = fetch_category_groups(project_id)

if not raw_groups:
    st.error("Failed to load categories.")
    st.stop()

group_children = parse_category_tree(raw_groups)
themes_cats    = find_group(group_children, themes_keyword)
leader_cats    = find_group(group_children, leadership_keyword)

if not themes_cats:
    st.error(
        f"No '{themes_keyword}' group found. "
        f"Available: {list(group_children.keys())}"
    )
    st.stop()
if not leader_cats:
    st.error(
        f"No '{leadership_keyword}' group found. "
        f"Available: {list(group_children.keys())}"
    )
    st.stop()

with st.spinner(f"Fetching mentions for {loaded_client} — {start_str} to {end_str}…"):
    df = fetch_all_mentions(project_id, query_id, start_str, end_str)

if df.empty:
    st.warning("No mentions found for this date range.")
    st.stop()

if "categories" not in df.columns:
    df["categories"] = [[] for _ in range(len(df))]

dom_col = get_dom_col(df)


# ═══════════════════════════════════════════════════════════════════════════
# KPI STRIP
# ═══════════════════════════════════════════════════════════════════════════

tid_set        = set(themes_cats.keys())
lid_set        = set(leader_cats.keys())
total_mentions = len(df)
themed_count   = df["categories"].apply(lambda c: bool(extract_cat_ids(c) & tid_set)).sum()
leader_count   = df["categories"].apply(lambda c: bool(extract_cat_ids(c) & lid_set)).sum()
unique_pubs    = df[dom_col].nunique() if dom_col else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Mentions",    f"{total_mentions:,}")
c2.metric("Theme-Tagged",      f"{themed_count:,}")
c3.metric("Leadership-Tagged", f"{leader_count:,}")
c4.metric("Unique Publishers", f"{unique_pubs:,}")


# ═══════════════════════════════════════════════════════════════════════════
# AI INSIGHTS — displayed below the KPI strip
# ═══════════════════════════════════════════════════════════════════════════

# Build top-themes and top-leaders strings for the prompt
theme_counts: dict[str, int] = {}
for cat_list in df["categories"]:
    for cid in extract_cat_ids(cat_list):
        if cid in themes_cats:
            n = themes_cats[cid]
            theme_counts[n] = theme_counts.get(n, 0) + 1

leader_counts: dict[str, int] = {}
for cat_list in df["categories"]:
    for cid in extract_cat_ids(cat_list):
        if cid in leader_cats:
            n = leader_cats[cid]
            leader_counts[n] = leader_counts.get(n, 0) + 1

top_themes_str  = ", ".join(
    f"{k} ({v})"
    for k, v in sorted(theme_counts.items(), key=lambda x: -x[1])[:5]
) or "N/A"
top_leaders_str = ", ".join(
    f"{k} ({v})"
    for k, v in sorted(leader_counts.items(), key=lambda x: -x[1])[:5]
) or "N/A"
date_range_str  = f"{start_str} to {end_str}"

if OPENAI_API_KEY:
    if (
        "dashboard_insight" not in st.session_state
        or st.session_state["dashboard_insight"] is None
    ):
        with st.spinner("Generating AI insights…"):
            st.session_state["dashboard_insight"] = generate_dashboard_insights(
                client_name=loaded_client,
                total_mentions=total_mentions,
                themed_count=int(themed_count),
                leader_count=int(leader_count),
                unique_pubs=unique_pubs,
                top_themes=top_themes_str,
                top_leaders=top_leaders_str,
                date_range=date_range_str,
            )

    insight_text = st.session_state.get("dashboard_insight", "")
    if insight_text:
        lines = [
            ln.strip().lstrip("-•·▪▸►◆●1234567890.").strip()
            for ln in insight_text.split("\n")
            if ln.strip()
        ]
        bullets_html = "".join(
            f'<div class="ai-insights-bullet">'
            f'<span class="ai-insights-bullet-dot">▸</span>'
            f'<span class="ai-insights-text">{line}</span></div>'
            for line in lines if line
        )
        st.markdown(
            f'<div class="ai-insights-card">{bullets_html}</div>',
            unsafe_allow_html=True,
        )
else:
    st.markdown(
        '<div style="background:#1a1d27;border:1px solid #2a2d3e;border-left:3px solid #4a4e66;'
        'border-radius:12px;padding:12px 16px;margin:0.8rem 0;font-size:0.8rem;color:#4a4e66;">'
        'Set <code>OPENAI_API_KEY</code> environment variable to enable AI Insights'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("<hr>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR — publisher filter (config-driven allowlist)
# ═══════════════════════════════════════════════════════════════════════════

# Pull the fixed publisher list from the loaded client's config
config_pub_list = loaded_cfg.get("PUBLISHERS", [])

# Count actual mentions per allowlisted publisher to show totals
pub_mention_counts: dict[str, int] = {}
if dom_col:
    vc = df[dom_col].fillna("").value_counts()
    for p in config_pub_list:
        pub_mention_counts[p] = int(vc.get(p, 0))

pub_selections: dict[str, bool] = {}

with st.sidebar:
    st.markdown("### Publishers")
    st.caption(f"{len(config_pub_list)} configured · toggle to include/exclude")
    for pub in config_pub_list:
        count_label = pub_mention_counts.get(pub, 0)
        pub_selections[pub] = st.checkbox(
            f"{pub}  ({count_label:,})",
            value=True,           # all config publishers ON by default
            key=f"pub_{pub}",
        )

selected_pubs = [p for p, on in pub_selections.items() if on]


# ═══════════════════════════════════════════════════════════════════════════
# BUILD PIVOTS
# ═══════════════════════════════════════════════════════════════════════════

with st.spinner("Building matrices…"):
    tl_matrix = build_cross_pivot(df, themes_cats, leader_cats)
    tl_lookup = build_mention_lookup(df, themes_cats, leader_cats)

    if selected_pubs:
        tp_matrix = build_theme_publisher_pivot(df, themes_cats, selected_pubs)
        tp_lookup = build_mention_lookup_pub(df, themes_cats, selected_pubs)
    else:
        tp_matrix = pd.DataFrame()
        tp_lookup = {}

if hide_zero_rows:
    tl_matrix = tl_matrix.loc[tl_matrix.sum(axis=1) > 0]
    if not tp_matrix.empty:
        tp_matrix = tp_matrix.loc[tp_matrix.sum(axis=1) > 0]

if "tl_click" not in st.session_state:
    st.session_state["tl_click"] = None
if "tp_click" not in st.session_state:
    st.session_state["tp_click"] = None


# ═══════════════════════════════════════════════════════════════════════════
# SECTION 1 — THEMES x PUBLISHERS
# ═══════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div class="section-label">
    <span class="section-label-text">Section 01</span>
    <div class="section-label-line"></div>
</div>
<div class="section-title">Themes x Publishers</div>
<div class="section-sub">{len(selected_pubs)} publishers selected · Click any cell to read articles on the right</div>
""", unsafe_allow_html=True)

if tp_matrix.empty or (hasattr(tp_matrix, "values") and tp_matrix.values.sum() == 0):
    st.info("No theme-tagged publisher mentions, or no publishers selected.")
else:
    tp_h = max(460, len(tp_matrix) * 42 + 240)
    col_chart2, col_panel2 = st.columns([3, 2], gap="large")

    with col_chart2:
        fig_tp     = build_heatmap(tp_matrix, "", "Publisher", "Theme", tp_h)
        tp_clicked = plotly_events(
            fig_tp, click_event=True, hover_event=False,
            select_event=False, key="tp_chart", override_height=tp_h,
        )
        if tp_clicked:
            pt = tp_clicked[0]
            tl, pl = pt.get("y", ""), pt.get("x", "")
            if tl and pl:
                st.session_state["tp_click"] = (tl, pl)

    with col_panel2:
        if st.session_state["tp_click"]:
            tl, pl = st.session_state["tp_click"]
            render_panel(
                tp_lookup, tl, pl, "Theme", "Publisher",
                client_name=loaded_client,
                max_rows=max_click_rows, panel_height=tp_h,
            )
        else:
            st.markdown("""
            <div class="panel-placeholder">
                <div style="font-weight:600; color:#4a4e66;">Click a cell</div>
                <div style="font-size:0.75rem; color:#3a3e55;">Articles will appear here</div>
            </div>
            """, unsafe_allow_html=True)

    with st.expander("View raw data table"):
        st.dataframe(styled_table(tp_matrix), use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)



# ═══════════════════════════════════════════════════════════════════════════
# SECTION 2 — THEMES x LEADERSHIP
# ═══════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="section-label">
    <span class="section-label-text">Section 02</span>
    <div class="section-label-line"></div>
</div>
<div class="section-title">Themes x Leadership</div>
<div class="section-sub">Click any cell to read articles on the right · hover for a quick preview</div>
""", unsafe_allow_html=True)

if tl_matrix.empty or tl_matrix.values.sum() == 0:
    st.info("No co-tagged Themes x Leadership mentions found.")
else:
    tl_h = max(440, len(tl_matrix) * 42 + 220)
    col_chart, col_panel = st.columns([3, 2], gap="large")

    with col_chart:
        fig_tl     = build_heatmap(tl_matrix, "", "Leadership", "Theme", tl_h)
        tl_clicked = plotly_events(
            fig_tl, click_event=True, hover_event=False,
            select_event=False, key="tl_chart", override_height=tl_h,
        )
        if tl_clicked:
            pt = tl_clicked[0]
            tl, ll = pt.get("y", ""), pt.get("x", "")
            if tl and ll:
                st.session_state["tl_click"] = (tl, ll)

    with col_panel:
        if st.session_state["tl_click"]:
            tl, ll = st.session_state["tl_click"]
            render_panel(
                tl_lookup, tl, ll, "Theme", "Leadership",
                client_name=loaded_client,
                max_rows=max_click_rows, panel_height=tl_h,
            )
        else:
            st.markdown("""
            <div class="panel-placeholder">
                <div style="font-weight:600; color:#4a4e66;">Click a cell</div>
                <div style="font-size:0.75rem; color:#3a3e55;">Articles will appear here</div>
            </div>
            """, unsafe_allow_html=True)

    with st.expander("View raw data table"):
        st.dataframe(styled_table(tl_matrix), use_container_width=True)

st.markdown("<hr>", unsafe_allow_html=True)



# ═══════════════════════════════════════════════════════════════════════════
# SECTION 3 — TOP PUBLISHERS BAR
# ═══════════════════════════════════════════════════════════════════════════

if dom_col:
    st.markdown("""
    <div class="section-label">
        <span class="section-label-text">Section 03</span>
        <div class="section-label-line"></div>
    </div>
    <div class="section-title">Top Publishers</div>
    <div class="section-sub">Total mention volume by source</div>
    """, unsafe_allow_html=True)

    # Filter bar chart to only configured publishers (preserving config order)
    vc = df[dom_col].fillna("").value_counts()
    top_pub_df = pd.DataFrame([
        {"Publisher": p, "Mentions": int(vc.get(p, 0))}
        for p in config_pub_list
    ])
    # Drop publishers with zero mentions so the chart stays clean
    top_pub_df = top_pub_df[top_pub_df["Mentions"] > 0].reset_index(drop=True)
    # Sort descending for the horizontal bar
    top_pub_df = top_pub_df.sort_values("Mentions", ascending=False).reset_index(drop=True)

    max_val    = top_pub_df["Mentions"].max()
    bar_colors = [
        RED    if v == max_val        else
        ORANGE if v >= max_val * 0.6  else
        "#4a9eff"
        for v in top_pub_df["Mentions"]
    ]

    fig_bar = go.Figure(go.Bar(
        x=top_pub_df["Mentions"],
        y=top_pub_df["Publisher"],
        orientation="h",
        marker_color=bar_colors,
        marker_line_width=0,
        text=top_pub_df["Mentions"],
        textposition="outside",
        textfont=dict(color=TEXT_MUTED, size=10, family="DM Mono"),
    ))
    fig_bar.update_layout(
        paper_bgcolor=BG, plot_bgcolor=BG,
        font=dict(family="DM Sans", color=TEXT_PRIMARY),
        height=500,
        margin=dict(l=180, r=80, t=20, b=40),
        yaxis=dict(
            autorange="reversed",
            tickfont=dict(size=10, color=TEXT_MUTED),
            linecolor=BORDER,
            gridcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title=dict(text="Mentions", font=dict(color=TEXT_MUTED, size=11)),
            tickfont=dict(color=TEXT_MUTED, size=10),
            linecolor=BORDER, gridcolor=BORDER, gridwidth=1,
        ),
        hoverlabel=dict(
            bgcolor=CARD_BG, bordercolor=BORDER,
            font=dict(size=11, color=TEXT_PRIMARY),
        ),
    )
    st.plotly_chart(fig_bar, use_container_width=True)
