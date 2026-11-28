"""The Mail tab: safe rendering of EVE's markup, folders, name lookups, and that a member only ever reads their own."""
import types
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from ..services import mail

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "shipyard-mail-tests"}}


class CleanBodyTests(SimpleTestCase):
    def test_eve_markup_becomes_text_with_line_breaks(self):
        body = '<font size="14" color="#ffd98d00">Hello pilot,<br><br>ore is out in <a href="showinfo:5//30001391">Piekura</a>.</font><br>o7'
        self.assertEqual(mail.clean_body(body), "Hello pilot,<br><br>ore is out in Piekura.<br>o7")

    def test_web_links_are_kept_and_made_safe(self):
        out = mail.clean_body('see <a href="https://zkillboard.com/kill/1/">this</a>')
        self.assertIn('<a href="https://zkillboard.com/kill/1/" target="_blank" rel="noopener noreferrer nofollow">this</a>', out)

    def test_kill_report_links_go_to_zkillboard(self):
        out = mail.clean_body('<a href="killReport:138873602:6259bff7f75e46462219bc718e3b778c0c50537f">Kill: Capsule</a>')
        self.assertIn('href="https://zkillboard.com/kill/138873602/"', out)

    def test_scripts_handlers_and_script_links_do_not_survive(self):
        nasty = ('<script>alert(1)</script><img src=x onerror="alert(2)"><a href="javascript:alert(3)">click</a>'
                 '<a href="data:text/html,<script>alert(4)</script>">d</a><b onmouseover=alert(5)>bold</b> 1 < 2 & "q"')
        out = mail.clean_body(nasty)
        self.assertNotIn("<script", out.lower())
        self.assertNotIn("<img", out.lower())
        self.assertNotIn("javascript:", out.lower())
        self.assertNotIn("onerror", out.lower())
        self.assertNotIn("onmouseover", out.lower())
        self.assertNotIn("<a ", out)
        self.assertIn("click", out)
        self.assertIn("bold", out)
        self.assertIn("1 &lt; 2 &amp;", out)

    def test_attribute_cannot_break_out_of_the_link(self):
        out = mail.clean_body('<a href="https://example.org/?a=&quot; onclick=&quot;alert(1)">x</a>')
        self.assertIn('href="https://example.org/?a=&quot; onclick=&quot;alert(1)"', out)
        self.assertEqual(out.count("<a "), 1)

    def test_plain_text_and_long_gaps(self):
        self.assertEqual(mail.clean_body("a\n\n\n\n\nb"), "a<br><br>b")
        self.assertEqual(mail.clean_body(""), "")
        self.assertEqual(mail.clean_body(None), "")


class HeaderTests(SimpleTestCase):
    def test_kinds(self):
        me = [{"recipient_id": 1, "recipient_type": "character"}]
        self.assertEqual(mail.kind_of({"labels": [1], "recipients": me}), "inbox")
        self.assertEqual(mail.kind_of({"labels": [2], "recipients": me}), "sent")
        self.assertEqual(mail.kind_of({"labels": [4], "recipients": [{"recipient_id": 9, "recipient_type": "corporation"}]}), "corp")
        self.assertEqual(mail.kind_of({"labels": [8], "recipients": [{"recipient_id": 9, "recipient_type": "alliance"}]}), "alliance")
        self.assertEqual(mail.kind_of({"labels": [], "recipients": [{"recipient_id": 77, "recipient_type": "mailing_list"}]}), "list")
        self.assertEqual(mail.kind_of({"labels": [2, 4], "recipients": []}), "sent")
        self.assertEqual(mail.kind_of({}), "inbox")

    def test_folders_show_the_list_name_and_own_labels(self):
        header = {"labels": [1, 16], "recipients": [{"recipient_id": 77, "recipient_type": "mailing_list"}]}
        self.assertEqual(mail.folders_of(header, {1: "Inbox", 16: "Buyers"}, {77: "Freeport news"}), ["Freeport news", "Buyers"])
        self.assertEqual(mail.folders_of({"labels": [1], "recipients": []}, {1: "Inbox"}, {}), [])


