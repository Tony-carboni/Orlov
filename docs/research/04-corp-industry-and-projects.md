# Corp-run industry: blueprints, hangars, Projects and payouts

*Research 2026-10-06. Question: how can OARMI make its blueprints available to members, have them build with materials from the corporate hangars, and pay them for it, using in-game mechanics only? What do Corporation Projects add, and what can be stolen?*

*Status of the facts: the Projects mechanics come from CCP's patch notes and support articles; the role and hangar mechanics from the EVE University wiki, CCP's Roles Listing and player reports. Two points could not be confirmed from documentation and are marked **verify in game**.*

## 1. The short version

- **Projects pay, they do not move items.** A Corporation Project states a goal, the game verifies contributions by itself, and ISK is paid per unit from a corp wallet. Hangar access, blueprints and materials are governed by the old corporation roles, not by Projects.
- **Blueprint originals can be made theft-proof** with the blueprint lockdown vote: locked, they can still be used for jobs but cannot be taken. Copies made from them can still leak.
- **Materials cannot be made theft-proof.** A job that consumes corp materials needs *Take* access on that hangar division, and Take access means the person can also carry the materials off. The only defences are to expose little, to log, and to trust few.
- **Manufacture projects pay when the job is installed, not when it finishes.** A builder can install, pocket the reward and cancel, which also destroys the materials. Pay the real reward on delivery of the product instead (Deliver Item project), or only let trusted builders install corp jobs.
- The low-risk version of all this is a **buyback**: members build with their own materials and blueprint copies and hand the product in through a Deliver Item project.

## 2. The building blocks

### 2.1 Corporate hangars

