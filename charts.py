"""
charts.py — Plotly chart builders for the MASCAC Baseball Dashboard.
Color palette: Royal Blue / Gold / Dark Navy
"""

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

ROYAL_BLUE   = "#4D9FFF"
BLUE_LIGHT   = "#99C2FF"
GOLD         = "#F5A800"
GOLD_LIGHT   = "#FFD040"
WHITE        = "#F1F5F9"
GRAY         = "#94A3B8"
BG_DARK      = "#0F2266"
BG_CARD      = "#080808"
BG_SURFACE   = "#111111"
GRID_LINE    = "#1E3D80"

_BASE_LAYOUT = dict(
    paper_bgcolor=BG_CARD,
    plot_bgcolor=BG_CARD,
    font=dict(color=WHITE, family="Inter, sans-serif", size=12),
    margin=dict(l=12, r=12, t=48, b=12),
    height=270,
    hovermode="x unified",
    hoverlabel=dict(
        bgcolor=BG_SURFACE,
        bordercolor=ROYAL_BLUE,
        font=dict(color=WHITE, size=12),
    ),
    xaxis=dict(
        showgrid=False,
        zeroline=False,
        tickfont=dict(size=10, color=GRAY),
        title="",
        linecolor=GRID_LINE,
    ),
    yaxis=dict(
        gridcolor=GRID_LINE,
        zeroline=False,
        tickfont=dict(size=10, color=GRAY),
        linecolor=GRID_LINE,
    ),
)


def _layout(**overrides):
    import copy
    base = copy.deepcopy(_BASE_LAYOUT)
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _last_n(rows: list, n: int = 5) -> list:
    played = [r for r in rows if r]
    return played[-n:]


def _ip_to_decimal(val) -> float:
    try:
        ip = float(val)
        full = int(ip)
        outs = round((ip - full) * 10)
        return full + outs / 3
    except (ValueError, TypeError):
        return 0.0


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _title_style(text: str, color: str = GOLD) -> dict:
    return dict(text=text, font=dict(size=13, color=color, family="Inter, sans-serif"))


# ---------------------------------------------------------------------------
# Hitter charts
# ---------------------------------------------------------------------------

def avg_moving_average_chart(game_log: list, player_name: str) -> go.Figure:
    rows = [r for r in game_log if r]
    dates, avgs = [], []
    cum_h = cum_ab = 0.0

    for i, row in enumerate(rows):
        cum_h  += _safe_float(row.get("h"))
        cum_ab += _safe_float(row.get("ab"))
        avgs.append(round(cum_h / cum_ab, 3) if cum_ab else 0.0)
        dates.append(row.get("date", f"G{i+1}"))

    fmt = [f"{v:.3f}".lstrip("0") or ".000" for v in avgs]

    fig = go.Figure()

    # Shaded area under the line
    fig.add_trace(go.Scatter(
        x=dates, y=avgs,
        fill="tozeroy",
        fillcolor="rgba(37,99,235,0.12)",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.add_trace(go.Scatter(
        x=dates, y=avgs,
        mode="lines+markers",
        line=dict(color=ROYAL_BLUE, width=2.5),
        marker=dict(size=8, color=GOLD, line=dict(color=ROYAL_BLUE, width=2)),
        hovertemplate="<b>%{x}</b><br>Season AVG: .%{customdata}<extra></extra>",
        customdata=fmt,
        name="AVG",
    ))

    fig.update_layout(**_layout(
        title=_title_style(f"{player_name} — Season AVG"),
        yaxis=dict(tickformat=".3f", title="AVG", **_BASE_LAYOUT["yaxis"]),
    ))
    return fig


def totals_bar_chart(
    game_log: list,
    stat: str,
    player_name: str,
    label: str,
    color: str = GOLD,
) -> go.Figure:
    rows = _last_n(game_log, 5)
    dates = [r.get("date", f"G{i+1}") for i, r in enumerate(rows)]
    values = [_safe_float(r.get(stat)) for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=values,
        marker=dict(
            color=color,
            line=dict(color=BG_CARD, width=1.5),
            opacity=0.88,
        ),
        hovertemplate="<b>%{x}</b><br>" + label + ": %{y:.0f}<extra></extra>",
        name=label,
    ))

    fig.update_layout(**_layout(
        title=_title_style(f"{player_name} — {label} per Game", color=color),
        yaxis=dict(title=label, dtick=1, **_BASE_LAYOUT["yaxis"]),
        bargap=0.35,
    ))
    return fig


# ---------------------------------------------------------------------------
# Pitcher charts
# ---------------------------------------------------------------------------

def era_moving_average_chart(game_log: list, player_name: str) -> go.Figure:
    rows = [r for r in game_log if r]
    dates, eras = [], []
    cum_er = cum_ip = 0.0

    for i, row in enumerate(rows):
        cum_er += _safe_float(row.get("er"))
        cum_ip += _ip_to_decimal(row.get("ip"))
        era = round((cum_er * 9) / cum_ip, 2) if cum_ip > 0 else 0.0
        eras.append(era)
        dates.append(row.get("date", f"G{i+1}"))

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=dates, y=eras,
        fill="tozeroy",
        fillcolor="rgba(245,158,11,0.10)",
        line=dict(color="rgba(0,0,0,0)"),
        hoverinfo="skip",
        showlegend=False,
    ))

    fig.add_trace(go.Scatter(
        x=dates, y=eras,
        mode="lines+markers",
        line=dict(color=GOLD, width=2.5),
        marker=dict(size=8, color=ROYAL_BLUE, line=dict(color=GOLD, width=2)),
        hovertemplate="<b>%{x}</b><br>Season ERA: %{y:.2f}<extra></extra>",
        name="ERA",
    ))

    fig.update_layout(**_layout(
        title=_title_style(f"{player_name} — Season ERA", color=GOLD),
        yaxis=dict(title="ERA", **_BASE_LAYOUT["yaxis"]),
    ))
    return fig


def pitcher_whip_chart(game_log: list, player_name: str) -> go.Figure:
    rows = _last_n(game_log, 5)
    dates, whips = [], []

    for i, row in enumerate(rows):
        whip = row.get("whip")
        whips.append(_safe_float(whip) if whip is not None else None)
        dates.append(row.get("date", f"G{i+1}"))

    color = BLUE_LIGHT

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=dates, y=whips,
        marker=dict(
            color=color,
            line=dict(color=BG_CARD, width=1.5),
            opacity=0.88,
        ),
        hovertemplate="<b>%{x}</b><br>WHIP: %{y:.2f}<extra></extra>",
        name="WHIP",
    ))

    fig.update_layout(**_layout(
        title=_title_style(f"{player_name} — WHIP per Outing", color=color),
        yaxis=dict(title="WHIP", **_BASE_LAYOUT["yaxis"]),
        bargap=0.35,
    ))
    return fig
