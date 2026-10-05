# BloomPetz Display Layout

Target OLED: 128x64 SSD1306, treated as a fixed four-line interface with approximately 16 character cells per line. Decorative particle art occupies narrow side gutters without changing the four-line text contract.

## Home screen contract

Current HOME screen behavior:

1. Pet art / symbol and rotating sayings. Long sayings use a character marquee.
2. Pet name alternating with live stat + value information. Long stat/value strings marquee.
3. Current selected daily action.
4. A/B controls plus rotating compact status: energy, treats, and daily-action completion.

Pet art is always one text line high and at most 16 ASCII characters wide.

## Controls

- UP / DOWN = select
- LEFT / RIGHT = edit/change/page
- A = enter/perform
- B = back/menu

The physical controls are six copper capacitive touch wires. Keyboard input from the Pi companion is routed through the same logical input handler.

## Main menu

The current hardware menu contains five items:

```text
FEED
TREAT
SLOT
EDIT PET / CREATE PET
STATS
```

Only three menu rows are displayed at once; line 4 remains the footer. The menu scrolls vertically as the selection moves.

Example lower window:

```text
  SLOT 1
  EDIT PET
> STATS
A ENTER B BACK
```

## STATS browser

The device exposes all 200 persistent developmental stats.

Category view:

```text
STATS 1/20
Bond / Social
AVG 2.4700%
UD MOVE A VIEW
```

Detail view:

```text
Bond / Social
1/10 affection
VALUE 3.1200%
<> MOVE B BACK
```

Controls:

- UP / DOWN = previous/next category
- A = open category
- LEFT / RIGHT = previous/next stat inside category
- B = back

The 20 categories and 200 stat names come from the canonical files in `data/stats/`.

## Creator

The pet creator/editor also uses the same four-line display.

Typical shape:

```text
>N:LophireA
 T:Void Cat
 D:[=^.^=]
 SAVE
```

Creator controls:

- UP / DOWN = move row
- A = next printable ASCII character
- B = previous printable ASCII character
- LEFT = delete/back
- RIGHT = append/accept; on SAVE, commit the pet

Name and type support up to 12 printable ASCII characters. Design/art supports up to 16.
