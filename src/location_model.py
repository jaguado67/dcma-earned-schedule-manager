from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd


# ============================================================
# PROJECT SPATIAL DEFINITION
# ============================================================
# S2 / S1 below grade
# P01 = Hall / first above-grade floor
# P02 ... P14 = residential
# 4 apartments per residential floor
#
# Per tower: 13 x 4 = 52 apartments
# Project: 52 + 52 = 104 apartments
# ============================================================

BASEMENTS = ("S2", "S1")
ABOVE_GRADE_FLOORS = 14
HALL_FLOOR = 1
RESIDENTIAL_FLOORS = tuple(range(2, 15))
APARTMENTS_PER_FLOOR = 4
RESIDENTIAL_UNITS_PER_TOWER = len(RESIDENTIAL_FLOORS) * APARTMENTS_PER_FLOOR

FINISH_KEYWORDS = (
    "piso", "cielo", "carpinter", "meson", "gasodom", "estuco",
    "enchape", "pintura", "acabado", "entrega calidad", "aparato",
    "grifer", "mueble", "ilumin", "marmol", "mármol", "piedra",
    "closet", "puerta", "porcelanato", "granito", "vidrio", "espejo",
)


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def activity_code_map(project) -> dict[str, dict[str, str]]:
    """Return {task_id: {activity_code_type: activity_code_name}}."""
    types = {
        row.get("actv_code_type_id"): row.get("actv_code_type", "")
        for row in project.tables.get("ACTVTYPE", [])
    }
    codes = {
        row.get("actv_code_id"): row
        for row in project.tables.get("ACTVCODE", [])
    }

    result: dict[str, dict[str, str]] = defaultdict(dict)
    for row in project.tables.get("TASKACTV", []):
        task_id = row.get("task_id")
        type_name = types.get(row.get("actv_code_type_id"), "")
        code = codes.get(row.get("actv_code_id"), {})
        code_name = code.get("actv_code_name") or code.get("short_name") or ""

        if task_id and type_name and code_name:
            result[task_id][type_name] = code_name

    return dict(result)


def _floor_number(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"-?\d+", str(value))
    if not match:
        return None
    try:
        return int(match.group())
    except ValueError:
        return None


def p6_floor_to_model_floor(value: str | None) -> int | None:
    """Normalize current P6 floor codes to the architectural model.

    Current schedule convention: Piso 1=S2, Piso 2=S1, Piso 3=P01 ... Piso 16=P14.
    Canonical future codes S2, S1 and P01..P14 are also accepted directly.
    Foundation code Piso -2 is intentionally excluded from facade floor progress.
    """
    if not value:
        return None
    text = str(value).strip()
    compact = re.sub(r"\s+", "", text).upper()
    if compact == "S2":
        return -2
    if compact == "S1":
        return -1
    canonical = re.fullmatch(r"P(\d{1,2})", compact)
    if canonical:
        floor = int(canonical.group(1))
        return floor if 1 <= floor <= ABOVE_GRADE_FLOORS else None

    n = _floor_number(text)
    if n is None:
        return None
    if "PISO" in text.upper():
        if n == 1:
            return -2
        if n == 2:
            return -1
        if 3 <= n <= 16:
            return n - 2
    return None


def _apartment_number(value: str | None) -> int | None:
    """Parse APT01, APTO 1, Apartment 01, 01, etc. into 1..4."""
    if not value:
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    try:
        number = int(match.group())
    except ValueError:
        return None
    return number if 1 <= number <= APARTMENTS_PER_FLOOR else None


def _is_finish(process_name: str | None) -> bool:
    text = (process_name or "").casefold()
    return any(key in text for key in FINISH_KEYWORDS)


def project_has_code(project, code_type_name: str) -> bool:
    return any(
        row.get("actv_code_type") == code_type_name
        for row in project.tables.get("ACTVTYPE", [])
    )


def activity_progress(project, finishes_only: bool = False) -> pd.DataFrame:
    """Task progress enriched with location Activity Codes.

    This function intentionally does not invent apartment granularity. If
    CBB_Apartamento is absent, Apartment remains None and the visualization
    may explicitly use a floor proxy.
    """
    code_map = activity_code_map(project)
    rows = []

    for task in project.tasks:
        task_id = task.get("task_id")
        codes = code_map.get(task_id, {})

        floor = p6_floor_to_model_floor(codes.get("CBB_Piso"))
        apartment = _apartment_number(codes.get("CBB_Apartamento"))
        process = codes.get("CBB_Procesos", "")
        zone = codes.get("CBB_Zona", "")

        if floor is None:
            continue
        is_finish = _is_finish(process)
        if finishes_only and not is_finish:
            continue

        pct = max(0.0, min(100.0, _as_float(task.get("phys_complete_pct"), 0.0)))
        status = task.get("status_code") or ""

        rows.append({
            "Floor": floor,
            "Apartment": apartment,
            "task_id": task_id,
            "task_code": task.get("task_code", ""),
            "task_name": task.get("task_name", ""),
            "Process": process,
            "Zone": zone,
            "IsFinish": is_finish,
            "Status": status,
            "PhysicalPct": pct,
        })

    return pd.DataFrame(rows)


