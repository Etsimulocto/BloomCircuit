# BloomPetz — Project Treatment and Build Brief

## Vision

BloomPetz is a small handcrafted desk companion that lives inside a wood-and-brass box. It combines a 128×64 OLED, six copper conductance touch wires, two lights, sound, a rechargeable battery, and an ESP32-S3 into a persistent digital pet platform.

The device behaves like a tiny old-school game system with a living companion inside it. The pet idles, reacts to touch, plays minigames, completes daily interactions, accumulates statistics, and remembers its history indefinitely.

## Current Prototype Status

BloomPetz is no longer only a treatment. The v0.1 vertical slice is running on the HAPPY JARZ ESP32-S3 platform.

Current working pieces include:

- ESP32-S3 SuperMini firmware
- SSD1306 128×64 four-line OLED
- six copper capacitive controls
- two APA106 lights
- three persistent pet slots
- on-device CREATE PET / EDIT PET
- printable-ASCII pet name, type, and symbol/art editing
- eight daily developmental actions
- Simon-style D-pad action challenge
- food energy and treats
- 200 persistent developmental floats
- 20-category / 200-stat on-device browser
- rotating pet sayings
- HOME-screen live stat ticker with marquee behavior for long text
- decorative scrolling particle art on the physical OLED
- Raspberry Pi mirror/controller with matching side particles
- USB screen/input protocol
- ESP32 Preferences-backed persistence

## Existing Platform

The Happy Jarz electronics platform provides the foundation:

- ESP32-S3 controller
- four lines of text per screen
- scrolling menus
- minigame support
- screensaver capability
- six fast copper conductance inputs
- two lights
- sound-output path
- rechargeable-battery system
- small handmade enclosure format

BloomPetz is a software and content layer built on this hardware.

## Controls

The six copper touch wires form a compact gamepad:

```text
UP       DOWN       LEFT
RIGHT    A          B
```

Current firmware behavior uses qualified taps with one event per touch. Navigation and game behavior depend on the active screen.

## Current Main Menu

The working v0.1 hardware menu is:

```text
FEED
TREAT
SLOT
EDIT PET / CREATE PET
STATS
```

The 128×64 OLED shows three menu rows at once and reserves line 4 for controls. The selection scrolls vertically through all five items.

Example lower menu view:

```text
  SLOT 1
  EDIT PET
> STATS
A ENTER B BACK
```

The longer-term product may grow additional top-level sections such as PLAY, QUESTS, COLLECTION, SCREENSAVERS, and SETTINGS, but those are roadmap items rather than the current v0.1 hardware menu.

## Pet System

Each pet currently stores:

- Name
- Type
- one-line ASCII design/art
- persistent ID and dates
- lifetime action/touch/treat counters
- food energy
- daily treats and completed-action flags
- 200 developmental stat values

Future pet packages can expand this with sprite frames, idle animations, personality content, sounds, favorite minigames, quest rules, unlock conditions, screensavers, and evolution behavior without changing the core electronics.

The system should remain expandable to many pet types and content packs.

## Persistent Stats

BloomPetz currently maintains 200 developmental floats arranged as 20 canonical categories with 10 named stats each.

Canonical mapping lives in `data/stats/stat_manifest.json`; each category points to its corresponding JSON file. Index ordering is part of the save format and must not be casually reordered after public saves exist.

Current categories include:

- Bond / Social
- Courage / Mental Strength
- Intelligence
- Curiosity / Discovery
- Creativity
- Strength / Body
- Defense
- Speed / Movement
- Energy
- Health
- Food / Nutrition
- Cleanliness / Care
- Emotional
- Personality
- Habits
- Fidget / Input Personality
- Memory / Sequence Skills
- Luck / Rare Traits
- Growth / Evolution
- Weird / Hidden

The full model is viewable directly on the device through the STATS browser. The companion app can later provide richer graphs, sorting, history, and comparisons.

## Home Screen

Current HOME layout:

1. Pet art/symbol alternating with short pet sayings; long sayings marquee.
2. Pet name alternating with live stat/value text; long stat strings marquee.
3. Current daily action.
4. A/B controls plus rotating compact energy/treat/action status.

Decorative particles scroll down the left/right OLED gutters and matching lanes are present in the Pi mirror app.

## Pet Care Loop

The current daily loop uses eight actions:

- CHECK
- CLEAN
- PET
- PLAY
- REST
- SCRATCH
- SOCIALIZE
- TRAIN

