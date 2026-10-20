# Corporation roles in EVE Online: what each role lets a member do

*For The Orlov Family's CEOs and directors. Written 2026-10-13 from EVE University's "Managing corporation members" page and the in-game role descriptions; check the role window in game when CCP changes something. Roles are set in the corporation window under Members → Role Management; titles bundle roles under Title Management.*

## How roles work

- **Granting.** The CEO, any Director, and anyone who holds a role as *grantable* can give that role to others. Director itself can only be given by the CEO and can never be made grantable.
- **Grantable vs. plain.** A plain role lets the member do the thing. A grantable role also lets them hand that same role to others. Give grantable roles sparingly.
- **Titles.** A title is a named bundle of roles (plus an optional vanity label on the character sheet). Only the CEO or Directors assign titles; one title can be given to many members. Use titles for recurring jobs ("Hauler", "Recruiter") so a member gets the right set in one click.
- **Three places for hangar and container access.** Hangar roles come in three flavours: *Headquarters* (the corp HQ), *Based At* (the station or structure the member's "base" is set to) and *Other* (every other office). Give the flavour the member actually works from.
- **Pairings matter.** Several roles only do something together with another one: a Contract Manager needs a wallet division and hangar Take, a Factory Manager needs a hangar Query and a Rent slot, a Trader needs a wallet division. The tables say so.

## The Communications Officer in full

The role the owner asked about for bulletins. A Communications Officer can:

- **Corporation bulletins:** add, edit and delete the bulletins shown in the corporation window to every member.
- **Corp channel message of the day:** edit the MOTD of the corporation chat channel.
- **Calendar:** create and edit corporation events, and alliance events where the corp is allowed to.
- **Corp bookmarks:** edit or delete bookmarks other members made in the corporation's bookmark folders.

They cannot see wallets or hangars, cannot accept applicants, cannot change standings, and cannot touch structures. It is the narrowest role that covers bulletins, which Directors and the CEO can also do anyway.

## Worked example: the "Recruiter" title (owner, 2026-10-17)

Wanted: send corporation invitations, handle applications, keep the bulletins and the corp chat MOTD. Not wanted: shares, wallets, hangars beyond what their other titles already give, sensitive corporation settings.

| Give | Why |
|---|---|
| **Personnel Manager** (plain, not grantable) | Invitations and applications: accept or reject, invite characters, recruitment adverts (confirm the advert part in the role tooltip in game; the wiki only lists applications and decorations). Cannot kick. |
| **Communications Officer** (plain) | Bulletins, corp chat MOTD, corporation calendar events. Nothing financial. |

That is the whole title. Everything on the "keep away" list is covered by *not* giving the rest: shares are Director/CEO only; wallets need Accountant, Junior Accountant, Account Take, Trader, Contract Manager or Rent roles, none of which are in the title; hangars need Hangar Query/Take or Container Take, none given, so the member keeps exactly the hangar access of their other titles; settings, standings, structures and SKINs need Director, Diplomat, Station Manager, Config Equipment or Brand Manager. Do not tick *grantable* on either role, or the recruiter can hand them on. Build it as a title (Title Management → new title "Recruiter" with those two roles) so the next recruiter gets the same two clicks.

Two things a Personnel Manager can do that are worth knowing: award decorations (medals, cosmetic, free) and see the member list in detail. Neither touches money or assets.

## Worked example: a director with limited exposure (owner, 2026-10-20)

Wanted: the corp's first director runs the corp day to day, with **full access to hangar divisions 4 to 7** and **one wallet, division 4**. Not wanted: hangar divisions 1 to 3 (the owner's only), every other wallet division, the journals of the other wallets.

The one rule that decides the build: **the Director role cannot be limited.** It is "everything", including every hangar, every wallet and the right to hand out any role, and it is CEO-only to give. So a director with limited exposure must **not** hold the Director role; everything else is given as a title. If the role was already given, take it away first (Role Management → the member → untick Director).

The title, built once under Title Management as "OARMI Director" and assigned to the member:

| Area | Roles in the title | Why |
|---|---|---|
| Hangars 4 to 7 | Hangar Query 4, 5, 6, 7 · Hangar Take 4, 5, 6, 7 · Container Take 4, 5, 6, 7, each in **all three places** (Headquarters, Based At, Other) | See, take and move containers in the four open divisions wherever the corp has an office. Divisions 1 to 3 get no role at all. |
| Wallet 4 | Account Take 4 | Take and transfer ISK from division 4, and see that division in the wallet window. No other division appears. |
| People | Personnel Manager | Invitations and applications. |
| Words | Communications Officer | Bulletins and the corp chat MOTD. |
| Fits | Fitting Manager | Save and manage corporation fittings (the doctrine fits). |

