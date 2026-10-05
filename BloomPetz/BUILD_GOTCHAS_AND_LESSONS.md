# BloomPetz Build Gotchas and Lessons Learned

This file documents the problems that repeatedly slowed down the BloomPetz / HAPPY JARZ build, what caused them, and the practical rule learned from each one.

The goal is simple: do not rediscover the same failure modes on the next game or firmware build.

## Core rule

Before patching BloomPetz firmware:

1. Inspect the live local `.ino` actually being compiled.
2. Identify the exact active function / engine / code path.
3. Make the smallest possible patch against that exact path.
4. Compile.
5. Only after a clean compile, upload.
6. Physically test the device.

The repo and the live local firmware can drift apart. Never assume the remote source perfectly represents the active sketch.

---

## OLED hookup and GPIO validation

### Problem
The SSD1306 OLED needed wiring/address validation before UI work was trustworthy.

### Working configuration
- SSD1306 128x64
- I2C address `0x3C`
- SDA GPIO8
- SCL GPIO6
- U8g2

### Lesson
Validate display transport first. Do not debug menu/render logic while the physical display bus is still uncertain.

---

## Capacitive-touch responsiveness

### Problem
Touch input initially felt laggy or inconsistent.

We investigated thresholding, qualification time, drift, cooldowns, holds, and hysteresis.

### Result
A physical unplug/replug cleared much of the odd behavior. The simpler touch model worked well afterward.

### Current design
- direct `touchRead()`
- baseline +20%
- 60 ms qualification
- slow baseline drift
- one event per touch
- no extra cooldown / hold / release delay

### Lesson
Do not immediately add software complexity to compensate for a transient hardware/reset state.

---

## Creator controls

### Problem
The first pet creator control mapping was awkward and later menu changes collided with it.

### Final approach
- UP/DOWN: row
- B: previous ASCII character
- A: next ASCII character
- LEFT: delete/back
- RIGHT: append/accept
- RIGHT on SAVE: commit
- LEFT on SAVE: back to Design
- printable ASCII only

### Lesson
For a six-input device, define one consistent control grammar and reuse it everywhere.

---

## Creator / menu patch collisions

### Problem
Adding EDIT PET / CREATE PET collided with newer menu versions.

Some patches targeted old hardcoded menus while the live sketch had already evolved.

### Lesson
Never patch a menu from memory. Inspect the live menu handler first.

---

## Local firmware drift vs GitHub

### Problem
This became one of the largest recurring sources of wasted time.

The live `.ino` on the Pi often contained working changes that were newer than the remote firmware source. GitHub patch scripts were current, but the remote firmware itself was not always the authoritative copy.

### Symptoms
- patch reports success but runtime behavior does not change
- code search shows one architecture while the compiled sketch uses another
- duplicate / legacy code paths coexist locally

### Lesson
The live local `.ino` is the authority for structural patching.

Use GitHub patch scripts as the delivery mechanism, but inspect the live source before creating them.

---

## OLED side scrolling art

### Problem
The first decorative side-art patch needed follow-up fixes for Arduino prototypes and rendering.

### Result
After a prototype fix and renderer fix, the physical side art behaved correctly.

### Lesson
OLED decoration should remain isolated from the four-line UI renderer so cosmetic code cannot destabilize menu text.

---

## Pet sayings ticker

### Problem
Earlier saying logic and later marquee logic collided.

Duplicate ticker state and helper functions existed in the sketch.

### Result
The ticker engine was rebuilt to alternate pet art and sayings cleanly, with marquee support for long sayings.

### Lesson
Only one subsystem should own a given HOME row at a time.

---

## HOME stat ticker

### Problem
Stats were initially added sequentially, then a patch accidentally moved HOME stats to line 3 when line 3 was meant to remain the action row.

### Intended HOME layout
- Line 1: pet art / saying ticker
- Line 2: pet name / stat ticker
- Line 3: selected action
- Line 4: controls/status

### Lesson
Treat the OLED line ownership as part of the UI contract. Do not casually move content between rows.

---

## STATS menu initially showing only 20 entries

### Problem
The first stats browser used a 20-category gate with 10 stats per category.

