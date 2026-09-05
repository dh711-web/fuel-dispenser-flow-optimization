# Fuel Dispenser Flow Optimization

Time-of-day operating schedule for fuel dispenser nozzles, trading pump power
against fill time under a hard fill-time constraint. No capital expenditure —
only the velocity setpoint changes.

## Problem

A dispenser nozzle is normally run at one fixed velocity — 2.385 m/s at the
site measured here — regardless of how busy the station is. Pump power rises
steeply with nozzle velocity, so running at peak-hour speed through the night
wastes energy for no benefit.

Two objectives conflict:

- **Pump power** `P(u)`, from a hydraulic sweep of the piping network
  (Darcy–Weisbach friction across each pipe segment plus nozzle contraction,
  velocity head and static head)
- **Fill time** `T(u) = V_tank / (u · A_nozzle)`, from continuity

subject to a 50 L fill finishing within 600 s, which fixes the lower bound on
nozzle velocity at **0.367 m/s**.

`P` is the total pump power with **four dispensers running simultaneously**,
all at the same nozzle velocity. Fill time is per nozzle. Both therefore
describe the same operating scenario.

## Approach

1. Take the pump power curve from the velocity sweep and discard operating
   points that violate the fill-time limit — 41 of 48 points remain,
   spanning 0.400–2.400 m/s.
2. Min-max normalise power and fill time so they trade off directly.
3. For each time slot, minimise `w·T_norm + (1−w)·P_norm` over the feasible
   grid, where `w` is a congestion weight for that slot.
4. Apply two operating rules: hold current velocity during the peak slot
   (throughput takes priority), and never raise velocity above the current
   setting.
5. Convert the power saving to cost using the time-of-use tariff and the
   operating hours of each slot.

The objective is evaluated over the whole feasible grid in one vectorised
operation, so the optimum is found directly. A surrogate model was considered
and dropped: with a single input and 41 candidate points, approximating the
objective costs more than evaluating it.

## Results

| Time slot | w | Tariff (KRW/kWh) | Velocity (m/s) | Fill time (s) | Pump power (W) | Saved (W) | Monthly saving (KRW) |
|---|---|---|---|---|---|---|---|
| 05–09 pre-morning | 0.21 | 80 | 0.500 | 440.6 | 91.76 | 373.52 | 3,586 |
| 09–12 morning | 0.58 | 130 | 1.150 | 191.6 | 213.90 | 251.38 | 2,941 |
| 12–14 midday | 0.37 | 130 | 0.750 | 293.7 | 138.21 | 327.07 | 2,551 |
| 14–18 afternoon peak | 0.99 | 190 | 2.385 | 92.4 | 465.28 | 0.00 | 0 |
| 18–23 evening | 0.79 | 130 | 1.850 | 119.1 | 352.37 | 112.91 | 2,202 |
| 23–05 overnight | 0.01 | 80 | 0.400 | 550.7 | 73.32 | 391.96 | 5,644 |

**Annual saving, one site: 203,088 KRW**

The peak slot contributes nothing by design — congestion above the 0.95
threshold pins velocity at its current setting, so throughput is never traded
away when the station is busy. The overnight slot contributes the most, not
because the tariff is high (it is the lowest, at 80 KRW/kWh) but because it
runs six hours a day at the largest velocity reduction.

The absolute figure is modest, but it comes with **zero capital cost**: no
pump, pipe or nozzle is replaced, only the velocity setpoint schedule. There
is no payback period to recover.

## Limitations

- **The largest saving carries the longest wait.** The overnight slot fills in
  550.7 s against a 600 s limit — a customer at 3 a.m. waits over nine
  minutes. The constraint is met, but the schedule sits close to its worst
  permitted service level exactly where it saves the most.
- **`w` is a proxy, not a measurement.** It comes from district transaction-share
  data, min-max normalised, with the two extreme slots clipped to 0.01 and
  0.99 rather than 0 and 1 — so the endpoints are set by hand. A queue-length
  or dwell-time measurement would be the correct input.
- **Single-site geometry.** The power curve reflects one station's piping
  layout. Extending these savings to other stations, or scaling to a national
  figure, would require repeating the sweep per site.
- **Full-tank assumption.** Fill time assumes a complete 50 L fill. Partial
  fills shorten it and widen the feasible velocity range.

## Repository

```
src/optimize_flow.py   objective, constraint handling, schedule generation
data/                  velocity sweep (xlsx)
results/schedule.csv   generated operating schedule
```

## Run

```bash
pip install -r requirements.txt
python src/optimize_flow.py
```
