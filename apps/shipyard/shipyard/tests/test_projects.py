"""Corp projects: payouts and contributions from snapshots."""
import datetime as dt

from django.test import TestCase
from django.utils import timezone

from ..models import CorpProject, ProjectContribution, ProjectSnapshot
from ..services import projects


class SnapshotTests(TestCase):
    def setUp(self):
        now = timezone.now()
        cid = projects.corp_id()
        self.p = CorpProject.objects.create(project_id="p1", corporation_id=cid, name="Haul ore", state="Active", kind="deliver_item",
                                            reward_initial=100_000_000, reward_remaining=40_000_000, reward_per_contribution=1000,
                                            progress_current=60_000, progress_desired=100_000, created=now - dt.timedelta(days=20))
        # first snapshot (10 days ago) saw 70 M remaining: 30 M had been paid before we watched; then 40 M → 30 M more
        ProjectSnapshot.objects.create(project=self.p, taken_at=now - dt.timedelta(days=10), state="Active", progress_current=30_000, reward_remaining=70_000_000)
        ProjectSnapshot.objects.create(project=self.p, taken_at=now - dt.timedelta(days=2), state="Active", progress_current=60_000, reward_remaining=40_000_000)
        ProjectContribution.objects.create(project=self.p, taken_at=now - dt.timedelta(days=10), character_id=1, character_name="Alice", contributed=20_000)
        ProjectContribution.objects.create(project=self.p, taken_at=now - dt.timedelta(days=10), character_id=2, character_name="Bob", contributed=10_000)
        ProjectContribution.objects.create(project=self.p, taken_at=now - dt.timedelta(days=2), character_id=1, character_name="Alice", contributed=45_000)
        ProjectContribution.objects.create(project=self.p, taken_at=now - dt.timedelta(days=2), character_id=2, character_name="Bob", contributed=15_000)

    def test_payouts_and_contributors(self):
        deltas = projects.payout_deltas()
        self.assertEqual([round(d["paid"]) for d in deltas], [30_000_000, 30_000_000])  # newest first
        self.assertEqual([d["progress"] for d in deltas], [30_000, 30_000])
        recent = projects.payout_deltas(timezone.now() - dt.timedelta(days=5))
        self.assertEqual(len(recent), 1)
        piv = projects.pivot(deltas, "month")
        self.assertEqual(piv["rows"][0][0], "Haul ore")
        self.assertAlmostEqual(piv["rows"][0][3], 60_000_000)
        c = projects.contributors(projects.contributor_deltas(), "week")
        self.assertEqual([(r["name"], r["units"], round(r["isk"])) for r in c], [("Alice", 45_000, 45_000_000), ("Bob", 15_000, 15_000_000)])
        self.assertEqual(self.p.paid_out, 60_000_000)
        self.assertAlmostEqual(self.p.progress_pct, 60.0)

    def test_kind_and_dates(self):
        self.assertEqual(projects._kind([{"deliver_item": {"items": []}}]), "deliver_item")
        self.assertEqual(projects._kind([]), "unknown")
        self.assertEqual(projects._parse_dt("2026-10-14T10:00:00Z").isoformat(), "2026-10-14T10:00:00+00:00")
        self.assertIsNone(projects._parse_dt(None))
