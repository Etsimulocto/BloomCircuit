# BloomPetz Idle D&D Game Ideas

## Core pitch
A tiny ASCII-first idle dungeon crawler that runs on the existing BloomPetz controller hardware:

- 128x64 OLED
- six conductive controls: UP / DOWN / LEFT / RIGHT / A / B
- two APA106 RGB LEDs
- optional sound later
- Raspberry Pi mirror/controller support

The whole game should feel like a pocket fantasy console: simple inputs, deep systems, tiny presentation.

---

## Main fantasy
You create an adventurer, enter an endless dungeon, move room-to-room on a small ASCII grid, fight monsters, collect gear, level stats, and keep progressing even when you are not actively playing.

Think:

- idle RPG
- roguelite dungeon crawl
- old-school terminal game
- D&D-flavored stats and loot
- infinite procedural rooms
- tiny tactical choices instead of twitch controls

---

## Controller mapping

### Exploration
- UP / DOWN / LEFT / RIGHT = move on room grid
- A = interact / open / confirm / attack
- B = character / inventory / back

### Combat
Possible simple scheme:
- LEFT / RIGHT = cycle target or action
- UP / DOWN = cycle combat options
- A = execute
- B = defend / back / item menu

Alternative ultra-fast scheme:
- A = attack
- B = defend / special
- arrows = move / target / stance

---

## ASCII visual language

Player:
```text
@
```

Enemies:
```text
g goblin
s skeleton
O ogre
D dragon
```

Objects:
```text
# wall
. floor
+ door
/ open door
^ trap
$ treasure
! potion
? mystery
> stairs down
< stairs up
* magic / effect
~ water
= bridge
% rubble
```

Example room:
```text
###########
#..g......#
#..###....#
#.@...$...#
####+######
```

The OLED does not need to show a huge map. Rooms can be small viewports or compact 8x4 / 10x4 tactical grids.

---

## Infinite dungeon structure

Use deterministic procedural generation from a seed.

Each room gets something like:

```text
floor
room_x
room_y
room_seed
room_type
encounter_seed
loot_seed
```

The game does not need to save every generated room forever. It can regenerate rooms from the world seed plus coordinates.

Possible room types:
- empty
- combat
- elite
- treasure
- trap
- merchant
- shrine
- camp
- puzzle
- event
- miniboss
- boss
- secret
- forge
- library
- cursed room

Every N rooms or floors, difficulty increases.

---

## Grid movement

Each room can use a very small tactical grid.

Example: 8x4 playable cells.

Movement matters because:
- melee requires adjacency
- ranged weapons have line/range limits
- hazards occupy cells
- enemies can chase
- doors become choke points
- treasure can sit behind danger

This gives the four directional inputs an actual game purpose instead of just menus.

---

## Player stats

Start with a manageable core set.

### Primary stats
- STR - Strength
- DEX - Dexterity
- CON - Constitution
- INT - Intelligence
- WIS - Wisdom
- CHA - Charisma

### Combat stats
- HP
- Max HP
- Armor
- Accuracy
- Evasion
- Crit Chance
- Crit Damage
- Block
- Initiative
- Move Speed

### Resource stats
- Gold
- XP
- Level
- Mana
- Stamina
- Luck

### Long-term / idle stats
- Dungeon Depth
- Rooms Cleared
- Monsters Defeated
- Bosses Defeated
- Treasure Found
- Distance Traveled
- Deaths / Knockouts
- Highest Floor
- Total Gold Earned
- Total Damage

Later we can absolutely go nuts with hidden stats like BloomPetz.

---

## Character classes

Good starting classes:
- Fighter
- Rogue
- Wizard
- Cleric
- Ranger
- Barbarian

Later:
- Paladin
- Warlock
- Monk
- Bard
- Druid
- Necromancer

Each class can mostly be stat weights + skill tables instead of separate giant code systems.

---

## Weapons

Basic categories:

### Melee
- dagger
- sword
- axe
- mace
- spear
- hammer
- greatsword

### Ranged
- shortbow
- longbow
- crossbow
- sling

### Magic
- wand
- staff
- tome
- orb

