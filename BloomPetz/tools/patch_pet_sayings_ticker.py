#!/usr/bin/env python3
"""Add a 10-second rotating pet sayings ticker to BloomPetz home line 1.

Designed to apply after the home-status rotation patch.
- Keeps the pet art/symbol visible whenever it fits beside the saying.
- Rotates through a large built-in bank of short cute/positive/funny sayings.
- Falls back to alternating art-only / saying-only for long art strings.
- Only affects HOME; action/result/menu screens keep their existing line 1.
"""
from pathlib import Path
import sys

MARKER = "// BLOOMPETZ_PET_SAYINGS_V1"

SAYINGS = [
"hi friend","tiny victory","you got this","good vibes","be curious","stay cozy","keep going","nice work","yay you","breathe easy",
"small steps","big heart","be kind","shine on","keep blooming","good job","still growing","you matter","one more try","soft power",
"happy dance","snack time?","boop!","beep boop","tiny chaos","much wow","oh hello","zoom zoom","no thoughts","head empty",
"pet approved","good human","best human","hehe","teehee","plot twist","so shiny","sparkle mode","wiggle time","cozy mode",
"nap pending","snack pending","loading joy","joy found","oops!","who, me?","very pet","such pet","tiny legend","big mood",
"main character","stay weird","be silly","have fun","try again","almost there","nice save","good catch","nailed it","level up",
"you did it","keep at it","steady now","easy does it","all good","we got this","carry on","keep moving","go gently","be brave",
"brave little bean","bright bean","good bean","silly bean","cozy bean","happy bean","tiny bean","magic bean","bean power","bean mode",
"hello world","hello you","good morning","good evening","hi there","hey buddy","hey pal","sup?","yo!","hiya!",
"spark joy","choose joy","find wonder","make magic","stay bright","dream big","think small","look closer","wonder more","play more",
"rest counts","pause is okay","slow is fine","take your time","no rush","easy now","you are okay","keep breathing","gentle day","soft day",
"sunshine mode","moon mode","star mode","cloud mode","rain mode","storm mode","glow mode","bloom mode","dream mode","chill mode",
"tiny spark","little star","bright star","moon buddy","cloud buddy","sun buddy","spark buddy","glow buddy","bloom buddy","dream buddy",
"snacks?","treat?","more snacks","where snack","need snack","snack quest","snack radar","snack detected","snack secured","snack wizard",
"boop nose","pat pat","scritch pls","pet me pls","hug mode","cuddle mode","cozy pls","blanket pls","nap with me","sit with me",
"I believe","I see you","I got you","you're doing it","you're growing","you're learning","you're enough","you're awesome","you're neat","you're cool",
"good energy","calm energy","wild energy","chaos energy","cozy energy","bright energy","soft energy","fun energy","pet energy","joy energy",
"tiny win","big win","bonus win","secret win","daily win","win unlocked","quest clear","nice quest","quest on","next quest",
"hmmmmm","interesting","curious...","thinking...","processing","calculating","probably fine","seems legit","science!","for science",
"not a bug","feature!","works for me","ship it","good enough","one sec","almost ready","still here","all systems go","systems cozy",
"100% pet","certified pet","real creature","very official","totally normal","normal-ish","probably pet","pet online","pet awake","pet says hi",
"do a wiggle","wiggle wiggle","tiny spin","spin move","dance break","party time","confetti!","celebrate","woohoo!","yayyyy!",
"be excellent","stay excellent","keep shining","keep smiling","smile time","good day","better day","new day","fresh start","start small",
"learn stuff","make stuff","build stuff","fix stuff","try stuff","cool idea","good idea","weird idea","wild idea","tiny idea",
"brain spark","idea spark","spark found","idea found","hmm yes","hmm maybe","why not?","let's go","do the thing","thing done",
"pet wisdom","pet logic","pet science","pet magic","pet business","pet meeting","pet report","pet status","pet update","pet fact",
"fact: you're cool","fact: snack good","fact: naps rule","fact: play helps","fact: joy wins","fact: pets know","fact: you tried","fact: still here","fact: progress","fact: boop",
"today counts","this counts","effort counts","rest matters","play matters","fun matters","you count","joy matters","kindness wins","care matters",
"stay curious","stay gentle","stay playful","stay hopeful","stay cozy","stay sunny","stay goofy","stay kind","stay you","stay awesome",
]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_pet_sayings_ticker.py <bloompetz_v0_1.ino>")

    p = Path(sys.argv[1]).expanduser().resolve()
    s = p.read_text()

    if MARKER in s:
        print("Pet sayings ticker already applied.")
        return

    # We patch the local, already-working firmware, not the stale repo sketch.
    draw_anchor = "static void drawHome() {"
    if draw_anchor not in s:
        raise SystemExit("drawHome() not found")

    sayings_cpp = ",\n".join(f'  "{x.replace(chr(34), chr(92)+chr(34))}"' for x in SAYINGS)
    block = f'''// BLOOMPETZ_PET_SAYINGS_V1
static const char* const PET_SAYINGS[] = {{
{sayings_cpp}
}};
static constexpr uint16_t PET_SAYING_COUNT = sizeof(PET_SAYINGS) / sizeof(PET_SAYINGS[0]);
static constexpr uint32_t PET_SAYING_MS = 10000UL;
static uint16_t petSayingIndex = 0;
static uint32_t lastPetSayingMs = 0;

static String petTickerLine(const PetSave &p) {{
  String art = String(p.art);
  String saying = String(PET_SAYINGS[petSayingIndex % PET_SAYING_COUNT]);

  // Prefer showing both when the custom pet symbol is compact enough.
  if (art.length() && art.length() + 1 + saying.length() <= 16) {{
    return art + " " + saying;
  }}

  // For larger art, alternate art and saying each 10-second step so neither
  // gets permanently sacrificed to the 16-character OLED width.
  if ((petSayingIndex & 1U) == 0 && art.length()) return art;
  return saying;
}}

static void advancePetSayingIfDue() {{
  if (uiMode != HOME || !pets[activeSlot].occupied) return;
  uint32_t now = millis();
  if (lastPetSayingMs == 0) lastPetSayingMs = now;
  if (now - lastPetSayingMs < PET_SAYING_MS) return;
  lastPetSayingMs = now;
  petSayingIndex = (uint16_t)((petSayingIndex + 1U) % PET_SAYING_COUNT);
  drawHome();
}}

'''

    s = s.replace(draw_anchor, block + draw_anchor, 1)

    # Replace HOME line 1 p.art with ticker output while leaving all other screens alone.
    candidates = [
        'renderDisplay(p.art, String(p.name), line3, line4);',
        'renderDisplay(p.art, String(p.name), line3, homeStatusLine(p));',
        'renderDisplay(p.art, String(p.name), line3, line4);\n',
    ]
    replaced = False
    for old in candidates:
        if old in s:
            new = old.replace('renderDisplay(p.art,', 'renderDisplay(petTickerLine(p),')
            s = s.replace(old, new, 1)
            replaced = True
            break
    if not replaced:
        # Generic fallback constrained to drawHome() region only.
        start = s.find("static void drawHome() {")
        end = s.find("\nstatic void ", start + 1)
        if start < 0 or end < 0:
            raise SystemExit("Could not isolate drawHome()")
        region = s[start:end]
        if "renderDisplay(p.art," not in region:
            raise SystemExit("HOME renderDisplay(p.art,...) not found; refusing to guess")
        region = region.replace("renderDisplay(p.art,", "renderDisplay(petTickerLine(p),", 1)
        s = s[:start] + region + s[end:]

    # Hook the 10-second ticker into loop without disturbing side-art or touch timing.
    loop_anchor = "void loop() {"
    pos = s.find(loop_anchor)
    if pos < 0:
        raise SystemExit("loop() not found")
    insert_at = s.find("\n", pos) + 1
    if insert_at <= 0:
        raise SystemExit("loop() opening line malformed")
    s = s[:insert_at] + "  advancePetSayingIfDue();\n" + s[insert_at:]

    p.write_text(s)
    print(f"Pet sayings ticker applied to {p}")
    print(f"Loaded {len(SAYINGS)} sayings; HOME line 1 rotates every 10 seconds.")


if __name__ == "__main__":
    main()
