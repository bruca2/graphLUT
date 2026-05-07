#!/usr/bin/env python3
"""
Sample channel curves from a 3D LUT in .cube format.

The script varies one input channel over [a, b], evaluates the 3D LUT using
tetrahedral interpolation, and writes the corresponding output R/G/B values.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable


CHANNEL_INDEX = {"r": 0, "g": 1, "b": 2}


def remap_input_value(value: float) -> float:
    return (876.0 * value + 64.0) / 1023.0


@dataclass(frozen=True)
class CubeLUT:
    size: int
    values: list[tuple[float, float, float]]
    domain_min: tuple[float, float, float]
    domain_max: tuple[float, float, float]

    def _value_at(self, r: int, g: int, b: int) -> tuple[float, float, float]:
        """Return LUT value for integer lattice coordinate (r, g, b)."""
        i = r + g * self.size + b * self.size * self.size
        return self.values[i]

    def _normalize(self, rgb: tuple[float, float, float]) -> tuple[float, float, float]:
        coords = []
        for value, lo, hi in zip(rgb, self.domain_min, self.domain_max):
            if hi == lo:
                raise ValueError("Invalid LUT domain: DOMAIN_MIN equals DOMAIN_MAX.")
            normalized = (value - lo) / (hi - lo)
            coords.append(min(1.0, max(0.0, normalized)) * (self.size - 1))
        return (coords[0], coords[1], coords[2])

    def apply_tetrahedral(self, rgb: tuple[float, float, float]) -> tuple[float, float, float]:
        """Evaluate the LUT at rgb using tetrahedral interpolation."""
        r, g, b = self._normalize(rgb)

        r0 = min(int(r), self.size - 2)
        g0 = min(int(g), self.size - 2)
        b0 = min(int(b), self.size - 2)

        dr = r - r0
        dg = g - g0
        db = b - b0

        c000 = self._value_at(r0, g0, b0)
        c100 = self._value_at(r0 + 1, g0, b0)
        c010 = self._value_at(r0, g0 + 1, b0)
        c001 = self._value_at(r0, g0, b0 + 1)
        c110 = self._value_at(r0 + 1, g0 + 1, b0)
        c101 = self._value_at(r0 + 1, g0, b0 + 1)
        c011 = self._value_at(r0, g0 + 1, b0 + 1)
        c111 = self._value_at(r0 + 1, g0 + 1, b0 + 1)

        if dr >= dg:
            if dg >= db:
                return _add(c000, _mul(_sub(c100, c000), dr), _mul(_sub(c110, c100), dg), _mul(_sub(c111, c110), db))
            if dr >= db:
                return _add(c000, _mul(_sub(c100, c000), dr), _mul(_sub(c111, c101), dg), _mul(_sub(c101, c100), db))
            return _add(c000, _mul(_sub(c001, c000), db), _mul(_sub(c101, c001), dr), _mul(_sub(c111, c101), dg))

        if db >= dg:
            return _add(c000, _mul(_sub(c111, c011), dr), _mul(_sub(c011, c001), dg), _mul(_sub(c001, c000), db))
        if db >= dr:
            return _add(c000, _mul(_sub(c010, c000), dg), _mul(_sub(c011, c010), db), _mul(_sub(c111, c011), dr))
        return _add(c000, _mul(_sub(c010, c000), dg), _mul(_sub(c110, c010), dr), _mul(_sub(c111, c110), db))


def _add(*colors: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        sum(color[0] for color in colors),
        sum(color[1] for color in colors),
        sum(color[2] for color in colors),
    )


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(color: tuple[float, float, float], scalar: float) -> tuple[float, float, float]:
    return (color[0] * scalar, color[1] * scalar, color[2] * scalar)


def load_cube(path: str) -> CubeLUT:
    size = None
    values: list[tuple[float, float, float]] = []
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)

    with open(path, "r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split()
            keyword = parts[0].upper()

            if keyword == "TITLE":
                continue
            if keyword == "LUT_1D_SIZE":
                raise ValueError("This script expects a 3D .cube LUT, not a 1D LUT.")
            if keyword == "LUT_3D_SIZE":
                size = int(parts[1])
                if size < 2:
                    raise ValueError("LUT_3D_SIZE must be at least 2.")
                continue
            if keyword == "DOMAIN_MIN":
                domain_min = _parse_float_triplet(parts[1:], line_number)
                continue
            if keyword == "DOMAIN_MAX":
                domain_max = _parse_float_triplet(parts[1:], line_number)
                continue

            values.append(_parse_float_triplet(parts, line_number))

    if size is None:
        raise ValueError("Missing LUT_3D_SIZE in .cube file.")

    expected = size**3
    if len(values) != expected:
        raise ValueError(f"Expected {expected} LUT rows for size {size}, found {len(values)}.")

    return CubeLUT(size=size, values=values, domain_min=domain_min, domain_max=domain_max)


def _parse_float_triplet(parts: list[str], line_number: int) -> tuple[float, float, float]:
    if len(parts) < 3:
        raise ValueError(f"Line {line_number}: expected three float values.")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def channel_curve(
    lut: CubeLUT,
    input_channel: str,
    a: float,
    b: float,
    samples: int,
    fixed_rgb: tuple[float, float, float],
) -> Iterable[tuple[float, float, float, float]]:
    if samples < 2:
        raise ValueError("samples must be at least 2.")

    channel = CHANNEL_INDEX[input_channel.lower()]
    step = (b - a) / (samples - 1)

    for i in range(samples):
        x = a + step * i
        rgb = list(fixed_rgb)
        rgb[channel] = x
        out_r, out_g, out_b = lut.apply_tetrahedral((rgb[0], rgb[1], rgb[2]))
        yield (x, out_r, out_g, out_b)


def write_curve_csv(rows: Iterable[tuple[float, float, float, float]], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["x", "out_r", "out_g", "out_b"])
        writer.writerows(rows)


def plot_curve(
    rows: list[tuple[float, float, float, float]],
    input_channel: str,
    show: bool = False,
    output_path: str | None = None,
    only_provided_channel: bool = False,
    title: str = "3D LUT Channel Curves",
) -> None:
    if output_path and Path(output_path).suffix.lower() == ".svg" and not show:
        write_curve_svg(rows, input_channel, output_path, only_provided_channel, title)
        return

    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError:
        if output_path and not show:
            svg_path = str(Path(output_path).with_suffix(".svg"))
            write_curve_svg(rows, input_channel, svg_path, only_provided_channel, title)
            print(f"matplotlib is not installed; wrote SVG plot to {svg_path}")
            return
        if output_path and Path(output_path).suffix.lower() == ".svg":
            write_curve_svg(rows, input_channel, output_path, only_provided_channel, title)
            print(f"matplotlib is not installed; wrote SVG plot to {output_path}")
            return
        raise RuntimeError("matplotlib is required for --plot without --plot-output. Use --plot-output curve.svg instead.")

    xs = [row[0] for row in rows]
    channels = _selected_plot_channels(input_channel, only_provided_channel)
    axis_min, axis_max = _shared_axis_limits(rows, channels)

    plt.figure(figsize=(9, 6))
    for label, color, row_index in channels:
        ys = [row[row_index] for row in rows]
        plt.plot(xs, ys, color=color, label=f"Output {label}")
    plt.xlabel(f"Input {input_channel.upper()}")
    plt.ylabel("Output value")
    plt.title(title)
    plt.xlim(axis_min, axis_max)
    plt.ylim(axis_min, axis_max)
    plt.gca().set_aspect("equal", adjustable="box")
    _add_zero_ticks(plt.gca(), axis_min, axis_max)
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    if output_path:
        if Path(output_path).suffix.lower() == ".svg":
            write_curve_svg(rows, input_channel, output_path, only_provided_channel, title)
        else:
            plt.savefig(output_path, dpi=150)
    if show:
        plt.show()
    plt.close()


def write_curve_svg(
    rows: list[tuple[float, float, float, float]],
    input_channel: str,
    output_path: str,
    only_provided_channel: bool = False,
    title: str = "3D LUT Channel Curves",
) -> None:
    width = 900
    height = 600
    left = 70
    right = 25
    top = 35
    bottom = 60

    xs = [row[0] for row in rows]
    channels = _selected_plot_channels(input_channel, only_provided_channel)
    axis_min, axis_max = _shared_axis_limits(rows, channels)
    x_min, x_max = axis_min, axis_max
    y_min, y_max = axis_min, axis_max

    plot_size = min(width - left - right, height - top - bottom)
    plot_w = plot_size
    plot_h = plot_size
    plot_right = left + plot_w
    plot_bottom = top + plot_h

    def sx(x: float) -> float:
        return left + (x - x_min) / (x_max - x_min) * plot_w

    def sy(y: float) -> float:
        return top + (y_max - y) / (y_max - y_min) * plot_h

    def polyline(channel_index: int) -> str:
        return " ".join(f"{sx(row[0]):.3f},{sy(row[channel_index]):.3f}" for row in rows)

    x_label = f"Input {input_channel.upper()}"
    y_label = "Output value"
    polylines = "\n".join(
        f'  <polyline fill="none" stroke="{color}" stroke-width="2" points="{polyline(row_index)}"/>'
        for _, color, row_index in channels
    )
    legend = "\n".join(
        f'  <text x="{width - 120}" y="{58 + 20 * i}" font-family="sans-serif" font-size="13" fill="{color}">Output {label}</text>'
        for i, (label, color, _) in enumerate(channels)
    )
    ticks = _svg_nice_ticks(axis_min, axis_max)
    tick_elements = _svg_tick_elements(ticks, left, plot_right, top, plot_bottom, sx, sy)
    zero_outside = _svg_zero_outside_label(axis_min, axis_max, left, plot_right, top, plot_bottom)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="white"/>
  <text x="{width / 2}" y="22" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{plot_bottom}" stroke="black"/>
  <line x1="{left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="black"/>
  <text x="{width / 2}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="14">{x_label}</text>
  <text x="18" y="{height / 2}" text-anchor="middle" font-family="sans-serif" font-size="14" transform="rotate(-90 18 {height / 2})">{y_label}</text>
{tick_elements}
{zero_outside}
{polylines}
{legend}
</svg>
"""
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(svg)