Weapon properties:
- damage
- accuracy
- speed
- range
- crit
- element
- durability optional
- rarity
- modifiers

Example:
```text
IRON SWORD
DMG 4-7
ACC +2
CRIT +1%
```

---

## Armor and equipment

Slots:
- weapon
- offhand
- head
- chest
- hands
- legs
- feet
- ring 1
- ring 2
- amulet

Could simplify on-device to:
- weapon
- armor
- accessory

while the desktop app exposes the full paper-doll inventory later.

---

## Item rarity

Simple rarity ladder:
- Common
- Uncommon
- Rare
- Epic
- Legendary
- Mythic
- Cursed

ASCII markers could help:
```text
. common
+ uncommon
* rare
! epic
@ legendary
# mythic
? cursed
```

The RGB bulbs can also communicate rarity without consuming OLED space.

---

## Loot generation

Item = base item + material + prefix + suffix + level scaling.

Examples:
- Rusty Sword of Sparks
- Iron Axe of Hunger
- Silent Bone Dagger
- Blessed Oak Staff
- Cursed Glass Ring

This gives us enormous item variety without storing thousands of hand-written objects.

Pseudo structure:
```text
base_id
material_id
prefix_id
suffix_id
item_level
rarity
seed
```

Regenerate the final stats from that compact data.

---

## Combat

Keep combat readable on four OLED lines when not in grid mode.

Example:
```text
GOBLIN HP 12/18
YOU HP 27/31
>ATTACK  ITEM
A DO     B BACK
```

Or run combat directly on the grid.

Basic loop:
1. player turn
2. enemy turn
3. status effects tick
4. check victory / defeat
5. loot roll

Useful conditions:
- poison
- bleed
- burn
- frozen
- stunned
- weakened
- blessed
- cursed

---

## Dice flavor

We can use D&D-style dice notation internally:
- d4
- d6
- d8
- d10
- d12
- d20

Examples:
```text
Longsword = 1d8 + STR
Dagger = 1d4 + DEX
Firebolt = 1d10 + INT
```

A short OLED roll animation could be adorable:
```text
D20...
[ 17 ]
HIT!
```

But the game should not need literal tabletop rules fidelity. Use the flavor without letting it become cumbersome.

---

## Idle system

The dungeon should continue meaningfully while idle without turning the player into an unattended suicide machine.

Possible idle modes:
- camp and recover
- train a stat
- craft
- identify items
- gather supplies
- auto-explore only previously-cleared safe zones
- send companion on expedition

When player returns:
```text
WHILE AWAY
+43 GOLD
+18 XP
2 ITEMS
A CLAIM
```

This is safer and more controllable than letting offline combat endlessly kill the character.

---

## Death / defeat

Avoid harsh save deletion.

Possible system:
- knocked out
- lose some carried gold
- return to last camp / floor checkpoint
- retain equipment and permanent progression

Roguelite option later:
- characters retire / fall
- account unlocks persist
- heir / next adventurer gains bonuses

---

## Town / hub

Between dungeon runs:
- Inn
- Blacksmith
- Shop
- Guild
- Temple
- Wizard
- Storage
- Quest board

ASCII hub menu:
```text
TOWN
>INN
 FORGE
 SHOP
```

The town can be menu-based initially instead of a full grid.

---

## Quests

Procedural quests:
- kill N monsters
- find item
- reach depth
- defeat elite
- survive cursed room
- recover relic
- escort / rescue event

Daily / long-form quests could give the idle system purpose.

---

## Monsters

Start small and table-driven.

Families:
- rats
- slimes
- goblins
- skeletons
- spiders
- bandits
- orcs
- cultists
- elementals
- undead
- demons
- dragons

Monster data:
```text
name
symbol
level
hp
attack
armor
speed
behavior
loot_table
```

Behaviors:
- chase
- flee
- ranged
- guard
- wander
- ambush
- swarm

---

## Bosses

Boss rooms should feel special even on a tiny screen.

Use:
- unique ASCII symbol
- LED animation
- special intro text
- multi-phase behavior
- guaranteed loot

Example:
```text
THE BONE KING
   [W]
HP 120/120
A FIGHT
```