- A corp has hangars wherever it has an **office**: in NPC stations and in Upwell structures (for OARMI: an office in GWON's Raitaru "Orlov Family Facilities" in Isikano). Offices are rented from the structure owner; the owner sets the rent and can refuse renewals. Unpaid rent **impounds** the corp's assets there (not asset safety), and getting them back costs 50 % of the rent or a new office.
- Each office has **7 divisions** (rename them in the Corporation window). Access is granted per division and per office group: *Hangar Access (Headquarters)*, *(Based at)* and *(Other)*. For a member based elsewhere, the Raitaru office falls under *Other*.
- Per division there are two rights: **Query** (see the contents) and **Take** (remove items). There is no third right "use for industry only"; that is the root of the materials problem.
- **Take without Query** is the trick other corps use (verified 2026-10-06, see §2.4): a member who has Take but *not* Query on a division cannot open or see that division in the inventory, yet corporation jobs can still consume materials from it. The materials are hidden rather than locked, so it is protection against casual theft, not against someone who knows what is there and finds a way to address it. Test it with a cheap stack before relying on it.
- The **Deliveries** hangar receives corp market purchases. The **Projects** hangar (new with Projects) receives Deliver Item contributions: every member can drop into it, only the CEO and directors can take from it, and its access cannot be changed.
- Containers in a hangar can be set to **log** who locked and unlocked which items; that is the only audit trail short of the corp's asset journal.

### 2.2 Roles that matter for industry

| Role | What it allows | Risk |
|---|---|---|
| **Factory Manager** | Lists and uses *all* corp-owned blueprints in the Industry window, whatever hangar they are in, and can set up, deliver **and cancel** corp jobs, including other people's | Can cancel anyone's corp job (materials are lost on cancel); can run copy and research jobs on corp originals |
| **Rent Factory Facility** | Required to install jobs *on behalf of the corporation* | None by itself |
| **Hangar Query** (per division) | See the division | None |
| **Hangar Take** (per division) | Remove items; also required for a job to consume materials from that division | Can take everything in that division |
| **Accountant / Junior Accountant** | Wallet access; a Project Manager needs access to one wallet division to fund a project | Can see and (Accountant) spend that wallet |
| **Project Manager** | Create, close, clone and delete Corporation Projects (CEO and directors have this anyway) | Can spend a wallet into project escrow |
| **Lock / Unlock Blueprint** | Start the lockdown or unlock vote for a blueprint original | None |

A builder who should use corp blueprints *and* corp materials therefore needs **Factory Manager + Rent Factory Facility + Take on the materials division** (+ Query on the blueprint division). The forum consensus is blunt: "No sane CEO or Director would give out a Factory Manager role to random people." Treat it as a director-level trust.

### 2.3 Blueprint lockdown

- A corp-owned **original** in a corp hangar can be **locked** through a corporation vote (Corporation window → Votes; the *Lock Blueprint* role or CEO starts it). The blueprint is locked from the moment the vote starts and stays locked if it passes. Locked originals **can still be used for industry jobs** at that office but **cannot be moved or taken**; releasing them needs an unlock vote. *Verify in game:* vote duration and who may vote (shareholders) for OARMI.
- Lockdown protects the **original** only. Anyone with Factory Manager can run a **copy job** and get blueprint copies delivered; whoever has Take on the delivery division can walk off with the copies. For T1 ship and module BPOs that is a nuisance; for expensive, well-researched originals it is a real leak.
- *Verify in game:* for corporation jobs, which division the finished product and the blueprint are delivered to, and whether the installer can choose that division. If the installer can route output to a division they have Take on, the protection of the product depends on where the output goes, not on where the materials came from. Test with a cheap blueprint before stocking anything valuable.

### 2.4 Is Take access really required? (checked 2026-10-06)

The owner heard that other corporations run corp jobs without even giving view rights on the material hangar. Both things are true at once:

- **Take is required.** CCP's Roles Listing, quoted word for word in two forum threads (2018 and 2023): Factory Manager "allows the listing and use of all corporation owned blueprints within the 'Blueprints' tab of the Industry window, independent of corporation hangar access. Proper 'Take' Access to the respective Hangars or containers is still required for any job requiring input materials." A player who tested it after Projects came out (December 2024) found the same: "In order to set a job a player must have access to take from a hangar."
- **Query is not required.** In a 2017 thread a CEO who wanted exactly our setup reported: "well i needed to only set take on division 2. Now nobody can see the materials (and take at will) in division 2 but still able to use the materials inside the hangar." That is what "no view rights" means in practice: Take without Query. Members cannot browse the division, so they cannot drag items out, while the industry window still pulls from it.
- **Blueprints** are the other half of the story: thanks to Factory Manager they can be used with no hangar access at all (Query on their division is enough to make them visible, and lockdown keeps them in place).

So the recommended division layout becomes: blueprints in a division with Query only (locked originals), materials in a division with **Take only**, products delivered to a division the builder has neither right on (*verify in game* that the output can be routed there, §2.3).

### 2.5 Corporation Projects

- Created by the CEO, directors or a member with the **Project Manager** role. Up to **100 active projects** per corp. Projects can be **cloned** for recurring builds.
- **Funding:** the creator picks a corp wallet division as active; the project's whole budget is moved from that wallet into **escrow** at creation. Each contribution earns the member an entitlement that reduces the escrow. Members **claim** their ISK from the project window; unclaimed entitlements are paid out automatically after 30 days. Cancelling a project returns what is left in escrow to the master wallet. Managers see the escrow total and every contributor's earnings.
- **Verification is automatic:** the game counts the contribution itself; nobody has to check screenshots or hand out ISK by hand.
- Project types useful for industry:

| Type | Contribution | Settings | Paid |
|---|---|---|---|
| **Manufacture** | **Installing** a manufacturing job for the chosen item at the chosen station or structure. "On the behalf of" decides whether private jobs, corporation jobs or both count | Item type, facility, number of units, ISK per unit, on behalf of | Per unit of product in the installed job, at installation |
| **Deliver Item** | Dropping the chosen item into the corp's **Projects** hangar at an office | Item type, quantity, ISK per unit | Per unit delivered |
| **Mine Materials** (older type) | Ore mined in the chosen system or type | Ore type, system, quantity, ISK per unit | Per unit mined |

- What Projects **cannot** do (as of 2025): hand items *out* to members. There is no "collect your materials here" project type; players asked for it in August 2025 and CCP has not added it. Handing out still means contracts, a shared hangar or manual delivery.

## 3. How one build run works (corp blueprints + corp materials)

1. OARMI rents an office in the Raitaru. Divisions, for example: 1 *Blueprints*, 2 *Build materials*, 3 *Finished goods*, 4 *Main stock* (nobody but directors).
2. Blueprint originals go into division 1 and are **locked** by vote.
3. A director moves exactly the materials for the planned run from 4 into 2.
4. A builder with Factory Manager + Rent Factory Facility, Query on 1 and Take (no Query) on 2 opens the Industry window, picks the corp blueprint (Blueprints tab, filter "corporation"), sets the owner to the corporation and installs the job. Materials are consumed from 2; the job fee is paid by the corp (the structure's industry tax goes to GWON as the structure owner).
5. A **Manufacture** project ("on behalf of: corporation", item, Raitaru, N units, X ISK per unit) credits the builder at installation.
6. When the job finishes, the builder (or any Factory Manager) delivers it; the product lands in a corp division (*verify which*, §2.3). The corp sells it, uses it, or hands it out.
7. The builder claims the ISK from the project; the CEO sees the contribution list.

## 4. Scenarios

### Scenario A — "The corp supplies everything" (what was asked for)

*Corp blueprints, corp materials, members build, corp pays per unit.*

- **Setup:** §3. Roles only for a handful of proven builders. Materials division with **Take but no Query** (§2.4), stocked per run, main stock elsewhere. Originals locked.
- **Payout:** Manufacture project per unit installed. Because installation pays, pair it with a small per-unit amount at installation and put the bulk of the reward in a **Deliver Item** project for the finished product, so a cancelled job earns nothing worth having.
- **Exposure:** everything in the materials division at any moment, every blueprint copy that a builder can have delivered to a division they can take from, and every running corp job (a Factory Manager can cancel it).
- **Good for:** a small circle of trusted industrialists who have no capital of their own; production that must be corp-owned (doctrine ships for a corp hangar, structure fuel, moon-goo reaction chains).
- **Admin:** a director restocks division 2 per run and moves products out; the project is cloned for each batch.

### Scenario B — "Buyback" (lowest risk)

*Members build with their own materials and their own blueprints or copies; the corp buys the product.*

- **Setup:** one Deliver Item project per product with the ISK per unit you are willing to pay (typically a few per cent under market, or above market if you want to steer production). Nothing in the corp hangars is exposed; the members never need a role.
- **Payout:** automatic per delivered unit; the product sits in the Projects hangar for the CEO or a director to collect.
- **Good for:** many members, newcomers, anything where the corp just wants the output. Also for **sourcing materials**: a Deliver Item project for minerals or ore is a buyback that fills division 4 of Scenario A.
- **Downside:** members need capital or copies; the corp's blueprints are not used at all unless you run Scenario D with it.

### Scenario C — "Hybrid pipeline"

*Miners deliver, trusted builders build, the corp sells or distributes.*

1. **Deliver Item** projects for ore or minerals (and for moon ore from the Athanor) fill the corp stock; miners are paid per unit.
2. Two or three trusted builders run Scenario A on that stock.
3. Products are sold on the market by someone with the *Trader* role, kept for doctrine fits, or handed out by contract.
- This is the model most industrial corps end up with. The theft exposure is limited to the builders' circle; everybody else only ever drops items in.

### Scenario D — "Blueprint copy service"

*Members use the corp's research without the corp risking the originals.*

- A Factory Manager runs copy jobs on the locked originals and hands the **copies** to members by contract (or the copies are dropped in a division members can take from, if you accept that they then belong to whoever takes them first).
- Members build with their own materials; the corp buys back through Deliver Item (Scenario B) or members simply keep the product.
- Exposure: only the copies, with their limited runs. The originals and the material stock are never touched.

### Scenario E — "What a bad actor can do" (by role)

| They hold | They can |
|---|---|
| Nothing (plain member) | Drop items into the Projects hangar; nothing else |
| Query on a division | See what is there (and tell others) |
| Take on a division | Empty that division at any time; corp containers slow this down and log it only if set up |
| Factory Manager | Cancel every running corp job (materials gone), run copy and research jobs on every corp original, deliver finished jobs |
| Factory Manager + Take on the output division | Take finished products and blueprint copies |
| Project Manager + wallet access | Create a project that pays themselves; the budget is visible and the project list shows who created it |
| Director | Everything above plus the Projects hangar and the lock votes |

None of this is reversible by CCP: theft inside a corporation is allowed by the game rules. The Audit Log and the asset journal tell you who, not how to get it back.

### Scenario F — payout maths

Example: 20 Ventures for a newbie fleet.

- Materials: about 1.5 million ISK per Venture at 2026 mineral prices (check in game), 30 million for the batch, moved into division 2.
- Manufacture project: 20 units, 200 000 ISK per unit at installation → 4 million in escrow.
- Deliver Item project: 20 Ventures, 800 000 ISK per unit on delivery → 16 million in escrow.
- A builder who installs and delivers all 20 earns 20 million for roughly an hour of work; a builder who installs and cancels earns 4 million and has cost the corp 30 million in minerals, which is why the installation part is kept small and the roles stay with trusted people.
- Both escrows come out of the chosen corp wallet division at project creation, so the wallet must hold 20 million before the projects can be made; leftovers return on cancellation.

## 5. Setup checklist for OARMI (when this is wanted)

1. Office in the Raitaru (Structure Browser → Orlov Family Facilities → Offices; GWON sets the rent).
2. Rename the divisions; decide which one members can Take from.
3. Move originals in, start the lockdown votes.
4. Titles: a "Builder" title bundling Factory Manager, Rent Factory Facility, Query on the blueprint division and Take (without Query) on the materials division (Other-office group). Give it to named people only.
5. Wallet division for industry; Junior Accountant for whoever runs the projects, or let a director do it.
6. First test run with one cheap blueprint and one builder: install, deliver, note **where the product and the blueprint ended up**, then cancel a second job to see what the cancel does. Update §2.3 of this document with the answers.
7. Create the Manufacture and Deliver Item projects, clone them per batch.
8. Optional on auth: Member Audit already shows who has which roles; no extra app is needed for Projects.

## 6. Open points to verify in game

- Output division and blueprint return for corporation jobs, and whether the installer chooses it.
- Lockdown vote: duration, quorum, whether the CEO alone (as sole shareholder) passes it.
- Whether a Manufacture project set to "on behalf of: corporation" also counts jobs that use a corp blueprint but private materials.
- Industry tax the Raitaru charges corp jobs of a tenant corp (set by GWON).

## 7. Sources

- CCP, [Stronger Organizations](https://www.eveonline.com/news/view/stronger-organizations) (Havoc: Manufacture project type, automatic payouts, Project Manager role)
- The Nosy Gamer, [EVE: Havoc patch notes, Corporation Projects](https://nosygamer.blogspot.com/2023/11/eve-havoc-patch-notes-corporation.html) (escrow, per-unit reward, installation counts)
- Skoli, [Corporation Projects in EVE Online](https://skoli.ru/en/post/2884) (project settings, claiming, 30-day auto payout)
- CCP support, [Corporation Projects](https://support.eveonline.com/hc/en-us/articles/9583433729308-Corporation-Projects) (Projects hangar, 100 active projects) and [Roles Listing](https://support.eveonline.com/hc/en-us/articles/203217712-Roles-Listing) (Factory Manager, Rent Factory Facility, Lock Blueprint)
- EVE University wiki, [Corporation logistics](https://wiki.eveuniversity.org/Corporation_logistics) (divisions, lockdown, Deliveries hangar, container logs) and [Managing corporation members](https://wiki.eveuniversity.org/Managing_corporation_members) (Query vs Take, office groups)
- EVE forums, [[SOLVED] Shared industry](https://forums.eveonline.com/t/solved-shared-industry/23035) (2017: Take without Query works for materials), [Sharing corp blueprints](https://forums.eveonline.com/t/sharing-corp-blueprints/123563) (2018: Factory Manager text, blueprints without hangar access), [Industry Projects are useless for generating corp engagement](https://forums.eveonline.com/t/industry-projects-are-useless-for-generating-corp-engagement/470209) (2024: Take still required after Projects)
- EVE forums, [Manufacturing roles in corporations suck](https://forums.eveonline.com/t/manufacturing-roles-in-corporations-suck/429556) (role pairing, cancel and install-then-cancel abuse), [Corp industry without hangar access](https://forums.eveonline.com/t/corp-industry-without-hangar-access/447213) (no use-only access to materials, container logging), [Corp Projects: reverse delivery](https://forums.eveonline.com/t/corp-projects-reverse-delivery/496816) (no hand-out project type)
- EVE forums, [What happens to corp offices when a structure is transferred](https://forums.eveonline.com/t/what-happens-to-corp-offices-in-structures-when-structure-is-transferred-to-new-owners/399164) (office rent, impound)
