from __future__ import annotations

import csv
import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Iterable


@dataclass
class XERProject:
    name: str
    tables: dict[str, list[dict[str, str]]]
    export_version: str = ""
    export_date: str = ""
    source: str = ""

    @property
    def project(self) -> dict[str, str]:
        return (self.tables.get("PROJECT") or [{}])[0]

    @property
    def tasks(self) -> list[dict[str, str]]:
        return self.tables.get("TASK", [])

    @property
    def relationships(self) -> list[dict[str, str]]:
        return self.tables.get("TASKPRED", [])

    @property
    def assignments(self) -> list[dict[str, str]]:
        return self.tables.get("TASKRSRC", [])


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def parse_xer(source: bytes | BinaryIO | str | Path, name: str | None = None) -> XERProject:
    if isinstance(source, (str, Path)):
        path = Path(source)
        raw = path.read_bytes()
        name = name or path.name
    elif isinstance(source, bytes):
        raw = source
    else:
        raw = source.read()
        name = name or getattr(source, "name", "uploaded.xer")

    text = _decode(raw)
    rows = csv.reader(io.StringIO(text), delimiter="\t")
    tables: dict[str, list[dict[str, str]]] = defaultdict(list)
    headers: dict[str, list[str]] = {}
    current = ""
    export_version = export_date = source_name = ""

    for row in rows:
        if not row:
            continue
        if row[0] == "ERMHDR":
            export_version = row[1] if len(row) > 1 else ""
            export_date = row[2] if len(row) > 2 else ""
            source_name = row[7] if len(row) > 7 else ""
        elif row[0] == "%T" and len(row) > 1:
            current = row[1]
        elif row[0] == "%F" and current:
            headers[current] = row[1:]
        elif row[0] == "%R" and current and current in headers:
            fields, values = headers[current], row[1:]
            tables[current].append(
                {field: values[i] if i < len(values) else "" for i, field in enumerate(fields)}
            )

    project_name = ((tables.get("PROJECT") or [{}])[0].get("proj_short_name") or name or "XER")
    return XERProject(project_name, dict(tables), export_version, export_date, source_name)


def as_float(value: str | None) -> float | None:
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

