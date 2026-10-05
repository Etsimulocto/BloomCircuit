# BLOOM DND — Game Spec V0.1

## Core goal
A tiny real-time-ish ASCII dungeon crawler for the BLOOM SYSTEM controller. Movement is free until collision/interactions wake up the RPG systems. The game should feel immediate, readable, persistent, and brutal without becoming menu-heavy.

## Screen model
Coordinate convention is always X x Y = width x height.

### Current proven hardware layout

The physical SSD1306 uses the full practical 21-character width with the current 6x12 font:

- Total text width: 21 x 4
- HUD: 7 x 4 on the left
- Map viewport: 14 x 4 on the right
- No BloomPetz side-art/gutters while DND is active

Example:

```text
HUD....##############
HUD....#............#
HUD....#............#
HUD....##############
```

The HUD and map are concatenated directly. There is no separator column.

The Raspberry Pi companion mirrors the same 21 logical columns. It must not expose a wider dungeon than the physical OLED. The Pi app measures its local monospaced font so all 21 columns fit its 192 px mirror without clipping.

## Controls
- D-pad alone: free movement, one grid cell per press.
- A: action modifier / action button.
- Current touch implementation emits one event per touch, so V0.1 directional attacks use: tap A, then tap a direction within about 700 ms.
- B: menu / HUD menu / back.
- Menu includes RETURN TO BLOOM SYSTEM.

Player symbol is `@`.
Directional aim/attack indicators may temporarily use `^`, `>`, `v`, `<`.

## HUD behavior
The current HUD is 7 columns wide and 4 rows high.

### Top HUD row
Dedicated contextual action/event feed.

It can show:
- current action
- roll
- response/result
- damage
- reward
- discovery

Examples of underlying messages:
- ATTACK GOBLIN
- ROLL D20
- HIT 17
- DAMAGE 6
- GOBLIN DOWN
- +8 XP
- FOUND KEY

Rows support horizontal marquee scrolling. Do not abbreviate labels merely to fit the viewport.

### Bottom 3 HUD rows
These are rotating status rows. They auto-scroll vertically through a larger status pool and each individual row can also scroll horizontally.

Possible entries include:
- Health 12/18
- Armor Class 14
- Level 3
- Experience 43/100
- Gold 27
- Iron Longsword
- Poisoned
- Torch 62%

No requirement that the same three statuses remain permanently visible.

## Menu behavior
Menus also prefer full words and numbers over abbreviations.

- Rows can horizontally marquee if content is longer than the visible width.
- Selected row begins scrolling first.
- Moving selection resets that row to the start.
- A selects.
- B backs out.

Current implemented menu categories:
- Character
- Inventory
- Symbols / Glossary
- System Menu

Planned categories may later include:
- Equipment
- Quests

## Movement and interaction model
The world is not turn-based on every empty tile.

Player movement is free through walkable tiles.

When a movement attempt collides with an entity or interactive object, that collision triggers the appropriate RPG interaction/roll.

Examples:
- enemy -> combat/contact roll
- chest -> open/lock roll
- trap -> save roll
- shrine -> interaction/luck/faith roll
- locked door -> lockpick/break roll
- NPC -> dialogue / social roll
- unknown object -> discovery roll

The map remains visible while the HUD narrates the event.

## Weapons
Weapons can be used at any time with directional input plus A behavior.

Weapons should differ by grid behavior, not only damage values.

Starter weapon families:
- Sword: range 1, reliable melee.
- Dagger: range 1, lower damage, improved crit/bleed behavior.
- Axe: range 1, heavy damage, armor/door breaking potential.
- Spear: range 2 straight line.
- Hammer/Mace: range 1, stun/armor damage potential.
- Bow: projectile travels straight until collision.
- Crossbow: heavier ranged shot, slower reload.
- Wand/Staff: directional magic projectile.
- Whip: range 2, possible pull effect later.
- Shield: defensive equipment with optional directional bash.

