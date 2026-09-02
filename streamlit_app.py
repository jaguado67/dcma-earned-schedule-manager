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
from src.earned_schedule import calculate_esm, template
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
    st.caption("DCMA + ESM Manager · v0.3.2")
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

tabs = st.tabs(["Resumen", "DCMA 14-Point", "Hallazgos", "Recursos y costos", "Earned Schedule", "Datos XER", "Protocolo"])

with tabs[0]:
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

with tabs[1]:
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

with tabs[2]:
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

with tabs[3]:
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

with tabs[4]:
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

with tabs[5]:
    st.subheader("Inventario de tablas XER")
    inv=pd.DataFrame([{"Tabla":k,"Registros":len(v)} for k,v in sorted(project.tables.items())])
    st.dataframe(inv,width="stretch",hide_index=True)
    table_name=st.selectbox("Inspeccionar tabla",sorted(project.tables))
    st.dataframe(pd.DataFrame(project.tables[table_name]),width="stretch",hide_index=True,height=500)

with tabs[6]:
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