A successful first completion for the day applies 25 developmental-stat rolls, with favored categories depending on the action. Gain scales with response speed from approximately 0.0001 to 0.0050 per roll.

Each rewarded action costs 12.5 energy. Replaying an action later that day is allowed for fun but does not award the daily developmental reward again.

Feeding is intentionally simple: food only refills when empty, restoring energy to 100. Treats are capped at three per day and each rolls one random developmental stat. Midnight resets daily actions and treats but not food energy.

The design goal remains non-punitive: needs should create personality and reasons to return without making the device stressful or demanding.

## Minigames

The current active-play slice uses a randomized three-direction Simon-style sequence controlled by the D-pad touch inputs.

Future games can include:

- Catch the falling item
- Expanded memory sequences
- Tap timing
- Dodge the obstacle
- Bubblefire practice
- Treasure hunt
- Pet reaction challenge

Games can award development, score, unlocks, or collection progress depending on the future content layer.

## Screensavers

Screensavers remain a major product direction. They should be able to run indefinitely while the pet is idle or sleeping.

Possible screensavers include:

- Sleeping pet
- Starfield
- Aquarium
- Fireplace
- Tiny forest
- Rainy window
- Space flight
- Dream sequence
- Seasonal scenes
- Rare hidden animations

The current prototype already has the rendering/control foundation needed for later screensaver content.

## Lights and Sound

The two APA106 lights provide a second emotional channel outside the display. Current firmware already uses light feedback during calibration and action play.

Future uses include:

- Mood indicator
- Hunger or alert state
- Quest completion
- Level-up reward
- Charging status
- Rare event effect
- Damage, surprise, or bubblefire reaction

Sound remains part of the platform direction for chirps, menu clicks, confirmation tones, sleep sounds, rewards, warnings, and minigame effects.

## Companion App

BloomPetz remains playable from the physical device. The companion app is additive rather than required.

The current Raspberry Pi mini app:

- mirrors the four OLED lines over USB
- accepts keyboard arrows plus A/B through the same firmware input path
- uses app-only readable color themes
- mirrors decorative side-particle lanes
- can auto-launch when the board is connected

Future app functions can include:

- pet library/archive
- full statistical history and graphs
- backup/restore
- pet/content installation
- firmware updates
- device settings
- community content

## Update Model

The ESP32 firmware contains the core engine. Pet and content packages should stay separated from the engine wherever practical.

Recommended layers:

1. Core firmware
2. Pet definitions and stats
3. Sprite and screensaver assets
4. Minigame definitions
5. Quest definitions
6. Save data

This lets new pets and content ship without redesigning the hardware.

During prototype development, the working local firmware may contain hardware integrations ahead of the repository's baseline sketch. Patch helpers in `tools/` exist specifically to modify that known-good local sketch without replacing it wholesale.

## Physical Product

The enclosure should stay small, simple, and handmade:

- Wood body
- Brass standoffs
- OLED viewing window
- Six exposed copper touch wires
- Two visible lights
- Speaker opening
- USB charging access
- Battery compartment or secured internal battery

The first product should use the existing Happy Jarz board and enclosure language. A standalone BloomPetz version can be produced separately for customers who only want the pet.

## Product Editions

- BloomPetz standalone
- Happy Jarz BloomPetz Edition
- Limited pet editions
- Seasonal editions
- Custom named pets
- Downloadable pet and screensaver packs

The hardware stays consistent while the personality, artwork, and software create different products.

## Current Vertical-Slice Milestone

Already working or substantially demonstrated:

1. Persistent pet slots
2. On-device pet creation and editing
3. Touch navigation
4. Simon-style action minigame
5. Eight daily developmental actions
6. Food and treats
7. 200-stat developmental save model
8. On-device STATS browser
9. Persistent save data
10. APA106 light reactions
11. Four-line OLED UI
12. Rotating sayings and live stat ticker
13. Pi mirror/controller
14. USB diagnostics and control path

Next expansion work can focus on richer pet behavior, idle animation, sound, quests, screensavers, evolution, archival `.bloompet` files, and additional minigames rather than rebuilding the hardware/UI foundation.

## Product Promise

BloomPetz is a tiny object that remembers.

It sits beside the user, reacts to touch, plays, rests, collects experiences, and slowly becomes a companion. The electronics and core v0.1 interaction loop are now functioning on the Happy Jarz platform. The next phase is expanding the software world: pets, behaviors, quests, minigames, screensavers, sound, evolution, and content packs.

BloomPetz is not just a gadget. It is the beginning of a small living game platform.
