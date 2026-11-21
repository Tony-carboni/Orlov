# Blacklist

Pilots removed from the alliance, the corporation or the Discord server who must not come back (owner, 2026-11-21: "start a blacklist log; if we accidentally let these pilots back in, flag it in the director chat"). The bot reads this table every morning (runbook 25): a listed pilot found in an alliance corporation, registered in auth with member access, or present on the Discord server is reported in `#oarmi-directors`.

Rules for the table: one row per pilot; the character ID is the EVE character id (the bot resolves it from the name when the column is empty); the Discord ID is the Discord user id when known, else empty; dates are EVE time. Known alts of a listed pilot get their own row with "alt of X" in the reason. Add a row by asking a session; the bot picks the file up at its next check, no restart needed. Keep this copy and the server copy (`~/aa-docker/orlovbot/blacklist.md`) the same.

| Pilot | Character ID | Discord ID | Removed | Reason |
|---|---|---|---|---|
| N1KO D95 | 1283156766 | | 2026-11-19 | Removed from OARMI (in the corp 10 to 19 November; auth account N1KO_D95 never linked Discord). Now in Omega Industrial Group, Forge Consortium. Owner's instruction 2026-11-21. |
| Kitten Kerns | 95662236 | 1561149281300123808 | 2026-11-14 | Banned from the Discord server by the owner on 14 November (Discord dominikstarz); locked out of Family Member on 20 October, unlocked 31 October after his character left OARMI. Now in The Order of Omerta, Hole Control. Auth account Kitten_Kerns (Family Friend). |
| zzioxx | 2124770412 | 1083839910185799782 | 2026-11-16 | Banned from the Discord server by the owner on 16 November (Discord .amaoui, auth account zzioxx, registered 10 October). Character still in OARMI on 21 November. |
