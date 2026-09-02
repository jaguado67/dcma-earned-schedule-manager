from __future__ import annotations

import numpy as np
import pandas as pd


REQUIRED = ["Period", "PV", "EV", "AC"]


def calculate_esm(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED if c not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas: {', '.join(missing)}")
    df = frame.copy()
    df["Period"] = pd.to_datetime(df["Period"])
    df = df.sort_values("Period").reset_index(drop=True)
    for c in ("PV", "EV", "AC"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    if df[["PV", "EV", "AC"]].isna().any().any():
        raise ValueError("PV, EV y AC deben ser numéricos.")

    at = np.arange(1, len(df) + 1, dtype=float)
    pv = df["PV"].to_numpy(float)
    ev = df["EV"].to_numpy(float)
    ac = df["AC"].to_numpy(float)
    es = []
    for earned in ev:
        idx = int(np.searchsorted(pv, earned, side="right") - 1)
        if idx < 0:
            value = earned / pv[0] if pv[0] else 0.0
        elif idx >= len(pv) - 1:
            value = float(len(pv)) if earned >= pv[-1] else float(idx + 1)
        else:
            base, nxt = pv[idx], pv[idx + 1]
            fraction = (earned - base) / (nxt - base) if nxt != base else 0.0
            value = idx + 1 + fraction
        es.append(value)
    df["AT"] = at
    df["ES"] = es
    df["SV(t)"] = df["ES"] - df["AT"]
    df["SPI(t)"] = df["ES"] / df["AT"]
    df["SV"] = df["EV"] - df["PV"]
    df["SPI"] = np.where(df["PV"] != 0, df["EV"] / df["PV"], np.nan)
    df["CV"] = df["EV"] - df["AC"]
    df["CPI"] = np.where(df["AC"] != 0, df["EV"] / df["AC"], np.nan)
    return df


def template() -> pd.DataFrame:
    return pd.DataFrame({
        "Period": pd.date_range("2026-01-31", periods=6, freq="ME"),
        "PV": [100, 220, 360, 520, 700, 900],
        "EV": [90, 190, 300, 430, 590, 760],
        "AC": [95, 205, 330, 470, 635, 810],
    })

