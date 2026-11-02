"""Attendance logic: find learners drifting away early, while a teacher can still help.

Records are (date, status), where status is P (present), A (absent), L (late) or E (excused).
Excused days do not count against a learner, and late counts as present but is watched.
"""
from collections import Counter
from datetime import date, timedelta

STATUSES = ("P", "A", "L", "E")
CHRONIC = 0.10              # missing 10% or more is the usual definition of chronic absence


def rate(records):
    """Share of counted days attended. Excused days are not counted."""
    counted = [s for _, s in records if s != "E"]
    if not counted:
        return None
    return sum(1 for s in counted if s in ("P", "L")) / len(counted)


def current_streak(records):
    """Consecutive most recent absences, ignoring excused days."""
    n = 0
    for _, s in sorted(records, reverse=True):
        if s == "E":
            continue
        if s == "A":
            n += 1
        else:
            break
    return n


def longest_streak(records):
    best = n = 0
    for _, s in sorted(records):
        if s == "E":
            continue
        n = n + 1 if s == "A" else 0
        best = max(best, n)
    return best


def recent_rate(records, today, days=14):
    cut = today - timedelta(days=days)
    return rate([r for r in records if r[0] > cut])


def trend(records, alpha=0.2):
    """Exponentially weighted attendance over time, ending with the latest level.
    Returns (latest smoothed level, change over the last half)."""
    seq = [1.0 if s in ("P", "L") else 0.0 for _, s in sorted(records) if s != "E"]
    if not seq:
        return None, 0.0
    level = seq[0]
    levels = []
    for v in seq:
        level = alpha * v + (1 - alpha) * level
        levels.append(level)
    return levels[-1], levels[-1] - levels[len(levels) // 2]


def weekday_pattern(records, minimum=3):
    """Weekdays with far more absences than the rest, such as market day or a clash with work."""
    days = Counter()
    absent = Counter()
    for d, s in records:
        if s != "E":
            days[d.weekday()] += 1
            absent[d.weekday()] += s == "A"
    overall = sum(absent.values()) / max(sum(days.values()), 1)
    out = []
    for w, n in days.items():
        if n >= minimum and absent[w] >= 2 and absent[w] / n >= max(2 * overall, 0.4):
            out.append((w, absent[w] / n))
    return sorted(out, key=lambda t: -t[1])


def assess(records, today, min_days=5):
    """Return (risk level, reasons) for one learner. Each reason is something a teacher can act on."""
    reasons = []
    r = rate(records)
    if r is None or len(records) < min_days:
        return "unknown", ["too few days recorded"]
    score = 0
    streak = current_streak(records)
    if streak >= 3:
        reasons.append(f"absent for the last {streak} school days")
        score += 2
    if 1 - r >= 0.2:
        reasons.append(f"missed {1 - r:.0%} of school days")
        score += 2
    elif 1 - r >= CHRONIC:
        reasons.append(f"missed {1 - r:.0%} of school days")
        score += 1
    recent = recent_rate(records, today)
    if recent is not None and r - recent >= 0.15:
        reasons.append(f"attendance fell to {recent:.0%} in the last two weeks")
        score += 1
    for w, share in weekday_pattern(records):
        reasons.append(f"often absent on {['Mondays', 'Tuesdays', 'Wednesdays', 'Thursdays', 'Fridays', 'Saturdays', 'Sundays'][w]} ({share:.0%})")
        score += 1
    late = sum(1 for _, s in records if s == "L")
    if late / len(records) >= 0.25:
        reasons.append(f"late on {late} days")
    return ("high" if score >= 3 else "medium" if score >= 1 else "low"), reasons


def class_summary(learners, today):
    """learners: {name: records}. Class-level numbers and the list to act on, most urgent first."""
    rates = [rate(r) for r in learners.values()]
    rates = [x for x in rates if x is not None]
    order = {"high": 0, "medium": 1, "low": 2, "unknown": 3}
    rows = []
    for name, rec in learners.items():
        level, why = assess(rec, today)
        rows.append({"name": name, "level": level, "why": why, "rate": rate(rec)})
    rows.sort(key=lambda r: (order[r["level"]], r["rate"] if r["rate"] is not None else 2))
    return {"mean": sum(rates) / len(rates) if rates else None, "chronic": sum(1 for x in rates if 1 - x >= CHRONIC), "rows": rows}


def daily_rates(learners):
    """Attendance by date across the class, to spot days when many were away, such as a flood."""
    days = {}
    for rec in learners.values():
        for d, s in rec:
            if s != "E":
                t = days.setdefault(d, [0, 0])
                t[0] += s in ("P", "L")
                t[1] += 1
    return [(d, a / n, n) for d, (a, n) in sorted(days.items())]


def unusual_days(learners, drop=0.25):
    """Dates when attendance fell far below the class's usual level."""
    rows = daily_rates(learners)
    if len(rows) < 5:
        return []
    typical = sorted(r for _, r, _ in rows)[len(rows) // 2]
    return [(d, r) for d, r, _ in rows if typical - r >= drop]