def _selected_plot_channels(input_channel: str, only_provided_channel: bool) -> list[tuple[str, str, int]]:
    channels = [("R", "red", 1), ("G", "green", 2), ("B", "blue", 3)]
    if not only_provided_channel:
        return channels

    selected = input_channel.upper()
    return [channel for channel in channels if channel[0] == selected]


def _add_zero_ticks(axis, axis_min: float, axis_max: float) -> None:
    for get_ticks, set_ticks in ((axis.get_xticks, axis.set_xticks), (axis.get_yticks, axis.set_yticks)):
        ticks = list(get_ticks())
        if axis_min <= 0.0 <= axis_max and not any(abs(tick) < 1e-12 for tick in ticks):
            ticks.append(0.0)
            set_ticks(sorted(ticks))

    if 0.0 < axis_min:
        axis.text(0.0, -0.055, "0", transform=axis.transAxes, ha="center", va="top", fontsize=9)
        axis.text(-0.04, 0.0, "0", transform=axis.transAxes, ha="right", va="center", fontsize=9)
    elif 0.0 > axis_max:
        axis.text(1.0, -0.055, "0", transform=axis.transAxes, ha="center", va="top", fontsize=9)
        axis.text(-0.04, 1.0, "0", transform=axis.transAxes, ha="right", va="center", fontsize=9)


