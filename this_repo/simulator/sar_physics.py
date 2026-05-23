from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

SAR_LIMIT_FCC = 1.6
ANOMALY_CENTER = (8.2, 4.4, 3.0)


def compute_sar(
    x: float,
    y: float,
    z: float,
    antenna_pos: tuple[float, float, float],
    freq_mhz: float,
    power_dbm: float,
) -> float:
    ax, ay, az = antenna_pos
    r = max(np.sqrt((x - ax) ** 2 + (y - ay) ** 2 + (z - az) ** 2), 0.5)
    power_mw = 10 ** (power_dbm / 10)
    freq_factor = freq_mhz / 2400
    tissue_conductivity = 1.8

    # Base SAR from inverse-square law (scaled 8x from V4 for a visible heatmap)
    base_sar = (power_mw * 0.008 * freq_factor * tissue_conductivity) / (2 * np.pi * r**2)

    # Surface proximity: SAR concentrates nearer to the body surface (higher z)
    surface_factor = 1.0 + 2.0 * (z / 5.0)

    # Gaussian hotspot centered on the anomaly cluster — creates a natural
    # color gradient that ramps from blue → teal → amber before the planted
    # anomaly pushes into crimson.  Sigma chosen so the warm zone is visible
    # from ~6 cm away.
    dist_sq = (x - ANOMALY_CENTER[0]) ** 2 + (y - ANOMALY_CENTER[1]) ** 2 + (z - ANOMALY_CENTER[2]) ** 2
    hotspot = 1.2 * np.exp(-dist_sq / 18.0)

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
    summary: dict[str, Any] = {"peak_sar": 0, "anomaly_count": 0, "total_points": 0, "anomalies": []}

    xs = np.arange(-8, 8.1, 0.5)
    ys = np.arange(-10, 10.1, 0.5)
    zs = np.arange(0, 5.1, 1.0)

    # Y-outer sweep: the anomaly at y≈4.4 is reached ~70 % through the scan
    # instead of 99 % (old X-outer order).  Good demo pacing — the heatmap
    # builds, the gradient becomes visible, then the climax fires.
    for yi in ys:
        for xi in xs:
            for zi in zs:
                sar = compute_sar(float(xi), float(yi), float(zi), antenna_pos, freq, power)

                # Planted anomaly — spherical injection zone (r < 1.2 from center)
                dist = np.sqrt(
                    (xi - ANOMALY_CENTER[0]) ** 2
                    + (yi - ANOMALY_CENTER[1]) ** 2
                    + (zi - ANOMALY_CENTER[2]) ** 2
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
