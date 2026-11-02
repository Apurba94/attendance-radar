"""The offline web app."""
from datetime import date

from . import core
from .fieldkit import App, Fail, Raw, card, form, h, line_chart, link, redirect, stats, table

SCHEMA = """
CREATE TABLE IF NOT EXISTS learners (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS marks (learner INTEGER NOT NULL REFERENCES learners(id), day TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY (learner, day));
"""


def create_app(db="attendance.db", today=date.today):
    a = App("Attendance Radar", db, SCHEMA, [("Radar", "/"), ("Take attendance", "/register"), ("Learners", "/learners")])

    def records(lid):
        return [(date.fromisoformat(r["day"]), r["status"]) for r in a.rows("SELECT day, status FROM marks WHERE learner = ? ORDER BY day", lid)]

    def everyone():
        return {r["name"]: records(r["id"]) for r in a.rows("SELECT * FROM learners WHERE active = 1")}

    @a.route("/")
    def home(req):
        s = core.class_summary(everyone(), today())
        ids = {r["name"]: r["id"] for r in a.rows("SELECT id, name FROM learners")}
        focus = [r for r in s["rows"] if r["level"] in ("high", "medium")]
        body = stats([("Learners", len(s["rows"])), ("Class attendance", "n/a" if s["mean"] is None else f"{s['mean']:.0%}"), ("Chronically absent", s["chronic"]), ("Need attention", len(focus))])
        body += card("Who needs attention", table(focus, [("Level", lambda r: Raw(f'<span class="{"bad" if r["level"] == "high" else "warn"}">{r["level"]}</span>')), ("Learner", lambda r: link(f"/learner/{ids[r['name']]}", r["name"])), ("Attendance", lambda r: f"{r['rate']:.0%}"), ("Why", lambda r: "; ".join(r["why"]))], "Nobody is flagged right now."))
        rows = core.daily_rates(everyone())
        body += card("Attendance by day", line_chart([(d.isoformat(), r * 100) for d, r, _ in rows]))
        odd = core.unusual_days(everyone())
        if odd:
            body += card("Unusual days", table(odd, [("Date", lambda r: r[0].isoformat()), ("Attendance", lambda r: f"{r[1]:.0%}")]))
        return a.page("Attendance radar", body)

    @a.route("/learners", ("GET", "POST"))
    def learners(req):
        if req.method == "POST":
            for n in req.text("names", limit=100000).splitlines():
                if n.strip():
                    a.run("INSERT OR IGNORE INTO learners (name) VALUES (?)", n.strip())
            return redirect("/register")
        return a.page("Learners", card("One name per line", form(a, "/learners", [("names", "Names", "textarea")], "Add")) + card("All", table(a.rows("SELECT * FROM learners ORDER BY name"), [("Name", lambda r: link(f"/learner/{r['id']}", r["name"]))])))

    @a.route("/register", ("GET", "POST"))
    def register(req):
        day = req.get("day") or today().isoformat()
        try:
            when = date.fromisoformat(day)
        except ValueError:
            raise Fail("That is not a date") from None
        if when > today():
            raise Fail("You cannot mark a date in the future")
        people = a.rows("SELECT * FROM learners WHERE active = 1 ORDER BY name")
        if req.method == "POST":
            for p in people:
                s = req.text(f"s{p['id']}")
                if s not in core.STATUSES:
                    raise Fail(f"Unknown status {s}")
                a.run("INSERT INTO marks (learner, day, status) VALUES (?, ?, ?) ON CONFLICT(learner, day) DO UPDATE SET status = excluded.status", p["id"], day, s)
            a.log("attendance", day)
            return redirect("/")
        have = {r["learner"]: r["status"] for r in a.rows("SELECT learner, status FROM marks WHERE day = ?", day)}
        names = {"P": "Present", "A": "Absent", "L": "Late", "E": "Excused"}
        rows = []
        for p in people:
            cur = have.get(p["id"], "P")
            opts = "".join(f'<label style="display:inline-block;margin-right:12px;font-weight:400"><input type="radio" name="s{p["id"]}" value="{s}"{" checked" if s == cur else ""}> {names[s]}</label>' for s in core.STATUSES)
            rows.append(f"<tr><td>{h(p['name'])}</td><td>{opts}</td></tr>")
        body = f'<div class="card"><form method="get" action="/register"><label>Date<input type="date" name="day" value="{h(day)}"></label><button>Open</button></form></div><form method="post" action="/register?day={h(day)}" class="card">{a.form_token()}<table>{"".join(rows)}</table><p><button>Save register</button></p></form>'
        return a.page(f"Register for {day}", body)

    @a.route("/learner/<id>")
    def learner(req, id):
        l = a.row("SELECT * FROM learners WHERE id = ?", id)
        if l is None:
            raise Fail("No such learner", 404)
        rec = records(id)
        level, why = core.assess(rec, today())
        r = core.rate(rec)
        body = stats([("Attendance", "n/a" if r is None else f"{r:.0%}"), ("Risk", level), ("Absent now", core.current_streak(rec)), ("Longest gap", core.longest_streak(rec))])
        body += card("Why", "".join(f"<p>{h(w)}</p>" for w in why) or "<p>No concerns.</p>")
        body += card("Recent days", table(list(reversed(rec))[:30], [("Date", lambda x: x[0].isoformat()), ("Status", lambda x: x[1])], "No days recorded."))
        return a.page(l["name"], body)

    return a
