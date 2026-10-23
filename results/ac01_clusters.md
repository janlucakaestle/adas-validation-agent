# AC-01 events in `estimate` (discovery data)

69 collisions with an attentive driver in scenarios avoidable by the ideal reference, each replayed and reproduced exactly. Release `fe59625d94287538…`. The boxes below are derived from this campaign and are NOT validated by it; see the hold-out report.

## cut_in: 61 collisions

- headway 0.30–0.60 (median 0.36) s; closing_speed 6.0–9.0 (median 8.3)
- ego speed 15.0–33.6 (median 20.1) m/s; friction 0.52–1.00 (median 0.81)
- BTN at hazard onset 0.50–1.22 (median 0.73); above 1 in 7
- TOR after hazard onset 0.00–0.00 (median 0.00) s; takeover time 0.86–2.94 (median 1.46) s
- box (edges rounded outwards): `scenario = 'cut_in' AND headway <= 0.60 AND closing_speed >= 5.9`

## lead_brake: 8 collisions

- headway 0.84–1.65 (median 1.24) s; lead_decel 7.4–8.9 (median 8.6)
- ego speed 23.4–35.2 (median 31.2) m/s; friction 0.68–0.96 (median 0.83)
- BTN at hazard onset 0.48–0.60 (median 0.54); above 1 in 0
- TOR after hazard onset 0.00–0.00 (median 0.00) s; takeover time 2.10–3.70 (median 3.18) s
- box (edges rounded outwards): `scenario = 'lead_brake' AND headway <= 1.65 AND lead_decel >= 7.4`
