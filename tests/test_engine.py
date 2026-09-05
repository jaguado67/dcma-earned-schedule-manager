from pathlib import Path

from src.dcma import assess
from src.earned_schedule import calculate_esm, template
from src.xer import parse_xer


ROOT = Path(__file__).parents[1]


def test_parse_demo_files():
    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    sierra = parse_xer(ROOT / "demo/torre_sierra_v2.xer")
    assert len(mar.tasks) == 1465
    assert len(sierra.tasks) == 1463
    assert len(mar.relationships) == 1749


def test_dcma_has_14_metrics():
    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    metrics, detail = assess(mar)
    assert [m.number for m in metrics] == list(range(1, 15))
    assert len(detail["leads"]) == 334
    assert len(detail["lags"]) == 258


def test_earned_schedule_columns():
    result = calculate_esm(template())
    assert {"ES", "SV(t)", "SPI(t)", "SPI", "CPI"}.issubset(result.columns)
    assert len(result) == 6



def test_location_model_builds_p02_to_p14_grid():
    from src.location_model import tower_grid

    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    grid = tower_grid(mar)
    assert len(grid) == 52
    assert grid["Floor"].min() == 2
    assert grid["Floor"].max() == 14
    assert grid["Apartment"].nunique() == 4


def test_location_model_reads_floor_activity_code():
    from src.location_model import floor_progress

    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    summary = floor_progress(mar)
    assert not summary.empty
    assert 1 in set(summary["Floor"])


def test_luxury_index_gives_finishes_preponderance():
    from src.location_model import luxury_index_grid

    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    grid = luxury_index_grid(mar)
    assert {"GeneralProgress", "FinishProgress", "Progress"}.issubset(grid.columns)
    assert len(grid) == 52


def test_location_master_has_104_apartments():
    from src.location_model import model_master

    master = model_master()
    apartments = master[
        master["LocationType"] == "APARTMENT"
    ]
    assert len(apartments) == 104
    assert set(master["Layer"]) == {
        "Torre Mar", "Torre Sierra", "Plataforma"
    }


def test_hall_is_p01_and_not_residential():
    from src.location_model import HALL_FLOOR, RESIDENTIAL_FLOORS

    assert HALL_FLOOR == 1
    assert 1 not in RESIDENTIAL_FLOORS
    assert RESIDENTIAL_FLOORS == tuple(range(2, 15))



def test_floor_rollup_is_derived_from_windows():
    import pandas as pd
    from src.location_model import floor_rollup

    grid = pd.DataFrame([
        {"Floor": 2, "Mapped": True, "Progress": 100.0},
        {"Floor": 2, "Mapped": True, "Progress": 50.0},
        {"Floor": 2, "Mapped": True, "Progress": 0.0},
        {"Floor": 2, "Mapped": True, "Progress": 50.0},
    ])
    roll = floor_rollup(grid).iloc[0]
    assert roll["Progress"] == 50.0
    assert roll["Coverage"] == 100.0


def test_luxury_index_does_not_convert_missing_finish_data_to_zero():
    import pandas as pd
    import src.location_model as lm

    original_tower_grid = lm.tower_grid
    try:
        def fake_grid(project, residential_floors=lm.RESIDENTIAL_FLOORS, apartments=lm.APARTMENTS_PER_FLOOR, finishes_only=False):
            if finishes_only:
                return pd.DataFrame([{
                    "Floor": 2, "Apartment": 1, "FloorCode": "P02", "ApartmentCode": "APT01",
                    "Location": "P02-APT01", "Activities": 0, "Complete": 0, "Active": 0,
                    "NotStarted": 0, "Progress": 0.0, "Mapped": False, "MappingLevel": "UNMAPPED",
                }])
            return pd.DataFrame([{
                "Floor": 2, "Apartment": 1, "FloorCode": "P02", "ApartmentCode": "APT01",
                "Location": "P02-APT01", "Activities": 10, "Complete": 2, "Active": 3,
                "NotStarted": 5, "Progress": 60.0, "Mapped": True, "MappingLevel": "APARTMENT",
            }])
        lm.tower_grid = fake_grid
        result = lm.luxury_index_grid(object(), residential_floors=(2,), apartments=1)
        row = result.iloc[0]
        assert row["Progress"] == 60.0
        assert row["MetricQuality"] == "GENERAL_ONLY"
    finally:
        lm.tower_grid = original_tower_grid


def test_progress_by_location_uses_unique_tower_ids():
    from src.location_model import progress_by_location

    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    progress = progress_by_location(mar, "MAR")
    assert "MAR-P02-APT01" in progress
    assert "MAR-P01-HALL" in progress
    assert "MAR-S2" in progress


def test_model_master_contains_p6_ready_location_codes():
    from src.location_model import model_master

    master = model_master()
    apt = master[master["LocationID"] == "MAR-P08-APT03"].iloc[0]
    assert apt["CBB_Edificio"] == "MAR"
    assert apt["CBB_Piso"] == "P08"
    assert apt["CBB_Apartamento"] == "APT03"
    assert apt["CBB_Zona"] == "APARTMENT"



def test_advanced_renderer_uses_13_residential_floors_and_four_apartments():
    from src.building_renderer import (
        BuildingConfig,
        APARTMENT_POSITIONS,
        RESIDENTIAL_FLOORS,
    )

    cfg = BuildingConfig()
    assert cfg.num_basements == 2
    assert cfg.num_residential == 13
    assert RESIDENTIAL_FLOORS == tuple(range(2, 15))
    assert list(APARTMENT_POSITIONS) == ["APT01", "APT02", "APT03", "APT04"]


def test_advanced_renderer_progress_palette():
    from src.building_renderer import progress_to_color

    assert progress_to_color(None) == "#323D47"
    assert progress_to_color(0) == "#E7ECEF"
    assert progress_to_color(30) == "#F0C35A"
    assert progress_to_color(80) == "#57A96B"
    assert progress_to_color(100) == "#078B55"


def test_p6_floor_normalization_matches_two_basements_and_14_above_grade():
    from src.location_model import p6_floor_to_model_floor

    assert p6_floor_to_model_floor("Piso 1") == -2
    assert p6_floor_to_model_floor("Piso 2") == -1
    assert p6_floor_to_model_floor("Piso 3") == 1
    assert p6_floor_to_model_floor("Piso 16") == 14
    assert p6_floor_to_model_floor("Piso -2") is None
    assert p6_floor_to_model_floor("P14") == 14


def test_tower_lob_maps_piso_3_to_p01_and_piso_16_to_p14():
    from src.line_of_balance import tower_lob

    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    frame = tower_lob(mar)
    assert not frame.empty
    assert "P01" in set(frame["Location"])
    assert "P14" in set(frame["Location"])
    assert frame.loc[frame["Location"] == "P14", "LocationOrder"].eq(14).all()


def test_tower_lob_keeps_foundation_separate_from_basements():
    from src.line_of_balance import tower_lob

    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    frame = tower_lob(mar)
    assert {"CIM", "S2", "S1"}.issubset(set(frame["Location"]))


def test_process_metrics_returns_cycle_time_for_repetitive_processes():
    from src.line_of_balance import process_metrics, tower_lob

    mar = parse_xer(ROOT / "demo/torre_mar_v2.xer")
    frame = tower_lob(mar)
    frame = frame[frame["Repetitive"]]
    metrics = process_metrics(frame)
    assert not metrics.empty
    assert "Estructura" in set(metrics["Process"])
