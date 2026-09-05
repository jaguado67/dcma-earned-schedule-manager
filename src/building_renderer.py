
from __future__ import annotations

import io
import random
from dataclasses import dataclass
from typing import Mapping

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import Polygon, PathPatch
from matplotlib.path import Path as MplPath
from matplotlib.colors import LinearSegmentedColormap


APARTMENT_POSITIONS = {
    "APT01": 18.0,
    "APT02": 46.0,
    "APT03": 114.0,
    "APT04": 142.0,
}

RESIDENTIAL_FLOORS = tuple(range(2, 15))


def progress_to_color(progress: float | None) -> str:
    """Shared progress palette for facade objects."""
    if progress is None:
        return "#323D47"
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


@dataclass
class BuildingConfig:
    num_basements: int = 2
    num_residential: int = 13
    floor_height: float = 38.0
    building_width: float = 160.0
    roof_height: float = 55.0
    apts_per_floor: int = 4
    has_balconies: bool = True
    random_seed: int = 42

    brick_base: str = "#B83A2A"
    brick_shadow: str = "#8A2318"
    mortar: str = "#A02E20"
    concrete: str = "#82878A"
    concrete_dark: str = "#5C6164"
    basement_wall: str = "#2B3036"
    roof_color: str = "#2D3134"
    roof_border: str = "#1B1D1F"
    trim_color: str = "#FFFFFF"
    trim_border: str = "#D0D0D0"
    glass_window: str = "#323D47"
    glass_hall: str = "#CBE4EC"
    glass_elevator: str = "#B4D5E0"
    lift_shaft: str = "#3E505B"
    ground_dirt: str = "#141517"
    ground_line: str = "#3D4246"
    cornice_color: str = "#EDE8E1"


