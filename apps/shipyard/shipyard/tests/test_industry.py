import datetime as dt
from unittest import mock

from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.utils import timezone

from ..models import BuildSnapshot, CharacterSync, Facility, IndustryJob, MaterialType, Ship
from ..services import industry


class AssetAggregationTests(TestCase):
    def test_items_in_containers_and_ships_roll_up_to_the_station(self):
        assets = [
            {"item_id": 1, "type_id": 34, "quantity": 1000, "location_id": 60003760},        # tritanium in the hangar
            {"item_id": 2, "type_id": 648, "quantity": 1, "location_id": 60003760},          # a Badger in the hangar
            {"item_id": 3, "type_id": 34, "quantity": 500, "location_id": 2},                # tritanium in the Badger's hold
            {"item_id": 4, "type_id": 3297, "quantity": 1, "location_id": 60003760},         # a container
            {"item_id": 5, "type_id": 35, "quantity": 20, "location_id": 4},                 # pyerite in the container
            {"item_id": 6, "type_id": 34, "quantity": 7, "location_id": 1030000000001},      # tritanium in a structure
            {"item_id": 7, "type_id": 999999, "quantity": 9, "location_id": 60003760},       # not a type we know
        ]
        totals = industry.aggregate_assets(assets, relevant={34, 35, 648})
        self.assertEqual(totals[(34, 60003760)], 1500)
        self.assertEqual(totals[(35, 60003760)], 20)
        self.assertEqual(totals[(648, 60003760)], 1)
        self.assertEqual(totals[(34, 1030000000001)], 7)
        self.assertNotIn((999999, 60003760), totals)

    def test_root_location_stops_on_a_loop(self):
        by_item = {1: {"location_id": 2}, 2: {"location_id": 1}}
        self.assertIn(industry.root_location({"location_id": 1}, by_item), (1, 2))


class StoreTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tony", password="x")

    def test_jobs_are_replaced_per_character(self):
        jobs = [{
            "job_id": 11, "activity_id": 1, "blueprint_type_id": 17741, "product_type_id": 17740, "runs": 2,
            "status": "active", "start_date": "2026-10-07T10:00:00Z", "end_date": "2026-10-08T10:00:00Z",
            "facility_id": 1030000000001, "cost": 18239547.0,
        }]
        industry._store_jobs(self.user, 1073057550, "Catherine Frey", jobs)
        industry._store_jobs(self.user, 1073057550, "Catherine Frey", jobs)  # a second read does not duplicate
        self.assertEqual(IndustryJob.objects.count(), 1)
        job = IndustryJob.objects.get()
        self.assertEqual(job.end_date, dt.datetime(2026, 10, 8, 10, tzinfo=dt.timezone.utc))
        self.assertEqual(job.location_id, 1030000000001)

    def test_owned_blueprints_prefers_an_original_then_the_better_me(self):
        CharacterSync.objects.create(user=self.user, character_id=1, character_name="Alpha")
        industry._store_blueprints(self.user, 1, [
            {"item_id": 1, "type_id": 17741, "location_id": 60003760, "location_flag": "Hangar", "material_efficiency": 10, "time_efficiency": 20, "runs": 5, "quantity": -2},
            {"item_id": 2, "type_id": 17741, "location_id": 60003760, "location_flag": "Hangar", "material_efficiency": 4, "time_efficiency": 8, "runs": -1, "quantity": -1},
            {"item_id": 3, "type_id": 17741, "location_id": 60003760, "location_flag": "Hangar", "material_efficiency": 7, "time_efficiency": 14, "runs": -1, "quantity": -1},
            {"item_id": 4, "type_id": 1000, "location_id": 60003760, "location_flag": "Hangar", "material_efficiency": 2, "time_efficiency": 4, "runs": 3, "quantity": -2},
        ])
        best = industry.owned_blueprints(self.user)
        self.assertEqual(best[17741]["kind"], "BPO")
        self.assertEqual((best[17741]["me"], best[17741]["te"]), (7, 14))
        self.assertEqual(best[1000]["kind"], "BPC")
        self.assertEqual(best[1000]["character_name"], "Alpha")

    def test_overview_counts_slots_and_recent_jobs(self):
        now = timezone.now()
        CharacterSync.objects.create(user=self.user, character_id=1, character_name="Alpha", manufacturing_slots=11, science_slots=3)
        MaterialType.objects.create(type_id=17740, name="Vindicator")
        Ship.objects.create(type_id=17740, name="Vindicator", group_id=27, hull_size="Battleship", category="Pirate", blueprint_type_id=17741)
        IndustryJob.objects.create(job_id=1, user=self.user, character_id=1, character_name="Alpha", activity_id=1, blueprint_type_id=17741, product_type_id=17740, runs=1, status="active", start_date=now, end_date=now + dt.timedelta(hours=2), location_id=60003760)
        IndustryJob.objects.create(job_id=2, user=self.user, character_id=1, character_name="Alpha", activity_id=4, blueprint_type_id=17741, runs=1, status="ready", start_date=now, end_date=now - dt.timedelta(hours=1), location_id=60003760)
        IndustryJob.objects.create(job_id=3, user=self.user, character_id=1, character_name="Alpha", activity_id=1, blueprint_type_id=17741, product_type_id=17740, runs=1, status="delivered", start_date=now, end_date=now - dt.timedelta(days=2), location_id=60003760)
        IndustryJob.objects.create(job_id=4, user=self.user, character_id=1, character_name="Alpha", activity_id=1, blueprint_type_id=17741, product_type_id=17740, runs=1, status="delivered", start_date=now, end_date=now - dt.timedelta(days=20), location_id=60003760)
        # EVE reports a finished, undelivered job as "active": the end date puts it with the ready ones
        IndustryJob.objects.create(job_id=5, user=self.user, character_id=1, character_name="Alpha", activity_id=1, blueprint_type_id=17741, product_type_id=17740, runs=1, status="active", start_date=now, end_date=now - dt.timedelta(hours=3), location_id=60003760)
        data = industry.overview(self.user)
        self.assertEqual(len(data["active_jobs"]), 1)
        self.assertEqual(len(data["ready_jobs"]), 2)
        self.assertEqual(len(data["recent_jobs"]), 1)
        self.assertEqual(data["slots"][0]["manufacturing_used"], 2)
        self.assertEqual(data["slots"][0]["science_used"], 1)
        self.assertEqual(data["active_jobs"][0]["product"], "Vindicator")
        self.assertEqual(data["active_jobs"][0]["ship"].type_id, 17740)
        self.assertEqual(data["active_jobs"][0]["place"][0], "Location 60003760")
        self.assertEqual(data["scopes"], ["own"])

    def test_relevant_type_ids_include_blueprints_and_materials(self):
        fac = Facility.objects.create(name="R", structure_type_id=35825, structure_name="Raitaru", system_id=1, system_name="X")
        ship = Ship.objects.create(type_id=17740, name="Vindicator", group_id=27, hull_size="Battleship", category="Pirate", blueprint_type_id=17741)
        BuildSnapshot.objects.create(ship=ship, facility=fac, me=0, materials=[{"type_id": 34, "quantity": 1}])
        ids = industry.relevant_type_ids()
        self.assertTrue({17740, 17741, 34} <= ids)

    def test_sync_user_skips_characters_without_full_access(self):
        with mock.patch.object(industry.characters, "token_for", return_value=None):
            self.assertEqual(industry.sync_user(self.user), [])


