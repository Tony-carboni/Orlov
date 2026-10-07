"""The member's character: which one the dashboard uses, its ESI token, its data.

Everything the dashboard knows about a member's character (skills, standings) is read
from ESI through a token that carries the full scope set, the same 33 scopes Member
Audit asks for. Picking a character that has no such token sends the member to EVE's
login once; the token then also registers the character in Member Audit.
"""

import datetime as dt
import logging

from django.apps import apps
from django.utils import timezone
from esi.models import Token

from .. import app_settings, constants
from ..models import UserSettings
from . import esi

logger = logging.getLogger(__name__)


def full_scopes() -> list[str]:
    """Member Audit's scope list when it is installed (kept in step with it), else our copy."""
    try:
        from memberaudit.models import Character

        scopes = list(Character.esi_scopes())
        if scopes:
            return scopes
    except Exception:  # noqa: BLE001
        pass
    return list(constants.FULL_SCOPES)


def token_for(user, character_id: int):
    """A valid token of this user for this character with the full scope set, or None."""
    return (
        Token.objects.filter(user=user, character_id=int(character_id))
        .require_scopes(full_scopes())
        .require_valid()
        .first()
    )


def has_full_access(user, character_id: int) -> bool:
    return token_for(user, character_id) is not None


def register_in_memberaudit(eve_character) -> bool:
    """Make sure the character is registered in Member Audit; True when it was added now."""
    if not apps.is_installed("memberaudit"):
        return False
    try:
        from memberaudit import tasks
        from memberaudit.app_settings import MEMBERAUDIT_TASKS_NORMAL_PRIORITY
        from memberaudit.models import Character

        character, created = Character.objects.update_or_create(
            eve_character=eve_character, defaults={"is_disabled": False}
        )
        if created:
            tasks.update_character.apply_async(
                kwargs={"character_pk": character.pk, "force_update": True, "ignore_stale": True},
                priority=MEMBERAUDIT_TASKS_NORMAL_PRIORITY,
            )
        return created
    except Exception as exc:  # noqa: BLE001
        logger.warning("Member Audit registration of %s failed: %s", eve_character, exc)
        return False


def load_character(settings: UserSettings, token) -> None:
    """Read skills and standings of the token's character into the member's settings."""
    access_token = token.valid_access_token()
    levels = esi.character_skills(token.character_id, access_token)
    for skill_id, (field, _, _) in constants.RELEVANT_SKILLS.items():
        setattr(settings, field, levels.get(skill_id, 0))
    settings.skills_source = UserSettings.SKILLS_ESI
    settings.skills_character_id = token.character_id
    settings.skills_character_name = token.character_name
    settings.skills_fetched_at = timezone.now()
    try:
        settings.standings = esi.character_standings(token.character_id, access_token)
        settings.standings_fetched_at = timezone.now()
    except Exception as exc:  # noqa: BLE001
        logger.warning("standings of %s not read: %s", token.character_name, exc)
    # the dashboard only ever uses what ESI says
    settings.manual_sales_tax = None
    settings.manual_broker_fee = None
    settings.save()


def is_stale(settings: UserSettings) -> bool:
    if not settings.skills_character_id or settings.skills_fetched_at is None:
        return True
    max_age = dt.timedelta(hours=app_settings.SHIPYARD_ESI_REFRESH_HOURS)
    return timezone.now() - settings.skills_fetched_at > max_age


def ensure_fresh(settings: UserSettings, user) -> str | None:
    """Refresh the character's data from ESI when it is older than a day, without a click.

    Returns a short notice for the page when something stands in the way, else None.
    """
    if not settings.skills_character_id:
        return None
    if not is_stale(settings):
        return None
    token = token_for(user, settings.skills_character_id)
    if token is None:
        return (
            f"{settings.skills_character_name} has no token with all scopes any more; "
            "pick the character again under My settings to grant access."
        )
    try:
        load_character(settings, token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("refresh of %s failed: %s", settings.skills_character_name, exc)
        return f"EVE did not answer when refreshing {settings.skills_character_name}; showing the last known data."
    return None


def choices(user, settings: UserSettings) -> list[dict]:
    """The characters on the member's auth account, for the picker."""
    rows = []
    for ownership in user.character_ownerships.select_related("character").order_by("character__character_name"):
        character = ownership.character
        rows.append({
            "character": character,
            "in_use": character.character_id == settings.skills_character_id,
            "full_access": has_full_access(user, character.character_id),
        })
    return rows
