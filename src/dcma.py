from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any

from .xer import XERProject, as_date, as_float


PASS = "Cumple"
FAIL = "No cumple"
REVIEW = "Revisar"
NA = "No evaluable"


@dataclass
class Metric:
    number: int
    name: str
    result: str
    value: str
    target: str
    numerator: int | None
    denominator: int | None
    note: str

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _pct(num: int, den: int) -> float:
    return 100.0 * num / den if den else 0.0


def _fmt(num: int, den: int) -> str:
    return f"{num:,} / {den:,} ({_pct(num, den):.2f}%)".replace(",", ".")


def assess(project: XERProject, baseline: XERProject | None = None) -> tuple[list[Metric], dict[str, Any]]:
    tasks = project.tasks
    rels = project.relationships
    ids = {t.get("task_id", "") for t in tasks}
    incoming, outgoing = set(), set()
    for rel in rels:
        if rel.get("task_id") in ids:
            incoming.add(rel["task_id"])
        if rel.get("pred_task_id") in ids:
            outgoing.add(rel["pred_task_id"])

    # DCMA denominators exclude completed activities for most forward-looking tests.
    incomplete = [t for t in tasks if t.get("status_code") != "TK_Complete"]
    non_milestone = [t for t in incomplete if t.get("task_type") not in {"TT_Mile", "TT_FinMile"}]
    missing = [t for t in non_milestone if t.get("task_id") not in incoming or t.get("task_id") not in outgoing]
    leads = [r for r in rels if (as_float(r.get("lag_hr_cnt")) or 0) < 0]
    lags = [r for r in rels if (as_float(r.get("lag_hr_cnt")) or 0) > 0]
    non_fs = [r for r in rels if r.get("pred_type") != "PR_FS"]
    hard_types = {"CS_MANDSTART", "CS_MANDFIN", "CS_MSO", "CS_MEO"}
    hard = [t for t in incomplete if t.get("cstr_type") in hard_types or t.get("cstr_type2") in hard_types]
    high_float = [t for t in incomplete if (as_float(t.get("total_float_hr_cnt")) or 0) > 352]
    negative_float = [t for t in incomplete if (as_float(t.get("total_float_hr_cnt")) or 0) < 0]
    high_duration = [t for t in non_milestone if (as_float(t.get("remain_drtn_hr_cnt")) or 0) > 352]

    proj = project.project
    data_date = as_date(proj.get("next_data_date"))
    data_date_authoritative = data_date is not None
    data_date_source = "PROJECT.next_data_date"
    if data_date is None:
        data_date = as_date(proj.get("last_recalc_date"))
        data_date_source = "PROJECT.last_recalc_date (proxy; validar)"

    invalid = []
    if data_date:
        for t in tasks:
            actual_start, actual_finish = as_date(t.get("act_start_date")), as_date(t.get("act_end_date"))
            forecast_start = as_date(t.get("early_start_date") or t.get("restart_date"))
            forecast_finish = as_date(t.get("early_end_date") or t.get("reend_date"))
            if actual_start and actual_start > data_date:
                invalid.append((t, "Actual Start posterior"))
            if actual_finish and actual_finish > data_date:
                invalid.append((t, "Actual Finish posterior"))
            if t.get("status_code") != "TK_Complete" and forecast_finish and forecast_finish < data_date:
                invalid.append((t, "Forecast Finish anterior"))
            if t.get("status_code") == "TK_NotStart" and forecast_start and forecast_start < data_date:
                invalid.append((t, "Forecast Start anterior"))

    assigned_ids = {a.get("task_id") for a in project.assignments}
    missing_resource = [t for t in non_milestone if t.get("task_id") not in assigned_ids]

    metrics = [
        Metric(1, "Lógica faltante", PASS if _pct(len(missing), len(non_milestone)) <= 5 else FAIL,
               _fmt(len(missing), len(non_milestone)), "≤ 5%", len(missing), len(non_milestone), "Actividades incompletas no-hito sin predecesor y/o sucesor."),
        Metric(2, "Leads", PASS if not leads else FAIL, _fmt(len(leads), len(rels)), "0%", len(leads), len(rels), "Relaciones con lag negativo."),
        Metric(3, "Lags", PASS if _pct(len(lags), len(rels)) <= 5 else FAIL, _fmt(len(lags), len(rels)), "≤ 5%", len(lags), len(rels), "Relaciones con lag positivo."),
        Metric(4, "Tipos de relación", PASS if _pct(len(non_fs), len(rels)) <= 10 else FAIL, _fmt(len(non_fs), len(rels)), "≤ 10% no-FS", len(non_fs), len(rels), "Relaciones que no son Finish-to-Start."),
        Metric(5, "Restricciones duras", PASS if _pct(len(hard), len(incomplete)) <= 5 else FAIL, _fmt(len(hard), len(incomplete)), "≤ 5%", len(hard), len(incomplete), "Mandatory Start/Finish o Start/Finish On."),
        Metric(6, "Holgura alta", PASS if _pct(len(high_float), len(incomplete)) <= 5 else FAIL, _fmt(len(high_float), len(incomplete)), "≤ 5%", len(high_float), len(incomplete), "Total Float superior a 44 días de 8 h."),
        Metric(7, "Holgura negativa", PASS if not negative_float else FAIL, _fmt(len(negative_float), len(incomplete)), "0%", len(negative_float), len(incomplete), "Actividades incompletas con Total Float negativo."),
        Metric(8, "Duración alta", PASS if _pct(len(high_duration), len(non_milestone)) <= 5 else FAIL, _fmt(len(high_duration), len(non_milestone)), "≤ 5%", len(high_duration), len(non_milestone), "Remaining Duration superior a 44 días de 8 h."),
        Metric(9, "Fechas inválidas", ((PASS if not invalid else FAIL) if data_date_authoritative else REVIEW) if data_date else NA,
               _fmt(len(invalid), len(tasks)) if data_date else "Data Date no disponible", "0%", len(invalid) if data_date else None, len(tasks) if data_date else None,
               f"Fecha usada: {data_date:%Y-%m-%d} desde {data_date_source}." if data_date else "Se requiere Data Date."),
        Metric(10, "Recursos", PASS if not missing_resource else FAIL, _fmt(len(missing_resource), len(non_milestone)), "0% sin recurso", len(missing_resource), len(non_milestone), "La carga Dummy cuenta formalmente; su calidad se informa aparte."),
    ]

    baseline_tasks = {t.get("task_code"): t for t in baseline.tasks} if baseline else {}
    bei = None
    if baseline and data_date_authoritative:
        comparable = []
        missed = []
        planned_complete = []
        completed_on_time = []
        current_by_code = {t.get("task_code"): t for t in tasks}
        for code, b in baseline_tasks.items():
            bf = as_date(b.get("target_end_date") or b.get("early_end_date"))
            c = current_by_code.get(code)
            if not bf or not c:
                continue
            comparable.append(c)
            cf = as_date(c.get("act_end_date") or c.get("early_end_date") or c.get("reend_date"))
            if cf and cf > bf:
                missed.append(c)
            if bf <= data_date:
                planned_complete.append(c)
                af = as_date(c.get("act_end_date"))
                if c.get("status_code") == "TK_Complete" and af and af <= data_date:
                    completed_on_time.append(c)
        metrics.append(Metric(11, "Actividades incumplidas", PASS if _pct(len(missed), len(comparable)) <= 5 else FAIL,
                              _fmt(len(missed), len(comparable)), "≤ 5%", len(missed), len(comparable), "Actual/Forecast Finish posterior al Baseline Finish."))
        bei = (len(completed_on_time), len(planned_complete))
    else:
        metrics.append(Metric(11, "Actividades incumplidas", NA, "Cargar baseline XER", "≤ 5%", None, None, "Requiere línea base contractual emparejada."))

    metrics.extend([
        Metric(12, "Prueba del camino crítico", NA, "Ejecutar prueba controlada en P6", "Desplazamiento equivalente", None, None, "Debe añadir 600 días a una actividad crítica, recalcular y comparar la terminación."),
        Metric(13, "CPLI", NA, "Requiere hito objetivo validado", "≥ 0,95", None, None, "CPLI=(Critical Path Length+Total Float)/Critical Path Length."),
        Metric(14, "BEI", (PASS if bei and bei[1] and bei[0] / bei[1] >= .95 else FAIL) if bei and bei[1] else NA,
               f"{bei[0] / bei[1]:.3f} ({bei[0]}/{bei[1]})" if bei and bei[1] else "Requiere baseline y Data Date validada",
               "≥ 0,95", bei[0] if bei else None, bei[1] if bei else None, "BEI=actividades realmente completadas / actividades previstas para completar."),
    ])

    detail = {
        "missing_logic": missing, "leads": leads, "lags": lags, "non_fs": non_fs, "hard_constraints": hard,
        "high_float": high_float, "negative_float": negative_float, "high_duration": high_duration,
        "invalid_dates": invalid, "missing_resource": missing_resource, "data_date": data_date,
    }
    return metrics, detail
