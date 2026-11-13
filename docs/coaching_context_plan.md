# Activity, Weekly, and Monthly Coaching Context Plan

Status: implemented with local deterministic evidence, versioned prompts, stored period metrics, and operator commands.
Live provider verification has not been run; existing text is preserved. Requirements are defined in
[specification.md](specification.md#ai-coaching). Delivery tracking belongs in
[implementation_plan.md](implementation_plan.md#coaching-context-and-period-comparisons).

## Original Gap

`worker/app/services/coaching/context_builder.py` sends recorded Garmin laps to activity coaching. Period contexts
contain activity KPIs, ready activity summaries, and current/previous totals by sport. They previously did not contain absolute
threshold-band time/distance or comparable endurance/tempo evidence. The previous source hash also omitted previous-period
inputs. `metrics.py` previously put exactly AnT into the middle band, contrary to the specified boundary. The implementation
now includes absolute evidence, complete context hashing, and the specified boundary without deleting existing notes.

## Data Flow and Contracts

| Stage | Local inputs | Reusable output | Model input and output |
| --- | --- | --- | --- |
| Activity facts | Activity KPIs, stored streams, dated thresholds, stored recorded laps, route matches | Versioned numeric evidence per activity, independent of AI availability | No model call for facts |
| Activity coaching | Activity facts, recorded laps, bounded recent comparable evidence | Existing description, short summary, recommendation; optional structured interpretation with evidence references | Laps supplied here once; model interprets facts and never calculates authoritative totals |
| Weekly review | Facts for every activity in the week and previous week; available short activity interpretations | Exact sport/band totals, changes, coverage, key-session evidence; stored summary/recommendation | Compact period facts and activity digests; no laps or streams |
| Monthly review | Facts for every activity in the month and previous month; compact comparable-session groups; available short interpretations | Exact distance comparisons and evidence-based endurance/tempo assessment; stored summary/recommendation | Compact month facts and a bounded set of representative sessions; no full lap arrays or activity descriptions |

Month facts aggregate activities directly. Weeks crossing month boundaries must never contribute activities outside
the month. Weekly prose can be optional supporting context later; monthly generation must not depend on weekly AI
success or sum rounded weekly numbers. Facts remain usable for historical activities with no coaching note.

## 1. Deterministic Activity Evidence

Persist one application-owned evidence record per activity when preparing its context or a dependent period context,
with additive migration `20261113_0025`. The resumable CLI can populate older activities without generating notes. Keep numerical facts
separate from model narrative so model failure, editing, or a missing note cannot remove an activity from totals.
Use schema/calculation versions and a source fingerprint covering activity metrics, relevant stored stream and lap
content, and the threshold snapshot resolved by activity local date. Use batch reads for period assembly.

Illustrative compact contract (numeric units remain explicit):

```json
{
  "schema_version": 1,
  "activity_id": 1455,
  "sport": "Run",
  "date": "2026-11-12",
  "route_group_id": null,
  "threshold_snapshot": {
    "effective_from": "2026-10-01",
    "aet_hr_bpm": 145,
    "ant_hr_bpm": 165
  },
  "volume": {
    "distance_m": 10000,
    "moving_time_s": 3600
  },
  "hr_bands": {
    "bands": {
      "below_aet": {
        "time_s": 2400,
        "distance_m": 6400
      },
      "between_aet_ant": {
        "time_s": 1000,
        "distance_m": 2900
      },
      "above_ant": {
        "time_s": 200,
        "distance_m": 700
      }
    },
    "coverage": {
      "classified_time_s": 3600,
      "classified_distance_m": 10000,
      "unknown_time_s": 0,
      "unknown_distance_m": 0
    },
    "limitations": []
  },
  "terrain": {
    "total_ascent_m": 60,
    "laps": [],
    "finish": {
      "start_distance_m": 8000,
      "end_distance_m": 10000,
      "coverage_fraction": 0,
      "ascent_m": null,
      "descent_m": null,
      "net_grade_pct": null
    },
    "limitation": "Terrain coverage unavailable in this illustrative example."
  },
  "candidates": {
    "endurance": [
      {
        "lap_range": [
          1,
          6
        ],
        "duration_s": 2400,
        "distance_m": 6400,
        "pace_s_per_km": 375,
        "hr_bpm": 138,
        "decoupling_pct": null,
        "net_grade_pct": null,
        "ascent_m_per_km": null,
        "limitations": [
          "Lap averages cannot establish within-lap effort or workout intent."
        ]
      }
    ],
    "tempo": []
  }
}
```

This is illustrative data, not an actual activity. Candidate lists are empty when no eligible segments exist;
terrain/drift metrics are nullable; a whole-run average is not a substitute for a steady or tempo block.

### Threshold time and distance

- Use HR to define the requested physiological bands: HR < AeT; AeT <= HR < AnT; HR >= AnT. Keep any future pace-band
  analysis separately labelled. Standardize the existing coaching helper's boundary and band naming.
- Require valid ordered HR thresholds, 0 < AeT < AnT. Resolve them for each activity date; never apply today's
  thresholds indiscriminately to historical activities. Include threshold provenance and flag changed definitions
  in comparisons. Running is the primary improvement scope; preserve separate sport totals and identify use of
  configured HR thresholds for cycling. Do not mix e-bike speed with running fitness evidence.
- Calculate duration and cumulative-distance deltas from aligned local samples. Define the convention explicitly:
  the valid ending sample HR classifies its preceding interval. Do not interpolate a supposed exact crossing.
- Exclude stopped intervals where reliable moving/timer information exists, reject non-increasing time, invalid HR,
  distance resets, non-finite values, and long gaps (initial maximum 60 seconds, matching existing coaching logic).
  Keep distance and time coverage independently: valid HR/time may classify time even when distance is unavailable.
- Record classified amounts, unknown amounts relative to activity moving totals, coverage, and reconciliation
  limitations. Never silently rescale measured bands to activity totals. Investigate excess measured totals and
  flag inconsistent streams rather than manufacture a negative unknown value.
- No valid HR/thresholds means unavailable, not three zero bands. HR coverage without distance supports time only.
  Aggregate missing and partial activities explicitly. Percentages use classified coverage as denominator and
  never replace the requested absolute totals.
- Recorded lap averages remain useful for pacing evidence, but must not be used as exact HR-band allocation.
  Missing streams leave exact totals unavailable; do not fetch remote data or invent stream-derived replacement laps.

### Endurance and tempo evidence

Extract compact candidates locally from chronological recorded laps, weighting by duration/distance and preserving
work/recovery separation. Do not discard short recovery laps from session interpretation. Store candidate identifiers,
source lap ranges, duration/distance, weighted HR, pace, terrain, and applicable limitations, rather than copying
all laps into period contexts. Selection rules and eligibility minima are versioned and tested.

Endurance evidence includes sustained easy/steady running duration and distance, pace at comparable HR, and valid
steady-effort decoupling. Whole-session decoupling on intervals is not endurance improvement evidence. Tempo means
sustained running work between AeT and AnT for this comparison; above-AnT repetitions stay separately identified.
Compare work-block pace at similar HR and the duration/distance sustained, excluding recoveries from work averages.
A recorded lap label or average HR alone is insufficient to identify a deliberate tempo workout.

Compare like sessions by sport, similar HR (initial tolerance +/-5 bpm), workout pattern, block duration (initial
+/-20%), and route when available. These are transparent matching tolerances, not physiological guarantees. Prefer
same-route evidence and report unobserved terrain/weather differences as limitations. Select up to three matched
pairs per evidence type, stratified across the period rather than simply taking the fastest sessions. Require at
least two independent matched pairs for a period improvement/stability/decline assessment; one pair is a tentative
observation, none is insufficient data. The implementation uses minimum steady/easy blocks of 20 minutes and tempo blocks of eight minutes, at most 10% lap
pace spread and 10 bpm lap-HR spread, excluding warmup, cooldown, rest, and recovery laps. Terrain matching requires
available net grade within one percentage point and ascent per km within 10 m, or a matched route/lap range when
terrain is missing. Drift is included only for a continuous, HR-complete, terrain-covered endurance block.
Keep reviewing these conservative rules against stored sessions as more recorded laps arrive.

Faster pace at comparable HR, longer sustained effort at comparable intensity, and lower drift in comparable steady
runs can support improvement. Increased volume alone does not establish improved endurance; faster whole-run average
pace or increased HR does not establish tempo improvement. Return evidence counts, observed changes, comparability
limitations, and `improving`, `stable`, `declining`, or `insufficient_data`. Do not automatically edit AeT/AnT settings.

## 2. Activity AI Contract

Activity prose must interpret the session rather than repeat the distance, duration, average pace/HR, elevation gain,
or other KPIs already displayed above it. Explain execution, effort, fatigue evidence, and implications for training.
Use a specific comparison number only when needed to explain a finding; do not require a KPI recap or numbers in
every paragraph. Keep reusable numeric evidence in the structured facts, not embedded redundantly in the prose.

Always include available activity-level elevation gain in model input (the current context already includes
`elevation_gain_m`). Total ascent alone cannot locate a hill at the end. Add compact terrain evidence calculated
locally from stored altitude/distance data: ascent, descent, and average grade aligned to recorded lap boundaries,
plus a final-section aggregate (last 20% of distance, with its distance range). Mark missing/partial altitude coverage
and avoid treating missing elevation as flat terrain. Smooth/reject noisy altitude changes with versioned local rules;
do not send coordinates, raw altitude samples, or an elevation profile. Terrain aggregates contextualize recorded
laps and do not replace them with invented splits.

Interpret late slowing alongside the supplied terrain evidence. An uphill finish can explain slower pace or higher
HR; do not label it fatigue from those changes alone. When only total ascent is available, acknowledge that the hill's
location is unknown and withhold a definitive fatigue claim. Terrain can confound a comparison; it does not prove
that fatigue is absent. Carry relevant terrain evidence/limitations into the compact endurance/tempo comparison
records so weekly and monthly reviews do not repeat an unsupported fatigue interpretation.

Keep the existing three text fields and short summary. Supply facts plus recorded laps, recent compact evidence,
thresholds, and existing route/best-effort context. Structured AI interpretation is optional follow-up work; if added, make it an additive,
validated field containing session type, execution/fatigue signals, uncertainty, and references to supplied evidence
IDs. The model may classify an ambiguous session but cannot overwrite deterministic numbers. Legacy ready notes
remain valid without structured interpretation. Periods can use facts with the legacy short summary.

## 3. Weekly AI Contract

Compute all sport totals and all three HR-band totals locally for the current and prior week. Send running evidence,
short activity digests, rest/training days, coverage, and prior-week deltas. Include all activities regardless of note
availability. Require the review to explicitly state time and distance in each available band, with sport scope,
then interpret training balance, execution, fatigue, and changes. Show unavailable values honestly.

Keep `summary` and `recommendation` as the external response fields. Increase the present 50-100-word summary allowance
to approximately 120-180 words so the required band figures do not crowd out analysis. Format seconds as h:mm:ss and
meters as km only at presentation/prompt assembly; sum unrounded values first. Include a compact deterministic band
table in the stored/read review payload and UI so exact figures remain available independently of narrative quality.

## 4. Monthly AI Contract

Include total distance by sport, running distance in each HR band, current/previous month absolute and percentage
changes, band time totals, coverage, running frequency, longest eligible endurance efforts, and the matched endurance
and tempo evidence described above. No prior distance means a percentage change is unavailable, not infinity.

For an unfinished month, compare month-to-date with the same elapsed calendar days of the previous month (clamped to
its length), state the exact windows, and label unequal exposure when the previous month has fewer days. Supply full
previous-month totals separately for context. Use the same rule for an unfinished week versus prior week-to-date;
never call partial/full volume differences a decline without qualifying the exposure.

Require approximately 150-220 words covering distance changes, endurance findings, tempo findings, and limitations,
plus next-period recommendations. Distinguish observed training exposure from supported performance improvement.
Use explicit insufficient-data wording when comparable sessions are missing. Cap the representative evidence and
short interpretations; do not send every lap or duplicate all weekly/activity prose.

## Generation, Invalidation, and Rollout

1. Use additive evidence storage and nullable review metric fields. Existing text remains readable; no data reset.
2. Calculate or refresh evidence while preparing activity and period contexts, before model calls and period input
   hashing. Source fingerprints detect relevant local-data changes. Provide a bounded,
   resumable local-only command to populate existing evidence, including prior comparison periods. This does not fetch
   Garmin splits, queue historical activity notes, or consume AI calls.
3. Version activity, weekly, monthly prompts and numerical calculation contracts independently. Keep monthly and weekly
   facts independent of AI readiness; retain the existing ready-note eligibility and pending-note wait rules for reviews.
   Failed/missing notes contribute facts and explicit missing-interpretation coverage without blocking forever.
4. Hash the complete canonical bounded review context, including current and previous-period facts, threshold and
   evidence versions, selected comparisons, available summaries, and in-progress/final state. The planner must also
   revisit dependent later periods when earlier evidence changes. Updating previous-period data must refresh reviews
   that reference it even if their own activity rows are unchanged. Plan after local evidence is ready.
5. Keep existing ready text visible during regeneration. Preserve existing rows on deployment; use an explicit bounded
   operator regeneration for historical reviews, rather than mass AI regeneration merely from a version bump. Subsequent
   eligible updates and finalization use the new contracts. Keep retries, leases, budgets, and failure handling intact.
6. Measure serialized input tokens (provider tokenizer if available; clearly labelled estimate otherwise), before/after
   context bytes, and completion usage on representative short/long weeks and months. Do not promise a fixed saving
   before measuring. Require period payloads to exclude lap arrays, stream samples, and long activity descriptions.

## Validation and Acceptance

- Unit-test exact AeT/AnT equality, pauses/gaps, missing HR/distance, invalid thresholds, threshold-date changes,
  non-finite samples, distance resets, and partial coverage. Assert classified totals reconcile with their measured
  coverage and never silently fill unknown data.
- Verify exact weekly/monthly aggregation across sports, month boundaries, notes absent/failed, prior zero volume,
  partial periods, and weeks overlapping months. Verify rounded weekly values are never used to build month totals.
- Test endurance/tempo comparison selection on steady runs, intervals/recoveries, unequal laps, changing thresholds,
  unmatched routes/intensities, uphill finishes, missing/noisy altitude, and insufficient matched pairs. No unsupported positive fitness claim may be required.
- Test source invalidation when prior-period evidence changes; prompt/schema compatibility; retry behavior; bounded
  historical regeneration; and storage/read compatibility with existing ready notes/reviews.
- Verify activity prompts request interpretation without a KPI recap, retain total elevation gain, include compact
  terrain evidence when available, and qualify late slowing when terrain evidence is missing or indicates a climb.
- Snapshot representative provider contexts for all three summaries. Assert absolute band totals and comparison
  evidence exist in period prompts, while raw samples and lap arrays are absent.
- Run relevant worker/backend/frontend tests, `make build`, and `make test` using the documented Docker workflow.
  Recreate affected services, apply the migration, and verify stored activity evidence, a weekly review with three
  band totals, and monthly distance/endurance/tempo findings through local API/UI reads. Normal reads must never
  contact Garmin or the model. Record validation before checking delivery tasks complete.

## Implemented Storage and Operational Details

- `activity_coaching_evidence` stores a source fingerprint and versioned facts; `period_coaching_summaries.metrics`
  stores the deterministic context alongside successful generated text, excluding activity digests. Both worker and
  backend mappings support the additive schema. Provider payloads round numbers to three decimal places; stored
  activity facts retain calculation precision. Activity text remains the existing three-field response.
- Weekly/monthly contexts contain at most 30/12 activity digests spread chronologically, while totals cover every
  activity. Performance comparisons contain up to three independent pairs per evidence type. At least two pairs
  are required: median pace improvement of at least 2%, or for endurance at most 1% slower pace alongside at least
  10% more sustained duration or a drift reduction of two percentage points, supports improvement. Pace slowing
  of at least 2% supports decline; otherwise the matched evidence is stable. These are descriptive rules, not a
  physiological diagnosis. Threshold snapshots must match for eligible pairs.
- The frontend displays measured time/distance by sport and band, unknown coverage, threshold-definition changes,
  and inconsistent stream totals. Missing bands stay unavailable. Source time may differ slightly from Garmin's
  moving-time KPI; evidence records the discrepancy and never rescales measured intervals.
- New prompts are activity version 4 and period version 3. Existing ready legacy reviews remain until explicit
  regeneration, a newer activity note, or period finalization. Pending/generating activity notes defer a review;
  failed/missing notes contribute facts without blocking. Existing activity notes are not mass-regenerated.
- Local sampled contexts for user 1 on 2026-11-13 were about 4.7 KB for the current three-activity week and 7.9 KB for
  the nine-activity month (rough estimates 1,200/2,000 input tokens, excluding system prompts). No period laps or raw
  streams were included. This is measured context size, not a claimed percentage saving or provider token count.
- CLI usage and deployment order are documented in [development.md](development.md#coaching-evidence-and-period-reviews).

Validation on 2026-11-13: additive migration applied; `make build`, frontend production build, and `make test`
passed (37 backend, 183 worker, 67 frontend tests). A scripted model exercises persistence and regeneration inside
isolated PostgreSQL test schemas. Recreated the affected local services and checked stored-review reads, backend
health, and local evidence/context preparation. Live provider generation was blocked by automatic approval review
because it would disclose private health-derived context and replace existing reviews without explicit authorization;
no live generation or review replacement occurred during this change. The automatic planner retains its existing
70-day eligible-note window; use the bounded operator command for older historical review updates.
