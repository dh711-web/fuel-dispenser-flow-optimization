"""
Time-of-day nozzle velocity optimization for a fuel dispenser.

The pump power curve P(u) is obtained from a hydraulic velocity sweep.
Fill time follows from continuity, T(u) = V_tank / (u * A_nozzle).
Lowering the nozzle velocity saves pump power but lengthens the fill,
so each time slot is solved as a weighted trade-off between the two,
subject to a hard limit on fill time.

Weight w is a congestion proxy for the slot: w -> 1 prioritises speed,
w -> 0 prioritises power.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------- constants

NOZZLE_DIAMETER = 0.017                              # m
NOZZLE_AREA = np.pi * NOZZLE_DIAMETER ** 2 / 4       # m^2
TANK_VOLUME = 0.05                                   # m^3 (50 L)
MAX_FILL_TIME = 600                                  # s (10 min)
CURRENT_VELOCITY = 2.385                             # m/s, as measured
PEAK_CONGESTION = 0.95                               # above this, hold current

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "data" / "pump_power_velocity_sweep.xlsx"
SHEET_NAME = "유속 스윕"
OUTPUT_FILE = ROOT / "results" / "schedule.csv"

# slot -> (congestion weight, electricity price [KRW/kWh], hours per day)
SCENARIOS = {
    "05-09 pre-morning": (0.21, 80, 4),
    "09-12 morning": (0.58, 130, 3),
    "12-14 midday": (0.37, 130, 2),
    "14-18 afternoon peak": (0.99, 190, 4),
    "18-23 evening": (0.79, 130, 5),
    "23-05 overnight": (0.01, 80, 6),
}


# ------------------------------------------------------------------ helpers

def minimum_velocity() -> float:
    """Lowest nozzle velocity that still meets the fill-time limit."""
    return (TANK_VOLUME / MAX_FILL_TIME) / NOZZLE_AREA


def load_sweep(path: Path = DATA_FILE) -> pd.DataFrame:
    """Load the velocity sweep and keep only feasible operating points."""
    raw = pd.read_excel(path, sheet_name=SHEET_NAME, header=0)

    df = pd.DataFrame({
        "velocity": raw["노즐유속 u_n"].astype(float),
        "power": raw["P (W)"].astype(float),
    })
    df["fill_time"] = TANK_VOLUME / (df["velocity"] * NOZZLE_AREA)

    df = df[df["velocity"] >= minimum_velocity()]
    df = df.sort_values("velocity").reset_index(drop=True)

    for col in ("power", "fill_time"):
        lo, hi = df[col].min(), df[col].max()
        df[f"{col}_norm"] = (df[col] - lo) / (hi - lo)

    return df


def optimal_velocity(df: pd.DataFrame, weight: float) -> float:
    """Minimise weight * normalised fill time + (1 - weight) * normalised power.

    The feasible set is the sweep grid itself, so the minimum is found
    directly. No surrogate is needed: evaluating the objective over the
    whole grid costs one vectorised operation.
    """
    cost = weight * df["fill_time_norm"] + (1 - weight) * df["power_norm"]
    return float(df.loc[cost.idxmin(), "velocity"])


def apply_operating_rules(velocity: float, weight: float) -> tuple[float, str]:
    """Constrain the optimiser output to what the site would actually run."""
    if weight >= PEAK_CONGESTION:
        return CURRENT_VELOCITY, "hold (peak, throughput priority)"
    if velocity >= CURRENT_VELOCITY:
        return CURRENT_VELOCITY, "hold (already optimal)"
    return velocity, f"reduce by {CURRENT_VELOCITY - velocity:.3f} m/s"


# --------------------------------------------------------------------- main

def build_schedule(df: pd.DataFrame) -> pd.DataFrame:
    """Solve every time slot and tabulate the resulting operating schedule."""
    baseline_power = float(np.interp(CURRENT_VELOCITY, df["velocity"], df["power"]))
    rows = []

    for slot, (weight, price, hours) in SCENARIOS.items():
        velocity, action = apply_operating_rules(optimal_velocity(df, weight), weight)

        power = float(np.interp(velocity, df["velocity"], df["power"]))
        fill_time = TANK_VOLUME / (velocity * NOZZLE_AREA)
        saved_w = baseline_power - power

        rows.append({
            "slot": slot,
            "congestion_w": weight,
            "velocity_m_s": round(velocity, 3),
            "fill_time_s": round(fill_time, 1),
            "power_w": round(power, 2),
            "power_saved_w": round(saved_w, 2),
            "monthly_saving_krw": round(saved_w / 1000 * hours * 30 * price),
            "action": action,
        })

    return pd.DataFrame(rows)


def main() -> None:
    df = load_sweep()
    print(f"fill-time limit {MAX_FILL_TIME} s -> minimum velocity "
          f"{minimum_velocity():.4f} m/s")
    print(f"feasible operating points: {len(df)} "
          f"({df['velocity'].min():.3f}-{df['velocity'].max():.3f} m/s)\n")

    schedule = build_schedule(df)
    print(schedule.to_string(index=False))

    monthly = schedule["monthly_saving_krw"].sum()
    print(f"\nmonthly saving, one site : {monthly:>12,.0f} KRW")
    print(f"annual saving, one site  : {monthly * 12:>12,.0f} KRW")

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    schedule.to_csv(OUTPUT_FILE, index=False)
    print(f"\nwritten to {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
