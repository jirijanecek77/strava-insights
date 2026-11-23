# Athlete Training Insights

Terms for interpreting completed training and generating coaching and running forecasts. These definitions record the current product language in [the specification](docs/specification.md); changes are recorded as the design interview settles them.

## Language

**Recorded activity**:
A completed running, cycling or e-bike session imported from the athlete's activity history. A future planned workout is not a recorded activity.

**Activity facts**:
Measurements and qualified numerical evidence describing a completed activity, including volume, intensity and the limitations of available observations.

**Activity coaching note**:
An interpretation of a completed activity containing a description, a short analytic summary and recommendations grounded in the available training evidence.
_Avoid_: Activity summary when referring to the entire note.

**Activity coaching summary**:
The short analytic conclusion of an activity coaching note, reused when evaluating surrounding training. It is distinct from the activity's numerical statistics and its full description.
_Avoid_: Activity summary without qualifying whether it means prose or numerical statistics.

**Activity evaluation**:
A coherent result pairing an activity's numerical facts with its successful short coaching interpretation. A change to available facts does not by itself make an older interpretation current.

**Period review**:
An evaluation of a calendar week or calendar month using available saved evaluations from the shorter periods it contains, with incomplete evidence explicitly recognized.

**Running forecast**:
A proposed sequence of running and rest days for the seven requested future dates, informed by completed training and current thresholds. Previously published forecasts are separate from completed training.
_Avoid_: Completed training when referring to planned workouts.

**Weekly objective**:
A build, maintain or recover goal with a reason and supported weekly volume, running frequency and long-run expectations for a running forecast.