class ScopeTests(TestCase):
    """Who sees whom: own characters, the corp, the alliance."""

    def setUp(self):
        self.director = AuthUtils.create_user("director")
        main = AuthUtils.add_main_character_2(self.director, "Director Main", 1001, corp_id=2001, corp_name="Corp A", alliance_id=3001, alliance_name="Alliance")
        self.main = main
        # another member of the same corp, one of another corp in the alliance, one outside
        self.same_corp = AuthUtils.create_user("samecorp")
        AuthUtils.add_main_character_2(self.same_corp, "Same Corp", 1002, corp_id=2001, corp_name="Corp A", alliance_id=3001, alliance_name="Alliance")
        self.other_corp = AuthUtils.create_user("othercorp")
        AuthUtils.add_main_character_2(self.other_corp, "Other Corp", 1003, corp_id=2002, corp_name="Corp B", alliance_id=3001, alliance_name="Alliance")
        self.outsider = AuthUtils.create_user("outsider")
        AuthUtils.add_main_character_2(self.outsider, "Outsider", 1004, corp_id=2003, corp_name="Corp C", alliance_id=None, alliance_name="")
        for user, cid in ((self.director, 1001), (self.same_corp, 1002), (self.other_corp, 1003), (self.outsider, 1004)):
            CharacterSync.objects.create(user=user, character_id=cid, character_name=EveCharacter.objects.get(character_id=cid).character_name)

    def _perm(self, codename):
        return Permission.objects.get(codename=codename, content_type__app_label="shipyard")

    def test_a_member_sees_only_their_own_characters(self):
        self.assertEqual(industry.allowed_scopes(self.director), ["own"])
        self.assertEqual([s.character_id for s in industry.visible_syncs(self.director, "own")], [1001])
        # asking for a wider scope without the permission still gives their own
        self.assertEqual([s.character_id for s in industry.visible_syncs(self.director, "own")], [1001])

    def test_a_corp_director_sees_the_corp(self):
        self.director.user_permissions.add(self._perm("view_corp_industry"))
        self.director = get_user_model().objects.get(pk=self.director.pk)
        self.assertEqual(industry.allowed_scopes(self.director), ["own", "corp"])
        self.assertEqual(sorted(s.character_id for s in industry.visible_syncs(self.director, "corp")), [1001, 1002])

    def test_an_alliance_director_sees_the_alliance(self):
        self.director.user_permissions.add(self._perm("view_alliance_industry"))
        self.director = get_user_model().objects.get(pk=self.director.pk)
        self.assertEqual(industry.allowed_scopes(self.director), ["own", "corp", "alliance"])
        self.assertEqual(sorted(s.character_id for s in industry.visible_syncs(self.director, "alliance")), [1001, 1002, 1003])
        self.assertEqual(sorted(s.character_id for s in industry.visible_syncs(self.director, "corp")), [1001, 1002])
