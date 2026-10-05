# BloomPetz v0.1 Bench Test Plan

This is the first vertical-slice acceptance test. Do not tune higher-level pet behavior until the lower layer being tested passes.

## Build target

ESP32-S3 SuperMini, Arduino ESP32 core. Use USB CDC on boot, matching the proven Happy Jarz build setup.

Firmware:

`BloomPetz/firmware/bloompetz_v0_1.ino`

Expected serial rate:

`115200`

## 1. Boot / identity

Flash firmware and open serial.

Expected boot record begins:

`BP|BOOT|fw=0.1.0`

Send:

`HELLO`

Expected:

`BP|IDENTITY|product=BloomPetz|fw=0.1.0`

## 2. APA106 diagnostic

Send:

`DIAG LED`

Expected physical result: both proven APA106 bulbs show red, green, and blue in sequence.

If this fails, do not change pet logic. Inspect the known-good GPIO7 / RMT / LED wiring layer.

## 3. Touch diagnostic

Send:

`DIAG TOUCH`

Record raw, baseline, and threshold values for UP, DOWN, LEFT, RIGHT, A, and B.

Touch each input and verify the raw reading crosses the stored threshold. If not, use:

`RECAL TOUCH`

Do not tune UI logic until all six inputs are independently visible.

## 4. Create first pet

Send example:

`CREATE 1|Lophire|Cat|[=^.^=] zZz`

Then:

`GET STATUS`
`GET SLOTS`
`GET SCREEN`

Expected:

- slot 1 occupied
- pet name/type retained
- art limited to 16 characters
- food/energy begins at 100
- four BP|SCREEN fields are emitted

## 5. Persistence

Send:

`SAVE`

Power-cycle the ESP32.

Then:

`GET STATUS`

The same pet must still be present with the same state.

## 6. Calendar / day state

Until a permanent RTC/NTP source is selected, set the date from the host:

`SET DATE 2026-10-04`

Complete or modify daily state, then send a different date:

`SET DATE 2026-10-05`

Expected daily reset:

- action-completion mask clears
- treat count returns to 0
- food/energy does NOT refill or empty
- lifetime counters and 200 developmental values remain

## 7. Action / Simon loop

From the physical home screen select an unfinished action with UP/DOWN and press A.

Expected sequence:

1. WATCH
2. three randomized D-pad directions displayed one at a time
3. matching LED direction flashes
4. YOUR TURN
5. repeat the three directions

On success, first completion that day must:

- consume exactly 12.5 food/energy
- mark that action complete for the calendar day
- perform 25 developmental stat rolls
- use an 80% favored-category / 20% global selection bias
- calculate gain from response speed in the range 0.0001 to 0.0050
- save automatically

Repeating the same action that day may still run for fidget/fun, but must not consume another 12.5 or grant another developmental reward.

Wrong sequence must not consume food or grant growth.

## 8. Eight-action food cycle

Complete all eight unique daily actions once.

Expected energy sequence:

100 -> 87.5 -> 75 -> 62.5 -> 50 -> 37.5 -> 25 -> 12.5 -> 0

At 0, further developmental actions are blocked until feeding.

## 9. Feed rule

At energy above 0, send:

`FEED`

Expected: pet refuses meaningful overfeeding and food does not exceed 100.

At energy 0, send:

`FEED`

Expected: food/energy returns to 100 and saves.

Crossing midnight must not independently alter food/energy.

## 10. Treat rule

Send `TREAT` three times.

Each accepted treat must:

- increment treatsToday
- increment lifetime treats
- select one random developmental stat
- apply random micro-growth from 0.0001 to 0.0050
- save

Fourth treat that calendar day must be refused.

## 11. Desktop app

Run:

`python3 BloomPetz/desktop/bloompetz_app.py`

Dependency:

`python3 -m pip install pyserial`

Connect to the ESP32 port.

Expected:

- app sends HELLO
- app sends local SET DATE automatically
- four-line device mirror updates from BP|SCREEN records
- Feed, Treat, Status, Slots, Stats and diagnostics commands work
- pet creation form can create/replace one of the three slots

## v0.1 pass condition

The vertical slice passes when a pet can be created, interacted with through a randomized three-input memory sequence, rewarded with persistent developmental growth, drained through the eight-action energy loop, fed, treated, rebooted, and recovered with its state intact.

The physical OLED is the one deliberately unfinished lower-level integration point. The repo does not yet contain the proven OLED driver, so v0.1 mirrors the exact four-line display contract over USB until that known-good display layer is imported.
