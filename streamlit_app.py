from __future__ import annotations

import io
import base64
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dcma import FAIL, NA, PASS, REVIEW, assess
from src.building_renderer import BuildingConfig, BuildingRenderer
from src.earned_schedule import calculate_esm, template
from src.location_model import (
    ABOVE_GRADE_FLOORS,
    APARTMENTS_PER_FLOOR,
    RESIDENTIAL_FLOORS,
    RESIDENTIAL_UNITS_PER_TOWER,
    basement_progress,
    core_grid,
    floor_rollup,
    hall_progress,
    luxury_core_grid,
    luxury_index_grid,
    mapping_quality,
    model_master,
    project_has_code,
    progress_by_location,
    tower_grid,
)
from src.line_of_balance import (
    overlap_register,
    platform_lob,
    process_metrics,
    tower_lob,
)
from src.xer import as_float, parse_xer


ROOT = Path(__file__).parent
st.set_page_config(page_title="DCMA + Earned Schedule Manager", page_icon="⏱️", layout="wide")

st.markdown("""
<style>
:root { --navy:#082D50; --blue:#0A5C91; --teal:#00A88F; --green:#078B55; --pale:#EAF4F3; }
.block-container {padding-top:2.35rem !important; padding-bottom:3rem; max-width:1680px;}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#F1F8F7 0%,#E8F2F6 58%,#EDF6F1 100%); border-right:1px solid #D5E5E6;}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top:1.7rem;}
[data-testid="stMetric"] {background:white; border:1px solid #dce9ed; border-radius:14px; padding:12px 16px; box-shadow:0 3px 12px rgba(8,45,80,.05)}
.brand-banner {background:linear-gradient(115deg,#082D50 0%,#0A5C91 54%,#078B55 100%); padding:18px 24px; border-radius:16px; color:white; margin:0 0 14px; min-height:88px; box-shadow:0 8px 24px rgba(8,45,80,.13); display:flex; align-items:center; justify-content:space-between; gap:20px; overflow:visible;}
.brand-banner h1 {margin:0; font-size:1.72rem; line-height:1.08}.brand-banner p {margin:.4rem 0 0; opacity:.88;font-size:.86rem}
.product-pills {display:flex; gap:7px; flex-wrap:wrap; justify-content:flex-end}.product-pills span {font-size:.66rem; font-weight:800; letter-spacing:.08em; background:rgba(255,255,255,.14); border:1px solid rgba(255,255,255,.25); border-radius:999px; padding:5px 9px;}
.bolivar-brand {display:flex; justify-content:center; align-items:center; margin:0 auto 18px; padding:0;}
.bolivar-brand img {width:122px; max-width:78%; height:auto; object-fit:contain; filter:drop-shadow(0 7px 8px rgba(8,45,80,.13));}
.cronos-signature {display:flex; justify-content:center; align-items:center; margin:14px -4px 2px; padding:10px 0 0; border-top:1px solid rgba(92,135,143,.20);}
.cronos-signature img {width:176px; max-width:100%; height:auto; object-fit:contain; filter:drop-shadow(0 5px 7px rgba(8,45,80,.10));}
.workflow-card {background:rgba(255,255,255,.68); border:1px solid #D9E8E8; border-radius:12px; padding:10px 12px; margin-top:14px; color:#29475A; font-size:.76rem; line-height:1.65}.workflow-card b {color:#082D50}.workflow-card .active {color:#078B55;font-weight:800}
.context-strip {display:flex; gap:8px; flex-wrap:wrap; margin:-2px 0 10px}.context-chip {background:#EDF6F5;border:1px solid #D5E7E3;border-radius:999px;padding:5px 10px;color:#36596A;font-size:.73rem}.context-chip b{color:#082D50}
.section-kicker {font-size:.76rem; letter-spacing:.12em; text-transform:uppercase; color:#078B55; font-weight:800; margin-bottom:-.25rem}
.clock-title {text-align:center; color:#0A2942; font-size:.82rem; font-weight:750; min-height:2.45rem; margin-bottom:-.55rem; line-height:1.2}
.performance-tag {display:inline-block; background:#E1F4EE; color:#087A4B; border:1px solid #A8DDCC; border-radius:999px; padding:2px 8px; font-size:.68rem; font-weight:750;}
.performance-heading {display:flex;align-items:center;gap:9px;margin-bottom:2px;color:#082D50;font-size:.96rem;font-weight:800}.performance-heading span{background:#E1F4EE;color:#087A4B;border:1px solid #A8DDCC;border-radius:999px;padding:3px 8px;font-size:.64rem;letter-spacing:.06em;text-transform:uppercase}
.na-reason {min-height:2.2rem;text-align:center;color:#60727D;font-size:.68rem;line-height:1.25;margin:-8px 6px 4px}.na-reason b{color:#425A68}
.dcma-legend {display:flex; gap:16px; flex-wrap:wrap; font-size:.78rem; color:#526471; margin:-4px 0 8px;}
.legend-dot {width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px;}
.status-pass {color:#087A4B;font-weight:700}.status-fail {color:#B3261E;font-weight:700}.status-na {color:#6B7280;font-weight:700}
.small-note {color:#526471;font-size:.88rem}
@media (max-width:900px){.brand-banner{padding:14px}.brand-banner h1{font-size:1.3rem}.brand-banner p,.product-pills{display:none}}
</style>
""", unsafe_allow_html=True)


def sidebar_branding_top():
    bolivar = base64.b64encode((ROOT / "assets/logo_bolivar.png").read_bytes()).decode()
    st.markdown(f'''<div class="bolivar-brand">
      <img alt="Constructora Bolívar" src="data:image/png;base64,{bolivar}">
    </div>''', unsafe_allow_html=True)


def sidebar_branding_bottom():
    cronos = base64.b64encode((ROOT / "assets/logo_cronostasis.png").read_bytes()).decode()
    st.markdown(f'''<div class="cronos-signature">
      <img alt="Cronostasis" src="data:image/png;base64,{cronos}">
    </div>''', unsafe_allow_html=True)


def product_header():
    st.markdown(f'''<div class="brand-banner">
      <div><h1>DCMA 14-Point + Earned Schedule Manager</h1><p>Salud del cronograma, desempeño temporal, recursos y costos con trazabilidad desde Primavera P6.</p></div>
      <div class="product-pills"><span>PRIMAVERA P6</span><span>DCMA</span><span>EARNED SCHEDULE</span></div>
    </div>''', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def parse_cached(raw: bytes, filename: str):
    return parse_xer(raw, filename)


def status_badge(value: str) -> str:
    if value == PASS:
        return "🟢 Cumple"
    if value == FAIL:
        return "🔴 No cumple"
    if value == REVIEW:
        return "🟠 Revisar"
    return "⚪ No evaluable"


def dataframe_download(frame: pd.DataFrame, name: str):
    st.download_button("Descargar CSV", frame.to_csv(index=False).encode("utf-8-sig"), name, "text/csv")


def dcma_clock(metric, performance_row=False):
    """Full-circle condition clock inspired by the DCMA dashboard convention."""
    is_performance = metric.number in {11, 13, 14}
    if metric.denominator not in (None, 0) and metric.numerator is not None:
        observed = 100 * metric.numerator / metric.denominator
    else:
        observed = None

    if metric.result == NA or observed is None:
        values, colors, center = [100], ["#ADB5B2"], "N/E"
    else:
        issue = max(0.0, min(100.0, observed))
        if metric.number in {13, 14}:
            # For high-is-good performance indices, numerator/denominator is achievement.
            values = [issue, 100 - issue]
            colors = ["#159455", "#D6543D"]
        else:
            # Structural metrics report exception share: green is the healthy remainder.
            values = [100 - issue, issue]
            issue_color = "#D6543D" if metric.result == FAIL else "#F0A51A"
            colors = ["#65AD38", issue_color]
        center = f"{observed:.1f}%"

    fig = go.Figure(go.Pie(
        values=values, hole=.62, sort=False, direction="clockwise",
        marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
        textinfo="none", hoverinfo="skip", showlegend=False,
    ))
    center_detail = "Dato requerido" if metric.result == NA else metric.target
    if metric.number == 12 and metric.result == NA:
        center_detail = "F9 requerido"
    fig.add_annotation(text=f"<b>{center}</b><br><span style='font-size:10px'>{center_detail}</span>",
                       x=.5, y=.5, showarrow=False, font=dict(color="#0A2942", size=16))
    fig.update_layout(height=145 if performance_row else 152, margin=dict(l=3, r=3, t=2, b=2), paper_bgcolor="rgba(0,0,0,0)")
    st.markdown(f'<div class="clock-title">{metric.number}. {metric.name}<br>{"<span class=performance-tag>Performance</span>" if is_performance else ""}</div>', unsafe_allow_html=True)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"dcma_clock_{metric.number}")
    st.markdown(f"<div style='text-align:center;font-size:.70rem;color:#526471;margin-top:-14px'>{status_badge(metric.result)}</div>", unsafe_allow_html=True)
    if performance_row and metric.result == NA:
        reasons = {
            11: "Requiere <b>línea base</b> y Data Date validada.",
            12: "Requiere ejecutar la prueba controlada y <b>recalcular en P6</b>.",
            13: "Requiere <b>hito contractual</b> y ruta crítica validada.",
            14: "Requiere <b>línea base contractual</b> vinculada.",
        }
        st.markdown(f'<div class="na-reason">{reasons.get(metric.number, "Información insuficiente para evaluar.")}</div>', unsafe_allow_html=True)


