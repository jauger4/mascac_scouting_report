"""
app.py — MASCAC Baseball Dashboard
Plugins: streamlit-extras (stylable_container) · streamlit-option-menu
Color scheme: Royal Blue · Gold · Dark Navy / White
"""

import subprocess
import pandas as pd
import streamlit as st
from streamlit_extras.stylable_container import stylable_container
from streamlit_option_menu import option_menu
from supabase import create_client

import charts
import scraper

subprocess.run(["playwright", "install", "chromium"], capture_output=True)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="MASCAC Baseball",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

ROYAL_BLUE  = "#4D9FFF"
BLUE_LIGHT  = "#99C2FF"
GOLD        = "#F5A800"
GOLD_LIGHT  = "#FFD040"
BG_DARK     = "#0F2266"
BG_CARD     = "#080808"
BG_SURFACE  = "#111111"
BG_HOVER    = "#1A1A1A"
WHITE       = "#F1F5F9"
GRAY        = "#94A3B8"
BORDER      = "#1E3D80"

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [data-testid="stAppViewContainer"] {{
    background-color: {BG_DARK};
    font-family: 'Inter', sans-serif;
}}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background-color: {BG_CARD};
    border-right: 1px solid {BORDER};
}}
[data-testid="stSidebar"] * {{ font-family: 'Inter', sans-serif; }}
[data-testid="stSidebarCollapseButton"] span {{ font-family: 'Material Symbols Rounded' !important; }}
[data-testid="stSidebar"] [data-testid="stSelectbox"] > div > div {{
    background-color: {BG_SURFACE};
    border: 1px solid {BORDER};
    color: {WHITE};
    border-radius: 8px;
}}