def _svg_nice_ticks(axis_min: float, axis_max: float) -> list[float]:
    """Generate nice tick values mimicking matplotlib's MaxNLocator with ~6 ticks."""
    span = axis_max - axis_min
    if span == 0:
        return [axis_min]
    raw_step = span / 6.0
    magnitude = 10.0 ** math.floor(math.log10(raw_step))
    normalized = raw_step / magnitude
    if normalized <= 1.0:
        nice = 1.0
    elif normalized <= 2.0:
        nice = 2.0
    elif normalized <= 2.5:
        nice = 2.5
    elif normalized <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    step = nice * magnitude
    start = math.ceil(axis_min / step - 1e-9) * step
    ticks: list[float] = []
    t = start
    while t <= axis_max + 1e-9 * step:
        rounded = round(t / step) * step
        if axis_min - 1e-9 <= rounded <= axis_max + 1e-9:
            ticks.append(rounded)
        t += step
    if axis_min <= 0.0 <= axis_max and not any(abs(tick) < 1e-12 for tick in ticks):
        ticks = sorted(ticks + [0.0])
    return ticks


def _svg_tick_elements(
    ticks: list[float],
    left: float,
    plot_right: float,
    top: float,
    plot_bottom: float,
    sx,
    sy,
) -> str:
    parts: list[str] = []
    for t in ticks:
        label = f"{t:.6g}"
        x = sx(t)
        y = sy(t)
        parts.append(f'  <line x1="{x:.3f}" y1="{top}" x2="{x:.3f}" y2="{plot_bottom}" stroke="#aaaaaa" stroke-width="0.8" stroke-opacity="0.3"/>')
        parts.append(f'  <line x1="{left}" y1="{y:.3f}" x2="{plot_right}" y2="{y:.3f}" stroke="#aaaaaa" stroke-width="0.8" stroke-opacity="0.3"/>')
        parts.append(f'  <line x1="{x:.3f}" y1="{plot_bottom}" x2="{x:.3f}" y2="{plot_bottom + 5}" stroke="black"/>')
        parts.append(f'  <text x="{x:.3f}" y="{plot_bottom + 17}" text-anchor="middle" font-family="sans-serif" font-size="11">{label}</text>')
        parts.append(f'  <line x1="{left - 5}" y1="{y:.3f}" x2="{left}" y2="{y:.3f}" stroke="black"/>')
        parts.append(f'  <text x="{left - 8}" y="{y + 4:.3f}" text-anchor="end" font-family="sans-serif" font-size="11">{label}</text>')
    return "\n".join(parts)