---

## RGB LED use

The two APA106 bulbs can become part of game language.

Examples:
- red pulse = combat
- green = heal / safe room
- gold = treasure
- blue = magic
- purple = rare / cursed
- white flash = crit
- slow ember = campfire
- independent colors = status effects / dual magic

Keep normal ceiling at the existing 50% policy unless intentionally changed.

---

## Sound later

Tiny sound effects would add a lot:
- sword hit
- coin
- door
- damage
- spell
- treasure
- boss warning

No need for music initially.

---

## Inventory strategy

The OLED cannot comfortably manage hundreds of items, so split responsibility:

### Device
- equipped items
- recent loot
- consumables
- compact inventory shortlist

### Desktop app
- full stash
- sorting
- comparisons
- archive
- detailed item stats

Same philosophy as BloomPetz active slots vs desktop archive.

---

## Save strategy

Keep saves compact and deterministic.

Store:
- player state
- equipment seeds / IDs
- inventory IDs
- world seed
- current floor / coordinates
- discovered special rooms
- quest state
- counters

Do NOT save the entire infinite dungeon map if rooms can regenerate from seed + coordinates.

---

## Infinite content trick

The important architecture idea:

**Procedural systems should combine small authored tables.**

Example dungeon room =
```text
biome
+ room shape
+ enemy group
+ event
+ hazard
+ loot table
+ modifier
```

Example weapon =
```text
base weapon
+ material
+ rarity
+ prefix
+ suffix
+ item level
```

Small tables multiplied together = ridiculous variety.

---

## Biomes

Possible endless depth themes:
- Crypt
- Caves
- Sewers
- Ruins
- Forest Temple
- Ice Vault
- Lava Keep
- Abyss
- Clockwork Dungeon
- Mushroom Caverns
- Haunted Library
- Dragon Depths

Changing biome every several floors makes an infinite dungeon feel structured.

---

## Mystery / hidden systems

Very BloomPetz-compatible idea:

Track hidden long-term character traits based on play style:
- bravery
- greed
- mercy
- recklessness
- explorer
- treasure hunter
- monster hunter
- spell preference
- favorite weapon
- trap awareness
- survival instinct

These can quietly affect encounters, loot, titles, companions, and endings.

---

## Titles

Emergent titles are cheap and fun:
- Ratbane
- The Lucky
- Goblin Friend
- Gravewalker
- Treasure Rat
- The Unburned
- Door Kicker
- Deep Delver

Titles can be generated from actual stats instead of selected manually.

---

## Companions

Later, tiny ASCII companions:
```text
@ player
& companion
```

Types:
- dog
- raven
- slime
- fairy
- skeleton
- mercenary

Could eventually let BloomPetz creatures cross into the dungeon game as companions.

---

## First playable version

Do NOT build the giant system first.

### V0.1 target
1. title screen
2. one character
3. STR / DEX / CON / HP / XP / level
4. one weapon slot
5. 8x4 ASCII room
6. D-pad movement
7. doors between procedural rooms
8. three enemies
9. basic melee attack
10. gold + XP
11. random weapon drops
12. inventory/equip menu
13. stairs / dungeon depth
14. save/load
15. RGB combat / loot effects

If that is fun, everything else can grow from it.

---

## Architecture rule from BloomPetz

Before changing firmware:

1. inspect the live local `.ino`
2. identify the exact active engine/function
3. patch the smallest possible surface
4. compile
5. flash
6. test the physical controller
7. only then add the next system

Do not assume GitHub's conceptual architecture matches the currently working local firmware after rapid prototyping.

---

## Tomorrow's first design decisions

Decide:
- game name
- player symbol
- grid dimensions
- turn-based vs timed enemy movement
- starting stats
- first 3 enemy types
- first 5 weapon types
- save struct
- room seed formula
- whether each floor is a connected room graph or coordinate-based endless space

Then build the smallest playable dungeon loop before adding giant item/stat tables.

## Core vibe

BloomPetz is adorable.

This one should be adorable **and dangerous**.

Tiny screen. Six controls. Endless dungeon.

`@` goes down.
