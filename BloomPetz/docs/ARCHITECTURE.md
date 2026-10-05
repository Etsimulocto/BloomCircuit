# BloomPetz Architecture

BloomPetz is split into four major layers:

1. hardware/runtime — OLED, touch, LEDs, sound, USB, persistence
2. pet engine — state, idle progression, interaction, personality, events
3. editable content/data — stats, reactions, traits, foods, milestones, growth
4. host app — mirror, library, backup, restore, editing, diagnostics

The physical device supports three active pet slots. Host storage may archive unlimited pets.

Prefer small modules and human-readable data over monolithic source files.

BloomCore rule: each subsystem should expose an independent diagnostic path and preserve known-good lower layers.