def _aggregate(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=group_cols + [
                "Activities", "Complete", "Active", "NotStarted", "Progress"
            ]
        )

    return (
        frame.groupby(group_cols, dropna=False, as_index=False)
        .agg(
            Activities=("task_id", "count"),
            Complete=("Status", lambda s: int((s == "TK_Complete").sum())),
            Active=("Status", lambda s: int((s == "TK_Active").sum())),
            NotStarted=("Status", lambda s: int((s == "TK_NotStart").sum())),
            Progress=("PhysicalPct", "mean"),
        )
        .sort_values(group_cols)
    )


def floor_progress(project, finishes_only: bool = False) -> pd.DataFrame:
    return _aggregate(
        activity_progress(project, finishes_only=finishes_only),
        ["Floor"],
    )


def apartment_progress(project, finishes_only: bool = False) -> pd.DataFrame:
    frame = activity_progress(project, finishes_only=finishes_only)
    if frame.empty or frame["Apartment"].notna().sum() == 0:
        return pd.DataFrame(
            columns=[
                "Floor", "Apartment", "Activities",
                "Complete", "Active", "NotStarted", "Progress"
            ]
        )

    frame = frame[frame["Apartment"].notna()].copy()
    frame["Apartment"] = frame["Apartment"].astype(int)
    return _aggregate(frame, ["Floor", "Apartment"])


def level_progress(project, floor: int, finishes_only: bool = False) -> dict:
    """Return one P6 level summary (P01=1, S1=-1, S2=-2)."""
    summary = floor_progress(project, finishes_only=finishes_only)
    if summary.empty:
        return {"Mapped": False, "Progress": 0.0, "Activities": 0}

    row = summary[summary["Floor"] == floor]
    if row.empty:
        return {"Mapped": False, "Progress": 0.0, "Activities": 0}

    r = row.iloc[0]
    return {
        "Mapped": True,
        "Progress": float(r["Progress"]),
        "Activities": int(r["Activities"]),
    }


def hall_progress(project, finishes_only: bool = False) -> dict:
    """P01 is Hall, not a residential floor."""
    return level_progress(project, HALL_FLOOR, finishes_only=finishes_only)


def basement_progress(project, basement: str, finishes_only: bool = False) -> dict:
    floor = {"S1": -1, "S2": -2}.get(str(basement).upper())
    if floor is None:
        raise ValueError("basement must be S1 or S2")
    return level_progress(project, floor, finishes_only=finishes_only)


def tower_grid(
    project=None,
    residential_floors: tuple[int, ...] = RESIDENTIAL_FLOORS,
    apartments: int = APARTMENTS_PER_FLOOR,
    finishes_only: bool = False,
) -> pd.DataFrame:
    """P02..P14 x 4 apartment/window cells.

    If CBB_Apartamento is present, each window is mapped independently.
    Otherwise CBB_Piso is transparently projected to the four apartment
    windows of that floor. MappingLevel records this distinction.
    """
    if project is None:
        floor_summary = pd.DataFrame()
        apartment_summary = pd.DataFrame()
        apartment_level = False
    else:
        floor_summary = floor_progress(project, finishes_only=finishes_only)
        apartment_summary = apartment_progress(project, finishes_only=finishes_only)
        apartment_level = not apartment_summary.empty

    by_floor = (
        floor_summary.set_index("Floor").to_dict("index")
        if not floor_summary.empty else {}
    )
    by_apartment = (
        apartment_summary.set_index(["Floor", "Apartment"]).to_dict("index")
        if apartment_level else {}
    )

    rows = []
    for floor in residential_floors:
        for apartment in range(1, apartments + 1):
            if apartment_level:
                info = by_apartment.get((floor, apartment), {})
                mapped = (floor, apartment) in by_apartment
                mapping_level = "APARTMENT" if mapped else "UNMAPPED"
            else:
                info = by_floor.get(floor, {})
                mapped = floor in by_floor
                mapping_level = "FLOOR_PROXY" if mapped else "UNMAPPED"

            rows.append({
                "Floor": floor,
                "Apartment": apartment,
                "FloorCode": f"P{floor:02d}",
                "ApartmentCode": f"APT{apartment:02d}",
                "Location": f"P{floor:02d}-APT{apartment:02d}",
                "Activities": int(info.get("Activities", 0)),
                "Complete": int(info.get("Complete", 0)),
                "Active": int(info.get("Active", 0)),
                "NotStarted": int(info.get("NotStarted", 0)),
                "Progress": float(info.get("Progress", 0.0)),
                "Mapped": bool(mapped),
                "MappingLevel": mapping_level,
            })

    return pd.DataFrame(rows)


