from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from .location_model import activity_code_map
from .xer import as_date


TOWER_REPETITIVE_LEVELS = tuple(range(1, 15))


@dataclass(frozen=True)
class TowerLocation:
    raw: str
    label: str
    order: int
    repetitive: bool


def tower_location(value: str | None) -> TowerLocation | None:
    """Translate Constructora Bolivar's current P6 floor coding to the spatial model.

    Current XER convention observed in v0.3.6 demo schedules:
      Piso -2 -> foundation / enabling works
      Piso 1  -> S2
      Piso 2  -> S1
      Piso 3  -> P01 (Hall)
      ...
      Piso 16 -> P14

    Canonical future codes (S2, S1, P01..P14) are also accepted directly.
    """
    if not value:
        return None
    text = str(value).strip()
    compact = re.sub(r"\s+", "", text).upper()

    if compact in {"S1", "S2"}:
        order = -1 if compact == "S1" else -2
        return TowerLocation(text, compact, order, False)

    canonical = re.fullmatch(r"P(\d{1,2})", compact)
    if canonical:
        n = int(canonical.group(1))
        if 1 <= n <= 14:
            return TowerLocation(text, f"P{n:02d}", n, True)

    match = re.search(r"-?\d+", text)
    if not match:
        return None
    n = int(match.group())

    if "PISO" in text.upper():
        if n == -2:
            return TowerLocation(text, "CIM", -3, False)
        if n == 1:
            return TowerLocation(text, "S2", -2, False)
        if n == 2:
            return TowerLocation(text, "S1", -1, False)
        if 3 <= n <= 16:
            level = n - 2
            return TowerLocation(text, f"P{level:02d}", level, True)

    return None


def _date(task: dict, *fields: str) -> datetime | None:
    for field in fields:
        value = as_date(task.get(field))
        if value is not None:
            return value
    return None


def _current_start(task: dict) -> datetime | None:
    return _date(task, "act_start_date", "restart_date", "early_start_date", "target_start_date")


def _current_finish(task: dict) -> datetime | None:
    return _date(task, "act_end_date", "reend_date", "early_end_date", "target_end_date")


def _planned_start(task: dict) -> datetime | None:
    return _date(task, "target_start_date", "early_start_date")


def _planned_finish(task: dict) -> datetime | None:
    return _date(task, "target_end_date", "early_end_date")


def _aggregate_records(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=[
            "Process", "Location", "LocationOrder", "RawLocation", "Repetitive",
            "Activities", "Progress", "Complete", "Active", "NotStarted",
            "PlannedStart", "PlannedFinish", "CurrentStart", "CurrentFinish",
        ])

    frame = pd.DataFrame(records)
    grouped = (
        frame.groupby(["Process", "Location", "LocationOrder", "RawLocation", "Repetitive"], as_index=False)
        .agg(
            Activities=("task_id", "count"),
            Progress=("Progress", "mean"),
            Complete=("Complete", "sum"),
            Active=("Active", "sum"),
            NotStarted=("NotStarted", "sum"),
            PlannedStart=("PlannedStart", "min"),
            PlannedFinish=("PlannedFinish", "max"),
            CurrentStart=("CurrentStart", "min"),
            CurrentFinish=("CurrentFinish", "max"),
        )
        .sort_values(["Process", "LocationOrder"])
    )
    return grouped


def tower_lob(project) -> pd.DataFrame:
    """Build process/location time bands for a tower XER."""
    if project is None:
        return _aggregate_records([])

    codes = activity_code_map(project)
    records: list[dict] = []
    for task in project.tasks:
        task_codes = codes.get(task.get("task_id"), {})
        loc = tower_location(task_codes.get("CBB_Piso"))
        process = (task_codes.get("CBB_Procesos") or "Sin proceso").strip()
        if loc is None or not process:
            continue
        status = task.get("status_code") or ""
        try:
            pct = max(0.0, min(100.0, float(task.get("phys_complete_pct") or 0.0)))
        except (TypeError, ValueError):
            pct = 0.0
        records.append({
            "task_id": task.get("task_id"),
            "Process": process,
            "Location": loc.label,
            "LocationOrder": loc.order,
            "RawLocation": loc.raw,
            "Repetitive": loc.repetitive,
            "Progress": pct,
            "Complete": int(status == "TK_Complete"),
            "Active": int(status == "TK_Active"),
            "NotStarted": int(status == "TK_NotStart"),
            "PlannedStart": _planned_start(task),
            "PlannedFinish": _planned_finish(task),
            "CurrentStart": _current_start(task),
            "CurrentFinish": _current_finish(task),
        })
    return _aggregate_records(records)


def _natural_order(value: str) -> tuple:
    chunks = re.split(r"(\d+)", str(value).casefold())
    return tuple(int(c) if c.isdigit() else c for c in chunks)