class BuildingRenderer:
    """High-detail report renderer.

    Geometry follows the advanced building code supplied by the user.
    Unlike the original status_by_floor demo, every apartment window,
    Hall, basement and CORE can receive a progress value by LocationID.
    """

    def __init__(
        self,
        config: BuildingConfig,
        tower_code: str,
        tower_name: str,
        progress_by_location: Mapping[str, float | None] | None = None,
    ):
        self.cfg = config
        self.tower_code = tower_code.upper()
        self.tower_name = tower_name
        self.progress = dict(progress_by_location or {})
        random.seed(self.cfg.random_seed)

        self.num_above = self.cfg.num_residential + 1
        self.basement_height = self.cfg.num_basements * self.cfg.floor_height
        self.above_ground_height = self.num_above * self.cfg.floor_height
        self.top_y = self.above_ground_height

        self.fig, self.ax = plt.subplots(figsize=(8.5, 25.0), dpi=150)
        self.fig.patch.set_facecolor("#FFFFFF")
        self.ax.set_facecolor("#EDF4FA")

    def value(self, suffix: str) -> float | None:
        return self.progress.get(f"{self.tower_code}-{suffix}")

    def draw_terrain(self):
        b_w = self.cfg.building_width
        self.ax.add_patch(
            patches.Rectangle(
                (-65, -self.basement_height - 35),
                b_w + 130,
                self.basement_height + 35,
                facecolor=self.cfg.ground_dirt,
                edgecolor="none",
                zorder=1,
            )
        )

        for y_strata in range(int(-self.basement_height - 30), 0, 12):
            self.ax.plot(
                [-65, -5], [y_strata, y_strata - 5],
                color="#25272B", lw=1.0, zorder=1.2
            )
            self.ax.plot(
                [b_w + 5, b_w + 65], [y_strata, y_strata - 5],
                color="#25272B", lw=1.0, zorder=1.2
            )

        self.ax.plot(
            [-65, b_w + 65], [0, 0],
            color=self.cfg.ground_line, linewidth=4.5, zorder=10
        )

    def draw_basements(self):
        b_w = self.cfg.building_width
        f_h = self.cfg.floor_height

        self.ax.add_patch(
            patches.Rectangle(
                (0, -self.basement_height), b_w, self.basement_height,
                facecolor=self.cfg.basement_wall,
                edgecolor=self.cfg.concrete_dark,
                linewidth=3.0,
                zorder=2,
            )
        )

        for b_level in (1, 2):
            by = -b_level * f_h
            self.ax.add_patch(
                patches.Rectangle(
                    (0, by - 3.5), b_w, 7.0,
                    facecolor=self.cfg.concrete,
                    edgecolor=self.cfg.concrete_dark,
                    lw=0.8,
                    zorder=2.8,
                )
            )
            for x_hole in range(8, int(b_w), 14):
                for y_hole in (by + 9, by + 28):
                    self.ax.plot(
                        x_hole, y_hole,
                        marker="o", markersize=2.2,
                        color="#1A1C1E", zorder=2.5
                    )

        self.ax.add_patch(
            patches.Rectangle(
                (0, -self.basement_height - 6), b_w, 6.0,
                facecolor=self.cfg.concrete_dark,
                edgecolor="none",
                zorder=2.8,
            )
        )
        self.ax.add_patch(
            patches.Rectangle(
                (0, -4.5), b_w, 6.5,
                facecolor=self.cfg.concrete,
                edgecolor=self.cfg.concrete_dark,
                lw=0.8,
                zorder=2.8,
            )
        )

        basement_cols = (28.0, 80.0, 132.0)
        louver_w, louver_h = 26.0, 20.0

        for b_level, code in ((1, "S1"), (2, "S2")):
            by = -b_level * f_h
            cavity_color = progress_to_color(self.value(code))
            if self.value(code) is None:
                cavity_color = "#181A1C"

            for bx in basement_cols:
                lx = bx - louver_w / 2.0
                ly = by + (f_h - louver_h) / 2.0

                self.ax.add_patch(
                    patches.Rectangle(
                        (lx - 2.0, ly - 2.0),
                        louver_w + 4.0,
                        louver_h + 4.0,
                        facecolor=self.cfg.concrete,
                        edgecolor=self.cfg.trim_border,
                        linewidth=1.0,
                        zorder=3,
                    )
                )
                self.ax.add_patch(
                    patches.Rectangle(
                        (lx, ly), louver_w, louver_h,
                        facecolor=cavity_color,
                        zorder=3.2,
                    )
                )

                for s in range(7):
                    sy = ly + (s + 0.5) * (louver_h / 7)
                    self.ax.plot(
                        [lx, lx + louver_w], [sy, sy],
                        color="#D7DEE3", lw=1.25, zorder=3.5
                    )

    def draw_hall(self):
        b_w = self.cfg.building_width
        f_h = self.cfg.floor_height

        hall_progress = self.value("P01-HALL")
        hall_color = (
            progress_to_color(hall_progress)
            if hall_progress is not None
            else self.cfg.glass_hall
        )

        self.ax.add_patch(
            patches.Rectangle(
                (0, 0), b_w, f_h,
                facecolor=hall_color,
                edgecolor=self.cfg.concrete,
                linewidth=2.0,
                zorder=3,
            )
        )

        mullion_step = b_w / 6.0
        for m in range(1, 6):
            mx = m * mullion_step
            self.ax.plot(
                [mx, mx], [0, f_h],
                color="#7E9DA8", linewidth=1.8, zorder=3.2
            )
        self.ax.plot(
            [0, b_w], [f_h * 0.72, f_h * 0.72],
            color="#7E9DA8", linewidth=1.4, zorder=3.2
        )

        self.ax.add_patch(
            patches.Rectangle((b_w * 0.15, 0), 22, 11, facecolor="#4E3E34", zorder=3.5)
        )
        self.ax.add_patch(
            patches.Rectangle((b_w * 0.19, 11), 6, 6, facecolor="#263238", zorder=3.5)
        )
        self.ax.add_patch(
            patches.Rectangle((b_w * 0.72, 0), 25, 8, facecolor="#37474F", zorder=3.5)
        )
        self.ax.add_patch(
            patches.Rectangle((b_w * 0.70, 0), 4, 15, facecolor="#263238", zorder=3.5)
        )

        door_w = 26.0
        door_h = f_h * 0.82
        dx = b_w / 2.0 - door_w / 2.0
        self.ax.add_patch(
            patches.Rectangle(
                (dx, 0), door_w, door_h,
                facecolor="#9EC0CE",
                edgecolor="#4A6572",
                linewidth=2.2,
                zorder=3.6,
            )
        )

        center_x = b_w / 2.0
        self.ax.plot(
            [center_x, center_x], [0, door_h],
            color="#4A6572", linewidth=1.8, zorder=3.7
        )
        self.ax.plot(
            [center_x - 2.5, center_x - 2.5],
            [door_h * 0.40, door_h * 0.58],
            color="#FFFFFF", lw=2.0, zorder=3.8
        )
        self.ax.plot(
            [center_x + 2.5, center_x + 2.5],
            [door_h * 0.40, door_h * 0.58],
            color="#FFFFFF", lw=2.0, zorder=3.8
        )

    def draw_brickwork(self):
        b_w = self.cfg.building_width
        f_h = self.cfg.floor_height
        res_start_y = f_h
        res_height = (self.num_above - 1) * f_h

        self.ax.add_patch(
            patches.Rectangle(
                (0, res_start_y), b_w, res_height,
                facecolor=self.cfg.brick_base,
                edgecolor=self.cfg.mortar,
                lw=1.2,
                zorder=2,
            )
        )

        brick_h, brick_w = 3.6, 10.0
        num_courses = int(res_height / brick_h)
        tones = ("#B43424", "#BA3A2A", "#BF4030", "#A82B1C", "#9F2516")

        for row in range(num_courses):
            y_curr = res_start_y + row * brick_h
            self.ax.plot(
                [0, b_w], [y_curr, y_curr],
                color=self.cfg.mortar, lw=0.35, alpha=0.45, zorder=2.1
            )

            offset = (row % 2) * (brick_w / 2.0)
            col_x = offset
            while col_x < b_w:
                self.ax.plot(
                    [col_x, col_x], [y_curr, y_curr + brick_h],
                    color=self.cfg.mortar, lw=0.30, alpha=0.4, zorder=2.1
                )
                if random.random() < 0.22:
                    self.ax.add_patch(
                        patches.Rectangle(
                            (col_x, y_curr),
                            min(brick_w, b_w - col_x),
                            brick_h,
                            facecolor=random.choice(tones),
                            edgecolor="none",
                            alpha=0.55,
                            zorder=2.15,
                        )
                    )
                col_x += brick_w

        for fl in range(2, self.num_above):
            fy = fl * f_h
            self.ax.add_patch(
                patches.Rectangle(
                    (0, fy - 1.8), b_w, 3.6,
                    facecolor=self.cfg.brick_shadow,
                    edgecolor="none",
                    zorder=2.4,
                )
            )
            self.ax.plot(
                [0, b_w], [fy - 2.5, fy - 2.5],
                color="#52120B", lw=0.8, alpha=0.65, zorder=2.45
            )

    def draw_elevator_and_windows(self):
        b_w = self.cfg.building_width
        f_h = self.cfg.floor_height
        res_start_y = f_h
        res_height = (self.num_above - 1) * f_h

        lift_w = 24.0
        lift_x = (b_w - lift_w) / 2.0
        center_lift_x = b_w / 2.0

        self.ax.add_patch(
            patches.Rectangle(
                (lift_x, res_start_y), lift_w, res_height,
                facecolor=self.cfg.lift_shaft,
                edgecolor=self.cfg.concrete_dark,
                lw=1.5,
                zorder=3,
            )
        )

        win_w, win_h = 17.5, 22.0

        for floor in RESIDENTIAL_FLOORS:
            fy = (floor - 1) * f_h

            core_id = f"P{floor:02d}-CORE"
            core_progress = self.value(core_id)
            core_color = (
                progress_to_color(core_progress)
                if core_progress is not None
                else self.cfg.glass_elevator
            )

            lift_pad = 2.0
            self.ax.add_patch(
                patches.Rectangle(
                    (lift_x + lift_pad, fy + 3.0),
                    lift_w - 2 * lift_pad,
                    f_h - 6.0,
                    facecolor=core_color,
                    edgecolor=self.cfg.trim_color,
                    lw=1.2,
                    zorder=3.5,
                )
            )

            self.ax.plot(
                [center_lift_x, center_lift_x],
                [fy + 3.0, fy + f_h - 3.0],
                color="#658896", lw=1.2, zorder=3.6
            )
            self.ax.plot(
                [center_lift_x - 4, center_lift_x - 4],
                [fy + 3.0, fy + f_h - 3.0],
                color="#658896", ls=":", lw=0.8, zorder=3.6
            )
            self.ax.plot(
                [center_lift_x + 4, center_lift_x + 4],
                [fy + 3.0, fy + f_h - 3.0],
                color="#658896", ls=":", lw=0.8, zorder=3.6
            )

            for apt_code, cx in APARTMENT_POSITIONS.items():
                wx = cx - win_w / 2.0
                wy = fy + (f_h - win_h) / 2.0 - 1.0
                location = f"P{floor:02d}-{apt_code}"
                value = self.value(location)
                glass_color = progress_to_color(value)

                self.ax.add_patch(
                    patches.Rectangle(
                        (wx - 2.0, wy - 3.2),
                        win_w + 4.0,
                        1.6,
                        facecolor="#571710",
                        edgecolor="none",
                        alpha=0.55,
                        zorder=2.8,
                    )
                )

                border_color = "#00A88F" if value is not None else self.cfg.trim_border
                self.ax.add_patch(
                    patches.Rectangle(
                        (wx - 2.0, wy - 2.0),
                        win_w + 4.0,
                        win_h + 4.0,
                        facecolor=self.cfg.trim_color,
                        edgecolor=border_color,
                        lw=0.7,
                        zorder=4,
                    )
                )

                lintel_poly = [
                    [cx - win_w / 2.0 - 1.0, wy + win_h + 2.0],
                    [cx + win_w / 2.0 + 1.0, wy + win_h + 2.0],
                    [cx + win_w / 2.0 - 1.5, wy + win_h + 4.8],
                    [cx - win_w / 2.0 + 1.5, wy + win_h + 4.8],
                ]
                self.ax.add_patch(
                    Polygon(
                        lintel_poly,
                        closed=True,
                        facecolor=self.cfg.trim_color,
                        edgecolor="#BEBEBE",
                        lw=0.5,
                        zorder=4.2,
                    )
                )

                self.ax.add_patch(
                    patches.Rectangle(
                        (wx, wy), win_w, win_h,
                        facecolor=glass_color,
                        zorder=4.1,
                    )
                )

                for px in range(1, 3):
                    gx = wx + px * (win_w / 3.0)
                    self.ax.plot(
                        [gx, gx], [wy, wy + win_h],
                        color=self.cfg.trim_color,
                        lw=0.85,
                        zorder=4.5,
                    )

                for py in range(1, 4):
                    gy = wy + py * (win_h / 4.0)
                    self.ax.plot(
                        [wx, wx + win_w], [gy, gy],
                        color=self.cfg.trim_color,
                        lw=0.85,
                        zorder=4.5,
                    )

                if self.cfg.has_balconies:
                    balcony_w, balcony_h = win_w + 6.0, 7.5
                    bx_pos = cx - balcony_w / 2.0
                    by_pos = wy - 1.5

                    self.ax.add_patch(
                        patches.Rectangle(
                            (bx_pos - 1.0, by_pos - 1.5),
                            balcony_w + 2.0,
                            1.8,
                            facecolor=self.cfg.concrete,
                            edgecolor=self.cfg.concrete_dark,
                            lw=0.5,
                            zorder=5.1,
                        )
                    )
                    self.ax.add_patch(
                        patches.Rectangle(
                            (bx_pos, by_pos),
                            balcony_w,
                            balcony_h,
                            facecolor="#75A4B8",
                            alpha=0.18,
                            edgecolor="#C2DBE6",
                            lw=0.8,
                            zorder=5.2,
                        )
                    )
                    self.ax.plot(
                        [bx_pos - 1.0, bx_pos + balcony_w + 1.0],
                        [by_pos + balcony_h, by_pos + balcony_h],
                        color="#FFFFFF", lw=1.5, zorder=5.3
                    )
                    for post_x in (bx_pos, cx, bx_pos + balcony_w):
                        self.ax.plot(
                            [post_x, post_x],
                            [by_pos, by_pos + balcony_h],
                            color="#D1D6DA",
                            lw=1.0,
                            zorder=5.4,
                        )

    def _clipped_gradient(
        self,
        poly_points,
        color_bottom,
        color_top,
        zorder=5.0,
        alpha=1.0,
        n=256,
    ):
        xs = [p[0] for p in poly_points]
        ys = [p[1] for p in poly_points]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)

        gradient = np.linspace(0, 1, n).reshape(n, 1)
        cmap = LinearSegmentedColormap.from_list(
            "_grad", [color_bottom, color_top]
        )
        im = self.ax.imshow(
            gradient,
            extent=[x0, x1, y0, y1],
            origin="lower",
            aspect="auto",
            cmap=cmap,
            zorder=zorder,
            alpha=alpha,
            interpolation="bilinear",
        )

        closed_pts = poly_points + [poly_points[0]]
        path = MplPath(closed_pts)
        clip_patch = PathPatch(
            path,
            transform=self.ax.transData,
            facecolor="none",
            edgecolor="none",
        )
        im.set_clip_path(clip_patch)
        return im

    def draw_cornice_and_roof(self):
        b_w = self.cfg.building_width
        r_h = self.cfg.roof_height
        y_top = self.top_y

        frieze_h, frieze_ov = 3.4, 4.0
        shadow_h, shadow_ov = 1.4, 5.5
        dent_h, dent_ov = 4.0, 7.0
        crown_h, crown_ov = 3.0, 9.5
        y0 = y_top - (frieze_h + shadow_h + dent_h + crown_h)

        self.ax.add_patch(
            patches.Rectangle(
                (0, y0 - 2.2), b_w, 2.2,
                facecolor="#3A0E08",
                alpha=0.30,
                edgecolor="none",
                zorder=4.6,
            )
        )
        self.ax.add_patch(
            patches.Rectangle(
                (-frieze_ov, y0),
                b_w + 2 * frieze_ov,
                frieze_h,
                facecolor=self.cfg.cornice_color,
                edgecolor="#D6D0C4",
                lw=0.6,
                zorder=4.75,
            )
        )

        y1 = y0 + frieze_h
        self.ax.add_patch(
            patches.Rectangle(
                (-shadow_ov, y1),
                b_w + 2 * shadow_ov,
                shadow_h,
                facecolor="#A8A296",
                edgecolor="#8A8478",
                lw=0.6,
                zorder=4.8,
            )
        )

        y2 = y1 + shadow_h
        self.ax.add_patch(
            patches.Rectangle(
                (-dent_ov, y2),
                b_w + 2 * dent_ov,
                dent_h,
                facecolor=self.cfg.cornice_color,
                edgecolor="#BDB7AB",
                lw=1.0,
                zorder=4.85,
            )
        )

        for dx in range(
            int(-dent_ov + 2),
            int(b_w + dent_ov - 4),
            7,
        ):
            self.ax.add_patch(
                patches.Rectangle(
                    (dx, y2 + 0.7),
                    4.0,
                    dent_h - 1.4,
                    facecolor="#DAD4C8",
                    edgecolor="#A8A296",
                    lw=0.4,
                    zorder=4.9,
                )
            )

        y3 = y2 + dent_h
        self.ax.add_patch(
            patches.Rectangle(
                (-crown_ov, y3),
                b_w + 2 * crown_ov,
                crown_h,
                facecolor="#F7F3EC",
                edgecolor="#C7C0B2",
                lw=1.0,
                zorder=4.95,
            )
        )

        overhang = 12.0
        roof_poly = [
            [-overhang, y_top],
            [b_w + overhang, y_top],
            [b_w - 15.0, y_top + r_h],
            [15.0, y_top + r_h],
        ]

        self._clipped_gradient(
            roof_poly,
            color_bottom="#15171A",
            color_top="#525C66",
            zorder=5.0,
        )

        self.ax.add_patch(
            Polygon(
                roof_poly,
                closed=True,
                facecolor="none",
                edgecolor=self.cfg.roof_border,
                lw=1.6,
                zorder=5.05,
            )
        )

        n_courses = 7
        for i in range(1, n_courses):
            r_step = (r_h / n_courses) * i
            inset = (r_step / r_h) * 15.0
            xl, xr = -overhang + inset, b_w + overhang - inset
            yy = y_top + r_step
            self.ax.plot(
                [xl, xr], [yy, yy],
                color="#0E1012", lw=0.9, alpha=0.55, zorder=5.15
            )
            self.ax.plot(
                [xl, xr], [yy + 0.55, yy + 0.55],
                color="#6E7882", lw=0.55, alpha=0.4, zorder=5.16
            )

        self.ax.plot(
            [15.0, b_w - 15.0],
            [y_top + r_h, y_top + r_h],
            color="#9BA5AD", lw=1.3, zorder=5.3
        )

        for cx in range(18, int(b_w - 15), 9):
            self.ax.plot(
                [cx, cx],
                [y_top + r_h, y_top + r_h + 2.2],
                color="#9BA5AD", lw=1.0, zorder=5.3
            )
            self.ax.plot(
                cx, y_top + r_h + 2.2,
                marker="o", markersize=1.6,
                color="#9BA5AD", zorder=5.3
            )

        for cx in (b_w * 0.20, b_w * 0.80):
            ch_y = y_top + r_h * 0.40
            ch_w, ch_h = 10.0, 15.0
            self.ax.add_patch(
                patches.Rectangle(
                    (cx - ch_w / 2.0, ch_y), ch_w, ch_h,
                    facecolor=self.cfg.brick_shadow,
                    edgecolor="#4A140D",
                    lw=1.0,
                    zorder=5.5,
                )
            )
            self.ax.add_patch(
                patches.Rectangle(
                    (cx - ch_w / 2.0 - 1.2, ch_y + ch_h),
                    ch_w + 2.4,
                    2.0,
                    facecolor="#3A3F43",
                    edgecolor="#1B1D1F",
                    lw=0.8,
                    zorder=5.55,
                )
            )

        dm_w, dm_h = 26.0, 30.0
        dm_x = (b_w - dm_w) / 2.0
        dm_y = y_top + 10.0
        apex = (b_w / 2.0, dm_y + dm_h + 9.0)
        base_l = (dm_x - 4.0, dm_y + dm_h)
        base_r = (dm_x + dm_w + 4.0, dm_y + dm_h)
        base_mid = (b_w / 2.0, dm_y + dm_h)

        self.ax.add_patch(
            Polygon(
                [base_l, base_mid, apex],
                closed=True,
                facecolor="#3D4247",
                edgecolor=self.cfg.trim_color,
                lw=1.2,
                zorder=6,
            )
        )
        self.ax.add_patch(
            Polygon(
                [base_mid, base_r, apex],
                closed=True,
                facecolor="#24272A",
                edgecolor=self.cfg.trim_color,
                lw=1.2,
                zorder=6,
            )
        )

        self.ax.add_patch(
            patches.Rectangle(
                (dm_x, dm_y), dm_w, dm_h - 2.0,
                facecolor=self.cfg.trim_color,
                edgecolor=self.cfg.trim_border,
                lw=0.8,
                zorder=6.15,
            )
        )

        dg_pad = 4.0
        dg_x, dg_y = dm_x + dg_pad, dm_y + dg_pad - 1.0
        dg_w, dg_h = dm_w - 2 * dg_pad, dm_h - 2 * dg_pad - 2.0

        self.ax.add_patch(
            patches.Rectangle(
                (dg_x, dg_y), dg_w, dg_h,
                facecolor=self.cfg.glass_window,
                zorder=6.5,
            )
        )

        for px in range(1, 3):
            gx = dg_x + px * (dg_w / 3.0)
            self.ax.plot(
                [gx, gx], [dg_y, dg_y + dg_h],
                color=self.cfg.trim_color, lw=0.9, zorder=7
            )
        for py in range(1, 4):
            gy = dg_y + py * (dg_h / 4.0)
            self.ax.plot(
                [dg_x, dg_x + dg_w], [gy, gy],
                color=self.cfg.trim_color, lw=0.9, zorder=7
            )

        rod_x, rod_y = apex
        self.ax.plot(
            [rod_x, rod_x], [rod_y, rod_y + 6.5],
            color="#9BA5AD", lw=1.3, zorder=7.5
        )
        self.ax.add_patch(
            patches.Circle(
                (rod_x, rod_y + 6.5),
                radius=0.9,
                facecolor="#C7CDD2",
                edgecolor="#6E7882",
                lw=0.5,
                zorder=7.6,
            )
        )

    def _floor_progress(self, floor: int) -> float | None:
        values = [
            self.value(f"P{floor:02d}-{apt}")
            for apt in APARTMENT_POSITIONS
        ]
        mapped = [v for v in values if v is not None]
        if not mapped:
            return None
        return sum(mapped) / len(mapped)

    def draw_annotations_and_controls(self):
        b_w = self.cfg.building_width
        f_h = self.cfg.floor_height
        label_x = b_w + 14.0

        levels = [
            ("S2", -1.5 * f_h, self.value("S2")),
            ("S1", -0.5 * f_h, self.value("S1")),
            ("P01 · HALL", 0.5 * f_h, self.value("P01-HALL")),
        ]

        for floor in RESIDENTIAL_FLOORS:
            levels.append(
                (
                    f"P{floor:02d}",
                    (floor - 1) * f_h + 0.5 * f_h,
                    self._floor_progress(floor),
                )
            )

        for code, mid_y, value in levels:
            text = code
            if value is not None:
                text += f"  {value:.0f}%"
            self.ax.text(
                label_x,
                mid_y,
                text,
                fontsize=9.0,
                fontweight="bold",
                color="#1A1A1A" if mid_y >= 0 else "#FFFFFF",
                va="center",
            )
            self.ax.add_patch(
                patches.Circle(
                    (label_x + 42.0, mid_y),
                    radius=2.5,
                    facecolor=progress_to_color(value),
                    edgecolor="#FFFFFF",
                    lw=0.8,
                    zorder=8,
                )
            )

        legend_y = self.top_y + self.cfg.roof_height + 8.0
        self.ax.text(
            label_x - 12,
            legend_y,
            "PROGRESO",
            fontsize=9.0,
            fontweight="bold",
            color="#1A1A1A",
        )

        legend = (
            ("Sin mapeo", "#323D47"),
            ("0%", "#E7ECEF"),
            ("25–49%", "#F0C35A"),
            ("50–74%", "#A9C96F"),
            ("75–99%", "#57A96B"),
            ("100%", "#078B55"),
        )

        for idx, (name, color) in enumerate(legend):
            ly = legend_y - 9.0 - idx * 7.0
            self.ax.add_patch(
                patches.Circle(
                    (label_x - 9, ly),
                    radius=2.0,
                    facecolor=color,
                    edgecolor="none",
                    zorder=8,
                )
            )
            self.ax.text(
                label_x - 4,
                ly,
                name,
                fontsize=7.4,
                color="#333333",
                va="center",
            )

        bracket_y = f_h + 1.5 * f_h
        self.ax.annotate(
            "4 APARTAMENTOS\nPOR PISO\nAPT01 · APT02 | CORE | APT03 · APT04",
            xy=(-12.0, bracket_y),
            xycoords="data",
            xytext=(-48.0, bracket_y),
            textcoords="data",
            arrowprops=dict(
                arrowstyle="->",
                color="#222222",
                lw=1.2,
            ),
            fontsize=7.0,
            fontweight="bold",
            color="#1F2421",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="square,pad=0.35",
                fc="#FFFFFF",
                ec="#7F8C8D",
                lw=0.9,
            ),
        )

        self.ax.text(
            self.cfg.building_width / 2.0,
            self.top_y + self.cfg.roof_height + 16,
            self.tower_name.upper(),
            ha="center",
            va="bottom",
            fontsize=15,
            fontweight="bold",
            color="#082D50",
        )
        self.ax.text(
            self.cfg.building_width / 2.0,
            self.top_y + self.cfg.roof_height + 7,
            "S2 + S1 · P01 Hall · P02–P14 residencial · 52 apartamentos",
            ha="center",
            va="bottom",
            fontsize=7.2,
            color="#526471",
        )

    def draw(self):
        self.draw_terrain()
        self.draw_basements()
        self.draw_hall()
        self.draw_brickwork()
        self.draw_elevator_and_windows()
        self.draw_cornice_and_roof()
        self.draw_annotations_and_controls()

        b_w = self.cfg.building_width
        self.ax.set_xlim(-68, b_w + 78)
        self.ax.set_ylim(
            -self.basement_height - 25,
            self.top_y + self.cfg.roof_height + 24,
        )
        self.ax.axis("off")
        plt.tight_layout()

    def render_bytes(self, fmt: str = "png") -> bytes:
        fmt = fmt.lower()
        if fmt not in {"png", "svg"}:
            raise ValueError("fmt must be 'png' or 'svg'")
        self.draw()
        buffer = io.BytesIO()
        self.fig.savefig(
            buffer,
            format=fmt,
            bbox_inches="tight",
            dpi=180 if fmt == "png" else None,
        )
        plt.close(self.fig)
        return buffer.getvalue()

    def render(self, output_base: str) -> tuple[str, str]:
        self.draw()
        png_file = f"{output_base}.png"
        svg_file = f"{output_base}.svg"
        self.fig.savefig(png_file, bbox_inches="tight", dpi=180)
        self.fig.savefig(svg_file, bbox_inches="tight")
        plt.close(self.fig)
        return png_file, svg_file