def core_grid(project=None, finishes_only: bool = False) -> pd.DataFrame:
    """Return P02..P14 common-area/CORE progress.

    CORE is only inferred when CBB_Apartamento exists. In that case, floor
    activities with no apartment assignment are treated as common-area/CORE
    work. When CBB_Apartamento does not exist, CORE remains explicitly
    unmapped rather than stealing floor progress from the apartments.
    """
    rows = []
    has_apartment_code = bool(project is not None and project_has_code(project, "CBB_Apartamento"))

    if has_apartment_code:
        frame = activity_progress(project, finishes_only=finishes_only)
        if not frame.empty:
            frame = frame[
                frame["Floor"].isin(RESIDENTIAL_FLOORS)
                & frame["Apartment"].isna()
            ]
            summary = _aggregate(frame, ["Floor"])
            by_floor = summary.set_index("Floor").to_dict("index") if not summary.empty else {}
        else:
            by_floor = {}
    else:
        by_floor = {}

    for floor in RESIDENTIAL_FLOORS:
        info = by_floor.get(floor, {})
        mapped = floor in by_floor
        rows.append({
            "Floor": floor,
            "FloorCode": f"P{floor:02d}",
            "Location": f"P{floor:02d}-CORE",
            "Activities": int(info.get("Activities", 0)),
            "Complete": int(info.get("Complete", 0)),
            "Active": int(info.get("Active", 0)),
            "NotStarted": int(info.get("NotStarted", 0)),
            "Progress": float(info.get("Progress", 0.0)),
            "Mapped": bool(mapped),
            "MappingLevel": "CORE_COMMON" if mapped else "UNMAPPED",
        })

    return pd.DataFrame(rows)


def luxury_core_grid(
    project,
    general_weight: float = 0.35,
    finish_weight: float = 0.65,
) -> pd.DataFrame:
    """Luxury blend for CORE/common-area locations with missing-data protection."""
    total = general_weight + finish_weight
    if total <= 0:
        raise ValueError("general_weight + finish_weight must be > 0")
    general_weight /= total
    finish_weight /= total

    general = core_grid(project, finishes_only=False).rename(columns={
        "Progress": "GeneralProgress",
        "Mapped": "GeneralMapped",
        "MappingLevel": "GeneralMappingLevel",
    })
    finishes = core_grid(project, finishes_only=True)[
        ["Floor", "Progress", "Mapped", "MappingLevel"]
    ].rename(columns={
        "Progress": "FinishProgress",
        "Mapped": "FinishMapped",
        "MappingLevel": "FinishMappingLevel",
    })

    result = general.merge(finishes, on="Floor", how="left")
    result["FinishProgress"] = result["FinishProgress"].fillna(0.0)
    result["FinishMapped"] = result["FinishMapped"].fillna(False).astype(bool)
    result["GeneralMapped"] = result["GeneralMapped"].fillna(False).astype(bool)

    both = result["GeneralMapped"] & result["FinishMapped"]
    general_only = result["GeneralMapped"] & ~result["FinishMapped"]
    finish_only = ~result["GeneralMapped"] & result["FinishMapped"]

    result["Progress"] = 0.0
    result.loc[both, "Progress"] = (
        general_weight * result.loc[both, "GeneralProgress"]
        + finish_weight * result.loc[both, "FinishProgress"]
    )
    result.loc[general_only, "Progress"] = result.loc[general_only, "GeneralProgress"]
    result.loc[finish_only, "Progress"] = result.loc[finish_only, "FinishProgress"]
    result["Mapped"] = result["GeneralMapped"] | result["FinishMapped"]
    result["MappingLevel"] = result["GeneralMappingLevel"]
    result["MetricQuality"] = "UNMAPPED"
    result.loc[both, "MetricQuality"] = "FULL_LUXURY_INDEX"
    result.loc[general_only, "MetricQuality"] = "GENERAL_ONLY"
    result.loc[finish_only, "MetricQuality"] = "FINISH_ONLY"
    return result