Left out on purpose: **Accountant and Junior Accountant** (both show the balances of *every* division, Accountant the journals too; a director who may not see the other wallets gets neither; the division 4 journal then stays with the owner), **Trader** (buys with the corp wallet), **Contract Manager** (contracts in the corp's name need a wallet and a hangar Take: add only if wanted, with division 4), **Rent Office** (rent is paid by the corp), **Station Manager, Config Equipment, Diplomat, Brand Manager** (structures, standings, SKINs), **Factory Manager** (corp industry jobs; the owner's production runs under the owner's own characters). Do not tick *grantable* on anything: the director then cannot hand roles on.

Wallet side: give division 4 a name (Corporation → Wallet → the division's name, "Directors" for example) and move the working ISK into it. Corporation projects paid by the director must use division 4 as their payout wallet. The two bookkeeping rules of 2026-10-18 still hold: the master wallet (division 1) stays the owner's, the "Director" division (7) is the owner's shared personal wallet and never corp money.

What the director then sees: the four hangars in every office, one wallet with its balance, applications and invitations, bulletins, corp fits; not the first three hangars, not the other six wallets, not the shareholders, not the corporation settings.

## General roles

| Role | What it allows |
|---|---|
| Director | Everything: all roles and grantable roles, editing corp details, seeing shareholders, setting a member's base, seeing a member's active ship, kicking members. CEO-only to give. |
| Personnel Manager | Accept or reject applications, award decorations. Cannot kick. |
| Accountant | See corp bills, balances, journals and every wallet transaction; edit automatic payment settings. |
| Junior Accountant | See bills and wallet division balances only, no journal or transactions (with Trader: sees transactions). |
| Auditor | See who changed which member's roles and when. |
| Communications Officer | Bulletins, corp channel MOTD, corp and alliance calendar events, other members' corp bookmarks. |
| Diplomat | Add and edit the corp's standings toward player corporations and alliances. |
| Fitting Manager | Add, edit and remove the corp's recommended ship fittings. |
| Brand Manager | Create and apply SKINR designs to the corp's Upwell structures. |
| Config Equipment | Configure and unlock audit-log containers in corp hangars (needs Take on that hangar; not needed just to read logs). |
| Config Starbase Equipment | Anchor, unanchor, online, offline and configure starbases (POS), and use their fuel and ammunition bays. |
| Starbase Fuel Technician | Check and refuel starbases; cannot take fuel or anything else out. |
| Starbase Defense Operator | Operate the weapon and electronic-warfare batteries of starbases. |
| Contract Manager | Create contracts in the corp's name (needs a wallet division for the fee and Take on a corp hangar for the items). |

## Station and structure services

| Role | What it allows |
|---|---|
| Station Manager | Edit the settings of the corp's Upwell structures: docking rights, slot availability, services. |
| Factory Manager | Install, cancel and deliver manufacturing and research jobs with corp assets (needs at least Query on the hangar and a Rent slot role). |
| Rent Factory Slot | Rent manufacturing slots for the corp (useful only with Factory Manager and hangar access). |
| Rent Research Slot | Rent research slots for the corp (same). |
| Rent Office | Rent offices in the corp's name without wallet access. Careful: office rent is paid by the corp, so this can drain the wallet. |
| Security Officer | Look into members' personal hangars at stations with a corp office and put items in; cannot take items out. |
| Trader | Buy on the market with the corp wallet (needs an Account Take division; sees the transaction log only with Junior Accountant or Accountant). |

## Wallet divisions

| Role | What it allows |
|---|---|
| Account Take 1 | Take and transfer ISK from the master wallet (division 1). |
| Account Take 2 to 7 | The same for wallet divisions 2 to 7. |

Seeing the journal of a division needs Accountant on top; Take alone moves money blind.

## Hangar divisions (seven divisions, three places each)

| Role | What it allows |
|---|---|
| Hangar Query 1 to 7 | See the contents of that hangar division. |
| Hangar Take 1 to 7 | Take items out of that division. Also needed to open containers in it and to read their audit logs. |
| Container Take 1 to 7 | Move whole containers, vaults and warehouses out of that division. Without Hangar Take the member can move the container but not open it. |

Each of these exists as Headquarters, Based At and Other, so a hauler who works from the HQ only needs the Headquarters flavour.

Corporation projects: a project's deliveries land in a corp hangar and its payout comes from a wallet division, so whoever runs projects needs Query and Take on that hangar and Account Take on that division; see `docs/research/04-corp-industry-and-projects.md` for the hangar and blueprint side.

## Not on the wiki page

The in-game role window may show roles the EVE University page does not describe (for example a skill-plan or project related role added with newer expansions). Read the role's tooltip in game before giving it; this document follows the wiki and the role descriptions as of October 2026.

Source: https://wiki.eveuniversity.org/Managing_corporation_members
