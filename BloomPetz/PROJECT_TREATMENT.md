# BloomPetz — Project Treatment and Build Brief

## Vision

BloomPetz is a small handcrafted desk companion that lives inside a wood-and-brass box. It combines a 128×64 OLED, six copper conductance touch wires, two lights, sound, a rechargeable battery, and an ESP32-S3 into a persistent digital pet platform.

The device behaves like a tiny old-school game system with a living companion inside it. The pet idles, sleeps, reacts to touch, plays minigames, completes quests, accumulates statistics, and remembers its history indefinitely.

## Existing Platform

The Happy Jarz electronics platform already provides the foundation:

- ESP32 controller
- Four lines of text per screen
- Scrolling menus
- Minigame support
- Infinite screensaver capability
- Six fast copper conductance inputs
- Two lights
- Sound output
- Rechargeable battery system
- Small handmade enclosure format

BloomPetz is a software and content layer built on this working hardware.

## Controls

The six copper touch wires form a compact gamepad:

```text
UP       DOWN       LEFT
RIGHT    A          B
```

The firmware should support tap, hold, repeated tap, and multi-touch combinations. Touch can mean navigation, petting, feeding, playing, confirming, or triggering secret behaviors depending on the current screen.

## Main Menu

```text
PET
STATS
PLAY
QUESTS
COLLECTION
SCREENSAVERS
SETTINGS
```

The menu system must remain readable on four lines and support scrolling. Every screen should be usable without a phone or computer.

## Pet System

Each pet is a data package containing:

- Name
- Sprite frames
- Idle animations
- Personality
- Needs and preferences
- Sounds
- Light reactions
- Favorite minigames
- Quest rules
- Unlock conditions
- Screensavers
- Growth or bonding behavior

The first companion can be Lophire, the small blue and pink dragon. Additional pets should be interchangeable without changing the electronics or core firmware.

The system should be designed for at least 50 simple pets and expandable content packs.

## Persistent Stats

BloomPetz should maintain a long-term record containing roughly 200 statistics. The screen only displays the most useful ones; the full record is available through the companion app.

Example categories:

- Hunger, thirst, energy, mood, and happiness
- Total days alive
- Total touches and interactions
- Feeding and play counts
- Minigame scores
- Quest completions
- Daily streaks
- Friendship level
- Favorite activity
- Rare events discovered
- Screensavers unlocked
- Pets collected
- Lifetime coins or resources
- Time spent sleeping and playing

Statistics should persist through power loss and firmware updates.

## Pet Care Loop

The pet should have simple needs that create reasons to return:

- Feed the pet
- Give it water
- Play a minigame
- Let it rest
- Complete a daily quest
- Discover a screensaver
- Check its mood and stats

Needs should create personality and reactions without making the device stressful or demanding.

## Minigames

The existing minigame system becomes the active play layer. Initial games can include:

- Catch the falling item
- Memory sequence
- Tap timing
- Dodge the obstacle
- Bubblefire practice
- Treasure hunt
- Pet reaction challenge

Each game should award score, coins, friendship, or unlock progress.

## Screensavers

Screensavers are a major part of the product identity. They should run indefinitely while the pet is idle or sleeping.

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

Screensavers can be bundled with pets or released as separate content packs.

## Lights and Sound

The two lights provide a second emotional channel outside the display:

- Mood indicator
- Hunger or alert state
- Quest completion
- Level-up reward
- Charging status
- Rare event effect
- Damage, surprise, or bubblefire reaction

Sound should include short reusable effects: chirps, menu clicks, confirmation tones, sleep sounds, quest rewards, warnings, and minigame effects.

## Companion App

The companion app is optional. BloomPetz must remain playable offline, while the app expands the experience.

The app can provide:

- Pet naming and customization
- Full statistics
- Backups and restore
- New pets
- New sprite packs
- Screensaver packs
- Quest packs
- Firmware updates
- GitHub project updates
- Device settings
- Community content later

The app should communicate with the ESP32 over Wi-Fi or Bluetooth, with the Raspberry Pi acting as an optional local hub.

## Update Model

The ESP32 firmware contains the core engine. Pet and content packages should be separated from the engine wherever possible.

Recommended layers:

1. Core firmware
2. Pet definitions and stats
3. Sprite and screensaver assets
4. Minigame definitions
5. Quest definitions
6. Save data

This lets new pets and content ship without redesigning the hardware.

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

## First Build Milestone

The first complete prototype should include:

1. Boot screen
2. Pet selection
3. Pet naming
4. Animated idle state
5. Touch navigation
6. One minigame
7. One daily quest
8. Mood and hunger stats
9. Persistent save data
10. Two light reactions
11. Sound effects
12. One screensaver
13. Firmware update path

Once this vertical slice works, additional pets and content become repeatable production work instead of new hardware projects.

## Product Promise

BloomPetz is a tiny object that remembers.

It sits beside the user, reacts to touch, plays, rests, collects experiences, and slowly becomes a companion. The electronics are already proven through the Happy Jarz platform. The project now needs the software world: pets, stats, quests, minigames, screensavers, and updates.

The first BloomPetz is not just a gadget. It is the beginning of a small living game platform.
