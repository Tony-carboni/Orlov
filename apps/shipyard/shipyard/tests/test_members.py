"""The Director page (0.40.0): the CEO's member notifications stored, the leavers listed, the permission gate."""
import datetime as dt
from unittest import mock

from allianceauth.tests.auth_utils import AuthUtils
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from ..models import CorpMemberEvent, RefreshRun
from ..services import members

CORP = 98843356


def _resp(payload, status=200):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


NOTIFICATIONS = [
    {"notification_id": 1, "type": "CharLeftCorpMsg", "timestamp": "2026-11-14T00:13:00Z", "text": "charID: 2001\ncorpID: 98843356\n"},
    {"notification_id": 2, "type": "CorpAppNewMsg", "timestamp": "2026-11-13T10:00:00Z", "text": "applicationText: 'hello there'\ncharID: 2002\ncorpID: 98843356\n"},
    {"notification_id": 3, "type": "CharAppAcceptMsg", "timestamp": "2026-11-13T11:00:00Z", "text": "charID: 2002\ncorpID: 98843356\n"},
    {"notification_id": 4, "type": "CharLeftCorpMsg", "timestamp": "2026-11-02T15:25:00Z", "text": "charID: 2003\ncorpID: 98635713\n"},  # another corporation
    {"notification_id": 5, "type": "StructureUnderAttack", "timestamp": "2026-11-02T15:25:00Z", "text": "x"},
    {"notification_id": 6, "type": "CharLeftCorpMsg", "timestamp": "2026-11-02T15:25:00Z", "text": "charID: 2002\ncorpID: 98843356\n"},  # left, then came back (3)
]


@override_settings(SHIPYARD_STANDALONE_HOST="", SHIPYARD_PROJECTS_CORP_ID=CORP)
class MemberEventTests(TestCase):
    def test_parse_reads_the_yaml_like_text(self):
        self.assertEqual(members.parse("applicationText: 'hi'\ncharID: 2002\ncorpID: 98843356\n"), {"applicationText": "hi", "charID": "2002", "corpID": "98843356"})
        self.assertEqual(members.parse(""), {})

    def _refresh(self):
        tok = mock.Mock(character_id=1073057550, character_name="Catherine Frey")
        tok.valid_access_token.return_value = "x"
        sess = mock.Mock()
        sess.get.return_value = _resp(NOTIFICATIONS)
        sess.post.return_value = _resp([{"id": 2001, "name": "Eternity Emperor", "category": "character"}, {"id": 2002, "name": "John Sono", "category": "character"}])
        with mock.patch.object(members, "token", return_value=tok), mock.patch.object(members, "session", return_value=sess):
            return members.refresh()

    def test_refresh_stores_the_corporation_s_member_messages_once(self):
        r = self._refresh()
        self.assertEqual((r["new"], r["seen"], r["character"]), (4, 5, "Catherine Frey"))
        self.assertEqual(sorted(CorpMemberEvent.objects.values_list("notification_id", "kind")), [(1, "left"), (2, "applied"), (3, "accepted"), (6, "left")])
        e = CorpMemberEvent.objects.get(notification_id=1)
        self.assertEqual((e.character_id, e.character_name, e.timestamp), (2001, "Eternity Emperor", dt.datetime(2026, 11, 14, 0, 13, tzinfo=dt.timezone.utc)))
        self.assertEqual(CorpMemberEvent.objects.get(notification_id=2).text, "hello there")
        self.assertEqual(self._refresh()["new"], 0)  # the second hour adds nothing
        self.assertEqual(CorpMemberEvent.objects.count(), 4)

    def test_refresh_without_a_ceo_token_says_so(self):
        with mock.patch.object(members, "token", return_value=None), self.assertRaises(RuntimeError):
            members.refresh()

    def test_leavers_newest_first_with_what_auth_knows(self):
        self._refresh()
        user = get_user_model().objects.create_user("ee", password="x")
        AuthUtils.add_main_character_2(user, "Eternity Emperor", 2001, corp_id=98000001, corp_name="Elsewhere Inc", alliance_id=None, alliance_name="")
        from allianceauth.authentication.models import CharacterOwnership
        from allianceauth.eveonline.models import EveCharacter
        CharacterOwnership.objects.create(user=user, character=EveCharacter.objects.get(character_id=2001), owner_hash="h-2001")
        rows = members.leavers()
        self.assertEqual([r["name"] for r in rows], ["Eternity Emperor", "John Sono"])
        self.assertIn("ee: main", rows[0]["auth"])
        self.assertIn("no Discord", rows[0]["auth"])
        self.assertEqual(rows[0]["now"], "now in Elsewhere Inc")
        self.assertEqual((rows[1]["auth"], rows[1]["returned"]), ("never registered", True))
        self.assertEqual(members.counts(days=3650)["left"], 2)
        self.assertEqual(members.leavers(days=5), rows[:1])

    def test_the_page_needs_the_director_permission(self):
        self._refresh()
        RefreshRun.objects.create(step="member_events", ok=True, finished_at=dt.datetime(2026, 11, 14, 9, 12, tzinfo=dt.timezone.utc), message="Catherine Frey")
        director = get_user_model().objects.create_user("hamu", password="x")
        AuthUtils.add_main_character_2(director, "Hamu", 3001, corp_id=CORP, corp_name="OARMI", alliance_id=None, alliance_name="")
        client = Client()
        client.force_login(director)
        self.assertEqual(client.get(reverse("shipyard:director")).status_code, 403)
        director.user_permissions.add(Permission.objects.get(codename="director_access", content_type__app_label="shipyard"))
        director = get_user_model().objects.get(pk=director.pk)  # permission cache
        client.force_login(director)
        r = client.get(reverse("shipyard:director"))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn("Eternity Emperor", html)
        self.assertIn("Read from Catherine Frey", html)
        self.assertIn('href="/shipyard/director/"', html)  # the nav shows the tab