def clock_dashboard(metrics):
    st.markdown('<div class="section-kicker">Schedule Health</div>', unsafe_allow_html=True)
    st.subheader("DCMA 14-Point Assessment")
    st.markdown('''<div class="dcma-legend">
      <span><i class="legend-dot" style="background:#65AD38"></i>Salud</span>
      <span><i class="legend-dot" style="background:#D6543D"></i>Desviación</span>
      <span><i class="legend-dot" style="background:#F0A51A"></i>Revisión</span>
      <span><i class="legend-dot" style="background:#ADB5B2"></i>No evaluable</span>
    </div>''', unsafe_allow_html=True)
    for start in (0, 5):
        row = metrics[start:start + 5]
        cols = st.columns(5, gap="medium")
        for col, metric in zip(cols, row):
            with col:
                dcma_clock(metric)
    st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<div class="performance-heading">Pruebas de desempeño <span>Baseline + ejecución</span></div>', unsafe_allow_html=True)
        st.caption("Estas pruebas no deben aprobarse por ausencia de información: se activan cuando existe línea base, hito contractual o prueba controlada en P6.")
        cols = st.columns(4, gap="large")
        for col, metric in zip(cols, metrics[10:14]):
            with col:
                dcma_clock(metric, performance_row=True)



def _progress_color(progress: float, mapped: bool) -> str:
    """Apartment/window color scale for Location Intelligence."""
    if not mapped:
        return "#323D47"  # original dark glass = no mapped P6 data

    p = max(0.0, min(100.0, float(progress)))
    if p >= 99.5:
        return "#078B55"
    if p >= 75:
        return "#57A96B"
    if p >= 50:
        return "#A9C96F"
    if p >= 25:
        return "#F0C35A"
    if p > 0:
        return "#E59A48"
    return "#E7ECEF"


def _tower_code(tower_name: str) -> str:
    return "SIE" if "sierra" in tower_name.casefold() else "MAR"


def _mapping_text(mapping_level: str) -> str:
    return {
        "APARTMENT": "CBB_Apartamento",
        "FLOOR_PROXY": "CBB_Piso → 4 ventanas",
        "CORE_COMMON": "Área común / CORE",
        "UNMAPPED": "Sin mapeo",
    }.get(mapping_level, mapping_level)


def _blend_level(general: dict, finish: dict, finish_weight: float) -> dict:
    """Luxury blend for Hall/basements without treating missing finish data as zero."""
    if general.get("Mapped") and finish.get("Mapped"):
        return {
            "Mapped": True,
            "Progress": (1.0-finish_weight)*general["Progress"] + finish_weight*finish["Progress"],
            "Activities": general.get("Activities", 0),
            "MetricQuality": "FULL_LUXURY_INDEX",
        }
    if general.get("Mapped"):
        return {**general, "MetricQuality": "GENERAL_ONLY"}
    if finish.get("Mapped"):
        return {**finish, "MetricQuality": "FINISH_ONLY"}
    return {"Mapped": False, "Progress": 0.0, "Activities": 0, "MetricQuality": "UNMAPPED"}