def _platform_location(task: dict, task_codes: dict[str, str]) -> str | None:
    preferred = ("CBB_Sector", "CBB_Tramo", "CBB_Zona", "Sector", "Tramo", "Zona", "Frente")
    by_fold = {str(k).casefold(): v for k, v in task_codes.items()}
    for key in preferred:
        value = by_fold.get(key.casefold())
        if value:
            return str(value).strip()

    for key, value in task_codes.items():
        key_fold = str(key).casefold()
        if any(token in key_fold for token in ("sector", "tramo", "frente", "zona")) and value:
            return str(value).strip()

    text = f"{task.get('task_name','')} {task.get('task_code','')}"
    match = re.search(r"\b(tramo|sector|frente|zona)\s*[-_#:]*\s*([a-z0-9]+)", text, flags=re.I)
    if match:
        return f"{match.group(1).title()} {match.group(2).upper()}"
    return None


def platform_lob(project) -> pd.DataFrame:
    """Build LOB records for Plataforma/Urbanismo using explicit sector/tramo codes when available."""
    if project is None:
        return _aggregate_records([])

    code_map = activity_code_map(project)
    raw_rows = []
    locations = set()
    for task in project.tasks:
        task_codes = code_map.get(task.get("task_id"), {})
        location = _platform_location(task, task_codes)
        if not location:
            continue
        locations.add(location)
        raw_rows.append((task, task_codes, location))

    ordered_locations = sorted(locations, key=_natural_order)
    order_map = {name: i + 1 for i, name in enumerate(ordered_locations)}

    records: list[dict] = []
    for task, task_codes, location in raw_rows:
        process = (task_codes.get("CBB_Procesos") or "Sin proceso").strip()
        status = task.get("status_code") or ""
        try:
            pct = max(0.0, min(100.0, float(task.get("phys_complete_pct") or 0.0)))
        except (TypeError, ValueError):
            pct = 0.0
        records.append({
            "task_id": task.get("task_id"),
            "Process": process,
            "Location": location,
            "LocationOrder": order_map[location],
            "RawLocation": location,
            "Repetitive": True,
            "Progress": pct,
            "Complete": int(status == "TK_Complete"),
            "Active": int(status == "TK_Active"),
            "NotStarted": int(status == "TK_NotStart"),
            "PlannedStart": _planned_start(task),
            "PlannedFinish": _planned_finish(task),
            "CurrentStart": _current_start(task),
            "CurrentFinish": _current_finish(task),
        })
    return _aggregate_records(records)


def process_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    """Estimate cycle time and production rate from the current start line."""
    if frame.empty:
        return pd.DataFrame(columns=["Process", "Locations", "CycleDays", "RatePerDay", "SpanDays"])

    rows = []
    for process, group in frame.groupby("Process"):
        g = group.dropna(subset=["CurrentStart"]).sort_values("LocationOrder")
        if len(g) < 2:
            cycle = None
            rate = None
            span = None
        else:
            first = g.iloc[0]
            last = g.iloc[-1]
            delta_l = float(last["LocationOrder"] - first["LocationOrder"])
            span = (last["CurrentStart"] - first["CurrentStart"]).total_seconds() / 86400.0
            cycle = span / delta_l if delta_l > 0 and span >= 0 else None
            rate = (1.0 / cycle) if cycle and cycle > 0 else None
        rows.append({
            "Process": process,
            "Locations": int(g["Location"].nunique()),
            "CycleDays": cycle,
            "RatePerDay": rate,
            "SpanDays": span,
        })
    return pd.DataFrame(rows).sort_values(["Locations", "Process"], ascending=[False, True])


def overlap_register(frame: pd.DataFrame) -> pd.DataFrame:
    """Flag same-location temporal overlaps between consecutively sequenced processes.

    This is an interference screening signal, not an automatic defect: some trades are
    intentionally concurrent and must be validated constructively.
    """
    if frame.empty:
        return pd.DataFrame(columns=["Location", "PredecessorProcess", "SuccessorProcess", "OverlapDays"])

    process_order = (
        frame.groupby("Process")["CurrentStart"].min().dropna().sort_values().index.tolist()
    )
    rank = {p: i for i, p in enumerate(process_order)}
    rows = []
    for location, group in frame.groupby("Location"):
        g = group.dropna(subset=["CurrentStart", "CurrentFinish"]).copy()
        g["_rank"] = g["Process"].map(rank)
        g = g.dropna(subset=["_rank"]).sort_values("_rank")
        for i in range(len(g) - 1):
            a = g.iloc[i]
            b = g.iloc[i + 1]
            overlap = (a["CurrentFinish"] - b["CurrentStart"]).total_seconds() / 86400.0
            if overlap > 0:
                rows.append({
                    "Location": location,
                    "PredecessorProcess": a["Process"],
                    "SuccessorProcess": b["Process"],
                    "OverlapDays": overlap,
                })
    return pd.DataFrame(rows)