def floor_rollup(grid: pd.DataFrame) -> pd.DataFrame:
    """Derive floor status from apartment windows, never the other way around.

    Progress is the mean of mapped apartments. Coverage reports how much of
    the 4-apartment floor is independently/explicitly represented.
    """
    rows = []
    for floor, group in grid.groupby("Floor", sort=True):
        mapped = group[group["Mapped"]]
        rows.append({
            "Floor": int(floor),
            "Progress": float(mapped["Progress"].mean()) if not mapped.empty else 0.0,
            "Mapped": not mapped.empty,
            "Coverage": float(group["Mapped"].mean() * 100.0),
            "MappedApartments": int(group["Mapped"].sum()),
            "TotalApartments": int(len(group)),
        })
    return pd.DataFrame(rows)


def luxury_index_grid(
    project,
    residential_floors: tuple[int, ...] = RESIDENTIAL_FLOORS,
    apartments: int = APARTMENTS_PER_FLOOR,
    general_weight: float = 0.35,
    finish_weight: float = 0.65,
) -> pd.DataFrame:
    """Blend general and luxury-finish progress without converting missing data to zero.

    When both general and finish information exist:
        Luxury Index = general_weight*General + finish_weight*Finishes

    When finish data is missing, the location falls back to GeneralProgress
    and MetricQuality='GENERAL_ONLY'. This prevents the dashboard from
    falsely treating missing finish mapping as 0% finish progress.
    """
    total = general_weight + finish_weight
    if total <= 0:
        raise ValueError("general_weight + finish_weight must be > 0")
    general_weight = general_weight / total
    finish_weight = finish_weight / total

    general = tower_grid(
        project,
        residential_floors=residential_floors,
        apartments=apartments,
        finishes_only=False,
    ).copy()

    finishes = tower_grid(
        project,
        residential_floors=residential_floors,
        apartments=apartments,
        finishes_only=True,
    ).copy()

    general = general.rename(columns={
        "Progress": "GeneralProgress",
        "Mapped": "GeneralMapped",
        "MappingLevel": "GeneralMappingLevel",
    })

    finishes = finishes[
        ["Floor", "Apartment", "Progress", "Mapped", "MappingLevel"]
    ].rename(columns={
        "Progress": "FinishProgress",
        "Mapped": "FinishMapped",
        "MappingLevel": "FinishMappingLevel",
    })

    result = general.merge(finishes, on=["Floor", "Apartment"], how="left")
    result["FinishProgress"] = result["FinishProgress"].fillna(0.0)
    result["FinishMapped"] = result["FinishMapped"].fillna(False).astype(bool)
    result["GeneralMapped"] = result["GeneralMapped"].fillna(False).astype(bool)

    both = result["GeneralMapped"] & result["FinishMapped"]
    general_only = result["GeneralMapped"] & ~result["FinishMapped"]
    finish_only = ~result["GeneralMapped"] & result["FinishMapped"]

    result["Progress"] = 0.0
    result.loc[both, "Progress"] = (
        general_weight * result.loc[both, "GeneralProgress"]
        + finish_weight * result.loc[both, "FinishProgress"]
    )
    result.loc[general_only, "Progress"] = result.loc[general_only, "GeneralProgress"]
    result.loc[finish_only, "Progress"] = result.loc[finish_only, "FinishProgress"]

    result["Mapped"] = result["GeneralMapped"] | result["FinishMapped"]
    result["MetricQuality"] = "UNMAPPED"
    result.loc[both, "MetricQuality"] = "FULL_LUXURY_INDEX"
    result.loc[general_only, "MetricQuality"] = "GENERAL_ONLY"
    result.loc[finish_only, "MetricQuality"] = "FINISH_ONLY"
    result["FinishWeight"] = finish_weight
    result["GeneralWeight"] = general_weight

    result["MappingLevel"] = result["GeneralMappingLevel"]
    apartment_mask = (
        result["GeneralMappingLevel"].eq("APARTMENT")
        | result["FinishMappingLevel"].eq("APARTMENT")
    )
    result.loc[apartment_mask, "MappingLevel"] = "APARTMENT"

    return result