def tower_location_figure(
    grid: pd.DataFrame,
    tower_name: str,
    metric_label: str,
    hall_info: dict | None = None,
    core_data: pd.DataFrame | None = None,
    basement_info: dict | None = None,
):
    """Interactive architectural elevation.

    The visual language follows the advanced Matplotlib building model:
    layered cornice, shaded mansard roof, chimneys, pedimented dormer,
    balconies, basement louvers, central CORE and four apartment windows.

    To preserve Streamlit performance, the interactive view does not draw
    every individual brick; the high-detail brick texture remains available
    in the PNG/SVG architectural export.
    """
    floor_h = 38.0
    b_width = 160.0
    hall_h = floor_h
    res_start_y = hall_h
    top_y = ABOVE_GRADE_FLOORS * floor_h
    basement_height = 2 * floor_h
    roof_h = 55.0

    c_brick = "#B83A2A"
    c_band = "#8A2318"
    c_concrete = "#82878A"
    c_concrete_dark = "#5C6164"
    c_basement_wall = "#2B3036"
    c_roof_border = "#1B1D1F"
    c_trim = "#FFFFFF"
    c_trim_border = "#D0D0D0"
    c_glass = "#323D47"
    c_glass_hall = "#CBE4EC"
    c_glass_elevator = "#B4D5E0"
    c_lift_shaft = "#3E505B"
    c_cornice = "#EDE8E1"

    win_w = 17.5
    win_h = 22.0
    apartment_x = {1: 18.0, 2: 46.0, 3: 114.0, 4: 142.0}
    lift_w = 24.0
    lift_x = (b_width - lift_w) / 2.0
    tower_code = _tower_code(tower_name)

    floor_data = floor_rollup(grid).set_index("Floor").to_dict("index")
    if core_data is None:
        core_data = pd.DataFrame()
    core_by_floor = (
        core_data.set_index("Floor").to_dict("index")
        if not core_data.empty else {}
    )
    basement_info = basement_info or {}

    fig = go.Figure()

    # -------------------------------------------------------------
    # Structural masses
    # -------------------------------------------------------------
    fig.add_shape(
        type="rect",
        x0=0, x1=b_width,
        y0=-basement_height, y1=0,
        fillcolor=c_basement_wall,
        line=dict(color=c_concrete_dark, width=2),
        layer="below",
    )

    fig.add_shape(
        type="rect",
        x0=0, x1=b_width,
        y0=res_start_y, y1=top_y,
        fillcolor=c_brick,
        line=dict(color="#A02E20", width=1.5),
        layer="below",
    )

    # P01 Hall
    hall_info = hall_info or {
        "Mapped": False, "Progress": 0.0, "Activities": 0
    }
    hall_fill = _progress_color(
        hall_info.get("Progress", 0.0),
        hall_info.get("Mapped", False),
    )
    if not hall_info.get("Mapped"):
        hall_fill = c_glass_hall

    fig.add_shape(
        type="rect",
        x0=0, x1=b_width,
        y0=0, y1=hall_h,
        fillcolor=hall_fill,
        line=dict(color=c_concrete, width=2),
        layer="below",
    )

    for m in range(1, 6):
        mx = m * (b_width / 6.0)
        fig.add_shape(
            type="line",
            x0=mx, x1=mx, y0=0, y1=hall_h,
            line=dict(color="#7E9DA8", width=1.2),
        )
    fig.add_shape(
        type="line",
        x0=0, x1=b_width,
        y0=hall_h * .72, y1=hall_h * .72,
        line=dict(color="#7E9DA8", width=1),
    )

    door_w = 26.0
    fig.add_shape(
        type="rect",
        x0=b_width/2-door_w/2,
        x1=b_width/2+door_w/2,
        y0=0, y1=hall_h*.82,
        fillcolor="#9EC0CE",
        line=dict(color="#4A6572", width=1.5),
    )
    fig.add_shape(
        type="line",
        x0=b_width/2, x1=b_width/2,
        y0=0, y1=hall_h*.82,
        line=dict(color="#4A6572", width=1),
    )
    for handle_x in (b_width/2 - 2.5, b_width/2 + 2.5):
        fig.add_shape(
            type="line",
            x0=handle_x, x1=handle_x,
            y0=hall_h*.33, y1=hall_h*.48,
            line=dict(color="#FFFFFF", width=1.5),
        )

    # Floor bands and facade shadows
    for floor in range(3, 15):
        y = (floor - 1) * floor_h
        fig.add_shape(
            type="rect",
            x0=0, x1=b_width,
            y0=y-1.8, y1=y+1.8,
            fillcolor=c_band,
            line=dict(width=0),
        )
        fig.add_shape(
            type="line",
            x0=0, x1=b_width,
            y0=y-2.5, y1=y-2.5,
            line=dict(color="#52120B", width=.7),
        )

    # CORE
    fig.add_shape(
        type="rect",
        x0=lift_x, x1=lift_x+lift_w,
        y0=res_start_y, y1=top_y,
        fillcolor=c_lift_shaft,
        line=dict(color=c_concrete_dark, width=1.3),
    )

    hover_x, hover_y, hover_text, customdata = [], [], [], []

    # -------------------------------------------------------------
    # Apartment windows + balconies + CORE
    # -------------------------------------------------------------
    for floor in RESIDENTIAL_FLOORS:
        fy = (floor - 1) * floor_h

        core = core_by_floor.get(floor, {})
        core_mapped = bool(core.get("Mapped", False))
        core_fill = (
            _progress_color(core.get("Progress", 0.0), core_mapped)
            if core_mapped else c_glass_elevator
        )
        fig.add_shape(
            type="rect",
            x0=lift_x+2.0, x1=lift_x+lift_w-2.0,
            y0=fy+3.0, y1=fy+floor_h-3.0,
            fillcolor=core_fill,
            line=dict(color=c_trim, width=1.0),
        )

        center_x = b_width/2.0
        fig.add_shape(
            type="line",
            x0=center_x, x1=center_x,
            y0=fy+3, y1=fy+floor_h-3,
            line=dict(color="#658896", width=1),
        )
        for guide in (-4, 4):
            fig.add_shape(
                type="line",
                x0=center_x+guide, x1=center_x+guide,
                y0=fy+3, y1=fy+floor_h-3,
                line=dict(color="#658896", width=.55, dash="dot"),
            )

        floor_rows = grid[grid["Floor"] == floor]
        for r in floor_rows.itertuples():
            apartment = int(r.Apartment)
            cx = apartment_x[apartment]
            wx = cx - win_w/2.0
            wy = fy + (floor_h-win_h)/2.0 - 1.0
            fill = _progress_color(float(r.Progress), bool(r.Mapped))

            # Drop shadow
            fig.add_shape(
                type="rect",
                x0=wx-2, x1=wx+win_w+2,
                y0=wy-3.2, y1=wy-1.6,
                fillcolor="#571710",
                opacity=.45,
                line=dict(width=0),
            )

            # White frame: teal border means true apartment-level mapping
            border_color = (
                "#00A88F"
                if getattr(r, "MappingLevel", "") == "APARTMENT"
                else c_trim_border
            )
            fig.add_shape(
                type="rect",
                x0=wx-2, x1=wx+win_w+2,
                y0=wy-2, y1=wy+win_h+2,
                fillcolor=c_trim,
                line=dict(color=border_color, width=1.0),
            )

            # Window face = progress
            fig.add_shape(
                type="rect",
                x0=wx, x1=wx+win_w,
                y0=wy, y1=wy+win_h,
                fillcolor=fill,
                line=dict(color=c_trim, width=.8),
            )

            # Pane grid
            for px in range(1, 3):
                gx = wx + px*(win_w/3.0)
                fig.add_shape(
                    type="line",
                    x0=gx, x1=gx,
                    y0=wy, y1=wy+win_h,
                    line=dict(color=c_trim, width=.55),
                )
            for py in range(1, 4):
                gy = wy + py*(win_h/4.0)
                fig.add_shape(
                    type="line",
                    x0=wx, x1=wx+win_w,
                    y0=gy, y1=gy,
                    line=dict(color=c_trim, width=.55),
                )

            # Lightweight balcony language from the advanced renderer.
            balcony_w = win_w + 6.0
            balcony_h = 7.5
            bx_pos = cx - balcony_w / 2.0
            by_pos = wy - 1.5

            fig.add_shape(
                type="rect",
                x0=bx_pos-1, x1=bx_pos+balcony_w+1,
                y0=by_pos-1.5, y1=by_pos+.2,
                fillcolor=c_concrete,
                line=dict(color=c_concrete_dark, width=.5),
            )
            fig.add_shape(
                type="rect",
                x0=bx_pos, x1=bx_pos+balcony_w,
                y0=by_pos, y1=by_pos+balcony_h,
                fillcolor="#75A4B8",
                opacity=.10,
                line=dict(color="#C2DBE6", width=.55),
            )
            fig.add_shape(
                type="line",
                x0=bx_pos-1, x1=bx_pos+balcony_w+1,
                y0=by_pos+balcony_h, y1=by_pos+balcony_h,
                line=dict(color="#FFFFFF", width=1.25),
            )

            full_location = f"{tower_code}-{r.Location}"
            if bool(r.Mapped):
                detail = (
                    f"<b>{full_location}</b><br>"
                    f"{metric_label}: <b>{r.Progress:.1f}%</b><br>"
                    f"Actividades: {int(r.Activities)}<br>"
                    f"Completadas: {int(r.Complete)} · "
                    f"En progreso: {int(r.Active)} · "
                    f"No iniciadas: {int(r.NotStarted)}<br>"
                    f"Mapeo: {_mapping_text(getattr(r, 'MappingLevel', ''))}"
                )
            else:
                detail = (
                    f"<b>{full_location}</b><br>"
                    "Sin actividades P6 mapeadas"
                )

            hover_x.append(cx)
            hover_y.append(wy + win_h/2.0)
            hover_text.append(detail)
            customdata.append(full_location)

    fig.add_trace(
        go.Scatter(
            x=hover_x,
            y=hover_y,
            mode="markers",
            marker=dict(size=24, color="rgba(0,0,0,0.001)"),
            text=hover_text,
            customdata=customdata,
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    # -------------------------------------------------------------
    # Basement louvers
    # -------------------------------------------------------------
    for b_level, code in ((1, "S1"), (2, "S2")):
        by = -b_level * floor_h
        info = basement_info.get(
            code, {"Mapped": False, "Progress": 0.0}
        )
        cavity_color = (
            _progress_color(
                info.get("Progress", 0.0),
                info.get("Mapped", False),
            )
            if info.get("Mapped") else "#181A1C"
        )

        for bx in (28.0, 80.0, 132.0):
            bw, bh = 26.0, 20.0
            bwx = bx-bw/2
            bwy = by+(floor_h-bh)/2

            fig.add_shape(
                type="rect",
                x0=bwx-2, x1=bwx+bw+2,
                y0=bwy-2, y1=bwy+bh+2,
                fillcolor=c_concrete,
                line=dict(color=c_trim_border, width=.8),
            )
            fig.add_shape(
                type="rect",
                x0=bwx, x1=bwx+bw,
                y0=bwy, y1=bwy+bh,
                fillcolor=cavity_color,
                line=dict(width=0),
            )
            for s in range(7):
                sy = bwy + (s+.5)*(bh/7)
                fig.add_shape(
                    type="line",
                    x0=bwx, x1=bwx+bw,
                    y0=sy, y1=sy,
                    line=dict(color="#D7DEE3", width=.55),
                )

    # -------------------------------------------------------------
    # Layered cornice from the improved code
    # -------------------------------------------------------------
    frieze_h, frieze_ov = 3.4, 4.0
    shadow_h, shadow_ov = 1.4, 5.5
    dent_h, dent_ov = 4.0, 7.0
    crown_h, crown_ov = 3.0, 9.5
    y0 = top_y - (frieze_h + shadow_h + dent_h + crown_h)

    fig.add_shape(
        type="rect",
        x0=0, x1=b_width,
        y0=y0-2.2, y1=y0,
        fillcolor="#3A0E08",
        opacity=.30,
        line=dict(width=0),
    )
    fig.add_shape(
        type="rect",
        x0=-frieze_ov, x1=b_width+frieze_ov,
        y0=y0, y1=y0+frieze_h,
        fillcolor=c_cornice,
        line=dict(color="#D6D0C4", width=.6),
    )

    y1 = y0 + frieze_h
    fig.add_shape(
        type="rect",
        x0=-shadow_ov, x1=b_width+shadow_ov,
        y0=y1, y1=y1+shadow_h,
        fillcolor="#A8A296",
        line=dict(color="#8A8478", width=.5),
    )

    y2 = y1 + shadow_h
    fig.add_shape(
        type="rect",
        x0=-dent_ov, x1=b_width+dent_ov,
        y0=y2, y1=y2+dent_h,
        fillcolor=c_cornice,
        line=dict(color="#BDB7AB", width=.8),
    )

    for dx in range(int(-dent_ov + 2), int(b_width + dent_ov - 4), 7):
        fig.add_shape(
            type="rect",
            x0=dx, x1=dx+4.0,
            y0=y2+.7, y1=y2+dent_h-.7,
            fillcolor="#DAD4C8",
            line=dict(color="#A8A296", width=.25),
        )

    y3 = y2 + dent_h
    fig.add_shape(
        type="rect",
        x0=-crown_ov, x1=b_width+crown_ov,
        y0=y3, y1=y3+crown_h,
        fillcolor="#F7F3EC",
        line=dict(color="#C7C0B2", width=.8),
    )

    # -------------------------------------------------------------
    # Shaded mansard roof simulated with stacked trapezoid bands
    # -------------------------------------------------------------
    roof_colors = [
        "#15171A", "#1B1F23", "#23282D", "#2C3339",
        "#354049", "#414B54", "#4A555F", "#525C66",
    ]
    bottom_left, bottom_right = -12.0, b_width + 12.0
    top_left, top_right = 15.0, b_width - 15.0
    n_bands = len(roof_colors)

    for i, color in enumerate(roof_colors):
        t0 = i / n_bands
        t1 = (i + 1) / n_bands
        yb = top_y + roof_h * t0
        yt = top_y + roof_h * t1

        xl0 = bottom_left + (top_left-bottom_left)*t0
        xr0 = bottom_right + (top_right-bottom_right)*t0
        xl1 = bottom_left + (top_left-bottom_left)*t1
        xr1 = bottom_right + (top_right-bottom_right)*t1

        fig.add_trace(
            go.Scatter(
                x=[xl0, xr0, xr1, xl1, xl0],
                y=[yb, yb, yt, yt, yb],
                mode="lines",
                fill="toself",
                fillcolor=color,
                line=dict(color=color, width=.2),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Roof outline and slate courses
    fig.add_trace(
        go.Scatter(
            x=[bottom_left, bottom_right, top_right, top_left, bottom_left],
            y=[top_y, top_y, top_y+roof_h, top_y+roof_h, top_y],
            mode="lines",
            line=dict(color=c_roof_border, width=1.5),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    for i in range(1, 7):
        t = i / 7
        y = top_y + roof_h * t
        xl = bottom_left + (top_left-bottom_left)*t
        xr = bottom_right + (top_right-bottom_right)*t
        fig.add_shape(
            type="line",
            x0=xl, x1=xr, y0=y, y1=y,
            line=dict(color="#111418", width=.6),
        )

    # Ridge cresting
    fig.add_shape(
        type="line",
        x0=top_left, x1=top_right,
        y0=top_y+roof_h, y1=top_y+roof_h,
        line=dict(color="#9BA5AD", width=1.2),
    )
    for cx in range(18, int(b_width - 15), 9):
        fig.add_shape(
            type="line",
            x0=cx, x1=cx,
            y0=top_y+roof_h,
            y1=top_y+roof_h+2.2,
            line=dict(color="#9BA5AD", width=.8),
        )

    # Chimneys
    for cx in (b_width*.20, b_width*.80):
        ch_y = top_y + roof_h*.40
        ch_w, ch_h = 10.0, 15.0
        fig.add_shape(
            type="rect",
            x0=cx-ch_w/2, x1=cx+ch_w/2,
            y0=ch_y, y1=ch_y+ch_h,
            fillcolor=c_band,
            line=dict(color="#4A140D", width=.8),
        )
        fig.add_shape(
            type="rect",
            x0=cx-ch_w/2-1.2, x1=cx+ch_w/2+1.2,
            y0=ch_y+ch_h, y1=ch_y+ch_h+2,
            fillcolor="#3A3F43",
            line=dict(color="#1B1D1F", width=.6),
        )

    # Pedimented dormer
    dm_w, dm_h = 26.0, 30.0
    dm_x = (b_width-dm_w)/2
    dm_y = top_y+10.0
    apex_x = b_width/2
    apex_y = dm_y+dm_h+9.0
    base_y = dm_y+dm_h

    fig.add_trace(
        go.Scatter(
            x=[dm_x-4, apex_x, apex_x, dm_x-4],
            y=[base_y, apex_y, base_y, base_y],
            mode="lines",
            fill="toself",
            fillcolor="#3D4247",
            line=dict(color="#FFFFFF", width=1),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[apex_x, dm_x+dm_w+4, apex_x, apex_x],
            y=[apex_y, base_y, base_y, apex_y],
            mode="lines",
            fill="toself",
            fillcolor="#24272A",
            line=dict(color="#FFFFFF", width=1),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.add_shape(
        type="rect",
        x0=dm_x, x1=dm_x+dm_w,
        y0=dm_y, y1=dm_y+dm_h-2,
        fillcolor=c_trim,
        line=dict(color=c_trim_border, width=.8),
    )
    fig.add_shape(
        type="rect",
        x0=dm_x+4, x1=dm_x+dm_w-4,
        y0=dm_y+3, y1=dm_y+dm_h-6,
        fillcolor=c_glass,
        line=dict(width=0),
    )

    # Lightning rod
    fig.add_shape(
        type="line",
        x0=apex_x, x1=apex_x,
        y0=apex_y, y1=apex_y+6.5,
        line=dict(color="#9BA5AD", width=1.1),
    )
    fig.add_shape(
        type="circle",
        x0=apex_x-.9, x1=apex_x+.9,
        y0=apex_y+5.6, y1=apex_y+7.4,
        fillcolor="#C7CDD2",
        line=dict(color="#6E7882", width=.5),
    )

    # -------------------------------------------------------------
    # Labels and derived floor status
    # -------------------------------------------------------------
    fig.add_annotation(
        x=b_width/2,
        y=top_y+roof_h+31,
        text=(
            "APT01 · APT02 &nbsp;&nbsp;|&nbsp;&nbsp; "
            "CORE &nbsp;&nbsp;|&nbsp;&nbsp; APT03 · APT04"
        ),
        showarrow=False,
        font=dict(size=9, color="#526471"),
    )

    fig.add_annotation(
        x=b_width+13,
        y=-floor_h*1.5,
        text="<b>S2</b>",
        showarrow=False,
        font=dict(size=10, color="#FFFFFF"),
    )
    fig.add_annotation(
        x=b_width+13,
        y=-floor_h*.5,
        text="<b>S1</b>",
        showarrow=False,
        font=dict(size=10, color="#FFFFFF"),
    )
    fig.add_annotation(
        x=b_width+13,
        y=hall_h/2,
        text="<b>P01 · HALL</b>",
        showarrow=False,
        font=dict(size=9, color="#082D50"),
    )

    for floor in RESIDENTIAL_FLOORS:
        mid_y = (floor-1)*floor_h + floor_h/2
        info = floor_data.get(floor, {})
        label = f"P{floor:02d}"
        if info.get("Mapped"):
            label += f"  {info.get('Progress', 0):.0f}%"

        fig.add_annotation(
            x=b_width+16,
            y=mid_y,
            text=f"<b>{label}</b>",
            showarrow=False,
            xanchor="left",
            font=dict(size=9, color="#082D50"),
        )

        badge_color = _progress_color(
            info.get("Progress", 0.0),
            bool(info.get("Mapped", False)),
        )
        fig.add_shape(
            type="circle",
            x0=b_width+10.5, x1=b_width+14.0,
            y0=mid_y-1.75, y1=mid_y+1.75,
            fillcolor=badge_color,
            line=dict(color="#FFFFFF", width=.6),
        )

    fig.add_annotation(
        x=b_width/2,
        y=top_y+roof_h+18,
        text=(
            f"<b>{tower_name.upper()}</b><br>"
            "<span style='font-size:11px'>"
            "S2 + S1 · P01 Hall · P02–P14 residencial · 52 apartamentos"
            "</span>"
        ),
        showarrow=False,
        align="center",
        font=dict(size=18, color="#082D50"),
    )

    # Preserve architectural proportions.
    fig.update_xaxes(
        visible=False,
        range=[-18, b_width+48],
        fixedrange=True,
        constrain="domain",
    )
    fig.update_yaxes(
        visible=False,
        range=[-basement_height-12, top_y+roof_h+42],
        fixedrange=True,
        scaleanchor="x",
        scaleratio=1,
        constrain="domain",
    )
    fig.update_layout(
        height=1180,
        margin=dict(l=10, r=10, t=18, b=10),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#EDF4FA",
        hoverlabel=dict(bgcolor="white", font_size=12),
        dragmode=False,
    )

    return fig

def _find_project(projects, token: str):
    token = token.casefold()
    return next((p for p in projects if token in (p.name or "").casefold()), None)


def _find_platform_project(projects):
    tokens = ("plataforma", "urbanismo", "infraestructura", "urban", "infra")
    for project_obj in projects:
        name = (project_obj.name or "").casefold()
        if any(token in name for token in tokens):
            return project_obj
    return None


def _matching_baseline(project_obj, baselines):
    if project_obj is None:
        return None
    return next((
        b for b in baselines
        if b.name == project_obj.name
        or b.project.get("proj_id") == project_obj.project.get("proj_id")
        or b.project.get("orig_proj_id") == project_obj.project.get("orig_proj_id")
    ), None)


def _location_legend():
    st.markdown(
        """
        <div style="display:flex;gap:14px;flex-wrap:wrap;
                    font-size:.78rem;color:#526471;margin:-4px 0 10px">
          <span><i class="legend-dot" style="background:#323D47"></i>Sin mapeo P6</span>
          <span><i class="legend-dot" style="background:#E7ECEF"></i>0%</span>
          <span><i class="legend-dot" style="background:#E59A48"></i>1–24%</span>
          <span><i class="legend-dot" style="background:#F0C35A"></i>25–49%</span>
          <span><i class="legend-dot" style="background:#A9C96F"></i>50–74%</span>
          <span><i class="legend-dot" style="background:#57A96B"></i>75–99%</span>
          <span><i class="legend-dot" style="background:#078B55"></i>100%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_tower_chart(fig):
    """Center the tall elevation so it retains architectural proportion."""
    _, center, _ = st.columns([.75, 1.5, .75])
    with center:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _location_detail_panel(tower_name: str, general_grid: pd.DataFrame, luxury_grid: pd.DataFrame):
    tower_code = _tower_code(tower_name)
    options = general_grid["Location"].tolist()
    selected = st.selectbox(
        "Detalle de apartamento",
        options,
        key=f"apt_detail_{tower_name}",
        format_func=lambda x: f"{tower_code}-{x}",
    )
    g = general_grid[general_grid["Location"] == selected].iloc[0]
    l = luxury_grid[luxury_grid["Location"] == selected].iloc[0]

    with st.container(border=True):
        st.markdown(f"#### {tower_code}-{selected}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avance general", f"{g['Progress']:.1f}%" if g["Mapped"] else "N/D")
        c2.metric("Acabados", f"{l['FinishProgress']:.1f}%" if l["FinishMapped"] else "N/D")
        c3.metric("Luxury Index", f"{l['Progress']:.1f}%" if l["Mapped"] else "N/D")
        c4.metric("Actividades", int(g["Activities"]))
        c5.metric("Mapeo", _mapping_text(str(g["MappingLevel"])))

        quality = str(l.get("MetricQuality", "UNMAPPED"))
        if quality == "GENERAL_ONLY":
            st.warning(
                "No hay actividades de acabados identificadas para esta localización. "
                "El Luxury Index usa temporalmente el avance general y no interpreta la ausencia como 0%."
            )
        elif quality == "FULL_LUXURY_INDEX":
            st.caption("Luxury Index calculado con datos de avance general y de acabados.")



def _architectural_export_panel(
    project_obj,
    tower_name: str,
    view_mode: str,
    finish_weight: float,
):
    """Generate report-quality PNG/SVG from the advanced Matplotlib renderer."""
    tower_code = _tower_code(tower_name)
    view = "luxury" if view_mode == "Acabados / Luxury Index" else "general"

    progress = progress_by_location(
        project_obj,
        tower_code=tower_code,
        view=view,
        finish_weight=finish_weight,
    )

    with st.expander("Exportar elevación arquitectónica"):
        st.caption(
            "La exportación usa el render de alto detalle: textura de ladrillo, "
            "balcones, cornisa estratificada, mansarda sombreada, chimeneas y dormer."
        )

        balconies = st.toggle(
            "Mostrar balcones",
            value=True,
            key=f"export_balconies_{tower_name}",
        )

        if st.button(
            "Generar PNG y SVG",
            key=f"generate_arch_{tower_name}",
            type="secondary",
        ):
            cfg = BuildingConfig(has_balconies=balconies)

            png_renderer = BuildingRenderer(
                cfg,
                tower_code=tower_code,
                tower_name=tower_name,
                progress_by_location=progress,
            )
            png_bytes = png_renderer.render_bytes("png")

            svg_renderer = BuildingRenderer(
                cfg,
                tower_code=tower_code,
                tower_name=tower_name,
                progress_by_location=progress,
            )
            svg_bytes = svg_renderer.render_bytes("svg")

            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "Descargar PNG",
                    png_bytes,
                    file_name=f"{tower_code}_location_intelligence_v0.4.0.png",
                    mime="image/png",
                    key=f"png_export_{tower_name}",
                )
            with c2:
                st.download_button(
                    "Descargar SVG",
                    svg_bytes,
                    file_name=f"{tower_code}_location_intelligence_v0.4.0.svg",
                    mime="image/svg+xml",
                    key=f"svg_export_{tower_name}",
                )
            st.image(
                png_bytes,
                caption=f"{tower_name} · vista arquitectónica de reporte",
                use_container_width=True,
            )


def _p6_readiness(project_obj):
    q = mapping_quality(project_obj)
    with st.expander("Preparación de Activity Codes P6"):
        rows = pd.DataFrame([
            {"Activity Code": "CBB_Piso", "Estado": "✓" if q["HasFloor"] else "—", "Uso": "Nivel / piso"},
            {"Activity Code": "CBB_Apartamento", "Estado": "✓" if q["HasApartment"] else "Pendiente", "Uso": "APT01–APT04 independiente"},
            {"Activity Code": "CBB_Procesos", "Estado": "✓" if q["HasProcess"] else "—", "Uso": "Acabados / proceso"},
            {"Activity Code": "CBB_Zona", "Estado": "✓" if q["HasZone"] else "Propuesto", "Uso": "HALL / CORE / áreas comunes"},
        ])
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption(
            f"Ventanas mapeadas: {q['MappedWindows']} de {q['TotalWindows']} · "
            f"Pisos residenciales con datos: {q['MappedFloors']} de {q['TotalFloors']}."
        )


def render_tower_layer(project_obj, tower_name: str):
    st.markdown(f"### {tower_name}")

    if project_obj is None:
        st.warning(
            f"No se encontró un XER asociado a {tower_name}. "
            "Se muestra la geometría espacial sin mapeo P6."
        )
        grid = tower_grid(None)
        _location_legend()
        _render_tower_chart(
            tower_location_figure(grid, tower_name, "Avance", hall_info=None)
        )
        return

    view_mode = st.radio(
        "Lectura de la fachada",
        ["Avance general", "Acabados / Luxury Index"],
        horizontal=True,
        key=f"location_mode_{tower_name}",
        help="La ventana es el apartamento. El color cambia según la métrica seleccionada.",
    )

    finish_weight = .65
    if view_mode == "Acabados / Luxury Index":
        finish_pct = st.slider(
            "Preponderancia de acabados",
            min_value=50, max_value=80, value=65, step=5,
            key=f"finish_weight_{tower_name}",
            help="En vivienda extra lujo los acabados pueden dominar la lectura de madurez. El valor por defecto es 65%.",
        )
        finish_weight = finish_pct / 100.0
        st.caption(
            f"Luxury Index = {(1-finish_weight):.0%} × avance general + "
            f"{finish_weight:.0%} × acabados, cuando ambos datos existen."
        )

    general_grid = tower_grid(project_obj)
    luxury_grid = luxury_index_grid(
        project_obj,
        general_weight=1.0-finish_weight,
        finish_weight=finish_weight,
    )

    if view_mode == "Acabados / Luxury Index":
        grid = luxury_grid
        metric_label = f"Luxury Index {int((1-finish_weight)*100)}/{int(finish_weight*100)}"
        hall_info = _blend_level(
            hall_progress(project_obj, finishes_only=False),
            hall_progress(project_obj, finishes_only=True),
            finish_weight,
        )
        basement_info = {
            code: _blend_level(
                basement_progress(project_obj, code, finishes_only=False),
                basement_progress(project_obj, code, finishes_only=True),
                finish_weight,
            )
            for code in ("S1", "S2")
        }
        core_data = luxury_core_grid(
            project_obj,
            general_weight=1.0-finish_weight,
            finish_weight=finish_weight,
        )
    else:
        grid = general_grid
        metric_label = "Avance físico"
        hall_info = hall_progress(project_obj, finishes_only=False)
        basement_info = {
            code: basement_progress(project_obj, code, finishes_only=False)
            for code in ("S1", "S2")
        }
        core_data = core_grid(project_obj, finishes_only=False)

    q = mapping_quality(project_obj)
    mapped = grid[grid["Mapped"]]
    apartment_code_available = q["HasApartment"]
    mapping_label = "Apartamento" if apartment_code_available else "Piso → 4 ventanas"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Sobre rasante", "14")
    c2.metric("P01", "Hall")
    c3.metric("Residenciales", "13")
    c4.metric("Apartamentos", str(RESIDENTIAL_UNITS_PER_TOWER))
    c5.metric(metric_label, f"{mapped['Progress'].mean():.1f}%" if not mapped.empty else "N/D")
    c6.metric("Granularidad", mapping_label)

    if view_mode == "Acabados / Luxury Index":
        general_mapped = luxury_grid[luxury_grid["GeneralMapped"]]
        if not general_mapped.empty:
            finish_coverage = 100.0 * general_mapped["FinishMapped"].mean()
            st.caption(f"Cobertura de datos de acabados sobre localizaciones con avance general: **{finish_coverage:.0f}%**.")
            if finish_coverage < 100:
                st.info(
                    "Las localizaciones sin datos de acabados no se penalizan artificialmente como 0%; "
                    "se muestran con avance general y quedan marcadas como GENERAL_ONLY."
                )

    _location_legend()
    _render_tower_chart(
        tower_location_figure(
            grid,
            tower_name,
            metric_label,
            hall_info=hall_info,
            core_data=core_data,
            basement_info=basement_info,
        )
    )

    _location_detail_panel(tower_name, general_grid, luxury_grid)
    _architectural_export_panel(project_obj, tower_name, view_mode, finish_weight)
    _p6_readiness(project_obj)

    if apartment_code_available:
        st.success(
            "CBB_Apartamento detectado: cada ventana puede representar el avance independiente de su apartamento."
        )
    else:
        st.info(
            "El XER actual aún no contiene CBB_Apartamento. El avance de CBB_Piso se proyecta explícitamente "
            "sobre las cuatro ventanas. Al incorporar APT01–APT04 en P6, cada ventana se independizará sin cambiar la geometría."
        )


def render_location_model(projects):
    st.markdown('<div class="section-kicker">Location Intelligence 2.0</div>', unsafe_allow_html=True)
    st.subheader("Modelo espacial del proyecto")
    st.write(
        "La fachada es una matriz visual de producción. Cada ventana residencial representa un apartamento; "
        "el CORE, el Hall y los sótanos conservan identidad propia. El estado del piso se deriva de sus apartamentos, "
        "no al revés."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Torres", 2)
    c2.metric("Sobre rasante", "14 pisos")
    c3.metric("Apartamentos / piso", APARTMENTS_PER_FLOOR)
    c4.metric("Unidades residenciales", RESIDENTIAL_UNITS_PER_TOWER * 2)

    layer = st.segmented_control(
        "Capa",
        ["1 · Torre Mar", "2 · Torre Sierra", "3 · Plataforma"],
        default="1 · Torre Mar",
        selection_mode="single",
    )

    mar = _find_project(projects, "torre mar")
    sierra = _find_project(projects, "torre sierra")
    infra = _find_platform_project(projects)

    if layer == "2 · Torre Sierra":
        render_tower_layer(sierra, "Torre Sierra")

    elif layer == "3 · Plataforma":
        st.markdown("### Plataforma · Urbanismo")
        if infra is None:
            st.info(
                "La tercera capa corresponde a Plataforma e incluye urbanismo e infraestructura exterior. "
                "Se poblará al cargar el XER correspondiente; la geometría se deriva de Sector/Tramo/Zona "
                "y no se fuerza a una lógica vertical de pisos."
            )
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Actividades", f"{len(infra.tasks):,}")
            c2.metric("Relaciones", f"{len(infra.relationships):,}")
            c3.metric("Asignaciones", f"{len(infra.assignments):,}")
            st.success("XER de Plataforma identificado. La Línea de Balance puede leer sectores/tramos y procesos repetitivos.")

        st.markdown("#### Estructura prevista de codificación")
        st.dataframe(
            pd.DataFrame([
                {"Nivel": "Obra", "Activity Code": "CBB_Obras", "Ejemplo": "Plataforma / Urbanismo"},
                {"Nivel": "Zona / sector", "Activity Code": "CBB_Sector", "Ejemplo": "Por definir"},
                {"Nivel": "Sistema", "Activity Code": "CBB_Sistema", "Ejemplo": "Por definir"},
                {"Nivel": "Proceso", "Activity Code": "CBB_Procesos", "Ejemplo": "Proceso P6"},
            ]),
            width="stretch", hide_index=True,
        )
        st.caption("CBB_Sector y CBB_Sistema son propuestas; no se asume que existan todavía en el XER.")

    else:
        render_tower_layer(mar, "Torre Mar")

    with st.expander("Maestro espacial del proyecto"):
        master = model_master()
        st.dataframe(master, width="stretch", hide_index=True)
        apartments = master[master["LocationType"] == "APARTMENT"]
        st.caption(
            f"Control: {len(apartments)} apartamentos residenciales "
            f"({RESIDENTIAL_UNITS_PER_TOWER} Torre Mar + {RESIDENTIAL_UNITS_PER_TOWER} Torre Sierra)."
        )
        st.download_button(
            "Descargar maestro espacial CSV",
            master.to_csv(index=False).encode("utf-8-sig"),
            "location_master_v0.4.0.csv",
            "text/csv",
        )


def _lob_location_ticks(frame: pd.DataFrame):
    locs = (
        frame[["LocationOrder", "Location"]]
        .drop_duplicates()
        .sort_values("LocationOrder")
    )
    return locs["LocationOrder"].tolist(), locs["Location"].tolist()


def _lob_chart(frame: pd.DataFrame, selected_processes: list[str], show_finish: bool, show_plan: bool, show_baseline: bool):
    plot = frame[frame["Process"].isin(selected_processes)].copy()
    fig = go.Figure()
    palette = px.colors.qualitative.Safe + px.colors.qualitative.Set2 + px.colors.qualitative.Plotly

    for i, process in enumerate(selected_processes):
        g = plot[plot["Process"] == process].sort_values("LocationOrder")
        if g.empty:
            continue
        color = palette[i % len(palette)]
        custom = g[["Location", "RawLocation", "Activities", "Progress", "Complete", "Active", "NotStarted"]].to_numpy()
        fig.add_trace(go.Scatter(
            x=g["CurrentStart"], y=g["LocationOrder"], mode="lines+markers",
            name=process, legendgroup=process,
            line=dict(color=color, width=3), marker=dict(size=7),
            customdata=custom,
            hovertemplate=(
                "<b>%{fullData.name}</b><br>Localización: %{customdata[0]}"
                "<br>Código P6: %{customdata[1]}<br>Inicio vigente: %{x|%d-%b-%Y}"
                "<br>Actividades: %{customdata[2]}<br>Avance medio: %{customdata[3]:.1f}%"
                "<br>C / IP / NS: %{customdata[4]} / %{customdata[5]} / %{customdata[6]}<extra></extra>"
            ),
        ))
        if show_finish:
            fig.add_trace(go.Scatter(
                x=g["CurrentFinish"], y=g["LocationOrder"], mode="lines+markers",
                name=f"{process} · fin", legendgroup=process, showlegend=False,
                line=dict(color=color, width=1.5, dash="dot"), marker=dict(size=5, symbol="diamond"),
                hovertemplate=f"<b>{process}</b><br>Fin vigente: %{{x|%d-%b-%Y}}<extra></extra>",
            ))
        if show_plan:
            fig.add_trace(go.Scatter(
                x=g["PlannedStart"], y=g["LocationOrder"], mode="lines",
                name=f"{process} · plan", legendgroup=process, showlegend=False,
                line=dict(color=color, width=1.5, dash="dash"), opacity=.5,
                hovertemplate=f"<b>{process}</b><br>Inicio plan: %{{x|%d-%b-%Y}}<extra></extra>",
            ))
        if show_baseline and "BaselineStart" in g.columns:
            fig.add_trace(go.Scatter(
                x=g["BaselineStart"], y=g["LocationOrder"], mode="lines",
                name=f"{process} · baseline", legendgroup=process, showlegend=False,
                line=dict(color=color, width=2, dash="dashdot"), opacity=.35,
                hovertemplate=f"<b>{process}</b><br>Inicio baseline: %{{x|%d-%b-%Y}}<extra></extra>",
            ))

    tickvals, ticktext = _lob_location_ticks(plot)
    fig.update_yaxes(
        tickmode="array", tickvals=tickvals, ticktext=ticktext,
        title="LOCALIZACIÓN", gridcolor="#DCE8EC", zeroline=False,
    )
    fig.update_xaxes(title="TIEMPO", gridcolor="#E6EEF1")
    fig.update_layout(
        height=720, margin=dict(l=35, r=20, t=35, b=45),
        paper_bgcolor="#FFFFFF", plot_bgcolor="#FBFDFE",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="closest",
    )
    return fig


def _render_lob_layer(project_obj, baseline_obj, layer_name: str, platform: bool = False):
    st.markdown(f"### {layer_name}")
    if project_obj is None:
        if platform:
            st.info(
                "No hay XER de Plataforma cargado. La capa está lista para leer CBB_Sector, CBB_Tramo, "
                "CBB_Zona o referencias Tramo/Sector/Zona en los nombres de actividad."
            )
        else:
            st.warning(f"No se encontró un XER asociado a {layer_name}.")
        return

    frame = platform_lob(project_obj) if platform else tower_lob(project_obj)
    if baseline_obj is not None:
        baseline_frame = platform_lob(baseline_obj) if platform else tower_lob(baseline_obj)
        if not baseline_frame.empty:
            baseline_dates = baseline_frame[[
                "Process", "Location", "PlannedStart", "PlannedFinish"
            ]].rename(columns={
                "PlannedStart": "BaselineStart",
                "PlannedFinish": "BaselineFinish",
            })
            frame = frame.merge(baseline_dates, on=["Process", "Location"], how="left")
    if frame.empty:
        st.warning(
            "No fue posible construir pares Proceso–Localización. Verifique CBB_Procesos y los códigos de ubicación."
        )
        return

    if not platform:
        include_substructure = st.toggle(
            "Incluir cimentación y sótanos", value=False, key=f"lob_sub_{layer_name}"
        )
        if not include_substructure:
            frame = frame[frame["Repetitive"]].copy()

    counts = frame.groupby("Process")["Location"].nunique().sort_values(ascending=False)
    candidates = counts.index.tolist()
    default_processes = candidates[:min(6, len(candidates))]
    selected_processes = st.multiselect(
        "Procesos", candidates, default=default_processes, key=f"lob_process_{layer_name}",
        help="Priorice procesos repetitivos con presencia en varias localizaciones."
    )
    if not selected_processes:
        st.info("Seleccione al menos un proceso.")
        return

    copt1, copt2, copt3 = st.columns(3)
    with copt1:
        show_finish = st.toggle("Mostrar línea de fin", value=True, key=f"lob_finish_{layer_name}")
    with copt2:
        show_plan = st.toggle("Mostrar Planned/Target", value=False, key=f"lob_plan_{layer_name}")
    with copt3:
        has_baseline = "BaselineStart" in frame.columns and frame["BaselineStart"].notna().any()
        show_baseline = st.toggle(
            "Mostrar Baseline", value=has_baseline, disabled=not has_baseline, key=f"lob_baseline_{layer_name}"
        )

    view = frame[frame["Process"].isin(selected_processes)].copy()
    metrics_df = process_metrics(view)
    overlaps = overlap_register(view)
    valid_cycles = metrics_df["CycleDays"].dropna()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Procesos visibles", len(selected_processes))
    c2.metric("Localizaciones", int(view["Location"].nunique()))
    c3.metric("Cycle time mediano", f"{valid_cycles.median():.1f} d/loc" if not valid_cycles.empty else "N/D")
    c4.metric("Solapes potenciales", len(overlaps))

    st.plotly_chart(
        _lob_chart(view, selected_processes, show_finish, show_plan, show_baseline),
        width="stretch", key=f"lob_chart_{layer_name}", config={"displaylogo": False}
    )
    st.caption(
        "Línea sólida = inicio vigente (actual cuando existe; de lo contrario forecast P6). "
        "Línea punteada = fin vigente. Los solapes son señales de revisión constructiva, no defectos automáticos."
    )

    left, right = st.columns([1.05, .95])
    with left:
        st.markdown("#### Velocidad de producción")
        display_metrics = metrics_df.copy()
        if not display_metrics.empty:
            display_metrics["CycleDays"] = display_metrics["CycleDays"].map(lambda x: round(x, 2) if pd.notna(x) else None)
            display_metrics["RatePerDay"] = display_metrics["RatePerDay"].map(lambda x: round(x, 4) if pd.notna(x) else None)
        st.dataframe(display_metrics, width="stretch", hide_index=True)
    with right:
        st.markdown("#### Registro de interferencias")
        if overlaps.empty:
            st.success("No se detectan solapes temporales entre procesos consecutivos en la vista seleccionada.")
        else:
            show_overlap = overlaps.sort_values("OverlapDays", ascending=False).copy()
            show_overlap["OverlapDays"] = show_overlap["OverlapDays"].round(1)
            st.dataframe(show_overlap.head(30), width="stretch", hide_index=True)

    with st.expander("Datos LOB derivados del XER"):
        cols = [
            "Process", "Location", "RawLocation", "Activities", "Progress",
            "PlannedStart", "PlannedFinish", "CurrentStart", "CurrentFinish"
        ]
        cols += [c for c in ("BaselineStart", "BaselineFinish") if c in view.columns]
        st.dataframe(view[cols].sort_values(["Process", "Location"]), width="stretch", hide_index=True)
        st.download_button(
            "Descargar datos LOB CSV",
            view.to_csv(index=False).encode("utf-8-sig"),
            f"LOB_{layer_name.replace(' ', '_')}_v0.4.0.csv",
            "text/csv",
            key=f"lob_csv_{layer_name}",
        )


def render_line_of_balance(projects, baselines):
    st.markdown('<div class="section-kicker">Location-Based Production Control</div>', unsafe_allow_html=True)
    st.subheader("Línea de Balance")
    st.write(
        "La vista separa explícitamente tiempo, localización y proceso. Las torres usan niveles verticales; "
        "Plataforma usa sectores o tramos de urbanismo e infraestructura exterior."
    )

    layer = st.segmented_control(
        "Capa LOB",
        ["1 · Torre Mar", "2 · Torre Sierra", "3 · Plataforma"],
        default="1 · Torre Mar", selection_mode="single", key="lob_layer",
    )
    mar = _find_project(projects, "torre mar")
    sierra = _find_project(projects, "torre sierra")
    platform = _find_platform_project(projects)

    if layer == "2 · Torre Sierra":
        _render_lob_layer(sierra, _matching_baseline(sierra, baselines), "Torre Sierra")
    elif layer == "3 · Plataforma":
        _render_lob_layer(platform, _matching_baseline(platform, baselines), "Plataforma", platform=True)
    else:
        _render_lob_layer(mar, _matching_baseline(mar, baselines), "Torre Mar")

    with st.expander("Convención espacial utilizada"):
        st.markdown(
            """
            **Torres:** el XER actual usa `Piso 1 = S2`, `Piso 2 = S1`, `Piso 3 = P01` … `Piso 16 = P14`.
            `Piso -2` se conserva como **CIM** (cimentación) y no se confunde con un tercer sótano.

            **Plataforma:** la localización se obtiene, en este orden, de `CBB_Sector`, `CBB_Tramo`, `CBB_Zona`
            (o códigos equivalentes) y, como respaldo, de expresiones Sector/Tramo/Zona/Frente en el nombre de actividad.
            """
        )



product_header()

with st.sidebar:
    sidebar_branding_top()
    st.markdown('<div class="section-kicker">Paso 1 de 4</div>', unsafe_allow_html=True)
    st.header("Cargar información")
    current_files = st.file_uploader("XER actuales", type=["xer"], accept_multiple_files=True,
                                     help="Puede cargar uno o varios proyectos del mismo corte.")
    baseline_files = st.file_uploader("Baseline XER (opcional)", type=["xer"], accept_multiple_files=True,
                                      help="Use nombres o Project IDs equivalentes para emparejar.")
    st.caption("La prueba 12 requiere un recálculo controlado en P6; no se simula silenciosamente.")
    use_demo = st.toggle("Usar Torre Mar y Torre Sierra de demostración", value=not current_files)
    input_state = "XER cargado" if current_files else ("Demo activo" if use_demo else "Pendiente")
    baseline_state = "Cargada" if baseline_files else "Opcional · pendiente"
    st.markdown(f'''<div class="workflow-card"><b>Estado del análisis</b><br>
      <span class="active">●</span> Entrada actual: {input_state}<br>
      ○ Línea base: {baseline_state}<br><br>
      <b>Flujo de trabajo</b><br>
      <span class="active">1 · Cargar y seleccionar</span><br>
      2 · Auditar las 14 pruebas<br>
      3 · Validar hallazgos<br>
      4 · Emitir decisión</div>''', unsafe_allow_html=True)
    st.caption("DCMA + ESM Manager · v0.4.0")
    sidebar_branding_bottom()

current = []
if current_files:
    current = [parse_cached(f.getvalue(), f.name) for f in current_files]
elif use_demo:
    for path in [ROOT / "demo/torre_mar_v2.xer", ROOT / "demo/torre_sierra_v2.xer"]:
        current.append(parse_cached(path.read_bytes(), path.name))

baselines = []
if baseline_files:
    baselines = [parse_cached(f.getvalue(), f.name) for f in baseline_files]

if not current:
    st.info("Cargue al menos un archivo XER para comenzar el análisis.")
    st.stop()

names = [p.name for p in current]
selected_name = st.selectbox("Proyecto activo", names)
project = next(p for p in current if p.name == selected_name)
baseline = next((b for b in baselines if b.name == project.name or b.project.get("proj_id") == project.project.get("proj_id")), None)
metrics, detail = assess(project, baseline)
metric_df = pd.DataFrame([m.dict() for m in metrics])
metric_df["Estado"] = metric_df["result"].map(status_badge)

p_context = project.project
st.markdown(f'''<div class="context-strip">
  <span class="context-chip"><b>Proyecto:</b> {project.name}</span>
  <span class="context-chip"><b>Data Date:</b> {p_context.get('last_recalc_date') or 'N/D'}</span>
  <span class="context-chip"><b>Origen:</b> {project.source or 'XER'}</span>
  <span class="context-chip"><b>Baseline:</b> {'Vinculada' if baseline else 'No cargada'}</span>
</div>''', unsafe_allow_html=True)

tab_resumen, tab_location, tab_lob, tab_dcma, tab_findings, tab_resources, tab_esm, tab_xer, tab_protocol = st.tabs([
    "Resumen", "Modelo de Localización", "Línea de Balance", "DCMA 14-Point", "Hallazgos", "Recursos y costos", "Earned Schedule", "Datos XER", "Protocolo"
])

with tab_resumen:
    p = project.project
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Actividades", f"{len(project.tasks):,}")
    c2.metric("Relaciones", f"{len(project.relationships):,}")
    c3.metric("Asignaciones", f"{len(project.assignments):,}")
    c4.metric("No cumple", int((metric_df.result == FAIL).sum()))
    c5.metric("No evaluable", int((metric_df.result == NA).sum()))
    c6.metric("Cumplimiento", f"{int((metric_df.result == PASS).sum())}/14")
    st.caption(f"Fuente: {project.source or 'XER'} · versión {project.export_version or 'N/D'} · exportación {project.export_date or 'N/D'} · último recálculo {p.get('last_recalc_date') or 'N/D'}")

    clock_dashboard(metrics)

    st.subheader("Lectura ejecutiva")
    if (metric_df.result == FAIL).sum() >= 4:
        st.error("El cronograma requiere intervención antes de utilizar sus fechas como compromiso ejecutable.")
    else:
        st.success("El cronograma supera la primera criba; continúe con validación constructiva y de capacidad.")
    st.write("La conformidad DCMA evalúa salud estructural. No reemplaza la validación de alcance, localización, cantidades, productividad, interfaces ni recursos reales.")

with tab_location:
    render_location_model(current)

with tab_lob:
    render_line_of_balance(current, baselines)

with tab_dcma:
    st.subheader("DCMA 14-Point Schedule Assessment")
    st.dataframe(metric_df[["number","name","Estado","value","target","note"]].rename(columns={"number":"#","name":"Prueba","value":"Resultado","target":"Meta","note":"Nota"}),
                 width="stretch", hide_index=True, height=560)
    dataframe_download(metric_df, f"dcma_14_{project.name}.csv")
    with st.expander("Cómo completar las métricas no evaluables"):
        st.markdown("""
        - **11 Missed Tasks y 14 BEI:** cargue la línea base contractual y confirme la Data Date.
        - **12 Critical Path Test:** en una copia de P6, añada 600 días a una actividad crítica, recalcule y cargue el XER de prueba en una futura versión del módulo.
        - **13 CPLI:** seleccione el hito contractual y valide Critical Path Length y Total Float.
        """)

with tab_findings:
    st.subheader("Explorador de hallazgos")
    finding = st.selectbox("Categoría", [
        ("missing_logic", "Lógica faltante"), ("leads", "Leads"), ("lags", "Lags"),
        ("non_fs", "Relaciones no-FS"), ("hard_constraints", "Restricciones duras"),
        ("high_float", "Holgura alta"), ("negative_float", "Holgura negativa"),
        ("high_duration", "Duración alta"), ("invalid_dates", "Fechas inválidas"),
        ("missing_resource", "Sin recursos")], format_func=lambda x: x[1])[0]
    rows = detail[finding]
    if finding == "invalid_dates":
        display = [{**r[0], "issue": r[1]} for r in rows]
    else:
        display = rows
    if display:
        fdf = pd.DataFrame(display)
        preferred = [c for c in ["task_code","task_name","status_code","pred_type","lag_hr_cnt","remain_drtn_hr_cnt","total_float_hr_cnt","early_start_date","early_end_date","issue"] if c in fdf.columns]
        st.dataframe(fdf[preferred] if preferred else fdf, width="stretch", hide_index=True, height=520)
        dataframe_download(fdf, f"{finding}_{project.name}.csv")
    else:
        st.success("No se identificaron registros en esta categoría.")

with tab_resources:
    st.subheader("Recursos, equipos, mano de obra y costos")
    assignments = pd.DataFrame(project.assignments)
    resources = {r.get("rsrc_id"): r for r in project.tables.get("RSRC", [])}
    if assignments.empty:
        st.warning("El XER no contiene asignaciones de recursos.")
    else:
        assignments["Recurso"] = assignments["rsrc_id"].map(lambda x: resources.get(x, {}).get("rsrc_name", "No identificado"))
        assignments["Tipo"] = assignments["rsrc_type"].replace({"RT_Labor":"Mano de obra","RT_Equip":"Equipo","RT_Mat":"Material"})
        for col in ["target_qty","remain_qty","target_cost","remain_cost","act_reg_cost"]:
            assignments[col] = pd.to_numeric(assignments.get(col), errors="coerce").fillna(0)
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Recursos maestros",len(resources)); c2.metric("Actividades asignadas",assignments.task_id.nunique())
        c3.metric("Costo objetivo",f"{assignments.target_cost.sum():,.2f}"); c4.metric("Costo restante",f"{assignments.remain_cost.sum():,.2f}")
        summary=assignments.groupby(["Recurso","Tipo"],dropna=False).agg(Asignaciones=("task_id","count"),Cantidad_objetivo=("target_qty","sum"),Cantidad_restante=("remain_qty","sum"),Costo_objetivo=("target_cost","sum"),Costo_restante=("remain_cost","sum")).reset_index()
        st.dataframe(summary,width="stretch",hide_index=True)
        if summary.Recurso.str.contains("dummy",case=False,na=False).any():
            st.warning("La carga está concentrada en Dummy. Cumple la presencia formal de recursos, pero no demuestra capacidad real.")
        st.info("Próxima capa: histograma time-phased por cuadrilla/equipo y comparación Demanda vs. Capacidad. Requiere calendarios y recursos reales.")

with tab_esm:
    st.subheader("Earned Schedule Management")
    st.write("EVM conserva la lectura monetaria; Earned Schedule devuelve el desempeño del plazo a unidades de tiempo mediante ES, SV(t) y SPI(t).")
    tpl = template()
    st.download_button("Descargar plantilla PV–EV–AC", tpl.to_csv(index=False).encode("utf-8-sig"), "plantilla_earned_schedule.csv", "text/csv")
    esm_file = st.file_uploader("Cargar serie acumulada PV, EV y AC", type=["csv","xlsx"], key="esm")
    if esm_file:
        raw = pd.read_csv(esm_file) if esm_file.name.lower().endswith(".csv") else pd.read_excel(esm_file)
        try:
            esm = calculate_esm(raw)
            last = esm.iloc[-1]
            c1,c2,c3,c4=st.columns(4)
            c1.metric("SPI",f"{last['SPI']:.3f}"); c2.metric("CPI",f"{last['CPI']:.3f}"); c3.metric("SPI(t)",f"{last['SPI(t)']:.3f}"); c4.metric("SV(t)",f"{last['SV(t)']:.2f} períodos")
            long=esm.melt(id_vars="Period",value_vars=["PV","EV","AC"],var_name="Serie",value_name="Valor")
            st.plotly_chart(px.line(long,x="Period",y="Valor",color="Serie",markers=True,title="Curvas acumuladas"),width="stretch")
            st.plotly_chart(px.line(esm,x="Period",y=["SPI","CPI","SPI(t)"],markers=True,title="Índices de desempeño"),width="stretch")
            st.dataframe(esm,width="stretch",hide_index=True)
        except ValueError as exc:
            st.error(str(exc))
    else:
        st.caption("El XER aislado no siempre contiene series time-phased confiables. Por eso esta versión solicita la curva acumulada y evita fabricar Earned Schedule desde totales estáticos.")

with tab_xer:
    st.subheader("Inventario de tablas XER")
    inv=pd.DataFrame([{"Tabla":k,"Registros":len(v)} for k,v in sorted(project.tables.items())])
    st.dataframe(inv,width="stretch",hide_index=True)
    table_name=st.selectbox("Inspeccionar tabla",sorted(project.tables))
    st.dataframe(pd.DataFrame(project.tables[table_name]),width="stretch",hide_index=True,height=500)

with tab_protocol:
    st.subheader("Flujo de control")
    st.markdown("""
    1. Conservar el XER original y registrar proyecto, revisión, Data Date y responsable.
    2. Cargar actualización y baseline contractual.
    3. Ejecutar las 14 pruebas y resolver los estados no evaluables.
    4. Validar lógica, interfaces y secuencia con el equipo de obra.
    5. Incorporar recursos reales, costos y capacidad.
    6. Calcular Earned Schedule con series acumuladas aprobadas.
    7. Corregir en una copia de P6, recalcular y someter a revisión.
    8. Publicar únicamente la versión aprobada en OPC.
    """)
    st.warning("La aplicación analiza y documenta. No modifica automáticamente los cronogramas ni reemplaza el F9 de Primavera P6.")
