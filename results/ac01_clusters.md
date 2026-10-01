# AC-01: where the attentive-driver collisions are

The preventable collisions with an attentive driver in `estimate` (67 runs), each replayed from its stored seed; every replay reproduced the stored collision and takeover time. Recomputed by `scripts/ac01_clusters.py`.

| | Cut-in | Lead braking |
| --- | --- | --- |
| Collisions / attentive runs | 63 / 32,015 (0.197%) | 4 / 48,011 (0.008%) |
| Headway (s) | 0.30–0.73 (median 0.36) | 0.98–1.29 (median 1.16) |
| Initial gap (m) | 4.6–11.5 (median 7.6) | 23.0–44.5 (median 38.4) |
| Ego speed (m/s) | 15.0–27.7 (median 19.2) | 20.8–35.3 (median 34.6) |
| Severity | closing speed, m/s: 6.1–9.0 (median 8.3) | lead deceleration, m/s²: 7.5–8.5 (median 8.2) |
| Friction | 0.51–1.00 (median 0.81) | 0.71–0.86 (median 0.78) |
| BTN at hazard onset | 0.48–1.39 (median 0.78); above 1 in 8 | 0.46–0.62 (median 0.61); above 1 in 0 |
| Takeover request after hazard onset (s) | 0.00–0.00 (median 0.00) | 0.05–0.05 (median 0.05) |
| Reaction after the request (s) | 0.55–2.49 (median 1.31) | 2.98–3.72 (median 3.34) |
| Impact speed (m/s) | 0.0–6.0 (median 2.8) | 5.3–13.9 (median 9.8) |
| Box holding them (edges rounded outwards) | headway ≤ 0.74 s and closing_speed ≥ 6.0: 2.5% of attentive cut-in runs, collision rate inside 8.0% | headway ≤ 1.30 s and lead_decel ≥ 7.5: 0.3% of attentive lead braking runs, collision rate inside 2.6% |

BTN (brake threat number) is the deceleration needed to stop, or match speed, 2 m behind the target, divided by μg. It can exceed 1 in a preventable run because preventability asks whether 0.9 μg braking avoids contact, not a 2 m stand-off.
