# Domain notes: claims to verify

These facts came from outside research (an AI-generated report and the sources it cited). **None are
verified yet.** The agent may state a fact as true only once it's marked ✅ here with a primary source;
otherwise it must say "reportedly" or leave it out. Verified friction facts become entries in
`data/constraints.yaml` (Step 2).

Status: ⬜ unverified · ✅ verified (source linked) · ✏️ corrected · ❌ dropped

| # | Claim | Used for | First look | Primary source to check | Status |
|---|---|---|---|---|---|
| 1 | The Passenger Facility Charge (PFC) is capped at **$4.50** per enplanement, and its revenue may only fund FAA-approved projects (safety, noise, capacity, including terminals) | PFC capacity figure | Long-standing and well known | FAA PFC Program page | ⬜ |
| 2 | **SNA** passenger cap under the 1985 settlement as amended: **11.8M** annual passengers through 2025, **12.5M** for 2026–2030, and the agreement ends **31 Dec 2030** | Friction (SNA) | Consistent with the amended agreement as I recall it | Orange County / John Wayne Airport settlement agreement page | ⬜ |
| 3 | **SNA curfew**: no commercial departures roughly 10 pm to 7 am | Friction (SNA) | Plausible; check exact hours and Sunday rules | John Wayne Airport noise/access plan | ⬜ |
| 4 | **LAX** handles **87.5M** passengers a year | Comparison text | Likely the 2019 peak; recent years are lower | LAWA annual traffic stats (latest year) | ⬜ |
| 5 | About **9.9M** LAX travellers start or end in Orange County | LAX vs SNA "why" | Weak sources (travel/shuttle blogs) | SCAG regional aviation study, or drop | ⬜ |
| 6 | **SFO** runways 28L/28R are **750 ft** apart, so in fog (instrument conditions) only one can land at a time, roughly halving arrival capacity | SFO "why" | Widely cited | FAA Airport Capacity Profile for SFO | ⬜ |
| 7 | SFO can't widen the runway gap without **bay fill**, which BCDC regulates under the McAteer-Petris Act; past runway plans stalled (incl. a 15:1 wetlands-swap offer) | Friction (SFO) | Plausible history (late-1990s/2000s runway plan) | BCDC Bay Plan; SFO runway reconfiguration history | ⬜ |
| 8 | About **80%** of trans-Pacific cargo flights stop at **ANC**; ANC is a top-5 cargo airport worldwide | ANC "why" | Widely repeated; the exact % varies by source | ANC press releases, ACI cargo rankings | ⬜ |
| 9 | ANC passenger traffic is about **5M** a year, mostly domestic and intra-Alaska | ANC answer | Plausible | ANC annual statistics | ⬜ |
| 10 | BTS on-time data runs about **2 months** behind | Uncertainty note | Matches what we saw (latest file 2026-07 on 2026-10-11) | Observed directly | ⬜ |

## Notes on the research report
- **Adopted:** the Strain + Growth − Friction structure; NAS-delay share as the strain signal; friction
  as an explicit, sourced input.
- **Not adopted:**
  - Code execution per question (undercuts determinism; see PLAN Step 5).
  - ASPM (login-gated, down when checked).
  - TAF as a live source (no data download found).
  - OpenAI Whisper by default (second vendor; still an option at Step 6).