/* ── Player buttons — base style ── */
div[data-testid="stButton"] > button {{
    width: 100%;
    text-align: left;
    background-color: {BG_SURFACE};
    color: {GRAY};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    margin: 2px 0;
    font-size: 13px;
    font-family: 'Inter', sans-serif;
    font-weight: 500;
    transition: all 0.15s ease;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
div[data-testid="stButton"] > button:hover {{
    background-color: {BG_HOVER};
    border-color: {ROYAL_BLUE};
    color: {WHITE};
}}
div[data-testid="stButton"] > button p {{
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

/* ── Sidebar refresh button override ── */
[data-testid="stSidebar"] div[data-testid="stButton"] > button {{
    background: linear-gradient(135deg, {GOLD}, #E09000);
    color: #0A0A0A;
    border: none;
    font-weight: 700;
    text-align: center;
    border-radius: 8px;
    padding: 10px;
    white-space: normal;
}}
[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {{
    background: linear-gradient(135deg, #E09000, #C07800);
    border: none;
}}

/* ── Plotly chart wrapper ── */
[data-testid="stPlotlyChart"] {{
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid {BORDER};
}}

/* ── Native dataframe (pitcher table) ── */
[data-testid="stDataFrame"] {{ border-radius: 10px; overflow: hidden; }}

/* ── Misc ── */
[data-testid="stCaptionContainer"] p {{ color: {GRAY}; font-size: 11px; }}
hr {{ border-color: {BORDER} !important; margin: 12px 0 !important; }}
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: {BG_DARK}; }}
::-webkit-scrollbar-thumb {{ background: {BORDER}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {ROYAL_BLUE}; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEAMS = [
    "Anna Maria", "Bridgewater St.", "Fitchburg St.", "Framingham St.",
    "Mass. Maritime", "MCLA", "Salem St.", "Westfield St.", "Worcester St.",
]

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "team":        TEAMS[0],
    "view":        "Hitting",
    "sel_hitter":  None,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _clear_selections():
    st.session_state["sel_hitter"] = None

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def load_hitters():
    return scraper.scrape_hitters()

@st.cache_data(ttl=3600, show_spinner=False)
def load_pitchers():
    return scraper.scrape_pitchers()

def load_game_log(slug: str, pos: str = "h") -> list:
    return scraper.scrape_game_log(slug, pos=pos)

# ---------------------------------------------------------------------------
# Notes (Supabase)
# ---------------------------------------------------------------------------

@st.cache_resource
def _supabase():
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )

@st.cache_data(ttl=30, show_spinner=False)
def load_notes() -> dict:
    try:
        res = _supabase().table("notes").select("slug, note").execute()
        return {r["slug"]: r["note"] for r in res.data}
    except Exception:
        return {}

def save_note(slug: str, text: str):
    sb = _supabase()
    if text.strip():
        sb.table("notes").upsert({"slug": slug, "note": text.strip()}).execute()
    else:
        sb.table("notes").delete().eq("slug", slug).execute()
    load_notes.clear()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(f"""
    <div style="padding:8px 0 20px; text-align:center;">
        <div style="font-size:40px; line-height:1;">⚾</div>
        <div style="font-size:22px; font-weight:900; color:{WHITE};
                    letter-spacing:0.04em; margin-top:8px;">MASCAC</div>
        <div style="font-size:10px; font-weight:700; color:{GOLD};
                    letter-spacing:0.14em; text-transform:uppercase; margin-top:3px;">
            Baseball Dashboard
        </div>
    </div>
    <hr style="border-color:{BORDER}; margin:0 0 20px;">
    """, unsafe_allow_html=True)

    st.markdown(f'<p style="color:{GRAY}; font-size:10px; font-weight:700; letter-spacing:0.10em; text-transform:uppercase; margin-bottom:6px;">Team</p>', unsafe_allow_html=True)
    new_team = st.selectbox("", TEAMS, index=TEAMS.index(st.session_state.team), label_visibility="collapsed")
    if new_team != st.session_state.team:
        st.session_state.team = new_team
        _clear_selections()

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
    st.markdown(f'<p style="color:{GRAY}; font-size:10px; font-weight:700; letter-spacing:0.10em; text-transform:uppercase; margin-bottom:6px;">Stats View</p>', unsafe_allow_html=True)

    selected_view = option_menu(
        menu_title=None,
        options=["Hitting", "Pitching"],
        icons=["bar-chart-fill", "crosshair"],
        default_index=["Hitting", "Pitching"].index(st.session_state.view),
        orientation="vertical",
        styles={
            "container": {
                "padding": "4px",
                "background-color": BG_SURFACE,
                "border": f"1px solid {BORDER}",
                "border-radius": "10px",
            },
            "icon":              {"color": GOLD, "font-size": "14px"},
            "nav-link":          {"color": GRAY, "font-size": "13px", "font-weight": "500",
                                  "border-radius": "7px", "padding": "8px 14px",
                                  "--hover-color": BG_HOVER},
            "nav-link-selected": {"background-color": ROYAL_BLUE, "color": WHITE, "font-weight": "700"},
        },
    )
    if selected_view != st.session_state.view:
        st.session_state.view = selected_view
        _clear_selections()
        st.rerun()


# ---------------------------------------------------------------------------
# Reusable HTML components
# ---------------------------------------------------------------------------

def fmt_avg(v) -> str:
    try:
        s = f"{float(v):.3f}"
        return s.lstrip("0") or ".000"
    except (ValueError, TypeError):
        return "---"

def fmt_int(v) -> str:
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return "--"

def fmt_float(v, d=2) -> str:
    try:
        return f"{float(v):.{d}f}"
    except (ValueError, TypeError):
        return "--"


def metric_card(title: str, value: str, subtitle: str, accent: str = GOLD):
    st.markdown(f"""
    <div style="
        background: {BG_CARD};
        border: 1px solid {BORDER};
        border-top: 3px solid {accent};
        border-radius: 10px;
        padding: 16px 20px 14px;
        min-height: 100px;
    ">
        <div style="font-size:10px; font-weight:700; color:{GRAY};
                    text-transform:uppercase; letter-spacing:0.10em; margin-bottom:8px;">
            {title}
        </div>
        <div style="font-size:28px; font-weight:800; color:{WHITE};
                    letter-spacing:-0.02em; line-height:1.1;">
            {value}
        </div>
        <div style="font-size:12px; color:{GRAY}; margin-top:6px; font-weight:500;">
            {subtitle}
        </div>
    </div>
    """, unsafe_allow_html=True)


def stat_badge(label: str, color: str = ROYAL_BLUE):
    return f'<span style="display:inline-block; background:rgba(41,121,255,0.15); color:{color}; border:1px solid {color}; border-radius:20px; padding:2px 10px; font-size:10px; font-weight:600; letter-spacing:0.04em; margin-right:6px;">{label}</span>'


def section_header(title: str, accent: str, badge_text: str = ""):
    badge_html = stat_badge(badge_text, accent) if badge_text else ""
    st.markdown(f"""
    <div style="margin-bottom:10px;">
        <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
            <span style="font-size:12px; font-weight:700; color:{accent};
                         letter-spacing:0.10em; text-transform:uppercase;">
                {title}
            </span>
            {badge_html}
        </div>
        <div style="height:1px; background:linear-gradient(90deg,{accent}66,transparent);"></div>
    </div>
    """, unsafe_allow_html=True)


def _stat_card(key_suffix: str, accent: str = ROYAL_BLUE):
    return stylable_container(
        key=f"card_{key_suffix}",
        css_styles=f"""
        {{
            background-color: {BG_CARD};
            border: 1px solid {BORDER};
            border-top: 3px solid {accent};
            border-radius: 10px;
            padding: 18px 16px 14px;
        }}
        """,
    )


def player_btn(label: str, key: str, state_key: str, slug: str):
    is_sel = st.session_state[state_key] == slug
    prefix = "▶  " if is_sel else ""
    if is_sel:
        st.markdown(f"""
        <style>
        div[data-testid="stButton"]:has(button[data-testid="{key}"]) button {{
            border-color: {GOLD} !important;
            color: {GOLD_LIGHT} !important;
            background-color: rgba(245,168,0,0.12) !important;
        }}
        </style>
        """, unsafe_allow_html=True)
    if st.button(f"{prefix}{label}", key=key):
        st.session_state[state_key] = slug if not is_sel else None
        st.rerun()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown(f"""
<div style="display:flex; align-items:center; gap:16px; padding:8px 0 24px;
            border-bottom:1px solid {BORDER}; margin-bottom:24px;">
    <div style="width:6px; height:54px;
                background:linear-gradient(180deg,{GOLD} 0%,{ROYAL_BLUE} 100%);
                border-radius:3px; flex-shrink:0;"></div>
    <div>
        <div style="font-size:32px; font-weight:900; color:{WHITE};
                    line-height:1.1; letter-spacing:-0.02em;">
            {st.session_state.team}
        </div>
        <div style="font-size:11px; font-weight:700; color:{GOLD};
                    letter-spacing:0.10em; text-transform:uppercase; margin-top:4px;">
            {"⚡ Hitting Stats" if st.session_state.view == "Hitting" else "🎯 Pitching Stats"} · MASCAC 2025–26
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# HITTING VIEW
# ---------------------------------------------------------------------------

if st.session_state.view == "Hitting":
    with st.spinner(""):
        hitters_raw = load_hitters()

    df = pd.DataFrame(hitters_raw)
    for col in ["avg", "xbh", "k", "h", "ab"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    team_df = df[df.get("team", pd.Series(dtype=str)) == st.session_state.team].copy()

    if team_df.empty:
        st.warning("No hitting data found for this team.")
        st.stop()

    top_avg = team_df.nlargest(9, "avg").dropna(subset=["avg"])
    top_xbh = team_df.nlargest(9, "xbh").dropna(subset=["xbh"])
    top_k   = team_df.nlargest(9, "k").dropna(subset=["k"])

    # ── Metric cards ──
    m1, m2, m3 = st.columns(3, gap="medium")
    with m1:
        if not top_avg.empty:
            r = top_avg.iloc[0]
            metric_card("AVG Leader", fmt_avg(r["avg"]), r["name"], ROYAL_BLUE)
    with m2:
        if not top_xbh.empty:
            r = top_xbh.iloc[0]
            metric_card("XBH Leader", fmt_int(r["xbh"]), r["name"], GOLD)
    with m3:
        if not top_k.empty:
            r = top_k.iloc[0]
            metric_card("Strikeout Leader", f"{fmt_int(r['k'])} K", r["name"], BLUE_LIGHT)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Leaderboard cards ──
    notes = load_notes()
    col1, col2, col3 = st.columns(3, gap="medium")

    with col1:
        with _stat_card("avg", ROYAL_BLUE):
            section_header("Batting Average", ROYAL_BLUE, "Top 9 · click for trends")
            for _, row in top_avg.iterrows():
                marker = "📝 " if row["slug"] in notes else ""
                player_btn(f"{marker}{row['name']}  ·  {fmt_avg(row['avg'])}", f"avg_{row['slug']}", "sel_hitter", row["slug"])

    with col2:
        with _stat_card("xbh", GOLD):
            section_header("Extra Base Hits", GOLD, "Top 9 · click for trends")
            for _, row in top_xbh.iterrows():
                marker = "📝 " if row["slug"] in notes else ""
                player_btn(f"{marker}{row['name']}  ·  {fmt_int(row['xbh'])} XBH", f"xbh_{row['slug']}", "sel_hitter", row["slug"])

    with col3:
        with _stat_card("k", BLUE_LIGHT):
            section_header("Strikeouts", BLUE_LIGHT, "Most 9 · click for trends")
            for _, row in top_k.iterrows():
                marker = "📝 " if row["slug"] in notes else ""
                player_btn(f"{marker}{row['name']}  ·  {fmt_int(row['k'])} K", f"k_{row['slug']}", "sel_hitter", row["slug"])

    # ── Charts + table + notes for selected hitter ──
    slug = st.session_state.sel_hitter
    if slug:
        row = team_df[team_df["slug"] == slug]
        if not row.empty:
            name = row.iloc[0]["name"]
            st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

            st.markdown(f"""
            <div style="margin-bottom:16px; padding:14px 18px;
                        background:{BG_SURFACE}; border:1px solid {BORDER};
                        border-left:4px solid {GOLD}; border-radius:8px;
                        display:flex; align-items:center; gap:12px;">
                <span style="font-size:18px;">⚾</span>
                <div>
                    <div style="font-size:15px; font-weight:700; color:{WHITE};">{name}</div>
                    <div style="font-size:11px; color:{GRAY}; margin-top:2px;">
                        AVG trend · Extra base hits · Strikeouts per game
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.spinner(f"Loading {name}…"):
                gl = load_game_log(slug, pos="h")

            if gl:
                cfg = {"displayModeBar": False}
                cc1, cc2, cc3 = st.columns(3, gap="medium")
                with cc1:
                    st.plotly_chart(charts.avg_moving_average_chart(gl, name),
                                    use_container_width=True, config=cfg)
                with cc2:
                    st.plotly_chart(charts.totals_bar_chart(gl, "xbh", name, "XBH", color=GOLD),
                                    use_container_width=True, config=cfg)
                with cc3:
                    st.plotly_chart(charts.totals_bar_chart(gl, "k", name, "K", color=BLUE_LIGHT),
                                    use_container_width=True, config=cfg)

                # ── Combined game log table ──
                tbl = pd.DataFrame(gl)[["date", "opponent", "score", "ab", "h", "avg", "xbh", "k"]].copy()
                tbl.columns = ["Date", "Opponent", "Score", "AB", "H", "AVG", "XBH", "K"]
                tbl["AVG"] = tbl["AVG"].apply(lambda v: f"{v:.3f}".lstrip("0") if pd.notna(v) else "--")
                tbl["XBH"] = tbl["XBH"].apply(lambda v: str(int(v)) if pd.notna(v) else "--")
                tbl["K"]   = tbl["K"].apply(lambda v: str(int(v)) if pd.notna(v) else "--")
                tbl["AB"]  = tbl["AB"].apply(lambda v: str(int(v)) if pd.notna(v) else "--")
                tbl["H"]   = tbl["H"].apply(lambda v: str(int(v)) if pd.notna(v) else "--")
                st.dataframe(tbl, use_container_width=True, hide_index=True)
            else:
                st.info("No game log available.")

            # ── Scout notes ──
            st.markdown(f'<p style="color:{GRAY}; font-size:10px; font-weight:700; letter-spacing:0.10em; text-transform:uppercase; margin:16px 0 4px;">Scout Notes</p>', unsafe_allow_html=True)
            note_text = st.text_area("", value=notes.get(slug, ""), key=f"note_{slug}", height=120, placeholder="Add scouting notes…", label_visibility="collapsed")
            if st.button("Save Note", key=f"savenote_{slug}"):
                save_note(slug, note_text)
                st.rerun()

# ---------------------------------------------------------------------------
# PITCHING VIEW
# ---------------------------------------------------------------------------

else:
    with st.spinner(""):
        pitchers_raw = load_pitchers()

    df = pd.DataFrame(pitchers_raw)
    for col in ["era", "k", "bb", "whip", "ip", "app"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    team_df = df[df.get("team", pd.Series(dtype=str)) == st.session_state.team].copy()

    if team_df.empty:
        st.warning("No pitching data found for this team.")
        st.stop()

    team_df = team_df.sort_values("era", ascending=True, na_position="last").reset_index(drop=True)

    # ── Metric cards ──
    p1, p2, p3 = st.columns(3, gap="medium")
    era_df   = team_df.dropna(subset=["era"])
    k_df     = team_df.dropna(subset=["k"]).sort_values("k", ascending=False)
    whip_df  = team_df.dropna(subset=["whip"])

    with p1:
        if not era_df.empty:
            r = era_df.iloc[0]
            metric_card("ERA Leader", fmt_float(r["era"]), r["name"], GOLD)
    with p2:
        if not k_df.empty:
            r = k_df.iloc[0]
            metric_card("Strikeout Leader", f"{fmt_int(r['k'])} K", r["name"], ROYAL_BLUE)
    with p3:
        if not whip_df.empty:
            r = whip_df.iloc[0]
            metric_card("WHIP Leader", fmt_float(r["whip"]), r["name"], BLUE_LIGHT)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── Section header ──
    with _stat_card("pitchers_hdr", ROYAL_BLUE):
        section_header("Pitching Staff", ROYAL_BLUE, "Sorted by ERA · click row for trends")

        # ── Native dataframe with row selection ──
        notes = load_notes()
        display_df = team_df[["name", "era", "app", "ip", "k", "bb", "whip"]].copy()
        display_df.columns = ["Player", "ERA", "G", "IP", "K", "BB", "WHIP"]
        display_df["Player"] = [
            f"📝 {name}" if slug in notes else name
            for name, slug in zip(team_df["name"], team_df["slug"])
        ]

        event = st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "ERA":  st.column_config.NumberColumn("ERA",  format="%.2f"),
                "WHIP": st.column_config.NumberColumn("WHIP", format="%.2f"),
                "K":    st.column_config.NumberColumn("K",    format="%d"),
                "BB":   st.column_config.NumberColumn("BB",   format="%d"),
                "G":    st.column_config.NumberColumn("G",    format="%d"),
                "IP":   st.column_config.NumberColumn("IP",   format="%.1f"),
            },
            height=min(400, 36 * len(display_df) + 38),
        )

    # ── Resolve selected pitcher ──
    sel_indices = event.selection.rows if event.selection else []
    sel_slug = team_df.iloc[sel_indices[0]]["slug"] if sel_indices else None

    # ── Charts ──
    if sel_slug:
        pitcher_row = team_df[team_df["slug"] == sel_slug]
        if not pitcher_row.empty:
            name = pitcher_row.iloc[0]["name"]

            st.markdown(f"""
            <div style="margin:22px 0 16px; padding:14px 18px;
                        background:{BG_SURFACE}; border:1px solid {BORDER};
                        border-left:4px solid {GOLD}; border-radius:8px;
                        display:flex; align-items:center; gap:12px;">
                <span style="font-size:18px;">🎯</span>
                <div>
                    <div style="font-size:15px; font-weight:700; color:{WHITE};">{name}</div>
                    <div style="font-size:11px; color:{GRAY}; margin-top:2px;">
                        Last 5 appearances · ERA trend · K & WHIP per outing
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            with st.spinner(f"Loading {name}'s game log…"):
                gl = load_game_log(sel_slug, pos="p")

            if gl:
                cfg = {"displayModeBar": False}
                c1, c2, c3 = st.columns(3, gap="medium")
                gl_df = pd.DataFrame(gl)

                def _pitcher_table(stat_col, stat_label, fmt="float"):
                    tbl = gl_df[["date", "opponent", "score", stat_col]].copy()
                    tbl.columns = ["Date", "Opponent", "Score", stat_label]
                    if fmt == "int":
                        tbl[stat_label] = tbl[stat_label].apply(
                            lambda v: str(int(v)) if pd.notna(v) else "--"
                        )
                    else:
                        tbl[stat_label] = tbl[stat_label].apply(
                            lambda v: f"{v:.2f}" if pd.notna(v) else "--"
                        )
                    st.dataframe(tbl, use_container_width=True, hide_index=True)

                with c1:
                    st.plotly_chart(charts.era_moving_average_chart(gl, name),
                                    use_container_width=True, config=cfg)
                    _pitcher_table("era", "ERA")
                with c2:
                    st.plotly_chart(charts.totals_bar_chart(gl, "k", name, "K", color=BLUE_LIGHT),
                                    use_container_width=True, config=cfg)
                    _pitcher_table("k", "K", fmt="int")
                with c3:
                    st.plotly_chart(charts.pitcher_whip_chart(gl, name),
                                    use_container_width=True, config=cfg)
                    _pitcher_table("whip", "WHIP")
                st.caption("BB per game not included in MASCAC game logs — season total shown in table above.")
            else:
                st.info("No game log data available for this pitcher.")
            st.markdown(f'<p style="color:{GRAY}; font-size:10px; font-weight:700; letter-spacing:0.10em; text-transform:uppercase; margin:16px 0 4px;">Scout Notes</p>', unsafe_allow_html=True)
            note_text = st.text_area("", value=notes.get(sel_slug, ""), key=f"note_{sel_slug}", height=80, placeholder="Add scouting notes…", label_visibility="collapsed")
            if st.button("Save Note", key=f"savenote_{sel_slug}"):
                save_note(sel_slug, note_text)
                st.rerun()
