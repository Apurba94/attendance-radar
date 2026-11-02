import unittest
from datetime import date, timedelta

from attendance_radar import core, create_app
from attendance_radar.core import assess, class_summary, current_streak, daily_rates, longest_streak, rate, recent_rate, trend, unusual_days, weekday_pattern

D0 = date(2026, 9, 6)      # a Sunday


def days(pattern, start=D0):
    """School days only: Sunday to Thursday, as in Bangladesh."""
    out = []
    d = start
    for s in pattern:
        while d.weekday() in (4, 5):
            d += timedelta(days=1)
        out.append((d, s))
        d += timedelta(days=1)
    return out


class TestBasics(unittest.TestCase):
    def test_rate_ignores_excused_and_counts_late(self):
        self.assertEqual(rate(days("PPAE")), 2 / 3)
        self.assertEqual(rate(days("L")), 1)
        self.assertIsNone(rate(days("E")))
        self.assertIsNone(rate([]))

    def test_streaks(self):
        self.assertEqual(current_streak(days("PPAA")), 2)
        self.assertEqual(current_streak(days("AAP")), 0)
        self.assertEqual(current_streak(days("AEA")), 2)
        self.assertEqual(longest_streak(days("AAPAAAP")), 3)

    def test_order_of_input_does_not_matter(self):
        r = days("PAAA")
        self.assertEqual(current_streak(list(reversed(r))), 3)

    def test_recent(self):
        r = days("P" * 30 + "A" * 5)
        self.assertLess(recent_rate(r, r[-1][0]), rate(r))

    def test_trend_shows_decline(self):
        level, change = trend(days("P" * 20 + "A" * 10))
        self.assertLess(change, -0.3)
        self.assertLess(level, 0.3)
        self.assertGreater(trend(days("A" * 10 + "P" * 20))[1], 0.2)
        self.assertEqual(trend([]), (None, 0.0))

    def test_weekday_pattern(self):
        rec = []
        for w in range(8):
            for i in range(5):
                d = D0 + timedelta(days=w * 7 + i)
                rec.append((d, "A" if i == 3 else "P"))
        hits = weekday_pattern(rec)
        self.assertEqual(hits[0][0], 2)
        self.assertEqual(hits[0][1], 1)

    def test_weekday_pattern_ignores_scattered_absence(self):
        self.assertEqual(weekday_pattern(days("PPPPPPAPPPPPPPAPPPPP")), [])


class TestRisk(unittest.TestCase):
    def test_good_attendance(self):
        r = days("P" * 40)
        self.assertEqual(assess(r, r[-1][0]), ("low", []))

    def test_current_absence(self):
        r = days("P" * 30 + "AAA")
        level, why = assess(r, r[-1][0])
        self.assertNotEqual(level, "low")
        self.assertIn("absent for the last 3 school days", why)

    def test_chronic(self):
        r = days("PPPPPPPA" * 5 + "P")          # 5 of 41 days, on no single weekday
        self.assertIn("missed 12%", assess(r, r[-1][0])[1][0])
        r = days("PPPPPPPPPA" * 4 + "PP")        # 4 of 42 days is 9.5%, just under the line
        self.assertFalse(any("missed" in w for w in assess(r, r[-1][0])[1]))

    def test_high_risk(self):
        r = days("PPPAPPAPAP" * 3 + "AAAA")
        self.assertEqual(assess(r, r[-1][0])[0], "high")

    def test_excused_illness_does_not_flag(self):
        r = days("P" * 30 + "EEEEE")
        self.assertEqual(assess(r, r[-1][0])[0], "low")

    def test_too_little_data(self):
        r = days("AA")
        self.assertEqual(assess(r, r[-1][0])[0], "unknown")

    def test_lateness_is_mentioned(self):
        r = days("LP" * 15)
        self.assertTrue(any("late on" in w for w in assess(r, r[-1][0])[1]))


class TestClass(unittest.TestCase):
    def data(self):
        return {"steady": days("P" * 30), "fading": days("P" * 24 + "AAAAAA"), "new": days("PP")}

    def test_summary_orders_by_urgency(self):
        today = days("P" * 30)[-1][0]
        s = class_summary(self.data(), today)
        self.assertEqual(s["rows"][0]["name"], "fading")
        self.assertEqual(s["rows"][-1]["name"], "new")
        self.assertEqual(s["chronic"], 1)

    def test_daily_and_unusual(self):
        rec = {f"l{i}": days("P" * 9 + "A" + "P" * 5) for i in range(5)}
        rec["x"] = days("P" * 15)
        rows = daily_rates(rec)
        self.assertEqual(len(rows), 15)
        odd = unusual_days(rec)
        self.assertEqual(len(odd), 1)
        self.assertAlmostEqual(odd[0][1], 1 / 6)

    def test_empty(self):
        self.assertIsNone(class_summary({}, D0)["mean"])


class TestApp(unittest.TestCase):
    def setUp(self):
        self.t = [date(2026, 11, 2)]
        self.a = create_app(":memory:", lambda: self.t[0])
        self.a.post("/learners", names="Rahima\nKarim")

    def mark(self, day, r, k):
        return self.a.post(f"/register?day={day}", s1=r, s2=k)

    def test_register_flow_and_flag(self):
        for i in range(10):
            d = date(2026, 10, 1) + timedelta(days=i * 2)
            self.assertEqual(self.mark(d.isoformat(), "P", "P" if i < 6 else "A").status, 303)
        page = self.a.get("/").body.decode()
        self.assertIn("Karim", page.split("Who needs attention")[1])
        self.assertIn("absent for the last 4", page)
        self.assertIn("/learner/2", page)

    def test_correcting_a_day_replaces_it(self):
        self.mark("2026-10-01", "A", "P")
        self.mark("2026-10-01", "P", "P")
        self.assertEqual(self.a.one("SELECT COUNT(*) FROM marks"), 2)
        self.assertEqual(self.a.one("SELECT status FROM marks WHERE learner = 1"), "P")

    def test_future_date_is_refused(self):
        self.assertEqual(self.mark("2030-01-01", "P", "P").status, 400)
        self.assertEqual(self.a.get("/register?day=nonsense").status, 400)

    def test_a_bad_status_saves_nothing(self):
        self.assertEqual(self.mark("2026-10-01", "P", "Z").status, 400)
        self.assertEqual(self.a.one("SELECT COUNT(*) FROM marks"), 0)

    def test_learner_page(self):
        self.mark("2026-10-01", "A", "P")
        self.assertIn("too few days", self.a.get("/learner/1").body.decode())
        self.assertEqual(self.a.get("/learner/9").status, 404)


if __name__ == "__main__":
    unittest.main()