def _svg_zero_outside_label(
    axis_min: float,
    axis_max: float,
    left: float,
    plot_right: float,
    top: float,
    plot_bottom: float,
) -> str:
    """Render a small '0' label at the near axis edge when 0 is outside the plot range."""
    if axis_min <= 0.0 <= axis_max:
        return ""
    parts: list[str] = []
    if 0.0 < axis_min:
        parts.append(f'  <text x="{left}" y="{plot_bottom + 17}" text-anchor="middle" font-family="sans-serif" font-size="9">0</text>')
        parts.append(f'  <text x="{left - 8}" y="{plot_bottom + 4}" text-anchor="end" font-family="sans-serif" font-size="9">0</text>')
    else:
        parts.append(f'  <text x="{plot_right}" y="{plot_bottom + 17}" text-anchor="middle" font-family="sans-serif" font-size="9">0</text>')
        parts.append(f'  <text x="{left - 8}" y="{top + 4}" text-anchor="end" font-family="sans-serif" font-size="9">0</text>')
    return "\n".join(parts)


def _shared_axis_limits(rows: list[tuple[float, float, float, float]], channels: list[tuple[str, str, int]]) -> tuple[float, float]:
    values = [row[0] for row in rows]
    values.extend(row[row_index] for row in rows for _, _, row_index in channels)

    axis_min = min(values)
    axis_max = max(values)
    if axis_min == axis_max:
        axis_min -= 0.5
        axis_max += 0.5

    return axis_min, axis_max


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract sampled output channel curves from a 3D .cube LUT.")
    parser.add_argument("cube_file", help="Input .cube file.")
    parser.add_argument("--output", default="lut_curve.csv", help="Output CSV path.")
    parser.add_argument("--channel", choices=["r", "g", "b"], default="r", help="Input channel to use as the x axis.")
    parser.add_argument("--start", type=float, default=0.0, help="Start value for x axis, remapped with (876 * start + 64) / 1023.")
    parser.add_argument("--end", type=float, default=1.0, help="End value for x axis, remapped with (876 * end + 64) / 1023.")
    parser.add_argument("--samples", type=int, default=256, help="Number of sampled x values.")
    parser.add_argument("--plot", action="store_true", help="Show the output channel curves with matplotlib.")
    parser.add_argument("--plot-output", help="Save the output channel curves to an image path. Use .svg for no dependencies.")
    parser.add_argument(
        "--plot-single-channel",
        action="store_true",
        help="Plot only the output channel matching --channel instead of all output channels.",
    )
    parser.add_argument(
        "--fixed-rgb",
        type=float,
        nargs=3,
        default=(0.0, 0.0, 0.0),
        metavar=("R", "G", "B"),
        help="Input RGB values for the two channels that are not varied. Each value is remapped with (876 * value + 64) / 1023.",
    )
    args = parser.parse_args()

    lut = load_cube(args.cube_file)
    a = remap_input_value(args.start)
    b = remap_input_value(args.end)
    fixed_rgb = tuple(remap_input_value(value) for value in args.fixed_rgb)
    rows = list(channel_curve(lut, args.channel, a, b, args.samples, fixed_rgb))
    write_curve_csv(rows, args.output)
    if args.plot or args.plot_output:
        plot_curve(
            rows,
            args.channel,
            show=args.plot,
            output_path=args.plot_output,
            only_provided_channel=args.plot_single_channel,
            title=Path(args.cube_file).stem,
        )


if __name__ == "__main__":
    main()
