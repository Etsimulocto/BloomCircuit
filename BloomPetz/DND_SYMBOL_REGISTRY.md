# BLOOM DND — Symbol Registry

## Rule
Every map glyph has exactly one global meaning. No duplicate meanings and no reusing a glyph for unrelated systems. Once a glyph is committed to a public save/game version, avoid changing its meaning.

The in-game B menu must include a SYMBOLS / GLOSSARY section that lists every registered symbol with its full description.

## Coordinate convention
Always use X x Y = width x height.

## Reserved player / aim symbols
- `@` — Player
- `^` — Aim north
- `>` — Aim east
- `v` — Aim south
- `<` — Aim west

These direction glyphs are temporary aim/attack indicators, not permanent terrain or entity symbols.

## World / terrain
- `.` — Floor
- `#` — Wall
- `+` — Closed door
- `/` — Open door
- `=` — Bridge
- `~` — Water
- `:` — Dirt / rough ground
- `"` — Grass
- `%` — Rubble
- `_` — Ledge / boundary

## Enemies
- `r` — Rat
- `g` — Goblin
- `s` — Skeleton
- `z` — Zombie
- `b` — Bat
- `o` — Orc
- `S` — Snake
- `W` — Wolf
- `M` — Mimic
- `D` — Demon
- `B` — Boss / boss-class enemy marker

## Objects / loot
- `!` — Potion / consumable pickup
- `$` — Gold / treasure currency pickup
- `?` — Unknown / unidentified object
- `k` — Key
- `c` — Chest
- `t` — Torch
- `w` — Weapon pickup
- `a` — Armor pickup
- `p` — Portal
- `&` — Shrine

## NPC / friendly entities
- `n` — Generic NPC
- `m` — Merchant
- `q` — Quest giver
- `f` — Friendly creature / ally
- `G` — Guard

## Temporary combat/effect glyphs
- `-` — Horizontal thrust / projectile trail
- `|` — Vertical thrust / projectile trail
- `x` — Physical hit / impact
- `*` — Magic effect / magical impact

## Important design rule
Generic pickup glyphs are allowed to represent a category, while the HUD/menu reveals the exact item.

Example:

`w` on the map means a weapon pickup. Inspecting or colliding with it can reveal:

```text
IRON LONGSWORD
Damage 4-9
Strength +2
```

This keeps the map language compact without sacrificing item variety.

## Glossary UI requirement
The B menu should contain:

```text
INVENTORY
CHARACTER
EQUIPMENT
QUESTS
SYMBOLS
SYSTEM MENU
```

SYMBOLS should open category lists such as:
- Player / Aim
- World
- Enemies
- Objects
- NPCs
- Effects

Menu entries use full words and horizontal marquee scrolling instead of forced abbreviations.

## Collision safety
Before adding any new glyph, check this registry first. If the character is already assigned, choose a different character. This applies even if the existing symbol is only used by a temporary effect.
