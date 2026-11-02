# Attendance Radar

A paper register tells you who was absent. Attendance Radar tells you who is drifting away, soon enough to do something about it. It runs offline, and takes about a minute a day.

```
python -m attendance_radar
```

Then open http://127.0.0.1:8030. It needs Python 3.10 or newer.

## What it notices

Each learner gets a level with reasons a teacher can act on:

- **Absent right now:** three or more school days in a row, the moment to call home
- **Chronic absence:** missing 10% or more of school days, a widely used warning line
- **A sudden fall:** the last two weeks far below the learner's usual level
- **A pattern:** absent most Wednesdays, which can point to market day, work or care duties
- **Lateness:** late on a quarter of days or more

Excused days do not count against anyone, so a learner with a documented illness is not flagged.

For the class, it shows overall attendance and unusual days when many were away, such as after a flood.

## How to read it

A flag starts a conversation, and it is not a judgement. Absence often has causes outside a learner's control, such as work, caring for family, safety or illness, and the reasons listed say what the numbers show, not why. Please handle these records with care: they are personal data about children.

## How it is tested

Rates, streaks and patterns are tested on hand-built registers using a Sunday to Thursday school week. Risk rules are tested at their boundaries, including excused illness, which must stay low. App tests cover corrections to a past day, future dates, and an invalid status that must save nothing.

## Limits

It does not contact families. The thresholds are sensible defaults, not validated for any one community. A learner with fewer than five recorded days shows as unknown. There are no logins, so keep the computer and the data file private.

## Tests

```
python -m unittest discover -s tests
```

MIT licence.