The desired device UX was direct access to all 200 stats.

### Result
STATS became a flat 200-stat browser using LEFT/RIGHT.

### Lesson
The data model can remain hierarchical internally while the device UI presents a flat navigation model.

---

## Menu patches targeting the wrong code

### Problem
Several patches technically applied, but matched obsolete menu patterns instead of the actual live hardcoded menu branch.

### Lesson
A patch succeeding syntactically does not prove it changed the active code path.

Inspect the exact live handler before editing.

---

## Compile vs upload confusion

### Problem
A clean compile was sometimes mistaken for new firmware running on the board.

Also, after a failed compile, an older cached binary may still exist and can be uploaded if the workflow is careless.

### Required workflow
1. compile
2. verify success
3. upload
4. physically test

### Lesson
Compile != flash.

Never claim behavior is on-device until upload succeeds and the hardware is tested.

---

## Startup splash and slot picker

### Work involved
The startup system required dedicated UI modes and state handling for:
- boot splash
- slot picker
- welcome back
- empty-slot creator launch
- occupied-slot HOME launch
- skip-on-input behavior

### Lesson
Boot flows should be explicit state machines, not special cases buried inside HOME logic.

---

## Screensaver entry / service loop

### Problem
The kaomoji screensaver itself worked, but adding lights exposed a service-loop bug.

A patch inserted a light service call into the wrong location and produced broken or recursive behavior.

### Lesson
Background services must be hooked exactly once in the main loop and gated by UI mode.

Never use a broad global string replacement for a recurring service hook without inspecting the resulting call graph.

---

## APA106 library choice

### Problem
An early screensaver-light attempt used `Adafruit_NeoPixel`.

That was the wrong path for the already-proven HAPPY JARZ hardware.

### Proven transport
- ESP32-S3
- GPIO7
- custom RMT
- 10 MHz RMT clock
- approximately 4/14 ticks for 0
- approximately 14/4 ticks for 1
- approximately 100 us latch/reset
- RGB byte order

### Lesson
When a physical transport is already proven on the exact hardware, reuse it instead of replacing it with a generic library.

---

## RMT / Arduino prototype errors

### Problem
Custom types such as `BloomSaverRgb` and constants used in array bounds were sometimes declared too late for Arduino's generated prototypes.

Typical errors:
- `does not name a type`
- `not declared in this scope`
- malformed generated function signatures

### Lesson
Arduino `.ino` preprocessing is not normal C++ source ordering.

Types used in function signatures may need to live in a header included before Arduino generates prototypes.

---

## Full-RGB screensaver fade

### Goal
Replace a small fixed palette / flashing effect with smooth ambient color motion.

### Final behavior
- two independent APA106 bulbs
- full 24-bit RGB target selection
- smooth current-to-target interpolation
- no hard color jumps
- screensaver brightness remains capped at 25%

### Problem encountered
The first fade patch referenced `bloomSaverFadePrimed` before its declaration.

### Lesson
Animation state should be grouped together and declared before every helper that references it.

---

## Arduino auto-prototype hell

### Problem
This was one of the most persistent technical traps.

`Rgb`, `BloomSaverRgb`, `LED_COUNT`, and `BLOOMPETZ_LED_COUNT` repeatedly became invisible to Arduino-generated prototypes.

Simply moving declarations visually higher inside the `.ino` was not always enough.

### Robust fix
Move shared types/counts into a header and include that header at the very top of the sketch.

### Additional failure
The first header patch inserted the include after the last `#include` found anywhere in the file, which could still be too late.

The final repair forced the LED header to line 1.

### Lesson
For Arduino custom types used in signatures: prefer a real header over fighting the `.ino` preprocessor.

---

## Stat growth was far too fast

### Problem
The original per-hit gains were too large for a system that rolls many stat updates every day.

With 8 daily actions x 25 rolls/action, stats could grow dramatically after very little play.

### Result
Growth was rebalanced toward roughly year-scale progression for ordinary stats.

### Lesson
Balance progression from total expected update frequency, not from how small a single increment looks in isolation.

---

## Treats secretly used the old fast growth path

### Problem
Action growth was not the only stat-growth source.

