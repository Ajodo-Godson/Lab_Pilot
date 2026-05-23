from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

SAR_LIMIT_FCC = 1.6

DEVICE_PRESETS: dict[str, dict[str, Any]] = {
    "handset": {
        "x_range": (-4, 4, 0.5),
        "y_range": (-8, 8, 0.5),
        "z_range": (0, 5, 1.0),
        "anomaly_center": (2.5, 4.4, 3.0),
        "z_depth": 5.0,
        "hotspot_sigma": 18.0,
        "hotspot_strength": 1.2,
    },
    "tablet": {
        "x_range": (-10, 10, 0.6),
        "y_range": (-14, 14, 0.6),
        "z_range": (0, 4, 1.0),
        "anomaly_center": (6.0, 8.0, 2.5),
        "z_depth": 4.0,
        "hotspot_sigma": 24.0,
        "hotspot_strength": 1.0,
    },
    "wearable": {
        "x_range": (-4, 4, 0.4),
        "y_range": (-4, 4, 0.4),
        "z_range": (0, 3, 0.8),
        "anomaly_center": (2.0, 2.0, 1.5),
        "z_depth": 3.0,
        "hotspot_sigma": 8.0,
        "hotspot_strength": 1.4,
    },
    "laptop": {
        "x_range": (-14, 14, 0.8),
        "y_range": (-10, 10, 0.8),
        "z_range": (0, 4, 1.0),
        "anomaly_center": (8.0, 6.0, 2.5),
        "z_depth": 4.0,
        "hotspot_sigma": 30.0,
        "hotspot_strength": 0.9,
    },
    "iot": {
        "x_range": (-5, 5, 0.5),
        "y_range": (-5, 5, 0.5),
        "z_range": (0, 4, 1.0),
        "anomaly_center": (3.0, 3.0, 2.0),
        "z_depth": 4.0,
        "hotspot_sigma": 12.0,
        "hotspot_strength": 1.1,
    },
    "speaker": {
        "x_range": (-6, 6, 0.5),
        "y_range": (-6, 6, 0.5),
        "z_range": (0, 5, 1.0),
        "anomaly_center": (4.0, 4.0, 3.0),
        "z_depth": 5.0,
        "hotspot_sigma": 16.0,
        "hotspot_strength": 1.0,
    },
}
DEVICE_PRESETS["gateway"] = DEVICE_PRESETS["speaker"]
DEVICE_PRESETS["other"] = DEVICE_PRESETS["handset"]

DEFAULT_PRESET = DEVICE_PRESETS["handset"]


def _get_preset(form_factor: str) -> dict[str, Any]:
    return DEVICE_PRESETS.get(form_factor, DEFAULT_PRESET)


def compute_sar(
    x: float,
    y: float,
    z: float,
    antenna_pos: tuple[float, float, float],
    freq_mhz: float,
    power_dbm: float,
    preset: dict[str, Any] | None = None,
) -> float:
    if preset is None:
        preset = DEFAULT_PRESET
    anomaly_center = preset["anomaly_center"]
    z_depth = preset["z_depth"]

    ax, ay, az = antenna_pos
    r = max(np.sqrt((x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2), 0.5)
    power_mw = 10 ** (power_dbm / 10)
    freq_factor = freq_mhz / 2400
    tissue_conductivity = 1.8

    base_sar = (power_mw * 0.008 * freq_factor * tissue_conductivity) / (2 * np.pi * r**2)

    surface_factor = 1.0 + 2.0 * (z / z_depth)

    dist_sq = (
        (x - anomaly_center[0]) ** 2
        + (y - anomaly_center[1]) ** 2
        + (z - anomaly_center[2]) ** 2
    )
    hotspot = preset["hotspot_strength"] * np.exp(-dist_sq / preset["hotspot_sigma"])

    sar = base_sar * surface_factor + hotspot
    return round(float(sar) * float(np.random.normal(1.0, 0.03)), 4)


async def stream_sar_grid(params: dict[str, Any], queue: asyncio.Queue) -> None:
    antenna_pos = (
        float(params.get("antenna_x", 0)),
        float(params.get("antenna_y", 1.5)),
        0.0,
    )
    freq = float(params.get("frequency_mhz", 2412))
    power = float(params.get("power_dbm", 20))
    form_factor = params.get("form_factor", "handset")
    preset = _get_preset(form_factor)
    anomaly_center = preset["anomaly_center"]
    summary: dict[str, Any] = {"peak_sar": 0, "anomaly_count": 0, "total_points": 0, "anomalies": []}

    x_lo, x_hi, x_step = preset["x_range"]
    y_lo, y_hi, y_step = preset["y_range"]
    z_lo, z_hi, z_step = preset["z_range"]
    xs = np.arange(x_lo, x_hi + x_step * 0.1, x_step)
    ys = np.arange(y_lo, y_hi + y_step * 0.1, y_step)
    zs = np.arange(z_lo, z_hi + z_step * 0.1, z_step)

    # Y-outer sweep: the anomaly at y≈4.4 is reached ~70 % through the scan
    # instead of 99 % (old X-outer order).  Good demo pacing — the heatmap
    # builds, the gradient becomes visible, then the climax fires.
    for yi in ys:
        for xi in xs:
            for zi in zs:
                sar = compute_sar(float(xi), float(yi), float(zi), antenna_pos, freq, power, preset)

                dist = np.sqrt(
                    (xi - anomaly_center[0]) ** 2
                    + (yi - anomaly_center[1]) ** 2
                    + (zi - anomaly_center[2]) ** 2
                )
                if dist < 1.2:
                    sar = round(float(np.random.uniform(1.44, 1.58)), 4)

                pct = round(sar / SAR_LIMIT_FCC, 4)
                point = {
                    "x": round(float(xi), 2),
                    "y": round(float(yi), 2),
                    "z": round(float(zi), 2),
                    "frequency_mhz": freq,
                    "power_dbm": power,
                    "sar_w_kg": sar,
                    "is_anomaly": pct > 0.90,
                    "pct_of_limit": pct,
                }

                summary["total_points"] += 1
                summary["peak_sar"] = max(summary["peak_sar"], sar)
                if point["is_anomaly"]:
                    summary["anomaly_count"] += 1
                    summary["anomalies"].append({"position": [point["x"], point["y"], point["z"]], "sar": sar})

                await queue.put({"event": "sar_point", "data": point})
                await asyncio.sleep(0.010)

    await queue.put({"event": "scan_complete", "data": summary})