@override_settings(CACHES=LOCMEM)
class NameTests(SimpleTestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_a_bad_id_does_not_lose_the_others(self):
        known = {1: "Alpha", 2: "Beta", 4: "Delta"}
        calls = []

        def post(ids):
            calls.append(list(ids))
            if any(i not in known for i in ids):
                raise RuntimeError("404")  # ESI refuses the whole request for one unknown id
            return [{"id": i, "name": known[i]} for i in ids]

        out = mail.resolve_names([1, 2, 3, 4, None, 0], post=post)
        self.assertEqual(out, known)
        # a second lookup of the found names is answered from the cache
        calls.clear()
        self.assertEqual(mail.resolve_names([1, 2, 4], post=post), known)
        self.assertEqual(calls, [])


HEADERS = {
    1001: {"headers": [
        {"mail_id": 5, "subject": "Moon pops Friday", "from": 501, "timestamp": "2026-11-27T18:00:00Z", "is_read": False, "labels": [1],
         "recipients": [{"recipient_id": 1001, "recipient_type": "character"}]},
        {"mail_id": 4, "subject": "Corp update", "from": 502, "timestamp": "2026-11-26T09:30:00Z", "is_read": True, "labels": [4],
         "recipients": [{"recipient_id": 2001, "recipient_type": "corporation"}]},
        {"mail_id": 3, "subject": "my reply", "from": 1001, "timestamp": "2026-11-25T09:30:00Z", "is_read": True, "labels": [2],
         "recipients": [{"recipient_id": 501, "recipient_type": "character"}]},
    ], "labels": {1: "Inbox", 2: "Sent", 4: "Corp"}, "unread": 1, "lists": {}},
}


@override_settings(SHIPYARD_STANDALONE_HOST="", CACHES=LOCMEM)
class MailViewTests(TestCase):
    def setUp(self):
        from allianceauth.tests.auth_utils import AuthUtils
        from django.core.cache import cache
        cache.clear()
        full = Permission.objects.get(codename="basic_access", content_type__app_label="shipyard")
        self.me = get_user_model().objects.create_user("me", password="x")
        AuthUtils.add_main_character_2(self.me, "My Main", 1001, corp_id=2001, corp_name="Corp", alliance_id=None, alliance_name="")
        self.me.user_permissions.add(full)
        self.other = get_user_model().objects.create_user("other", password="x")
        AuthUtils.add_main_character_2(self.other, "Other Main", 1002, corp_id=2001, corp_name="Corp", alliance_id=None, alliance_name="")
        self.other.user_permissions.add(full)
        self.limited = get_user_model().objects.create_user("limited", password="x")
        AuthUtils.add_main_character_2(self.limited, "Limited Main", 1003, corp_id=2001, corp_name="Corp", alliance_id=None, alliance_name="")
        self.limited.user_permissions.add(Permission.objects.get(codename="reprocessing_access", content_type__app_label="shipyard"))
        # the characters are on their accounts (the page lists a member's CharacterOwnership rows)
        from allianceauth.authentication.models import CharacterOwnership
        from allianceauth.eveonline.models import EveCharacter
        for user, cid in ((self.me, 1001), (self.other, 1002), (self.limited, 1003)):
            CharacterOwnership.objects.get_or_create(user=user, character=EveCharacter.objects.get(character_id=cid), defaults={"owner_hash": f"hash{cid}"})
        token = types.SimpleNamespace(valid_access_token=lambda: "access")
        self.asked = []

        def token_for(user, character_id):
            self.asked.append((user.username, int(character_id)))
            return token if (user.username, int(character_id)) in {("me", 1001), ("other", 1002)} else None

        self.patches = [
            mock.patch.object(mail, "token_for", side_effect=token_for),
            mock.patch.object(mail, "_fetch_character", side_effect=lambda cid, tok, pages: HEADERS.get(cid, {"headers": [], "labels": {}, "unread": 0, "lists": {}})),
            mock.patch.object(mail, "resolve_names", side_effect=lambda ids, post=None: {501: "Sender One", 502: "The CEO", 1001: "My Main"}),
            mock.patch.object(mail, "_fetch_body", return_value={
                "subject": "Moon pops Friday", "from": 501, "timestamp": "2026-11-27T18:00:00Z",
                "recipients": [{"recipient_id": 1001, "recipient_type": "character"}],
                "body": 'Chunk arrives <b>Friday</b>.<br><script>alert(1)</script><a href="https://example.org/">details</a>'}),
        ]
        self.mocks = [p.start() for p in self.patches]
        self.addCleanup(lambda: [p.stop() for p in self.patches])

    def _client(self, user):
        c = Client()
        c.force_login(user)
        return c

    def test_the_page_lists_my_own_mail_only(self):
        r = self._client(self.me).get(reverse("shipyard:mail"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([row.subject for row in r.context["rows"]], ["Moon pops Friday", "Corp update", "my reply"])
        self.assertEqual([row.kind for row in r.context["rows"]], ["inbox", "corp", "sent"])
        self.assertEqual(r.context["rows"][0].from_name, "Sender One")
        self.assertEqual(r.context["unread_total"], 1)
        self.assertContains(r, "Moon pops Friday")
        # only my own characters were ever asked for a token
        self.assertEqual({name for name, _ in self.asked}, {"me"})
        self.assertEqual({cid for _, cid in self.asked}, {1001})

    def test_another_member_sees_their_own_empty_box(self):
        r = self._client(self.other).get(reverse("shipyard:mail"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["rows"], [])
        self.assertNotContains(r, "Moon pops Friday")

    def test_reading_a_mail_returns_clean_html(self):
        r = self._client(self.me).get(reverse("shipyard:mail_body", args=[1001, 5]))
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["from"], "Sender One")
        self.assertEqual(d["to"], ["My Main"])
        self.assertNotIn("<script", d["body_html"])
        self.assertIn("Chunk arrives Friday.", d["body_html"])
        self.assertIn('<a href="https://example.org/"', d["body_html"])

    def test_nobody_reads_another_members_mail(self):
        # "other" asks for a mail of my character: refused before anything is fetched
        r = self._client(self.other).get(reverse("shipyard:mail_body", args=[1001, 5]))
        self.assertEqual(r.status_code, 404)
        self.mocks[3].assert_not_called()
        # a superuser is refused the same way: the check is ownership, not rank
        boss = get_user_model().objects.create_superuser("boss", password="x")
        from allianceauth.tests.auth_utils import AuthUtils
        AuthUtils.add_main_character_2(boss, "Boss Main", 1009, corp_id=2001, corp_name="Corp", alliance_id=None, alliance_name="")
        r = self._client(boss).get(reverse("shipyard:mail_body", args=[1001, 5]))
        self.assertEqual(r.status_code, 404)
        self.mocks[3].assert_not_called()

    def test_limited_members_and_visitors_do_not_get_the_tab(self):
        self.assertEqual(self._client(self.limited).get(reverse("shipyard:mail")).status_code, 403)
        self.assertEqual(self._client(self.limited).get(reverse("shipyard:mail_body", args=[1003, 1])).status_code, 403)
        self.assertEqual(Client().get(reverse("shipyard:mail")).status_code, 302)

    def test_refresh_reads_again_and_load_older_asks_for_more(self):
        c = self._client(self.me)
        c.get(reverse("shipyard:mail"))
        c.get(reverse("shipyard:mail"))
        self.assertEqual(self.mocks[1].call_count, 1)  # the second view came from the cache
        r = c.post(reverse("shipyard:mail"), {"depth": "1"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.mocks[1].call_count, 2)
        c.get(reverse("shipyard:mail") + "?depth=3")
        self.assertEqual(self.mocks[1].call_args[0][2], 3)
        c.get(reverse("shipyard:mail") + "?depth=99")
        self.assertEqual(self.mocks[1].call_args[0][2], mail.MAX_PAGES)