Treats still had their own older random gain formula.

### Lesson
When rebalancing a stat system, search every write path to the stat array, not just the primary action function.

---

## Percent vs raw stat display

### Problem
Internal float precision and player-visible precision were initially being mixed together.

### Final rule
- internal values can retain more precision
- player-facing OLED percentage uses exactly four decimals, e.g. `0.0000%`

### Lesson
Storage precision and UI precision are separate design decisions.

---

## Broken `Serial.printf()` patch

### Problem
A generated patch accidentally inserted a literal newline inside a C++ string literal.

The compiler reported a missing terminating quote.

### Lesson
Patch scripts that emit C++ strings must explicitly escape `\n` and should be tested against the generated source text.

---

## Existing inflated prototype stats

### Problem
Changing future growth rates does not repair values already saved under the old balance.

### Possible future migration
A one-time normalization can preserve relative differences while shrinking legacy values.

### Lesson
Balance migrations and future balance formulas should be separate operations.

Never silently re-normalize saves on every boot.

---

## Random HOME sayings and stats

### Problem
The user repeatedly saw the same startup pair (`hi friend` / `attachment`).

Initial patches randomized a newer ticker implementation, but the actual live firmware still used an older sequential engine.

The live grep exposed the real active logic:
- saying index advanced with `+1`
- stat index advanced with `+1`

### Lesson
When runtime behavior contradicts the source you think is active, trust the runtime symptom and inspect the live sketch for duplicate engines.

Do not keep patching the assumed path.

---

## Random startup indices

### Problem
Even after later transitions are randomized, startup can still always begin at index 0 if the initial state is not randomized before the first render.

### Lesson
Randomizing transitions is not the same as randomizing initial state.

Initialize random state before the first player-visible frame.

---

## Duplicate / legacy code paths

### Problem
Rapid development left multiple generations of code in the same sketch:
- old ticker engine
- newer ticker engine
- old menu patterns
- newer menu patterns
- old LED declarations
- patch-generated declarations

### Lesson
Fast prototyping eventually requires consolidation.

Before large new features, consider a cleanup pass that removes dead engines and establishes one authoritative implementation per subsystem.

---

## Patch scripts reporting success without proving the active behavior changed

### Problem
Several patch scripts correctly matched and changed text, then printed a success message, while the active runtime path remained untouched.

### Lesson
Patch success means only that text changed.

Real success requires:
- inspect result
- compile
- flash
- physical test

---

## Brightness policy

### Required policy
- normal LED ceiling: 50%
- screensaver: 25%

### Lesson
Brightness caps are product constraints, not animation implementation details. Preserve them explicitly in every lighting patch.

---

## Random color behavior

### Problem
A small fixed palette made the lights feel repetitive and flash-like.

### Result
Screensaver lighting now chooses independent full-range RGB targets and fades between them.

### Lesson
For ambient effects, interpolate through color space rather than rapidly jumping between palette entries.

---

## Serial ownership / Pi desktop mirror

### Problem
After flashing, the board resets while the Pi desktop app may still own the serial port. The mirror can appear blank until the app reconnects.

### Lesson
Treat flash/reset as a serial-session boundary. Restart the desktop watcher/app after firmware uploads when needed.

---

# Project-wide lessons

The hardest part of this project was not ESP32 programming itself. The recurring difficulty came from:

- rapid local evolution
- GitHub/local source drift
- duplicate generations of code
- Arduino `.ino` preprocessing
- patch scripts matching inactive code
- compile/upload being separate steps

## Rules for the next game build

1. Keep one authoritative implementation per subsystem.
2. Inspect live firmware before creating patches.
3. Prefer exact anchors over broad regex replacements.
4. Put shared C++ types in headers early.
5. Separate state machines cleanly by UI mode.
6. Keep display row ownership explicit.
7. Search every write path when changing game balance.
8. Compile before upload.
9. Upload before claiming device behavior changed.
10. Physically test before calling a feature finished.
11. Preserve hardware-proven transports instead of swapping libraries casually.
12. Periodically consolidate prototype code before layering on another major game.

Tomorrow's D&D game should start from these lessons instead of relearning them.