def mapping_quality(project) -> dict:
    """Compact readiness indicators for the Location Intelligence layer."""
    grid = tower_grid(project)
    return {
        "HasFloor": project_has_code(project, "CBB_Piso"),
        "HasApartment": project_has_code(project, "CBB_Apartamento"),
        "HasProcess": project_has_code(project, "CBB_Procesos"),
        "HasZone": project_has_code(project, "CBB_Zona"),
        "MappedWindows": int(grid["Mapped"].sum()),
        "TotalWindows": int(len(grid)),
        "MappedFloors": int(grid.loc[grid["Mapped"], "Floor"].nunique()),
        "TotalFloors": len(RESIDENTIAL_FLOORS),
    }


def progress_by_location(
    project,
    tower_code: str,
    view: str = "general",
    finish_weight: float = 0.65,
) -> dict[str, float | None]:
    """Return renderer-ready progress keyed by unique spatial LocationID."""
    tower_code = tower_code.upper()
    if view == "luxury":
        grid = luxury_index_grid(
            project,
            general_weight=1.0 - finish_weight,
            finish_weight=finish_weight,
        )
    else:
        grid = tower_grid(project)

    result: dict[str, float | None] = {}
    for row in grid.itertuples():
        result[f"{tower_code}-{row.Location}"] = float(row.Progress) if row.Mapped else None

    hall = hall_progress(project)
    result[f"{tower_code}-P01-HALL"] = float(hall["Progress"]) if hall["Mapped"] else None

    cores = core_grid(project)
    for row in cores.itertuples():
        result[f"{tower_code}-{row.Location}"] = float(row.Progress) if row.Mapped else None

    for basement in BASEMENTS:
        info = basement_progress(project, basement)
        result[f"{tower_code}-{basement}"] = float(info["Progress"]) if info["Mapped"] else None

    return result


def model_master() -> pd.DataFrame:
    """Spatial master independent from P6 activities."""
    rows = []

    tower_defs = (
        (1, "MAR", "Torre Mar"),
        (2, "SIE", "Torre Sierra"),
    )

    for layer_number, tower_code, tower_name in tower_defs:
        rows.extend([
            {
                "Layer": tower_name, "LayerNumber": layer_number,
                "TowerCode": tower_code, "Level": "S2",
                "LocationType": "BASEMENT", "LocationID": f"{tower_code}-S2",
                "CBB_Edificio": tower_code, "CBB_Piso": "S2",
                "CBB_Apartamento": "", "CBB_Zona": "BASEMENT",
            },
            {
                "Layer": tower_name, "LayerNumber": layer_number,
                "TowerCode": tower_code, "Level": "S1",
                "LocationType": "BASEMENT", "LocationID": f"{tower_code}-S1",
                "CBB_Edificio": tower_code, "CBB_Piso": "S1",
                "CBB_Apartamento": "", "CBB_Zona": "BASEMENT",
            },
            {
                "Layer": tower_name, "LayerNumber": layer_number,
                "TowerCode": tower_code, "Level": "P01",
                "LocationType": "HALL", "LocationID": f"{tower_code}-P01-HALL",
                "CBB_Edificio": tower_code, "CBB_Piso": "P01",
                "CBB_Apartamento": "", "CBB_Zona": "HALL",
            },
        ])

        for floor in RESIDENTIAL_FLOORS:
            rows.append({
                "Layer": tower_name, "LayerNumber": layer_number,
                "TowerCode": tower_code, "Level": f"P{floor:02d}",
                "LocationType": "CORE", "LocationID": f"{tower_code}-P{floor:02d}-CORE",
                "CBB_Edificio": tower_code, "CBB_Piso": f"P{floor:02d}",
                "CBB_Apartamento": "", "CBB_Zona": "CORE",
            })

            for apartment in range(1, APARTMENTS_PER_FLOOR + 1):
                apt_code = f"APT{apartment:02d}"
                rows.append({
                    "Layer": tower_name, "LayerNumber": layer_number,
                    "TowerCode": tower_code, "Level": f"P{floor:02d}",
                    "LocationType": "APARTMENT",
                    "LocationID": f"{tower_code}-P{floor:02d}-{apt_code}",
                    "CBB_Edificio": tower_code, "CBB_Piso": f"P{floor:02d}",
                    "CBB_Apartamento": apt_code, "CBB_Zona": "APARTMENT",
                })

    rows.append({
        "Layer": "Plataforma", "LayerNumber": 3,
        "TowerCode": "PLT", "Level": "",
        "LocationType": "PLATFORM", "LocationID": "PLT",
        "CBB_Edificio": "PLT", "CBB_Piso": "",
        "CBB_Apartamento": "", "CBB_Zona": "PLATFORM_URBANISM",
    })

    return pd.DataFrame(rows)
