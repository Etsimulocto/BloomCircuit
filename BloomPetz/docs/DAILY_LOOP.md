# BloomPetz Daily Loop

## Core idea

BloomPetz uses a small number of tactile daily interactions to drive a very large developmental-stat system.

The pet does not require hundreds of chores. The player interacts through eight daily developmental actions, one full meal cycle, and up to three treats.

## Eight daily actions

Each action uses the same interaction pattern:

1. Select the action.
2. Press A to start.
3. BloomPetz displays a randomized three-step memory sequence using only UP, DOWN, LEFT, and RIGHT.
4. The player repeats the sequence.
5. Correct completion consumes 12.5 food/energy points.
6. The action rolls weighted developmental stats.
7. Response speed scales the micro-growth amount within the configured 0.0001 to 0.0050 range.

A and B are never part of the memory sequence:

- A = start / confirm
- B = back / cancel

The current provisional eight-action list is:

- CHECK
- CLEAN
- PET
- PLAY
- REST
- SCRATCH
- SOCIALIZE
- TRAIN

SOCIALIZE and TRAIN are provisional names replacing FEED and TREAT, which are now separate care systems.

## Food / energy

The pool runs from 0 to 100.

Each successful daily action consumes exactly 12.5 points, or one eighth of a full pool.

Therefore one full meal can fund all eight daily actions:

- Start: 100.0
- After action 1: 87.5
- After action 2: 75.0
- After action 3: 62.5
- After action 4: 50.0
- After action 5: 37.5
- After action 6: 25.0
- After action 7: 12.5
- After action 8: 0.0

At zero, normal developmental actions are blocked until feeding restores usable food/energy.

## Feeding

One meaningful full meal per day is normally enough.

Feeding restores the food/energy pool to 100 when appropriate. Food does not stack above 100.

Crossing midnight does not magically empty the pet's stomach. Remaining food/energy carries into the next calendar day. This prevents a 11:59 PM / 12:01 AM double-feeding exploit.

If the pet is still sufficiently full, extra feeding may produce a reaction but does not stack energy or duplicate developmental rewards.

## Treats

Treats are separate from the eight daily actions.

- Maximum: 3 accepted treats per calendar day.
- Each accepted treat may roll weighted random developmental-stat micro-growth.
- Treats do not replace the main meal.
- Treat number 4 and beyond are refused until the next daily reset.

## Calendar-day reset

At 00:00 local device time, reset:

- daily action completion flags
- daily per-source developmental-gain caps
- daily treat count

Do not reset:

- remaining food/energy
- lifetime counters
- age/history
- developmental stat values
- personality
- habits

The reset is for daily opportunities, not for the pet's physical state.

## Developmental stat rule

The roughly 200 slow-growth developmental stats are not individual chores.

Each successful action selects a weighted set of stats based on that action's theme, with occasional spillover into unrelated stats. The player's memory-response speed determines the size of the micro-growth roll.

Configured range:

- minimum: 0.0001
- maximum: 0.0050

A typical long-term target is approximately 0.0027 average gain on days when a stat receives a qualifying daily contribution, which is about enough to move from 0.0 to 1.0 over roughly one year of consistent development.

Lifetime counters such as total taps remain uncapped and are separate from these slow-growth developmental values.
