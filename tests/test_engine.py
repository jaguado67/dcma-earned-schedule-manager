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