Useful weapon data fields:
- damageMin
- damageMax
- range
- hitBonus
- critChance
- speed/cooldown
- damageType
- specialEffect

Possible effects:
- bleed
- stun
- burn
- poison
- pierce
- knockback
- lifesteal
- chain
- cleave

## Combat flow
Combat should stay in-world rather than switching to a separate combat screen for every hit.

Typical event sequence:

```text
ATTACK GOBLIN
ROLL D20
+3 STRENGTH
TOTAL 17
HIT
DAMAGE 5
GOBLIN DOWN
+6 XP
+3 GOLD
```

The top HUD row plays this event queue while the map remains visible.

## Enemy movement
Enemies move independently of the player at slow per-entity intervals.

They are not required to wait for player input.

Behavior can include:
- wander
- chase
- wait
- flee
- interact with environment

Example timing ranges for initial tuning only:
- Rat: 500–900 ms
- Bat: 400–700 ms
- Goblin: 900–1400 ms
- Skeleton: 1200–1800 ms
- Zombie: 1800–2600 ms

World simulation freezes while blocking menus are open so the player cannot be killed while reading inventory, stats, or the symbol glossary.

## Dice / stats direction
Use recognizable tabletop-style rolls without reproducing full tabletop rules.

Core stats can begin with:
- Strength
- Dexterity
- Constitution
- Intelligence
- Wisdom
- Charisma
- Health
- Armor Class
- Level
- Experience
- Gold

V0.1 may use a smaller subset while systems are proven.

## Current playable hardware slice

The following is already working on the ESP32-S3 hardware:

- 14 x 4 map viewport
- 7 x 4 scrolling HUD
- `@` player
- free D-pad movement
- tap A then direction within about 700 ms for directional attack
- collision-triggered rolls
- independently timed Rat / Goblin / Skeleton movement
- Health / Strength / Dexterity / Armor Class / Experience / Gold / Level HUD data
- Iron Sword starter weapon
- Chest, Gold, Potion, Door, Trap interactions
- Character / Inventory / Symbols / System Menu
- full-width physical OLED rendering
- Raspberry Pi 21-column mirror/controller
- return to BLOOM SYSTEM

This is still a hardware proof slice rather than the finished game. Save/load, equipment swapping, procedural room generation, expanded items, classes, quests, and long-term persistence remain future work.

## World structure
The dungeon should become procedurally generated and effectively infinite without storing a giant world map.

Room generation should be reproducible from values such as:
- world seed
- depth/floor
- room X/Y
- biome
- special flags

Room types may include:
- combat
- treasure
- shrine
- trap
- merchant
- camp
- puzzle
- cursed
- secret
- boss
- rare event

## Persistence ideas
Long-term goal: the dungeon remembers meaningful events.

Examples:
- escaped enemies can reappear later
- named/scarred enemies can persist
- an enemy that steals an item may later carry that exact item
- dead player remains can appear in a later run
- rooms can gain persistent marks or state

## Time integration
The BLOOM SYSTEM host-time clock is shared by all games.

DND can eventually use real date/time for:
- daily dungeon modifier
- daily merchant inventory
- daily quest
- daily heal/reward
- date-seeded rooms/events

## Display ownership contract
DND owns the full OLED while active.

Background BloomPetz services must not repaint the display during DND. In particular, the decorative side-art refresh previously repainted the shared BloomPetz screen buffer every ~120 ms and caused DND/BLOOM SYSTEM flicker. That repaint path is now gated off while DND is active.

DND's renderer also updates the shared mirror rows so the Pi companion receives the current game frame.

## V0.1 next scope
Build outward from the proven hardware loop:

- preserve 7 HUD + 14 map geometry
- procedural rooms
- inventory expansion
- equipment swapping
- save/load
- symbol registry cleanup and locking
- additional enemies/items
- one simple generated dungeon biome
- room-to-room traversal

Expand classes, spells, crafting, factions, companions, advanced loot, idle expeditions, and persistent world events only after the core movement/combat loop remains solid on hardware.
