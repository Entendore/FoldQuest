#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FOLD QUEST v9 - learn to fold proteins (2D hydrophobic-polar lattice model)
============================================================================

RED beads (H, hydrophobic) hate water - bury them in a core.
BLUE beads (P, polar) shield that core from water - which flees the oily
parts and hydrates the polar ones.

New to folding? The FOLDING SCHOOL (7 interactive lessons) runs automatically
on level 1, or press ? / F1 anytime. Press S for FIELD NOTES, the 10-chapter
science guide written for this game.

Controls
--------
drag an END of the chain      : the chain follows your cursor - DRAW the fold
drag a MIDDLE bead            : that half of the chain pivots around the anchor
drag middle bead + SHIFT      : swing the OTHER half of the chain instead
CTRL+drag / MIDDLE-drag bead  : REDRAW the loop around it through your cursor
point at the pulsing gold dot : flip a single corner bead (fine adjustment)
MOUSE WHEEL / , . on a bead   : rotate the hovered half by 90 degrees
Z / right-click : undo        Y : redo            R : reset
T : thermal shake             H : hint ghost      A : adopt the AI fold
V : watch the AI fold (annealing + temperature + energy trace)
O : replay YOUR OWN folding   X : fold analysis (grades your fold)
G : 2-player duel (hot-seat)  S : science field notes
E : endless random fold       D : design your own protein
N / P : next / prev level     M : sound   F : fullscreen   F12 : screenshot
ESC : title screen

Run:  pip install pygame   then   python foldquest.py
"""

import os
import math
import json
import random
import threading
import datetime
import time as _time
from collections import deque
import array as _array

import pygame

# ------------------------------------------------------------------ settings
TILE       = 44
GRID_W     = 26
GRID_H     = 15
HUD_TOP    = 100
HUD_BOT    = 80
SIDE       = (1280 - GRID_W * TILE) // 2
W, H       = 1280, HUD_TOP + GRID_H * TILE + HUD_BOT
OX, OY     = SIDE, HUD_TOP
FPS        = 60
BEAD_R     = int(TILE * 0.36)
DRAG_SPEED = 17.0
WATER_N    = 120
REPLAN_WIN = 6

DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))

COL_BG       = (10, 14, 24)
COL_PANEL    = (13, 18, 30)
COL_GRIDDOT  = (33, 43, 64)
COL_GRIDDOT2 = (54, 70, 104)
COL_BOND     = (146, 158, 184)
COL_BOND_HI  = (214, 224, 244)
COL_H_FILL   = (255, 106, 74)
COL_H_RIM    = (255, 176, 140)
COL_H_GLOW   = (255, 96, 46)
COL_P_FILL   = (82, 150, 250)
COL_P_RIM    = (164, 210, 255)
COL_P_GLOW   = (66, 126, 250)
COL_GOLD     = (255, 204, 64)
COL_TEXT     = (226, 232, 244)
COL_DIM      = (138, 150, 172)
COL_TEAL     = (92, 220, 200)
COL_RED      = (235, 96, 96)
COL_WATER    = (80, 140, 255)
COL_STRAND   = (172, 148, 255)
COL_HOT      = (255, 122, 80)

# ------------------------------------------------------------ folding school
TUT_STEPS = [
    dict(title="MEET THE PROTEIN",
         text=["A protein is a chain of amino acids - one bead per residue here.",
               "RED (H) beads are hydrophobic ('water-fearing'); BLUE (P) are polar.",
               "The strip above shows the sequence - order matters! Grab any bead and drag."],
         obj=("drag", "TRY IT: drag any bead and release it")),
    dict(title="THE HYDROPHOBIC EFFECT",
         text=["The drifting blue specks are water molecules.",
               "Watch: water flees RED beads and clings to BLUE ones. Drag a red bead to see it scatter.",
               "This squeeze - the hydrophobic effect - is the main force that folds real proteins."],
         obj=(None, "WATCH: water flees the reds, then press NEXT")),
    dict(title="CONTACTS & ENERGY",
         text=["Put two RED beads side by side (not neighbors on the chain): a GOLD link forms.",
               "That is an H-H contact. Every contact lowers free energy by 1 (more negative = stable).",
               "The lowest-energy shape is the native state - the fold the protein 'wants'."],
         obj=("contact1", "TRY IT: form your first H-H contact")),
    dict(title="DRAW THE FOLD",
         text=["Drag an END of the chain and the whole chain follows like a rope.",
               "You can literally draw the fold you want - that is how you build a compact core.",
               "Pull an end around and watch the chain trail behind you."],
         obj=("end", "TRY IT: drag an END of the chain, then release")),
    dict(title="PIVOTS & FLIPS",
         text=["Drag a MIDDLE bead to swing that half of the chain (SHIFT swings the other half).",
               "CTRL+drag (or middle mouse) redraws a whole loop through your cursor.",
               "A gold dot marks a flippable corner bead; the mouse wheel rotates too."],
         obj=("pivot", "TRY IT: swing a middle bead, flip a corner, or redraw a loop")),
    dict(title="THE FOLDING TOOLBOX",
         text=["T = thermal shake: random hot moves, like a protein rattled by heat.",
               "H = ghost of the target · A = adopt the AI fold · V = watch the AI's full run.",
               "S opens the SCIENCE NOTES · X grades your fold (fold analysis).",
               "And Z is undo - even proteins get second chances."],
         obj=("shake", "TRY IT: press T for a thermal shake (or just continue)")),
    dict(title="FOLD IT YOURSELF",
         text=["Goal: reach the target contacts shown top-right. Level 1 needs 3.",
               "Strategy: pair your H's one at a time, keep room for the core, don't box the chain in.",
               "If it snags, undo and reroute. You've got this - go find the native fold."],
         obj=("target", "TRY IT: reach 3 H-H contacts")),
]

# ---------------------------------------------------------------- field notes
NOTES = [
    ("What is a protein?",
     "Proteins are the machines of life: they digest your food, fight infections and carry "
     "oxygen in your blood. Each one begins as a long chain of amino acids - 20 kinds in "
     "nature - joined by peptide bonds. The chain does not stay floppy: it folds, within "
     "milliseconds, into one precise 3D shape. That shape decides its job. Sequence decides "
     "shape; shape decides function."),
    ("The hydrophobic effect",
     "Some amino acids are oily (hydrophobic), some are water-friendly (polar). Water "
     "molecules would rather bond with each other than touch oil. So when a protein enters "
     "water, its oily parts get squeezed together into a dry core while polar parts face "
     "outward. This squeeze - the hydrophobic effect - is the dominant force that folds "
     "proteins. Watch it happen to the blue specks in the game."),
    ("The HP lattice model",
     "To study folding, scientists simplify: keep only two residue types - Hydrophobic (H) "
     "and Polar (P) - and place the chain on a grid with equal-length bonds. This is the HP "
     "lattice model (Dill, 1985). It discards most chemistry but keeps the essence: "
     "sequence, chain geometry and the hydrophobic effect. Finding its best fold is "
     "NP-hard; even this toy version is a genuinely hard puzzle."),
    ("Energy & the native state",
     "Every shape a chain can take has an energy. Here it is simply -(H-H contacts): each "
     "pair of touching hydrophobics earns -1. Lower energy = more stable. The lowest-energy "
     "structure is the native state - the fold the protein reliably finds in a cell. Each "
     "level's target is the native energy of that sequence."),
    ("Levinthal's paradox",
     "In 1969 Cyrus Levinthal noted that a 100-residue protein has astronomically more "
     "possible shapes than there are atoms in the universe. Trying them one by one, even at "
     "a billion per second, would outlast the age of the universe - yet real proteins fold "
     "in milliseconds. Folding therefore cannot be blind search: the physics funnels the "
     "chain downhill toward the native state."),
    ("The energy landscape",
     "Imagine every possible fold laid out as terrain whose altitude is energy. Unfolded "
     "chains start on the high plateaus; the native state is the deepest valley. Folding "
     "is a ball rolling downhill. But the terrain is rugged - dotted with traps (local "
     "minima) where a chain can get stuck. Good sequences have smooth funnels; chaperones "
     "and heat help chains escape traps. Your tools: undo, the thermal shake, and "
     "annealing."),
    ("Secondary structure",
     "Proteins build small local patterns first: alpha-helices (coiled springs) and "
     "beta-sheets (strands zipped side by side). These form quickly because each residue "
     "finds stable partners nearby. In this 2D game, straight runs of residues play the "
     "role of beta-strands - they are highlighted in violet, and sheets appear when strands "
     "lie side by side (try THE ZIPPER)."),
    ("Chaperones & misfolding",
     "Many chains cannot fold alone - they would stick together and clump. Cells deploy "
     "chaperones: molecular machines (Hsp60, Hsp70) that clamp a struggling chain, shield "
     "its sticky patches and give it another chance, often powered by ATP. When misfolding "
     "wins, aggregates form: amyloid plaques in Alzheimer's, and prions, whose wrong shape "
     "templates more wrong shape. Your thermal shake is you playing chaperone."),
    ("Folding & AI",
     "For 50 years the CASP contest asked scientists to predict a protein's shape from its "
     "sequence. In 2020, DeepMind's AlphaFold2 effectively solved it and has since mapped "
     "about 200 million structures. Yet predicting the final shape is not the same as "
     "understanding the folding path a chain takes. This game's AI uses simulated "
     "annealing (Metropolis, 1953): propose random moves, keep improvements, tolerate "
     "mistakes at high temperature, and cool slowly. Press V to watch."),
    ("Your moves = science moves",
     "Every interaction here mirrors a real simulation move. Dragging an end is the end "
     "move. Flipping a corner bead is the corner (pull) move. Swinging half the chain is a "
     "pivot move - the workhorse of lattice folding studies since the 1980s. CTRL-dragging "
     "a loop is local replanning. And the thermal shake is literally Metropolis Monte "
     "Carlo. You are not just solving puzzles - you are hand-running a folding algorithm."),
]

# -------------------------------------------------------------------- levels
LEVELS = [
    dict(name="THE HAIRPIN", seq="HHPPHHPH", target=3, par=8,
         native=[(0,0),(1,0),(2,0),(2,1),(1,1),(0,1),(0,2),(1,2)],
         blurb="Hydrophobic (red) residues hate water - tuck them together!",
         fact="Real proteins fold in microseconds. No pressure."),
    dict(name="THE ZIPPER", seq="HHHPPHHHPHHP", target=5, par=11,
         native=[(0,0),(0,1),(0,2),(0,3),(1,3),(1,2),(1,1),(1,0),
                 (2,0),(2,1),(2,2),(2,3)],
         blurb="Strand against strand: zip up a little beta-sheet.",
         fact="Real beta-sheets are zippered together by hydrogen bonds."),
    dict(name="THE CORE", seq="HPPPPHPPHPPHPPP", target=4, par=12,
         native=[(1,1),(0,1),(0,0),(1,0),(2,0),(2,1),(3,1),(3,2),
                 (2,2),(2,3),(1,3),(1,2),(0,2),(0,3),(0,4)],
         blurb="Only four hydrophobics - find them a snug 2x2 core.",
         fact="The oily hydrophobic core is the engine that drives folding."),
    dict(name="THE SPIRAL", seq="PHHPHHPHHPPPHHHH", target=7, par=14,
         native=[(0,3),(1,3),(2,3),(3,3),(3,2),(3,1),(3,0),(2,0),
                 (1,0),(0,0),(0,1),(0,2),(1,2),(2,2),(2,1),(1,1)],
         blurb="Coil it up - a compact spiral hides the oily middle.",
         fact="Levinthal's paradox: blind search would outlive the universe."),
    dict(name="THE MAZE", seq="PHHHHPPHHHHHHPHHHHHH", target=9, par=16,
         native=[(0,0),(1,0),(2,0),(3,0),(4,0),(4,1),(4,2),(4,3),(3,3),
                 (2,3),(1,3),(0,3),(0,2),(0,1),(1,1),(2,1),(3,1),
                 (3,2),(2,2),(1,2)],
         blurb="A 20-mer maze - plan the route before you pull.",
         fact="Chaperone machines help real proteins fold. The AI button is yours."),
    dict(name="THE COIL", seq="PHHHPHPPHHHHHHHHHHHHHHHH", target=11, par=18,
         native=[(0,0),(1,0),(2,0),(3,0),(4,0),(5,0),(5,1),(5,2),(5,3),
                 (4,3),(3,3),(2,3),(1,3),(0,3),(0,2),(0,1),(1,1),(2,1),
                 (3,1),(4,1),(4,2),(3,2),(2,2),(1,2)],
         blurb="24 residues, 11 contacts. Think like a chaperone.",
         fact="AlphaFold cracked protein structure in 2021. You're doing it the fun way."),
    dict(name="THE MONSTER", seq="PHHHHPHPPHHHHHHHHPHHHHHHHHHHH", target=14, par=21,
         native=[(0,0),(1,0),(2,0),(3,0),(4,0),(5,0),(6,0),(6,1),(6,2),
                 (6,3),(5,3),(4,3),(3,3),(2,3),(1,3),(0,3),(0,2),(0,1),
                 (1,1),(2,1),(3,1),(4,1),(5,1),(5,2),(4,2),(3,2),(2,2),(1,2)],
         blurb="28 residues of trouble - coil with intent.",
         fact="Bigger proteins fold domain by domain, not all at once."),
    dict(name="THE MEGAFOLD", seq="PHHHHHPHPPHHHHHHPHPHHHHHHHHHHHHH", target=15, par=23,
         native=[(0,0),(1,0),(2,0),(3,0),(4,0),(5,0),(6,0),(7,0),(7,1),
                 (7,2),(7,3),(6,3),(5,3),(4,3),(3,3),(2,3),(1,3),(0,3),
                 (0,2),(0,1),(1,1),(2,1),(3,1),(4,1),(5,1),(6,1),(6,2),
                 (5,2),(4,2),(3,2),(2,2),(1,2)],
         blurb="32 residues. Boss-level packing.",
         fact="The largest known proteins fold for whole seconds. You've got time."),
    dict(name="TWIN CORES", seq="HPPHPPHPPHPPPPPPPPPPPHPPHPPHPPHP", target=8, par=30,
         native=[(1,1),(1,0),(2,0),(2,1),(3,1),(3,2),(2,2),(2,3),(1,3),
                 (1,2),(0,2),(0,3),(0,4),(1,4),(2,4),(3,4),(4,4),(4,3),
                 (4,2),(4,1),(5,1),(6,1),(6,0),(7,0),(7,1),(8,1),(8,2),
                 (7,2),(7,3),(6,3),(6,2),(5,2)],
         blurb="Two oily cores, one chain - fold it in two domains.",
         fact="Many real proteins fold domain by domain, quite independently."),
]

FACTS = [
    "Real proteins fold in microseconds to milliseconds.",
    "The oily hydrophobic core is the engine that drives folding.",
    "Levinthal's paradox: blind search would outlive the universe.",
    "Chaperone machines help real proteins fold - the AI button is yours.",
    "AlphaFold cracked protein structure prediction in 2021.",
    "Misfolded proteins can aggregate - that is how prions cause trouble.",
    "Ribosomes build the chain; folding starts while it emerges.",
    "Beta-sheets and alpha-helices are a real protein's favorite moves.",
    "Your cells are folding thousands of proteins right now.",
]

ACH = [
    ("first",     "First Contact",       "Make your first H-H contact"),
    ("perfect",   "X-ray Crystal",       "Reproduce the exact native fold"),
    ("gold",      "Gold Standard",       "Match the best known energy"),
    ("nohint",    "Unassisted",          "Win a level with no hints or AI"),
    ("speed",     "Folding Flash",       "Win any level in under 30 seconds"),
    ("par",       "Efficient Folder",    "Win at or under par moves"),
    ("shake",     "Molecular Chaperone", "Use the thermal shake 10 times"),
    ("loop",      "Loop Sculptor",       "Redraw 25 loops with Ctrl-drag"),
    ("endless5",  "Marathon Matcher",    "Solve 5 endless folds"),
    ("alllevels", "Master Folder",       "Complete every level"),
    ("daily3",    "Daily Devotee",       "Keep a 3-day daily-fold streak"),
    ("designer3", "Protein Designer",    "Fold 3 of your own designs"),
    ("class",     "Top of the Class",    "Complete the folding school"),
    ("duelist",   "Fold-Off Champion",   "Win a 2-player duel"),
]

# ------------------------------------------------------------------- helpers
def clamp(v, a, b):
    return a if v < a else (b if v > b else v)

def cell_px(c):
    return (OX + c[0] * TILE + TILE // 2, OY + c[1] * TILE + TILE // 2)

def px_to_cell(p):
    return (clamp(int((p[0] - OX) // TILE), 0, GRID_W - 1),
            clamp(int((p[1] - OY) // TILE), 0, GRID_H - 1))

def contact_pairs(conf, seq):
    pos = {}
    for i, c in enumerate(conf):
        pos[c] = i
    out = []
    for i, c in enumerate(conf):
        if seq[i] != "H":
            continue
        for d in DIRS:
            j = pos.get((c[0] + d[0], c[1] + d[1]))
            if j is not None and j > i + 1 and seq[j] == "H":
                out.append((i, j))
    return out

def count_contacts(conf, seq):
    return len(contact_pairs(conf, seq))

def valid_conf(conf):
    if len(set(conf)) != len(conf):
        return False
    for a, b in zip(conf, conf[1:]):
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
            return False
    return True

def initial_conf(n):
    if n <= GRID_W - 2:
        y = GRID_H // 2
        x0 = (GRID_W - n) // 2
        return [(x0 + i, y) for i in range(n)]
    conf = []
    rw = GRID_W - 4
    y, cnt, left = 2, 0, False
    for _i in range(n):
        x = 2 + (rw - 1 - cnt if left else cnt)
        conf.append((x, y))
        cnt += 1
        if cnt >= rw:
            cnt = 0
            y += 1
            left = not left
    return conf

def recentre(conf):
    xs = [p[0] for p in conf]
    ys = [p[1] for p in conf]
    dx = (GRID_W - 1 - (max(xs) - min(xs))) // 2 - min(xs)
    dy = (GRID_H - 1 - (max(ys) - min(ys))) // 2 - min(ys)
    return [(p[0] + dx, p[1] + dy) for p in conf]

def rot_about(p, a, k):
    dx, dy = p[0] - a[0], p[1] - a[1]
    for _ in range(k):
        dx, dy = -dy, dx
    return (a[0] + dx, a[1] + dy)

def bfs_path(start, goal, blocked):
    q = deque([start])
    parent = {start: None}
    best, bestk = start, abs(goal[0] - start[0]) + abs(goal[1] - start[1])
    goal_found = False
    while q:
        cur = q.popleft()
        if cur == goal:
            goal_found = True
            break
        k = abs(goal[0] - cur[0]) + abs(goal[1] - cur[1])
        if k < bestk:
            bestk, best = k, cur
        for d in DIRS:
            nxt = (cur[0] + d[0], cur[1] + d[1])
            if (0 <= nxt[0] < GRID_W and 0 <= nxt[1] < GRID_H
                    and nxt not in parent and nxt not in blocked):
                parent[nxt] = cur
                q.append(nxt)
    tgt = goal if goal_found else best
    path, c = [], tgt
    while c != start:
        path.append(c)
        c = parent[c]
    path.reverse()
    return path

def exact_path(start, goal, length, blocked, budget=700):
    if length <= 0:
        return None
    d0 = abs(start[0] - goal[0]) + abs(start[1] - goal[1])
    if d0 > length or (length - d0) % 2:
        return None
    path = [start]
    visited = {start}
    count = [0]

    def dfs(cur, rem):
        count[0] += 1
        if count[0] > budget:
            return None
        if cur == goal and rem == 0:
            return list(path)
        if rem == 0:
            return None
        if abs(cur[0] - goal[0]) + abs(cur[1] - goal[1]) > rem:
            return None
        cells = []
        for d in DIRS:
            c = (cur[0] + d[0], cur[1] + d[1])
            if (0 <= c[0] < GRID_W and 0 <= c[1] < GRID_H
                    and c not in visited and c not in blocked):
                cells.append(c)
        keyed = sorted(cells,
                       key=lambda c: abs(c[0] - goal[0]) + abs(c[1] - goal[1])
                       + random.uniform(0.0, 1.6))
        for c in keyed:
            visited.add(c)
            path.append(c)
            r = dfs(c, rem - 1)
            if r is not None:
                return r
            path.pop()
            visited.discard(c)
        return None

    return dfs(start, length)

def random_seq(rng, n, hf=0.45, hcap=4, pcap=6):
    seq = []
    h_run = p_run = 0
    for _i in range(n):
        ch = "H" if rng.random() < hf else "P"
        if ch == "H" and h_run >= hcap:
            ch = "P"
        elif ch == "P" and p_run >= pcap:
            ch = "H"
        h_run = h_run + 1 if ch == "H" else 0
        p_run = p_run + 1 if ch == "P" else 0
        seq.append(ch)
    idxs = [i for i, c in enumerate(seq) if c == "P"]
    while seq.count("H") < 5 and idxs:
        i = idxs.pop(rng.randrange(len(idxs)))
        seq[i] = "H"
    return "".join(seq)

def generate_random(rng, base):
    archetype = rng.choice(("mixed", "mixed", "sparse", "domains", "greasy"))
    if archetype == "domains":
        b1 = random_seq(rng, rng.randint(9, 11), 0.35)
        b2 = random_seq(rng, rng.randint(9, 11), 0.35)
        return (b1 + "P" * rng.randint(5, 7) + b2,
                "A two-domain protein - fold each core.")
    if archetype == "sparse":
        return (random_seq(rng, clamp(base + rng.randint(-2, 2), 12, 26), 0.28),
                "A sparse protein - every H counts.")
    if archetype == "greasy":
        return (random_seq(rng, clamp(base + rng.randint(-2, 2), 12, 26), 0.62, hcap=5),
                "An oily, H-rich protein - collapse it all.")
    return (random_seq(rng, clamp(base + rng.randint(-2, 2), 12, 26), 0.45),
            "A fresh random protein - beat the target.")

def today_str():
    return _time.strftime("%Y-%m-%d")

def daily_seed():
    return int(_time.strftime("%Y%m%d"))

def daily_streak(save):
    daily = save.get("daily", {})
    if not daily:
        return 0
    d = datetime.date.today()
    s = 0
    while d.strftime("%Y-%m-%d") in daily:
        s += 1
        d -= datetime.timedelta(days=1)
    return s

# --------------------------------------------------------------------- fonts
_FONTS = {}

def F(size):
    f = _FONTS.get(size)
    if f is None:
        f = pygame.font.Font(None, size)
        _FONTS[size] = f
    return f

def draw_text(s, txt, size, x, y, color=COL_TEXT, align="tl", shadow=True):
    img = F(size).render(txt, True, color)
    r = img.get_rect()
    if align == "tl":
        r.topleft = (x, y)
    elif align == "tc":
        r.midtop = (x, y)
    elif align == "cc":
        r.center = (x, y)
    elif align == "tr":
        r.topright = (x, y)
    elif align == "ml":
        r.midleft = (x, y)
    elif align == "br":
        r.bottomright = (x, y)
    elif align == "bc":
        r.midbottom = (x, y)
    if shadow:
        sh = F(size).render(txt, True, (8, 10, 16))
        s.blit(sh, r.move(2, 2))
    s.blit(img, r)
    return r

def wrap_text(txt, size, maxw):
    f = F(size)
    words = txt.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.size(t)[0] <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

# ============================================================== ART / SPRITES
ART = {}

def _sphere_sprite(r, kind, letters):
    d = 2 * r + 2
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = r + 1
    if kind == "H":
        base, deep, ring, lc = (255, 118, 84), (110, 28, 12), (208, 96, 62), (70, 22, 10)
    else:
        base, deep, ring, lc = (92, 158, 252), (16, 36, 92), (70, 112, 208), (12, 30, 64)
    for y in range(d):
        for x in range(d):
            dx, dy = x - c, y - c
            dist = math.hypot(dx, dy)
            if dist > r + 0.6:
                continue
            t = clamp(dist / r, 0.0, 1.0)
            col = [base[k] + (deep[k] - base[k]) * (t ** 1.6) for k in range(3)]
            if dist > 0.01:
                nx, ny = -dx / dist, -dy / dist
                hl = max(0.0, nx * 0.707 + ny * 0.707) ** 2 * 0.45
            else:
                hl = 0.25
            sx, sy = dx + r * 0.38, dy + r * 0.38
            spec = math.exp(-((sx * sx + sy * sy) / (r * 0.30) ** 2)) * 0.85
            for k in range(3):
                col[k] = int(min(255, col[k] + 255 * (hl * 0.35 + spec * 0.55) * (1 - t * 0.4)))
            a = int(255 * clamp((r - dist) / 1.2 + 0.5, 0.0, 1.0))
            s.set_at((x, y), (col[0], col[1], col[2], a))
    pygame.draw.circle(s, ring, (c, c), r, 1)
    if letters:
        img = F(15).render(kind, True, lc)
        s.blit(img, img.get_rect(center=(c, c + 1)))
    return s

def _glow_sprite(rgb, r, strength=1.0, core=0.35):
    d = 2 * r + 2
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = r + 1
    for y in range(d):
        for x in range(d):
            dist = math.hypot(x - c, y - c)
            if dist > r:
                continue
            f = 1.0 - dist / r
            a = int(255 * strength * (f ** 2))
            k = core * f
            s.set_at((x, y), (int(rgb[0] + (255 - rgb[0]) * k),
                              int(rgb[1] + (255 - rgb[1]) * k),
                              int(rgb[2] + (255 - rgb[2]) * k), a))
    return s

def _grad_panel(w, h, c_top, c_bot):
    s = pygame.Surface((w, h))
    for y in range(h):
        t = y / float(h)
        col = (int(c_top[0] + (c_bot[0] - c_top[0]) * t),
               int(c_top[1] + (c_bot[1] - c_top[1]) * t),
               int(c_top[2] + (c_bot[2] - c_top[2]) * t))
        pygame.draw.line(s, col, (0, y), (w, y))
    return s

def _shadow_strip(w, h, a0):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(h):
        a = int(a0 * (1 - y / float(h)))
        pygame.draw.line(s, (0, 0, 0, a), (0, y), (w, y))
    return s

def make_bg():
    s = pygame.Surface((W, H))
    top, bot = (15, 20, 35), (7, 10, 19)
    for y in range(H):
        t = y / float(H)
        col = (int(top[0] + (bot[0] - top[0]) * t),
               int(top[1] + (bot[1] - top[1]) * t),
               int(top[2] + (bot[2] - top[2]) * t))
        pygame.draw.line(s, col, (0, y), (W, y))
    rng = random.Random(7)
    for _ in range(11):
        col = rng.choice([(40, 78, 118), (58, 48, 104), (30, 88, 86),
                          (84, 62, 112), (96, 44, 60)])
        rad = rng.randint(90, 240)
        try:
            blob = pygame.transform.smoothscale(_glow_sprite(col, 24, 0.12), (2 * rad, 2 * rad))
        except Exception:
            blob = _glow_sprite(col, 24, 0.12)
        s.blit(blob, (rng.randint(-rad, W - rad), rng.randint(-rad, H - rad)))
    for gx in range(GRID_W):
        for gy in range(GRID_H):
            c = (OX + gx * TILE + TILE // 2, OY + gy * TILE + TILE // 2)
            if gx % 5 == 2 and gy % 5 == 2:
                pygame.draw.circle(s, COL_GRIDDOT2, c, 3)
            else:
                pygame.draw.circle(s, COL_GRIDDOT, c, 2)
    gr = pygame.Rect(OX - 4, OY - 4, GRID_W * TILE + 8, GRID_H * TILE + 8)
    rrect(s, (26, 36, 56), gr.inflate(8, 8), 14, 1)
    rrect(s, (46, 62, 94), gr, 12, 2)
    v = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(60):
        rrect(v, (0, 0, 0, int((60 - i) * 0.5)),
              pygame.Rect(i, i, W - 2 * i, H - 2 * i), 0, 1)
    s.blit(v, (0, 0))
    try:
        s = s.convert()
    except Exception:
        pass
    return s

def build_art():
    ART.clear()
    try:
        ART["bead"] = {("H", True): _sphere_sprite(BEAD_R, "H", True),
                       ("H", False): _sphere_sprite(BEAD_R, "H", False),
                       ("P", True): _sphere_sprite(BEAD_R, "P", True),
                       ("P", False): _sphere_sprite(BEAD_R, "P", False)}
        ART["mini"] = {"H": _sphere_sprite(7, "H", False),
                       "P": _sphere_sprite(7, "P", False)}
        ART["glow"] = {"H": [_glow_sprite(COL_H_GLOW, r) for r in (20, 24, 28)],
                       "P": [_glow_sprite(COL_P_GLOW, r) for r in (20, 24, 28)],
                       "gold": [_glow_sprite(COL_GOLD, r) for r in (22, 26, 30)],
                       "teal": [_glow_sprite(COL_TEAL, r) for r in (22, 26, 30)]}
        ART["gold_small"] = _glow_sprite(COL_GOLD, 13, 0.35)
        ART["water"] = [_glow_sprite((110, 170, 255), 4, 0.55),
                        _glow_sprite((120, 180, 255), 5, 0.42),
                        _glow_sprite((140, 200, 255), 5, 0.60)]
        ART["bar_top"] = _grad_panel(W, HUD_TOP, (21, 28, 46), (12, 17, 29))
        pygame.draw.line(ART["bar_top"], (46, 60, 90), (0, HUD_TOP - 2), (W, HUD_TOP - 2), 2)
        ART["bar_bot"] = _grad_panel(W, HUD_BOT, (12, 17, 29), (20, 27, 44))
        pygame.draw.line(ART["bar_bot"], (46, 60, 90), (0, 0), (W, 0), 2)
        ART["shadow"] = _shadow_strip(W, 14, 95)
        ART["shadow_up"] = pygame.transform.flip(ART["shadow"], False, True)
        ART["bg"] = make_bg()
        gold = ART["glow"]["gold"]
        try:
            ART["title_glow"] = pygame.transform.smoothscale(gold[1], (480, 110))
            ART["head_glow"] = pygame.transform.smoothscale(gold[1], (540, 96))
            ART["banner_glow"] = pygame.transform.smoothscale(gold[1], (640, 72))
            ART["energy_glow"] = pygame.transform.smoothscale(gold[1], (200, 66))
        except Exception:
            pass
        for key in ("bead", "mini"):
            for spr in ART[key].values():
                try:
                    spr.convert_alpha()
                except Exception:
                    pass
        for lst in ART["glow"].values():
            for spr in lst:
                try:
                    spr.convert_alpha()
                except Exception:
                    pass
        for key in ("gold_small", "water", "shadow", "shadow_up",
                    "title_glow", "head_glow", "banner_glow", "energy_glow"):
            spr = ART.get(key)
            if spr is not None:
                try:
                    if isinstance(spr, list):
                        for sp in spr:
                            sp.convert_alpha()
                    else:
                        spr.convert_alpha()
                except Exception:
                    pass
    except Exception:
        pass

def blit_center(surf, spr, x, y):
    surf.blit(spr, (int(x) - spr.get_width() // 2, int(y) - spr.get_height() // 2))

def bond_style(a, b):
    if a == "H" and b == "H":
        return (198, 110, 90), (255, 182, 152)
    if a == "P" and b == "P":
        return (92, 124, 192), (172, 208, 255)
    return COL_BOND, COL_BOND_HI

# --------------------------------------------------------------------- audio
MUTED = {"on": False}
AUDIO = False
SFX = {}

def make_snd(notes, shape="sine", vol=0.3):
    init = pygame.mixer.get_init()
    if not init:
        return None
    rate, _fmt, chans = init
    buf = _array.array("h")
    for freq, dur in notes:
        n = max(8, int(rate * dur))
        for i in range(n):
            t = i / float(rate)
            env = min(1.0, t / 0.004, max(0.0, (dur - t) / 0.05))
            ph = 2.0 * math.pi * freq * t
            v = math.sin(ph) if shape == "sine" else (0.6 if math.sin(ph) >= 0 else -0.6)
            s = int(30000 * vol * env * v)
            if chans >= 2:
                buf.append(s)
                buf.append(s)
            else:
                buf.append(s)
    try:
        return pygame.mixer.Sound(buffer=buf.tobytes())
    except Exception:
        return None

def init_audio():
    global AUDIO
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(44100, -16, 1, 512)
    except Exception:
        pass
    if pygame.mixer.get_init() is None:
        return
    try:
        SFX["pick"]  = make_snd([(520, 0.05)], vol=0.22)
        SFX["drop"]  = make_snd([(392, 0.07)], vol=0.20)
        SFX["bad"]   = make_snd([(150, 0.09), (110, 0.09)], shape="square", vol=0.16)
        SFX["ding"]  = [make_snd([(880, 0.05), (1108, 0.09)], vol=0.26),
                        make_snd([(988, 0.05), (1244, 0.09)], vol=0.27),
                        make_snd([(1108, 0.05), (1396, 0.09)], vol=0.28),
                        make_snd([(1244, 0.05), (1568, 0.10)], vol=0.29)]
        SFX["ui"]    = make_snd([(660, 0.04)], vol=0.15)
        SFX["morph"] = make_snd([(392, 0.07), (494, 0.07), (587, 0.07),
                                 (740, 0.12), (880, 0.18)], vol=0.24)
        SFX["shake"] = make_snd([(210, 0.05), (170, 0.05), (190, 0.05),
                                 (150, 0.06)], shape="square", vol=0.13)
        SFX["win"]   = make_snd([(523, 0.10), (659, 0.10), (784, 0.10),
                                 (1047, 0.14), (784, 0.07), (1047, 0.24)], vol=0.32)

        def _ok(v):
            if isinstance(v, list):
                return bool(v) and all(x is not None for x in v)
            return v is not None
        AUDIO = all(_ok(v) for v in SFX.values())
    except Exception:
        AUDIO = False

def play(name, idx=0):
    if AUDIO and not MUTED["on"]:
        sfx = SFX.get(name)
        if sfx:
            try:
                if isinstance(sfx, list):
                    s = sfx[min(idx, len(sfx) - 1)]
                    if s:
                        s.play()
                else:
                    sfx.play()
            except Exception:
                pass

# ------------------------------------------------------------------ save file
def save_path():
    return os.path.join(os.path.expanduser("~"), ".foldquest_save.json")

def load_save():
    try:
        with open(save_path(), "r") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def persist(d):
    try:
        with open(save_path(), "w") as f:
            json.dump(d, f)
    except Exception:
        pass

# ------------------------------------------------- simulated annealing "AI" --
def sa_transform(p, a, mv):
    dx, dy = p[0] - a[0], p[1] - a[1]
    if mv == 1:
        dx, dy = -dy, dx
    elif mv == 2:
        dx, dy = -dx, -dy
    elif mv == 3:
        dx, dy = dy, -dx
    elif mv == 4:
        dx = -dx
    elif mv == 5:
        dy = -dy
    return (a[0] + dx, a[1] + dy)

def random_conf(n, rng):
    for _ in range(300):
        conf = [(0, 0)]
        occ = {(0, 0)}
        cur = (0, 0)
        ok = True
        for _i in range(1, n):
            opts = [d for d in DIRS if (cur[0] + d[0], cur[1] + d[1]) not in occ]
            if not opts:
                ok = False
                break
            weights = [1.0 / (1.0 + 0.12 * (abs(cur[0] + d[0]) + abs(cur[1] + d[1])))
                       for d in opts]
            d = rng.choices(opts, weights=weights)[0]
            cur = (cur[0] + d[0], cur[1] + d[1])
            conf.append(cur)
            occ.add(cur)
        if ok:
            return conf
    return [(i, 0) for i in range(n)]

def anneal(seq, rng):
    """Monte-Carlo folding. Returns (best_conf, best_contacts, best_trace,
    best_temps) - the trace/temps describe the winning restart's trajectory."""
    n = len(seq)
    iters = 1500 + 115 * n
    restarts = 8 if n <= 16 else 6
    best, bestc, best_trace, best_temps = None, -1, None, None
    for _r in range(restarts):
        conf = random_conf(n, rng)
        cur_trace = [list(conf)]
        cur_temps = [1.8]
        c = count_contacts(conf, seq)
        best_in_restart, best_conf_in_restart = c, list(conf)
        T0, T1 = 1.8, 0.02
        for it in range(iters):
            T = T0 * (T1 / T0) ** (it / max(1, iters - 1))
            cand = list(conf)
            moved = False
            if rng.random() < 0.30:
                i = rng.randrange(n)
                occ = set(conf)
                if i == 0 or i == n - 1:
                    nb = conf[1] if i == 0 else conf[n - 2]
                    opts = []
                    for d in DIRS:
                        cc = (nb[0] + d[0], nb[1] + d[1])
                        if cc not in occ:
                            opts.append(cc)
                    if opts:
                        cand[i] = rng.choice(opts)
                        moved = True
                else:
                    a, b = conf[i - 1], conf[i + 1]
                    na = {(a[0] + d[0], a[1] + d[1]) for d in DIRS}
                    nb2 = {(b[0] + d[0], b[1] + d[1]) for d in DIRS}
                    cur = conf[i]
                    cell = None
                    for cc in (na & nb2):
                        if cc != cur and cc not in occ:
                            cell = cc
                            break
                    if cell is not None:
                        cand[i] = cell
                        moved = True
            else:
                i = rng.randrange(1, n - 1)
                if rng.random() < 0.5:
                    lo, hi, anchor = i, n, i - 1
                else:
                    lo, hi, anchor = 0, i + 1, i + 1
                a = conf[anchor]
                fixed = {conf[j] for j in range(n) if not (lo <= j < hi)}
                mv = rng.choice((1, 2, 3, 4, 5))
                ok = True
                for j in range(lo, hi):
                    q = sa_transform(conf[j], a, mv)
                    if q in fixed:
                        ok = False
                        break
                    cand[j] = q
                moved = ok
            if not moved:
                continue
            c2 = count_contacts(cand, seq)
            if c2 >= c or rng.random() < math.exp((c2 - c) / T):
                conf, c = cand, c2
                if len(cur_trace) < 500:
                    cur_trace.append(list(conf))
                    cur_temps.append(T)
                if c > best_in_restart:
                    best_in_restart, best_conf_in_restart = c, list(conf)
                if c > bestc:
                    bestc, best = c, list(conf)
        if best_in_restart >= bestc and best_in_restart > 0:
            cur_trace.append(best_conf_in_restart)
            cur_temps.append(T1)
            best_trace = cur_trace
            best_temps = cur_temps
    if best is None:
        best = random_conf(n, rng)
        bestc = count_contacts(best, seq)
    if best_trace is None:
        best_trace = [list(best)]
        best_temps = [1.8]
    return best, bestc, best_trace, best_temps

def start_ai(seq, level_i):
    box = {}

    def run():
        try:
            rng = random.Random(7919 * (level_i + 1) + 123)
            conf, c, trace, temps = anneal(seq, rng)
            box["conf"] = [tuple(p) for p in conf]
            box["contacts"] = int(c)
            if trace:
                last = trace[-1]
                lastT = temps[-1] if temps else 1.8
                if len(trace) > 200:
                    step = int(math.ceil(len(trace) / 200.0))
                    trace = trace[::step]
                    if temps:
                        temps = temps[::step]
                if trace[-1] is not last:
                    trace.append(last)
                    if temps:
                        temps.append(lastT)
                box["trace"] = [[tuple(p) for p in stepconf] for stepconf in trace]
                box["temps"] = [float(t) for t in temps] if temps else None
            else:
                box["trace"] = None
                box["temps"] = None
        except Exception:
            box["conf"] = None
            box["contacts"] = 0
            box["trace"] = None
            box["temps"] = None
        box["done"] = True

    try:
        threading.Thread(target=run, daemon=True).start()
    except Exception:
        box = {"conf": None, "contacts": 0, "trace": None, "temps": None, "done": True}
    return box

# ------------------------------------------------------------- draw helpers
def draw_bead(s, x, y, r, kind, ring=False, scale=1.0, letters=True):
    x, y = int(x), int(y)
    mini = ART.get("mini", {}).get(kind)
    if r <= 8 and mini is not None:
        s.blit(mini, (x - mini.get_width() // 2, y - mini.get_height() // 2))
        if ring:
            pygame.draw.circle(s, COL_GOLD, (x, y), 11, 2)
        return
    spr = ART.get("bead", {}).get((kind, letters))
    if spr is None:
        R = max(3, int(r * scale))
        fill = COL_H_FILL if kind == "H" else COL_P_FILL
        rim = COL_H_RIM if kind == "H" else COL_P_RIM
        pygame.draw.circle(s, fill, (x, y), R)
        pygame.draw.circle(s, rim, (x, y), R, max(2, R // 7))
        if letters and R >= 13:
            img = F(14).render(kind, True, (44, 16, 8) if kind == "H" else (10, 24, 48))
            s.blit(img, img.get_rect(center=(x, y + 1)))
        if ring:
            pygame.draw.circle(s, COL_GOLD, (x, y), R + 4, 2)
        return
    R = max(4, int(r * scale))
    if R == BEAD_R:
        use = spr
    else:
        try:
            use = pygame.transform.smoothscale(spr, (2 * R, 2 * R))
        except Exception:
            use = spr
    s.blit(use, (x - use.get_width() // 2, y - use.get_height() // 2))
    if ring:
        pygame.draw.circle(s, COL_GOLD, (x, y), R + 4, 2)

def draw_star(s, x, y, r, col):
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + rr * math.cos(ang), y + rr * math.sin(ang)))
    pygame.draw.polygon(s, col, pts)

def rrect(s, col, rect, radius=10, width=0):
    try:
        pygame.draw.rect(s, col, rect, width, border_radius=radius)
    except TypeError:
        pygame.draw.rect(s, col, rect, width)

def fmt_time(t):
    t = int(t)
    return "%d:%02d" % (t // 60, t % 60)

# ================================================================== the game
LESSON_CARD = pygame.Rect(W // 2 - 390, 588, 780, 162)

class Game:
    def __init__(self):
        self.save = load_save()
        MUTED["on"] = bool(self.save.get("muted", False))
        self.unlocked = clamp(int(self.save.get("unlocked", 0)), 0, len(LEVELS) - 1)
        self.state = "title"
        self.mode = "campaign"
        self.phase = 0.0
        self.title_demo_t = 0.0
        self.bg = ART.get("bg") or make_bg()
        self.fx = pygame.Surface((W, H), pygame.SRCALPHA)
        try:
            self.fx = self.fx.convert_alpha()
        except Exception:
            pass
        self.demo = [(L["seq"], recentre(L["native"])) for L in LEVELS]
        self.demo_idx = -1
        self.demo_pop = 1.0
        self.cursor = None
        self.title_chips = []
        self.title_awards_rect = None
        self.show_idx = False
        self.show_water = bool(self.save.get("water", True))
        self.shake_uses = 0
        self.replans = 0
        self.screen = None
        self.designer_open = False
        self.designer_seq = ""
        self.designer_msg = ""
        self.ach_open = False
        self.notes_open = False
        self.notes_idx = 0
        self.notes_rows = []
        self.analysis_open = False
        self.endless_n = 0
        self.designer_n = 0
        self.strand_seen = False
        # duel state
        self.duel = False
        self.duel_turn = 0
        self.duel_moves = [0, 0]
        self.duel_winner = 1
        # folding school state
        self.tut_step = 0
        self.tut_flags = set()
        self.tut_obj_done = False
        self.tut_entry_done = False
        self.tut_done_t = 0.0
        # bottom-bar buttons
        self.btns = []
        x, y = 24, H - HUD_BOT + 18
        for bid, label, key, bw in (("prev", "< PREV", None, 88),
                                    ("next", "NEXT >", None, 92),
                                    ("undo", "UNDO", "Z", 88),
                                    ("redo", "REDO", "Y", 88),
                                    ("reset", "RESET", "R", 96),
                                    ("hint", "HINT", "H", 88),
                                    ("ai", "AI FOLD", "A", 104),
                                    ("endless", "ENDLESS", "E", 104),
                                    ("help", "?", None, 36),
                                    ("mute", "SOUND", "M", 100)):
            self.btns.append(dict(id=bid, label=label, key=key,
                                  rect=pygame.Rect(x, y, bw, 46)))
            x += bw + 10
        self.win_keep = pygame.Rect(W // 2 - 291, 560, 138, 52)
        self.win_mine = pygame.Rect(W // 2 - 143, 560, 138, 52)
        self.win_watch = pygame.Rect(W // 2 + 5, 560, 138, 52)
        self.win_next = pygame.Rect(W // 2 + 153, 560, 138, 52)
        self.design_fold = pygame.Rect(W // 2 - 180, 560, 170, 52)
        self.design_cancel = pygame.Rect(W // 2 + 10, 560, 170, 52)
        self.tut_next = pygame.Rect(LESSON_CARD.right - 100, LESSON_CARD.y + 10, 84, 30)
        self.tut_skip = pygame.Rect(LESSON_CARD.right - 124, LESSON_CARD.bottom - 26, 110, 22)
        self.notes_panel = pygame.Rect(W // 2 - 420, 96, 840, 648)
        self.notes_close = pygame.Rect(self.notes_panel.right - 110,
                                       self.notes_panel.bottom - 46, 92, 34)
        self.load_level(self.unlocked)
        self.state = "title"

    # ------------------------------------------------------------- level load
    def load_level(self, i):
        i = clamp(i, 0, len(LEVELS) - 1)
        L = LEVELS[i]
        self.mode = "campaign"
        self.level_i = i
        self.seq = L["seq"]
        self.n = len(self.seq)
        self.level_name = L["name"]
        self.blurb = L["blurb"]
        self.fact = L["fact"]
        nat = [tuple(p) for p in L["native"]]
        self.native = nat if valid_conf(nat) else None
        self.target = len(contact_pairs(nat, self.seq)) if self.native else None
        self.ghost_conf = recentre(self.native) if self.native else None
        self.ai_seed = i
        self._reset_common()
        self.par = L.get("par", (self.target or 6) + 6)
        self.tutorial = (i == 0 and not self.save.get("tut", False))
        self.state = "play"
        if self.tutorial:
            self.toast("Welcome to FOLDING SCHOOL - 7 quick lessons")
        elif self.target is not None:
            self.toast("%s - reach %d H-H contacts (par %d moves)"
                       % (self.level_name, self.target, self.par))
        if self.duel:
            self.toast("DUEL continues - player 1 starts this protein")

    def load_endless(self):
        k = self.save.get("endless", 0) + 1
        rng = random.Random()
        self.mode = "endless"
        self.endless_n = k
        self.level_i = 0
        base = 13 + min(13, k)
        seq, blurb = generate_random(rng, base)
        self.seq = seq
        self.n = len(self.seq)
        self.level_name = "ENDLESS #%d" % k
        self.blurb = blurb
        self.fact = random.choice(FACTS)
        self.native = None
        self.target = None
        self.ghost_conf = None
        self.ai_seed = 1000 + k
        self._reset_common()
        self.par = 0
        self.tutorial = False
        self.state = "play"
        self.toast("Random fold #%d - the AI is finding a target..." % k)

    def load_daily(self):
        seed = daily_seed()
        rng = random.Random(seed)
        self.mode = "daily"
        self.level_i = 0
        seq, blurb = generate_random(rng, rng.randint(14, 20))
        self.seq = seq
        self.n = len(self.seq)
        self.level_name = "DAILY FOLD"
        self.blurb = blurb + " The same puzzle for everyone today."
        self.fact = FACTS[seed % len(FACTS)]
        self.native = None
        self.target = None
        self.ghost_conf = None
        self.ai_seed = seed
        self._reset_common()
        self.par = 0
        self.tutorial = False
        self.state = "play"
        rec = self.save.get("daily", {}).get(today_str())
        if rec:
            self.toast("Daily fold - already solved! Your best: %d moves" % rec.get("moves", 0))
        else:
            self.toast("Daily fold - fresh puzzle, same for everyone today")

    def load_designer(self, seq):
        self.mode = "designer"
        self.designer_n = self.save.get("designer", 0) + 1
        self.level_i = 0
        self.seq = seq
        self.n = len(self.seq)
        self.level_name = "DESIGN #%d" % self.designer_n
        self.blurb = "Your very own protein - show it how to fold."
        self.fact = random.choice(FACTS)
        self.native = None
        self.target = None
        self.ghost_conf = None
        self.ai_seed = 5000 + self.designer_n
        self._reset_common()
        self.par = 0
        self.tutorial = False
        self.state = "play"
        self.toast("Design #%d - the AI is finding a target..." % self.designer_n)

    def _reset_common(self):
        self.conf = initial_conf(self.n)
        self.vis = [[random.uniform(-140, W + 140), random.uniform(-120, H + 120)]
                    for _ in range(self.n)]
        self.trail = [[] for _ in range(self.n)]
        self.mytrace = [list(self.conf)]
        self.undo = []
        self.redo = []
        self.moves = 0
        self.time = 0.0
        self.hints = 0
        self.ai_assisted = False
        self.celebrated = -1
        self.drag = None
        self.replay = None
        self.paused = False
        self.win_overlay = False
        self.gold = False
        self.perfect = False
        self.pairs = set()
        self.contact_idx = set()
        self.contacts = 0
        self.link_count = [0] * self.n
        self.particles = []
        self.floats = []
        self.toasts = []
        self.hint_t = 0.0
        self.shake_amp = 0.0
        self.bad_flash = 0.0
        self.bad_pos = None
        self.last_ding = 0.0
        self.hover = None
        self.pop = [0.0] * self.n
        self.energy_pop = 0.0
        self._last_contacts = 0
        self.morph_t = 0.0
        self.par = 0
        self.stars = 0
        self.stars_t = 0.0
        self.star_chimes = 0
        self.combo = 0
        self.combo_t = 0.0
        self.shake_queue = 0
        self.shake_acc = 0.0
        self.shake_time = 0.0
        self.last_progress = 0.0
        self.tip_shown = False
        self.notes_open = False
        self.analysis_open = False
        self.duel_turn = 0
        self.duel_moves = [0, 0]
        self.tut_step = 0
        self.tut_flags = set()
        self.tut_obj_done = False
        self.tut_entry_done = False
        self.tut_done_t = 0.0
        self.refresh(silent=True)
        self.ai_box = start_ai(self.seq, self.ai_seed)
        self.ai_conf = None
        self.ai_contacts = None
        self.ai_trace = None
        self.ai_temps = None
        self.best_conf = None
        self.best_contacts = None
        self._init_water()

    def _init_water(self):
        self.water = []
        for _ in range(WATER_N):
            x = random.uniform(OX + 8, OX + GRID_W * TILE - 8)
            y = random.uniform(OY + 8, OY + GRID_H * TILE - 8)
            ang = random.uniform(0, 6.2832)
            sp = random.uniform(4, 14)
            self.water.append([x, y, math.cos(ang) * sp, math.sin(ang) * sp,
                               random.uniform(0, 6.2832)])

    def start_play(self, level=None):
        self.load_level(self.unlocked if level is None else level)

    # ------------------------------------------------------------ state info
    def refresh(self, silent=False):
        old = self.pairs
        self.pairs = set(contact_pairs(self.conf, self.seq))
        self.contacts = len(self.pairs)
        if self.contacts != self._last_contacts:
            self.energy_pop = 1.0
            self._last_contacts = self.contacts
        self.contact_idx = set()
        self.link_count = [0] * self.n
        for (i, j) in self.pairs:
            self.contact_idx.add(i)
            self.contact_idx.add(j)
            self.link_count[i] += 1
            self.link_count[j] += 1
        if silent:
            return
        gained = self.pairs - old
        lost = old - self.pairs
        if gained:
            career = self.save.setdefault("career", {})
            career["contacts"] = int(career.get("contacts", 0)) + len(gained)
            self.last_progress = self.time
        for (i, j) in gained:
            x = (self.vis[i][0] + self.vis[j][0]) / 2
            y = (self.vis[i][1] + self.vis[j][1]) / 2
            self.floats.append(dict(txt="+1", x=x, y=y - 14, t=0.9, col=COL_GOLD))
            self.spawn_sparks(x, y, COL_GOLD, 8)
            self.pop[i] = 1.0
            self.pop[j] = 1.0
        for (i, j) in lost:
            x = (self.vis[i][0] + self.vis[j][0]) / 2
            y = (self.vis[i][1] + self.vis[j][1]) / 2
            self.floats.append(dict(txt="-1", x=x, y=y - 14, t=0.9, col=COL_RED))
        if gained:
            now = pygame.time.get_ticks() * 0.001
            if now - self.last_ding > 0.15:
                play("ding", min(3, self.combo))
                self.last_ding = now
            if self.contacts > 0 and "first" not in self.save.get("ach", {}):
                self.award("first")

    def strand_runs(self):
        runs = []
        n = self.n
        i = 0
        while i < n - 1:
            d = (self.conf[i + 1][0] - self.conf[i][0],
                 self.conf[i + 1][1] - self.conf[i][1])
            j = i + 1
            while (j < n - 1 and
                   (self.conf[j + 1][0] - self.conf[j][0],
                    self.conf[j + 1][1] - self.conf[j][1]) == d):
                j += 1
            if j - i >= 3:
                runs.append((i, j))
            i = j
        return runs

    def bead_at(self, pos):
        best, bd = None, 1e18
        for i in range(self.n):
            dx = self.vis[i][0] - pos[0]
            dy = self.vis[i][1] - pos[1]
            d2 = dx * dx + dy * dy
            if d2 < bd:
                bd, best = d2, i
        return best if bd <= (TILE * 0.62) ** 2 else None

    def seq_bead_pos(self):
        sp = 19 if self.n <= 28 else 17
        x0 = W // 2 - sp * (self.n - 1) // 2
        return [(x0 + i * sp, 46) for i in range(self.n)]

    def hover_idx(self):
        if self.state != "play" or self.win_overlay or self.replay:
            return None
        if self.drag:
            return self.drag["i"]
        m = pygame.mouse.get_pos()
        if 22 < m[1] < 68:
            for i, (bx, by) in enumerate(self.seq_bead_pos()):
                if abs(m[0] - bx) <= 10 and abs(m[1] - by) <= 12:
                    return i
        return self.bead_at(m)

    def poll_ai(self):
        if not self.ai_box or not self.ai_box.get("done"):
            return
        b = self.ai_box
        self.ai_box = None
        conf = b.get("conf")
        if conf and valid_conf(conf):
            self.ai_conf = recentre(conf)
            self.ai_contacts = int(b.get("contacts", 0))
        self.ai_trace = b.get("trace") or None
        self.ai_temps = b.get("temps") or None
        if self.mode in ("endless", "daily", "designer"):
            if self.ai_conf:
                self.best_conf = self.ai_conf
                self.best_contacts = self.ai_contacts
                self.target = max(2, self.ai_contacts - 1)
                self.par = self.target + 7
                self.native = list(self.ai_conf)
                self.ghost_conf = self.ai_conf
                self.toast("AI record -%d · your target -%d"
                           % (self.ai_contacts, self.target))
            else:
                self.target = 2
                self.par = 9
            return
        if self.native is not None:
            if self.ai_conf and self.ai_contacts >= self.target:
                self.best_conf, self.best_contacts = self.ai_conf, self.ai_contacts
            else:
                self.best_conf, self.best_contacts = self.ghost_conf, self.target
        elif self.ai_conf:
            self.best_conf, self.best_contacts = self.ai_conf, self.ai_contacts
            self.target = self.ai_contacts
            self.native = list(self.ai_conf)
            self.ghost_conf = self.ai_conf

    # --------------------------------------------- move bookkeeping & duel
    def snapshot_trace(self):
        """Record the current conformation into your personal folding replay."""
        if not self.mytrace or list(self.conf) != self.mytrace[-1]:
            self.mytrace.append(list(self.conf))
            if len(self.mytrace) > 500:
                self.mytrace.pop(0)

    def next_turn(self):
        if not self.duel:
            return
        self.duel_moves[self.duel_turn] += 1
        self.duel_turn = 1 - self.duel_turn
        self.toast("PLAYER %d'S TURN" % (self.duel_turn + 1), 1.2)
        play("ui")

    def toggle_duel(self):
        if self.state != "play" or self.win_overlay or self.tutorial or self.replay:
            return
        self.duel = not self.duel
        self.duel_turn = 0
        self.duel_moves = [0, 0]
        if self.duel:
            self.toast("DUEL ON - players alternate every move; first to target wins")
        else:
            self.toast("Duel off")
        play("ui")

    # -------------------------------------------------------- folding school
    def start_lessons(self):
        self.tutorial = True
        self.tut_step = 0
        self.tut_flags = set()
        self.tut_obj_done = False
        self.tut_entry_done = False
        self.tut_done_t = 0.0
        play("ui")

    def tut_obj_complete(self):
        oty = TUT_STEPS[self.tut_step]["obj"][0]
        if oty is None:
            return False
        if oty == "drag":
            return "drag" in self.tut_flags
        if oty == "contact1":
            return self.contacts >= 1
        if oty == "end":
            return "end" in self.tut_flags
        if oty == "pivot":
            return "pivot" in self.tut_flags
        if oty == "shake":
            return "shake" in self.tut_flags
        if oty == "target":
            return self.target is not None and self.contacts >= self.target
        return True

    def update_tutorial(self, dt):
        done = self.tut_obj_complete()
        if done and not self.tut_obj_done:
            play("ding", 2)
            self.spawn_sparks(W // 2, LESSON_CARD.y - 6, COL_GOLD, 8)
        self.tut_obj_done = done
        if done:
            self.tut_done_t += dt
            limit = 2.8 if self.tut_entry_done else 1.1
            if self.tut_done_t > limit:
                self.tut_advance()

    def tut_advance(self):
        play("ui")
        if self.tut_step >= len(TUT_STEPS) - 1:
            self.finish_tutorial()
            return
        self.tut_step += 1
        self.tut_done_t = 0.0
        if self.tut_step == 1 and not self.show_water:
            self.show_water = True
            self.save["water"] = True
            persist(self.save)
            self.toast("Water on for this lesson (W toggles it)")
        self.tut_obj_done = self.tut_obj_complete()
        self.tut_entry_done = self.tut_obj_done

    def finish_tutorial(self, skipped=False):
        self.tutorial = False
        self.save["tut"] = True
        persist(self.save)
        if skipped:
            self.toast("Lessons skipped - press ? anytime to retake them")
        else:
            self.toast("Lessons complete! Press S for the science field notes")
            self.spawn_sparks(W // 2, 560, COL_GOLD, 16)
            self.award("class")
        play("morph")

    # ------------------------------------------------------------------ input
    def on_key(self, ev):
        if self.designer_open:
            k = ev.key
            u = ev.unicode.lower() if ev.unicode else ""
            if k == pygame.K_ESCAPE:
                self.designer_open = False
                play("ui")
            elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.submit_design()
            elif k == pygame.K_BACKSPACE:
                self.designer_seq = self.designer_seq[:-1]
            elif u in ("h", "p") and len(self.designer_seq) < 32:
                self.designer_seq += u.upper()
                self.designer_msg = ""
            return
        if self.notes_open:
            self.notes_open = False
            return
        if self.analysis_open:
            self.analysis_open = False
            return
        if self.state == "title":
            if self.ach_open:
                self.ach_open = False
                return
            if ev.key == pygame.K_TAB:
                self.ach_open = True
                return
            if ev.key == pygame.K_ESCAPE:
                return "quit"
            self.start_play()
            return
        if self.paused:
            self.paused = False
            return
        if self.replay:
            self.end_replay()
            return
        if self.ach_open:
            self.ach_open = False
            return
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.drag = None
            self.state = "title"
            persist(self.save)
            return
        if k == pygame.K_z:
            self.do_undo()
        elif k == pygame.K_y:
            self.do_redo()
        elif k == pygame.K_r:
            self.reset_level()
        elif k == pygame.K_h:
            self.show_hint()
        elif k == pygame.K_a:
            self.adopt_ai()
        elif k == pygame.K_v:
            self.start_replay("ai")
        elif k == pygame.K_o:
            if self.win_overlay:
                self.win_overlay = False
            self.start_replay("mine")
        elif k == pygame.K_g:
            self.toggle_duel()
        elif k == pygame.K_x:
            if self.win_overlay:
                self.win_overlay = False
            if not self.tutorial and not self.replay and not self.designer_open:
                self.analysis_open = True
                play("ui")
        elif k == pygame.K_s:
            if not self.win_overlay and not self.replay and not self.designer_open \
                    and not self.ach_open and not self.analysis_open:
                self.notes_open = True
                play("ui")
        elif k == pygame.K_m:
            self.toggle_mute()
        elif k == pygame.K_e:
            self.load_endless()
        elif k == pygame.K_d:
            if not self.win_overlay and not self.tutorial and not self.replay:
                self.designer_open = True
                self.designer_seq = ""
                self.designer_msg = ""
        elif k == pygame.K_TAB:
            self.ach_open = True
        elif k == pygame.K_t:
            self.do_shake()
        elif k == pygame.K_w:
            self.show_water = not self.show_water
            self.save["water"] = self.show_water
            persist(self.save)
            self.toast("Water on" if self.show_water else "Water off")
        elif k == pygame.K_i:
            self.show_idx = not self.show_idx
        elif k in (pygame.K_COMMA, pygame.K_LEFT):
            self.keyboard_pivot(3)
        elif k in (pygame.K_PERIOD, pygame.K_RIGHT):
            self.keyboard_pivot(1)
        elif k == pygame.K_f:
            try:
                pygame.display.toggle_fullscreen()
            except Exception:
                self.toast("Fullscreen not available")
        elif k == pygame.K_F12:
            self.screenshot()
        elif k == pygame.K_n:
            if self.mode == "endless":
                self.load_endless()
            elif self.mode == "daily":
                self.toast("One daily fold per day - come back tomorrow!")
            elif self.mode == "designer":
                self.designer_open = True
                self.designer_seq = ""
                self.designer_msg = ""
            else:
                self.goto_level(self.level_i + 1)
        elif k == pygame.K_p:
            if self.mode != "campaign":
                self.load_level(self.unlocked)
            else:
                self.goto_level(self.level_i - 1)
        elif k == pygame.K_F1:
            if self.mode == "campaign":
                self.start_lessons()
            else:
                self.toast("Lessons live in the campaign levels")

    def on_click(self, pos, button):
        if self.designer_open:
            if button == 1:
                if self.design_cancel.collidepoint(pos):
                    self.designer_open = False
                    play("ui")
                elif self.design_fold.collidepoint(pos):
                    self.submit_design()
            return
        if self.notes_open:
            if button == 1:
                if (not self.notes_panel.collidepoint(pos)
                        or self.notes_close.collidepoint(pos)):
                    self.notes_open = False
                    play("ui")
                else:
                    for i, rr in enumerate(self.notes_rows):
                        if rr.collidepoint(pos):
                            self.notes_idx = i
                            play("ui")
                            break
            return
        if self.analysis_open:
            self.analysis_open = False
            return
        if self.state == "title":
            if button == 1:
                if self.ach_open:
                    self.ach_open = False
                    return
                if (self.title_awards_rect
                        and self.title_awards_rect.collidepoint(pos)):
                    self.ach_open = True
                    play("ui")
                    return
                for rect, tag in self.title_chips:
                    if rect.collidepoint(pos):
                        if tag == "random":
                            play("ui")
                            self.load_endless()
                        elif tag == "daily":
                            play("ui")
                            self.load_daily()
                        elif tag == "design":
                            play("ui")
                            self.designer_open = True
                            self.designer_seq = ""
                            self.designer_msg = ""
                        elif tag == "notes":
                            play("ui")
                            self.notes_open = True
                        elif tag <= self.unlocked:
                            play("ui")
                            self.start_play(tag)
                        return
                self.start_play()
                play("ui")
            return
        if self.paused:
            self.paused = False
            return
        if self.replay:
            self.end_replay()
            return
        if self.ach_open:
            self.ach_open = False
            return
        if button == 1 and self.tutorial:
            if self.tut_next.collidepoint(pos):
                self.tut_advance()
                return
            if self.tut_skip.collidepoint(pos):
                self.finish_tutorial(skipped=True)
                return
        if button == 1:
            if self.win_overlay:
                self.overlay_click(pos)
                return
            for b in self.btns:
                if b["rect"].collidepoint(pos):
                    self.btn_action(b["id"])
                    return
            if self.drag or self.shake_queue > 0:
                return
            idx = self.bead_at(pos)
            if idx is not None:
                mods = pygame.key.get_mods()
                self.begin_drag(idx, shift=bool(mods & pygame.KMOD_SHIFT),
                                replan=bool(mods & pygame.KMOD_CTRL))
        elif button == 2:
            if self.win_overlay:
                return
            if self.drag or self.shake_queue > 0:
                return
            idx = self.bead_at(pos)
            if idx is not None:
                self.begin_drag(idx, replan=True)
        elif button == 3:
            self.do_undo()

    def on_wheel(self, dy):
        if self.state != "play" or self.paused or self.replay or self.win_overlay \
                or self.drag or self.shake_queue > 0 or self.designer_open \
                or self.ach_open or self.notes_open or self.analysis_open:
            return
        if self.hover is None:
            return
        if 0 < self.hover < self.n - 1:
            self.keyboard_pivot(3 if dy > 0 else 1, quiet=True)

    def on_release(self, button):
        if self.state != "play":
            self.drag = None
            return
        if button in (1, 2) and self.drag:
            d = self.drag
            self.drag = None
            if list(self.conf) != d["start"]:
                self.undo.append(d["start"])
                if len(self.undo) > 200:
                    self.undo.pop(0)
                self.moves += 1
                self.redo = []
                self.tut_flags.add("drag")
                if d["kind"] == "end":
                    self.tut_flags.add("end")
                elif d["kind"] in ("pivot", "replan"):
                    self.tut_flags.add("pivot")
                self.snapshot_trace()
                self.next_turn()
            delta = self.contacts - d.get("c0", self.contacts)
            if delta > 0:
                self.combo += 1
                self.combo_t = 9.0
                if self.combo >= 2:
                    m = pygame.mouse.get_pos()
                    self.floats.append(dict(txt="COMBO x%d" % self.combo,
                                            x=m[0], y=m[1] - 30, t=1.1, col=COL_TEAL))
            elif delta < 0:
                self.combo = 0
            play("drop")

    def begin_drag(self, i, shift=False, replan=False):
        start = list(self.conf)
        if replan and 0 < i < self.n - 1 and self.n >= 12:
            lo = max(1, i - REPLAN_WIN)
            hi = min(self.n - 2, i + REPLAN_WIN)
            if hi - lo >= 6:
                self.drag = dict(kind="replan", i=i, lo=lo, hi=hi, start=start,
                                 moving=list(range(lo, hi + 1)),
                                 c0=self.contacts, last_try=None)
                play("pick")
                return
        if i == 0 or i == self.n - 1:
            self.drag = dict(kind="end", i=i, start=start, acc=0.0, path=[],
                             c0=self.contacts)
        else:
            suffix_shorter = (self.n - i) <= (i + 1)
            use_suffix = suffix_shorter != shift
            if use_suffix:
                moving = list(range(i, self.n))
                anchor = i - 1
            else:
                moving = list(range(0, i + 1))
                anchor = i + 1
            self.drag = dict(kind="pivot", i=i, start=start, moving=moving,
                             anchor=anchor, lastdir=None, ghost=None, flip=None,
                             c0=self.contacts)
        play("pick")

    # ------------------------------------------------------------------ moves
    def update_end_drag(self, mpos, dt):
        d = self.drag
        head = d["i"]
        cur = self.conf[head]
        target = px_to_cell(mpos)
        if target == cur:
            d["acc"] = 0.0
            d["path"] = []
            return
        blocked = set(self.conf)
        blocked.discard(cur)
        path = bfs_path(cur, target, blocked)
        d["path"] = list(path)
        if not path:
            return
        d["acc"] += dt * DRAG_SPEED
        steps = 0
        while d["acc"] >= 1.0 and path and steps < 12:
            nxt = path.pop(0)
            if nxt in blocked:
                break
            if head == 0:
                self.conf = [nxt] + self.conf[:-1]
            else:
                self.conf = self.conf[1:] + [nxt]
            d["acc"] -= 1.0
            steps += 1
            self.refresh()
        if not path:
            d["acc"] = min(d["acc"], 0.99)

    def flip_target(self, i):
        if i <= 0 or i >= self.n - 1:
            return None
        a, b = self.conf[i - 1], self.conf[i + 1]
        na = {(a[0] + d[0], a[1] + d[1]) for d in DIRS}
        nb = {(b[0] + d[0], b[1] + d[1]) for d in DIRS}
        cur = self.conf[i]
        occ = set(self.conf)
        for c in (na & nb):
            if (c != cur and 0 <= c[0] < GRID_W and 0 <= c[1] < GRID_H
                    and c not in occ):
                return c
        return None

    def update_pivot_drag(self, mpos):
        d = self.drag
        gi = d["i"]
        cell = px_to_cell(mpos)
        flip = self.flip_target(gi)
        d["flip"] = flip
        if flip is not None and cell == flip:
            d["ghost"] = None
            d["lastdir"] = None
            self.conf[gi] = flip
            self.refresh()
            return
        a = self.conf[d["anchor"]]
        vx, vy = cell[0] - a[0], cell[1] - a[1]
        if abs(vx) + abs(vy) < 2:
            return
        if abs(vx) >= abs(vy):
            dirv = (1 if vx > 0 else -1, 0)
        else:
            dirv = (0, 1 if vy > 0 else -1)
        d0 = (self.conf[gi][0] - a[0], self.conf[gi][1] - a[1])
        if d0 not in DIRS:
            return
        if d0 == dirv:
            d["ghost"] = None
            d["lastdir"] = dirv
            return
        k = (DIRS.index(dirv) - DIRS.index(d0)) % 4
        moving = set(d["moving"])
        fixed = {self.conf[j] for j in range(self.n) if j not in moving}
        new, bad = {}, None
        for j in d["moving"]:
            q = rot_about(self.conf[j], a, k)
            new[j] = q
            if bad is None and (q in fixed or not (0 <= q[0] < GRID_W
                                                   and 0 <= q[1] < GRID_H)):
                bad = q
        if bad is None:
            self.conf = [new[j] if j in new else self.conf[j] for j in range(self.n)]
            self.refresh()
            d["ghost"] = None
        else:
            d["ghost"] = [new[j] for j in d["moving"]]
            if d.get("lastdir") != dirv:
                self.invalid_feedback(mpos)
        d["lastdir"] = dirv

    # ------------------------------------------------------ loop redraw move
    def update_replan_drag(self, mpos):
        d = self.drag
        cell = px_to_cell(mpos)
        if cell == d.get("last_try"):
            return
        d["last_try"] = cell
        if self.replan_window(cell):
            self.refresh()
            self.replans += 1
            if self.replans >= 25:
                self.award("loop")
            play("ui")

    def replan_window(self, m):
        d = self.drag
        lo, hi = d["lo"], d["hi"]
        A, B = self.conf[lo], self.conf[hi]
        L = hi - lo
        if m == A or m == B:
            return False
        blocked = {self.conf[j] for j in range(self.n) if j < lo or j > hi}
        if m in blocked:
            return False
        dAm = abs(A[0] - m[0]) + abs(A[1] - m[1])
        dBm = abs(B[0] - m[0]) + abs(B[1] - m[1])
        lo1, hi1 = max(dAm, 1), L - max(dBm, 1)
        if lo1 > hi1:
            return False
        pref = d["i"] - lo
        cands = [L1 for L1 in range(lo1, hi1 + 1)
                 if (L1 - dAm) % 2 == 0 and (L - L1 - dBm) % 2 == 0]
        cands.sort(key=lambda L1: abs(L1 - pref))
        for L1 in cands[:5]:
            p1 = exact_path(A, m, L1, blocked | {B}, budget=700)
            if not p1:
                continue
            p2 = exact_path(m, B, L - L1, blocked | (set(p1) - {m}), budget=700)
            if p2:
                full = p1 + p2[1:]
                if len(full) == L + 1 and len(set(full)) == L + 1:
                    self.conf = self.conf[:lo] + full + self.conf[hi + 1:]
                    return True
        return False

    def invalid_feedback(self, mpos):
        self.bad_flash = 1.0
        self.bad_pos = mpos
        self.shake_amp = 5.0
        play("bad")

    # ------------------------------------------------------- keyboard folding
    def keyboard_pivot(self, k, quiet=False):
        if (self.state != "play" or self.win_overlay
                or self.drag or self.shake_queue > 0 or self.replay):
            return
        i = self.hover
        if i is None or i == 0 or i == self.n - 1:
            if not quiet:
                self.toast("Hover a middle bead, then rotate with the wheel or , .")
            return
        if (self.n - i) <= (i + 1):
            moving, anchor = range(i, self.n), i - 1
        else:
            moving, anchor = range(0, i + 1), i + 1
        a = self.conf[anchor]
        fixed = {self.conf[j] for j in range(self.n) if j not in set(moving)}
        cand = list(self.conf)
        for j in moving:
            q = rot_about(self.conf[j], a, k)
            if q in fixed or not (0 <= q[0] < GRID_W and 0 <= q[1] < GRID_H):
                self.invalid_feedback(pygame.mouse.get_pos())
                return
            cand[j] = q
        self.undo.append(list(self.conf))
        self.redo = []
        self.moves += 1
        self.tut_flags.add("pivot")
        self.conf = cand
        self.refresh()
        self.snapshot_trace()
        self.next_turn()
        play("ui")

    # ------------------------------------------------------------ thermal shake
    def do_shake(self):
        if (self.state != "play" or self.win_overlay
                or self.drag or self.shake_queue > 0 or self.replay):
            return
        self.undo.append(list(self.conf))
        self.redo = []
        self.moves += 1
        self.combo = 0
        self.tut_flags.add("shake")
        self.shake_queue = 12
        self.shake_acc = 0.0
        self.shake_time = 0.0
        self.shake_amp = 3.0
        self.shake_uses += 1
        if self.shake_uses >= 10:
            self.award("shake")
        play("shake")
        self.toast("Thermal shake! (Z undoes it)")

    def random_move(self):
        occ = set(self.conf)
        n = self.n
        for _ in range(2 * n):
            i = random.randrange(n)
            if i == 0 or i == n - 1:
                nb = self.conf[1] if i == 0 else self.conf[n - 2]
                opts = []
                for d in DIRS:
                    c = (nb[0] + d[0], nb[1] + d[1])
                    if (0 <= c[0] < GRID_W and 0 <= c[1] < GRID_H
                            and c not in occ):
                        opts.append(c)
                if opts:
                    c = random.choice(opts)
                    if i == 0:
                        self.conf = [c] + self.conf[:-1]
                    else:
                        self.conf = self.conf[1:] + [c]
                    return True
            else:
                fl = self.flip_target(i)
                if fl is not None and random.random() < 0.55:
                    self.conf[i] = fl
                    return True
                if (n - i) <= (i + 1):
                    moving, anchor = range(i, n), i - 1
                else:
                    moving, anchor = range(0, i + 1), i + 1
                k = random.choice((1, 2, 3))
                a = self.conf[anchor]
                fixed = {self.conf[j] for j in range(n) if j not in set(moving)}
                cand = list(self.conf)
                ok = True
                for j in moving:
                    q = rot_about(self.conf[j], a, k)
                    if q in fixed or not (0 <= q[0] < GRID_W and 0 <= q[1] < GRID_H):
                        ok = False
                        break
                    cand[j] = q
                if ok:
                    self.conf = cand
                    return True
        return False

    def process_shake(self, dt):
        was_running = self.shake_queue > 0
        if not was_running:
            return
        self.shake_time += dt
        self.shake_acc += dt
        while self.shake_acc >= 0.045 and self.shake_queue > 0:
            self.shake_acc -= 0.045
            self.random_move()
            self.shake_queue -= 1
            self.refresh()
        if self.shake_time > 1.6:
            self.shake_queue = 0
        if was_running and self.shake_queue <= 0:
            self.snapshot_trace()
            self.next_turn()

    # ------------------------------------------------------------- water sim
    def update_water(self, dt):
        if not self.show_water:
            return
        gx0, gy0 = OX + 6, OY + 6
        gx1, gy1 = OX + GRID_W * TILE - 6, OY + GRID_H * TILE - 6
        R = 92.0
        R2 = R * R
        PR = 55.0
        PR2 = PR * PR
        for w in self.water:
            w[2] += random.uniform(-26, 26) * dt
            w[3] += random.uniform(-26, 26) * dt
            for i in range(self.n):
                kind = self.seq[i]
                dx = w[0] - self.vis[i][0]
                dy = w[1] - self.vis[i][1]
                d2 = dx * dx + dy * dy
                if kind == "H":
                    if 1 < d2 < R2:            # hydrophobic: water flees
                        d = math.sqrt(d2)
                        f = (1.0 - d / R) * 240.0 * dt
                        w[2] += dx / d * f
                        w[3] += dy / d * f
                else:
                    if 1 < d2 < PR2:           # polar: water hydrates
                        d = math.sqrt(d2)
                        f = (1.0 - d / PR) * 55.0 * dt
                        w[2] -= dx / d * f
                        w[3] -= dy / d * f
            w[2] *= max(0.0, 1.0 - 1.1 * dt)
            w[3] *= max(0.0, 1.0 - 1.1 * dt)
            sp = math.hypot(w[2], w[3])
            if sp > 46:
                w[2] *= 46 / sp
                w[3] *= 46 / sp
            w[0] += w[2] * dt
            w[1] += w[3] * dt
            if w[0] < gx0:
                w[0] = gx0
                w[2] = abs(w[2])
            elif w[0] > gx1:
                w[0] = gx1
                w[2] = -abs(w[2])
            if w[1] < gy0:
                w[1] = gy0
                w[3] = abs(w[3])
            elif w[1] > gy1:
                w[1] = gy1
                w[3] = -abs(w[3])

    # ------------------------------------------------------------ replays
    def start_replay(self, source="ai"):
        if (self.state != "play" or self.win_overlay
                or self.drag or self.shake_queue > 0 or self.replay
                or self.designer_open or self.ach_open or self.analysis_open):
            return
        if source == "ai":
            if not self.ai_trace or len(self.ai_trace) < 2:
                self.toast("No AI replay available yet")
                return
            tr_src = self.ai_trace
            recenter_flag = True
            title = "SIMULATED ANNEALING - WATCH THE AI FOLD"
            temps = self.ai_temps
            speed_min = 6.0
        else:
            if not self.mytrace or len(self.mytrace) < 2:
                self.toast("Make some moves first, then replay them")
                return
            tr_src = self.mytrace
            recenter_flag = False
            title = "YOUR FOLD - MOVE BY MOVE"
            temps = None
            speed_min = 4.0
        tr = [[tuple(c) for c in step] for step in tr_src]
        self.replay = dict(trace=tr, idx=0, acc=0.0, saved=list(self.conf),
                           speed=max(speed_min, len(tr) / 9.0),
                           energy=[count_contacts(tr[0], self.seq)],
                           recenter=recenter_flag, title=title,
                           temps=list(temps) if temps else None, source=source)
        self.drag = None
        play("morph")

    def update_replay(self, dt):
        r = self.replay
        r["acc"] += dt * r["speed"]
        n = len(r["trace"])
        while r["acc"] >= 1.0 and r["idx"] < n - 1:
            r["acc"] -= 1.0
            r["idx"] += 1
            step = r["trace"][r["idx"]]
            if r.get("recenter", True):
                self.conf = recentre(list(step))
            else:
                self.conf = [tuple(c) for c in step]
            self.refresh()
            r["energy"].append(self.contacts)
        if r["idx"] >= n - 1:
            self.end_replay()

    def end_replay(self):
        if not self.replay:
            return
        self.conf = self.replay["saved"]
        self.replay = None
        self.refresh(silent=True)
        self.toast("Replay done - your fold is restored")
        play("drop")

    # ------------------------------------------------------------------ update
    def update(self, dt):
        self.phase += dt
        if (self.designer_open or self.ach_open or self.notes_open
                or self.analysis_open):
            return
        if self.state == "title":
            self.title_demo_t += dt
            idx = int(self.title_demo_t / 3.2) % len(self.demo)
            if idx != self.demo_idx:
                self.demo_idx = idx
                self.demo_pop = 0.0
            self.demo_pop = min(1.0, self.demo_pop + dt * 4.0)
            return
        if self.paused:
            if pygame.display.get_active():
                self.paused = False
            return
        if not pygame.display.get_active():
            self.paused = True
            return
        if not self.win_overlay and not self.replay:
            self.time += dt
        if self.replay:
            self.update_replay(dt)
        elif self.drag:
            m = pygame.mouse.get_pos()
            kind = self.drag["kind"]
            if kind == "end":
                self.update_end_drag(m, dt)
            elif kind == "replan":
                self.update_replan_drag(m)
            else:
                self.update_pivot_drag(m)
        self.process_shake(dt)
        lspeed = 3.2 if self.morph_t > 0 else 13.0
        k = 1.0 - math.exp(-lspeed * dt)
        for i in range(self.n):
            tx, ty = cell_px(self.conf[i])
            px0, py0 = self.vis[i][0], self.vis[i][1]
            self.vis[i][0] += (tx - px0) * k
            self.vis[i][1] += (ty - py0) * k
            if abs(self.vis[i][0] - px0) + abs(self.vis[i][1] - py0) > 1.4:
                tr = self.trail[i]
                tr.append([self.vis[i][0], self.vis[i][1], 0.38])
                if len(tr) > 12:
                    tr.pop(0)
        for tr in self.trail:
            for pt in tr:
                pt[2] -= dt
            tr[:] = [p for p in tr if p[2] > 0]
        if self.morph_t > 0:
            self.morph_t -= dt
        self.update_water(dt)
        if not self.strand_seen:
            if any(j - i + 1 >= 4 for (i, j) in self.strand_runs()):
                self.strand_seen = True
                self.toast("A straight run of 4+ residues = a beta-strand (violet)")
        for p in self.particles:
            p["life"] -= dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += p["g"] * dt
            if "spin" in p:
                p["angle"] = (p.get("angle", 0.0) + p["spin"] * dt) % 6.2832
                p["flutter"] = (p.get("flutter", 0.0) + p["flut"] * dt) % 6.2832
        self.particles = [p for p in self.particles if p["life"] > 0]
        for f in self.floats:
            f["t"] -= dt
            f["y"] -= 26 * dt
        self.floats = [f for f in self.floats if f["t"] > 0]
        for tm in self.toasts:
            tm["t"] -= dt
        self.toasts = [t for t in self.toasts if t["t"] > 0]
        for i in range(self.n):
            if self.pop[i] > 0:
                self.pop[i] = max(0.0, self.pop[i] - 2.6 * dt)
        if self.energy_pop > 0:
            self.energy_pop = max(0.0, self.energy_pop - 2.2 * dt)
        self.shake_amp = max(0.0, self.shake_amp - 26 * dt)
        self.bad_flash = max(0.0, self.bad_flash - 3.0 * dt)
        if self.hint_t > 0:
            self.hint_t -= dt
        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo = 0
        if (not self.tip_shown and self.time - self.last_progress > 75
                and not self.win_overlay and self.drag is None
                and self.replay is None and not self.tutorial):
            self.tip_shown = True
            self.toast("Stuck? H shows a hint, T rattles the chain, V watches the AI")
        if self.win_overlay:
            self.stars_t += dt
            while (self.star_chimes < min(3, self.stars)
                   and self.stars_t > 0.25 + 0.18 * self.star_chimes):
                sx = W // 2 + (self.star_chimes - 1) * 52
                self.spawn_sparks(sx, 200, COL_GOLD, 12)
                play("ding")
                self.star_chimes += 1
        self.hover = self.hover_idx()
        self.poll_ai()
        if self.tutorial and not self.win_overlay:
            self.update_tutorial(dt)
        self.check_win()

    # ---------------------------------------------------------------- win logic
    def check_win(self):
        if (self.state == "play" and not self.win_overlay and not self.tutorial
                and self.drag is None and self.shake_queue == 0
                and self.replay is None and self.target is not None
                and self.contacts >= self.target
                and self.contacts > self.celebrated):
            self.celebrate()

    def is_perfect(self):
        if not self.native:
            return False

        def norm(cells):
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            x0, y0 = min(xs), min(ys)
            return {(c[0] - x0, (c[1] - y0)) for c in cells}

        tgt = norm(self.native)
        transforms = (lambda p: p, lambda p: (p[1], p[0]), lambda p: (-p[0], p[1]),
                      lambda p: (p[0], -p[1]), lambda p: (p[1], -p[0]),
                      lambda p: (-p[1], p[0]), lambda p: (-p[0], -p[1]),
                      lambda p: (-p[1], -p[0]))
        for tf in transforms:
            if norm([tf(p) for p in self.conf]) == tgt:
                return True
        return False

    def celebrate(self):
        self.celebrated = self.contacts
        self.win_overlay = True
        self.drag = None
        if self.duel:
            self.duel_winner = 2 - self.duel_turn
        self.gold = bool(self.best_contacts is not None
                         and self.contacts >= self.best_contacts)
        self.perfect = self.is_perfect()
        par = self.par or ((self.target or 6) + 6)
        self.stars = 3 if self.moves <= par else (2 if self.moves <= par + 6 else 1)
        self.stars_t = 0.0
        self.star_chimes = 0
        career = self.save.setdefault("career", {})
        career["folds"] = int(career.get("folds", 0)) + 1
        career["moves"] = int(career.get("moves", 0)) + self.moves
        career["time"] = round(float(career.get("time", 0)) + self.time, 1)
        if self.mode == "campaign":
            if self.level_i < len(LEVELS) - 1:
                self.unlocked = max(self.unlocked, self.level_i + 1)
            self.save["unlocked"] = self.unlocked
            self.save["completed"] = max(self.save.get("completed", 0),
                                         self.level_i + 1)
            best = self.save.setdefault("best", {}).setdefault(str(self.level_i), {})
            if self.moves < best.get("moves", 10 ** 9):
                best["moves"] = self.moves
            if self.time < best.get("time", 10 ** 9):
                best["time"] = round(self.time, 1)
            if self.gold:
                best["gold"] = True
            stars = self.save.setdefault("stars", {})
            key = str(self.level_i)
            stars[key] = max(int(stars.get(key, 0)), self.stars)
            persist(self.save)
            if self.save.get("completed", 0) >= len(LEVELS):
                self.award("alllevels")
        elif self.mode == "endless":
            self.save["endless"] = self.save.get("endless", 0) + 1
            persist(self.save)
            if self.save.get("endless", 0) >= 5:
                self.award("endless5")
        elif self.mode == "daily":
            d = self.save.setdefault("daily", {})
            prev = d.get(today_str())
            if prev is None or self.moves < prev.get("moves", 10 ** 9):
                d[today_str()] = {"moves": self.moves, "time": round(self.time, 1)}
            persist(self.save)
            if daily_streak(self.save) >= 3:
                self.award("daily3")
        elif self.mode == "designer":
            self.save["designer"] = self.save.get("designer", 0) + 1
            persist(self.save)
            if self.save.get("designer", 0) >= 3:
                self.award("designer3")
        if self.duel:
            self.award("duelist")
        if self.perfect:
            self.award("perfect")
        if self.gold:
            self.award("gold")
        if self.hints == 0 and not self.ai_assisted:
            self.award("nohint")
        if self.time < 30:
            self.award("speed")
        if self.moves <= par:
            self.award("par")
        self.confetti()
        play("win")

    def overlay_click(self, pos):
        if self.win_next.collidepoint(pos):
            play("ui")
            if self.mode == "endless":
                self.load_endless()
            elif self.mode == "daily":
                self.state = "title"
            elif self.mode == "designer":
                self.win_overlay = False
                self.designer_open = True
                self.designer_seq = ""
                self.designer_msg = ""
            elif self.level_i < len(LEVELS) - 1:
                self.load_level(self.level_i + 1)
            else:
                self.state = "title"
        elif self.win_mine.collidepoint(pos):
            self.win_overlay = False
            play("ui")
            self.start_replay("mine")
        elif self.win_watch.collidepoint(pos):
            self.win_overlay = False
            play("ui")
            self.start_replay("ai")
        elif self.win_keep.collidepoint(pos):
            self.win_overlay = False
            play("ui")

    # ---------------------------------------------------------------- actions
    def btn_action(self, bid):
        if bid == "prev":
            if self.mode != "campaign":
                self.load_level(self.unlocked)
            else:
                self.goto_level(self.level_i - 1)
        elif bid == "next":
            if self.mode == "endless":
                self.load_endless()
            elif self.mode == "daily":
                self.state = "title"
                persist(self.save)
            elif self.mode == "designer":
                self.designer_open = True
                self.designer_seq = ""
                self.designer_msg = ""
            elif (self.level_i < len(LEVELS) - 1
                  and self.level_i < self.unlocked):
                self.goto_level(self.level_i + 1)
            else:
                self.toast("Fold this level to unlock the next one")
        elif bid == "endless":
            self.load_endless()
        elif bid == "undo":
            self.do_undo()
        elif bid == "redo":
            self.do_redo()
        elif bid == "reset":
            self.reset_level()
        elif bid == "hint":
            self.show_hint()
        elif bid == "ai":
            self.adopt_ai()
        elif bid == "help":
            if self.mode == "campaign":
                self.start_lessons()
            else:
                self.toast("Lessons live in the campaign levels")
        elif bid == "mute":
            self.toggle_mute()

    def goto_level(self, i):
        if self.state != "play":
            return
        i = clamp(i, 0, len(LEVELS) - 1)
        if i > self.unlocked:
            self.toast("Locked - fold the current level first")
            return
        self.load_level(i)
        play("ui")

    def do_undo(self):
        if self.state != "play" or self.win_overlay \
                or self.drag or self.shake_queue > 0 or self.replay:
            return
        if not self.undo:
            self.toast("Nothing to undo")
            return
        self.redo.append(list(self.conf))
        self.conf = self.undo.pop()
        self.celebrated = -1
        self.refresh(silent=True)
        self.snapshot_trace()
        play("ui")

    def do_redo(self):
        if self.state != "play" or self.win_overlay \
                or self.drag or self.shake_queue > 0 or self.replay:
            return
        if not self.redo:
            self.toast("Nothing to redo")
            return
        self.undo.append(list(self.conf))
        self.conf = self.redo.pop()
        self.celebrated = -1
        self.refresh(silent=True)
        self.snapshot_trace()
        play("ui")

    def reset_level(self):
        if self.state != "play" or self.win_overlay \
                or self.drag or self.shake_queue > 0 or self.replay:
            return
        self.undo.append(list(self.conf))
        self.redo = []
        self.conf = initial_conf(self.n)
        self.moves = 0
        self.time = 0.0
        self.celebrated = -1
        self.combo = 0
        self.last_progress = 0.0
        self.tip_shown = False
        self.mytrace = [list(self.conf)]
        self.duel_turn = 0
        self.duel_moves = [0, 0]
        self.refresh(silent=True)
        self.toast("Level reset")
        play("ui")

    def show_hint(self):
        if self.state != "play" or self.win_overlay:
            return
        if not self.ghost_conf:
            self.toast("No hint yet - the AI is still folding")
            return
        self.hint_t = 5.0
        self.hints += 1
        play("ui")

    def adopt_ai(self):
        if self.state != "play" or self.win_overlay \
                or self.drag or self.shake_queue > 0 or self.replay:
            return
        if not self.best_conf:
            self.toast("The AI is still thinking...")
            return
        self.undo.append(list(self.conf))
        self.redo = []
        self.conf = [tuple(c) for c in self.best_conf]
        self.ai_assisted = True
        self.moves += 1
        self.morph_t = 1.8
        self.refresh()
        self.snapshot_trace()
        self.next_turn()
        play("morph")
        self.toast("AI fold adopted - Z undoes it")
        self.check_win()

    def toggle_mute(self):
        MUTED["on"] = not MUTED["on"]
        self.save["muted"] = MUTED["on"]
        persist(self.save)
        self.toast("Sound off" if MUTED["on"] else "Sound on")

    def screenshot(self):
        if self.screen is None:
            return
        try:
            path = os.path.join(os.path.expanduser("~"),
                                "foldquest_shot_%d.png" % pygame.time.get_ticks())
            pygame.image.save(self.screen, path)
            self.toast("Screenshot saved to your home folder")
        except Exception:
            self.toast("Screenshot failed")

    def submit_design(self):
        seq = self.designer_seq.upper()
        if len(seq) < 8:
            self.designer_msg = "Too short - use at least 8 residues."
            return
        if seq.count("H") < 3:
            self.designer_msg = "Add at least 3 hydrophobic (H) residues."
            return
        if any(ch not in "HP" for ch in seq):
            self.designer_msg = "Only H and P residues are allowed."
            return
        self.designer_open = False
        play("ui")
        self.load_designer(seq)

    def award(self, aid):
        ach = self.save.setdefault("ach", {})
        if ach.get(aid):
            return
        ach[aid] = True
        persist(self.save)
        for a_id, name, _desc in ACH:
            if a_id == aid:
                self.toast("AWARD UNLOCKED: %s" % name)
                self.spawn_sparks(W // 2, 60, COL_GOLD, 14)
                play("ding")
                return

    # ------------------------------------------------------------ fold analysis
    def compute_analysis(self):
        occ = set(self.conf)
        h_idx = [i for i in range(self.n) if self.seq[i] == "H"]
        buried = 0
        exposed_faces = 0
        for i in h_idx:
            c = self.conf[i]
            full = True
            for d in DIRS:
                nb = (c[0] + d[0], c[1] + d[1])
                if nb not in occ:
                    full = False
                    exposed_faces += 1
            if full:
                buried += 1
        xs = [p[0] for p in self.conf]
        ys = [p[1] for p in self.conf]
        w = max(xs) - min(xs) + 1
        h = max(ys) - min(ys) + 1
        fill = self.n / float(w * h)
        runs = self.strand_runs()
        longest = max((j - i + 1 for (i, j) in runs), default=0)
        strands = len(runs)
        wet = 0
        if self.show_water:
            for wp in self.water:
                for i in h_idx:
                    if math.hypot(wp[0] - self.vis[i][0],
                                  wp[1] - self.vis[i][1]) < 55:
                        wet += 1
                        break
        ratio = self.contacts / float(self.target) if self.target else 1.0
        if ratio >= 0.999 and exposed_faces == 0:
            grade = "S"
        elif ratio >= 0.999:
            grade = "A"
        elif ratio >= 0.75:
            grade = "B"
        elif ratio >= 0.5:
            grade = "C"
        else:
            grade = "D"
        return dict(buried=buried, nH=len(h_idx), exposed=exposed_faces,
                    w=w, h=h, fill=fill, longest=longest, strands=strands,
                    wet=wet, grade=grade, ratio=ratio)

    # ---------------------------------------------------------------- fx bits
    def toast(self, txt, dur=2.8):
        self.toasts.append(dict(txt=txt, t=dur))
        if len(self.toasts) > 6:
            self.toasts.pop(0)

    def spawn_sparks(self, x, y, col, n=8):
        for _ in range(n):
            ang = random.uniform(0, 6.2832)
            sp = random.uniform(50, 170)
            life = random.uniform(0.35, 0.8)
            self.particles.append(dict(x=x, y=y,
                                       vx=math.cos(ang) * sp,
                                       vy=math.sin(ang) * sp - 40,
                                       g=150, life=life, maxlife=life,
                                       size=random.uniform(2, 4.5), col=col))

    def confetti(self):
        cols = [COL_GOLD, COL_TEAL, COL_H_FILL, COL_P_FILL, (255, 255, 255)]
        for _ in range(90):
            life = random.uniform(1.2, 2.6)
            self.particles.append(dict(x=W // 2 + random.uniform(-40, 40),
                                       y=H // 2 - 60,
                                       vx=random.uniform(-280, 280),
                                       vy=random.uniform(-330, -60),
                                       g=350, life=life, maxlife=life,
                                       size=random.uniform(3, 6),
                                       col=random.choice(cols),
                                       angle=random.uniform(0, 6.28),
                                       spin=random.uniform(-7, 7),
                                       flutter=random.uniform(0, 6.28),
                                       flut=random.uniform(5, 11)))

    # ------------------------------------------------------------------ draw
    def draw(self, screen):
        screen.blit(self.bg, (0, 0))
        if self.state == "title":
            self.draw_title(screen)
        else:
            off = (0, 0)
            if self.shake_amp > 0.2:
                s = int(self.shake_amp)
                off = (random.randint(-s, s), random.randint(-s, s))
            self.draw_world(screen, off)
            self.draw_top_hud(screen)
            self.draw_bottom_hud(screen)
            self.draw_floats(screen)
            self.draw_banner(screen)
            self.draw_combo(screen)
            self.draw_replay(screen)
            self.draw_toasts(screen)
            if self.tutorial:
                self.draw_lessons(screen)
            if self.win_overlay:
                self.draw_win(screen)
            if self.paused:
                self.draw_paused(screen)
            self.draw_particles(screen, off)
        if self.ach_open:
            self.draw_achievements(screen)
        if self.notes_open:
            self.draw_notes(screen)
        if self.analysis_open:
            self.draw_analysis(screen)
        if self.designer_open:
            self.draw_designer(screen)

    def draw_world(self, screen, off):
        ox, oy = off
        glows = ART.get("glow", {})
        water = ART.get("water")
        gold_small = ART.get("gold_small")
        gridrect = pygame.Rect(OX - 4, OY - 4, GRID_W * TILE + 8, GRID_H * TILE + 8)
        for (i, j) in self.pairs:
            x1, y1 = self.vis[i][0] + ox, self.vis[i][1] + oy
            x2, y2 = self.vis[j][0] + ox, self.vis[j][1] + oy
            a = 0.5 + 0.5 * math.sin(self.phase * 2.6 + i * 0.9 + j * 0.5)
            col = (int(185 + 70 * a), int(130 + 85 * a), int(40 + 60 * a))
            pygame.draw.line(screen, col, (x1, y1), (x2, y2), 3 + int(2 * a))
            for tt in ((self.phase * 0.6) % 1.0, (self.phase * 0.6 + 0.5) % 1.0):
                px = x1 + (x2 - x1) * tt
                py = y1 + (y2 - y1) * tt
                pygame.draw.circle(screen, (255, 230, 150), (int(px), int(py)), 3)
                pygame.draw.circle(screen, (255, 255, 235), (int(px), int(py)), 1)
            mxx, myy = (x1 + x2) / 2, (y1 + y2) / 2
            aa = self.phase * 1.3 + (i + j) * 0.5
            pts = [(mxx + 5 * math.cos(aa + kk * math.pi / 2),
                    myy + 5 * math.sin(aa + kk * math.pi / 2)) for kk in range(4)]
            pygame.draw.polygon(screen, (255, 238, 160), pts)
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        if self.target and self.contacts >= self.target and not self.tutorial:
            ga = int(110 + 70 * math.sin(self.phase * 3.0))
            rrect(fx, (255, 204, 64, ga), gridrect, 12, 3)
            rrect(fx, (255, 204, 64, ga // 3), gridrect.inflate(10, 10), 14, 2)
        if self.show_water and water:
            for w in self.water:
                tw = (math.sin(self.phase * 2.0 + w[4]) + 1.0) * 1.5
                blit_center(fx, water[min(2, int(tw))], w[0], w[1])
        for i in range(self.n):
            tr = self.trail[i]
            if len(tr) > 1:
                g = COL_H_GLOW if self.seq[i] == "H" else COL_P_GLOW
                for k in range(len(tr) - 1):
                    f = tr[k][2] / 0.38
                    a = int(60 * f)
                    if a > 3:
                        wd = max(1, int(3 * f))
                        pygame.draw.line(fx, (g[0], g[1], g[2], a),
                                         (tr[k][0], tr[k][1]),
                                         (tr[k + 1][0], tr[k + 1][1]), wd)
        for (i, j) in self.pairs:
            x1, y1 = self.vis[i][0] + ox, self.vis[i][1] + oy
            x2, y2 = self.vis[j][0] + ox, self.vis[j][1] + oy
            pygame.draw.line(fx, (255, 170, 40, 60), (x1, y1), (x2, y2), 13)
        for i in range(self.n):
            x, y = self.vis[i][0] + ox, self.vis[i][1] + oy
            pygame.draw.circle(fx, (0, 0, 0, 75), (int(x + 3), int(y + 5)), BEAD_R)
        for i in range(self.n):
            x, y = self.vis[i][0] + ox, self.vis[i][1] + oy
            kind = self.seq[i]
            if kind == "H":
                b = clamp(int(1.5 + 1.5 * math.sin(self.phase * 2.0 + i * 0.55)), 0, 2)
            else:
                b = 1
            if i == self.hover or (self.drag and i == self.drag["i"]):
                b = 2
            lst = glows.get(kind)
            if lst:
                blit_center(fx, lst[b], x, y)
            if gold_small and kind == "H" and i in self.contact_idx:
                blit_center(fx, gold_small, x, y)
        for i in range(self.n - 1):
            p1 = (self.vis[i][0] + ox, self.vis[i][1] + oy)
            p2 = (self.vis[i + 1][0] + ox, self.vis[i + 1][1] + oy)
            pygame.draw.line(fx, (0, 0, 0, 85), (p1[0], p1[1] + 4), (p2[0], p2[1] + 4), 9)
        if (self.hover is not None and not self.drag
                and 0 < self.hover < self.n - 1
                and not self.win_overlay):
            i = self.hover
            if (self.n - i) <= (i + 1):
                mside, anc = range(i, self.n), i - 1
            else:
                mside, anc = range(0, i + 1), i + 1
            for j in mside:
                x, y = self.vis[j]
                pygame.draw.circle(fx, (255, 255, 255, 24), (int(x), int(y)), BEAD_R + 5)
            ax, ay = cell_px(self.conf[anc])
            pygame.draw.circle(fx, (255, 255, 255, 90), (ax, ay), BEAD_R + 7, 2)
        if (self.mode == "campaign" and self.level_i == 0 and self.moves == 0
                and not self.tutorial and not self.drag
                and not self.win_overlay):
            for ei in (0, self.n - 1):
                x, y = self.vis[ei]
                rr = BEAD_R + 9 + int(4 * math.sin(self.phase * 4))
                pygame.draw.circle(fx, (120, 220, 200, 170), (int(x), int(y)), rr, 2)
        self.draw_ghost(fx)
        self.draw_drag_fx(fx, ox, oy)
        if self.bad_flash > 0 and self.bad_pos:
            bx, by = self.bad_pos
            r = int(TILE * 0.38 * (0.5 + 0.5 * self.bad_flash))
            pygame.draw.circle(fx, (235, 70, 60, int(150 * self.bad_flash)),
                               (int(bx), int(by)), r, 3)
        screen.blit(fx, (0, 0))
        for i in range(self.n - 1):
            p1 = (self.vis[i][0] + ox, self.vis[i][1] + oy)
            p2 = (self.vis[i + 1][0] + ox, self.vis[i + 1][1] + oy)
            base, hi = bond_style(self.seq[i], self.seq[i + 1])
            pygame.draw.line(screen, base, p1, p2, 7)
            pygame.draw.line(screen, hi, (p1[0], p1[1] - 1), (p2[0], p2[1] - 1), 2)
        for (a, b) in self.strand_runs():
            p1 = (self.vis[a][0] + ox, self.vis[a][1] + oy)
            p2 = (self.vis[b][0] + ox, self.vis[b][1] + oy)
            pygame.draw.line(screen, COL_STRAND, p1, p2, 3)
            pygame.draw.circle(screen, (205, 185, 255), (int(p1[0]), int(p1[1])), 3)
            pygame.draw.circle(screen, (205, 185, 255), (int(p2[0]), int(p2[1])), 3)
        moving = set(self.drag["moving"]) if (self.drag and "moving" in self.drag) else set()
        for i in range(self.n):
            x, y = self.vis[i][0] + ox, self.vis[i][1] + oy
            kind = self.seq[i]
            sc = 1.0 + 0.22 * self.pop[i]
            if self.drag and i == self.drag["i"]:
                sc = max(sc, 1.2)
            elif i == self.hover:
                sc = max(sc, 1.1)
            if i in moving:
                sc = max(sc, 1.08)
            draw_bead(screen, x, y, BEAD_R, kind,
                      ring=(kind == "H" and i in self.contact_idx), scale=sc)
            if i == self.hover and not self.drag:
                hcol = COL_TEAL if (i == 0 or i == self.n - 1) else (255, 255, 255)
                rr = BEAD_R + 8
                for kk in range(8):
                    ang = self.phase * 2.0 + kk * math.pi / 4
                    pygame.draw.circle(screen, hcol,
                                       (int(x + rr * math.cos(ang)),
                                        int(y + rr * math.sin(ang))), 2)
        if self.show_idx:
            for i in range(self.n):
                x, y = self.vis[i][0] + ox, self.vis[i][1] + oy
                draw_text(screen, str(i + 1), 11, x, y + BEAD_R + 2,
                          COL_DIM, "tc", shadow=False)
        if (self.mode == "campaign" and self.level_i == 0 and self.moves == 0
                and not self.tutorial and not self.drag
                and not self.win_overlay):
            x, y = self.vis[0]
            draw_text(screen, "grab an end - draw your fold", 15,
                      x - 70, y - 52, COL_TEAL, "tl")
        if self.hover is not None and not self.win_overlay:
            i = self.hover
            ch = self.seq[i]
            if i == 0 or i == self.n - 1:
                tip = "pull the chain"
            else:
                tip = "pivot · Ctrl redraws loop"
            txt = "#%d %s · %s" % (i + 1, ch, tip)
            if self.link_count[i]:
                txt += " · %d link" % self.link_count[i]
            x, y = self.vis[i][0] + ox, self.vis[i][1] + oy
            tw = F(15).size(txt)[0]
            r = pygame.Rect(int(x) + 14, int(y) - 44, tw + 18, 26)
            r.clamp_ip(pygame.Rect(8, HUD_TOP + 8, W - 16,
                                   H - HUD_TOP - HUD_BOT - 16))
            rrect(screen, (7, 9, 16), r.move(2, 3), 7)
            rrect(screen, (16, 22, 36), r, 7)
            rrect(screen, (70, 88, 124), r, 7, 1)
            draw_text(screen, txt, 15, r.x + 9, r.y + 5, COL_TEXT, "tl", shadow=False)

    def draw_ghost(self, fx):
        if self.hint_t <= 0 or not self.ghost_conf:
            return
        a01 = clamp(min(self.hint_t / 0.6, (5.0 - self.hint_t) / 0.35), 0.0, 1.0)
        g = self.ghost_conf
        for kk in range(len(g) - 1):
            p1, p2 = cell_px(g[kk]), cell_px(g[kk + 1])
            pygame.draw.line(fx, (150, 160, 185, int(55 * a01)), p1, p2, 5)
        for (i, j) in contact_pairs(g, self.seq):
            p1, p2 = cell_px(g[i]), cell_px(g[j])
            pygame.draw.line(fx, (255, 204, 64, int(120 * a01)), p1, p2, 3)
        for i, c in enumerate(g):
            x, y = cell_px(c)
            pygame.draw.circle(fx, (255, 204, 64, int(26 * a01)), (x, y), BEAD_R)
            pygame.draw.circle(fx, (255, 204, 64, int(150 * a01)), (x, y), BEAD_R, 2)
            img = F(13).render(str(i + 1), True, (255, 224, 130))
            img.set_alpha(int(200 * a01))
            fx.blit(img, img.get_rect(center=(x, y + 1)))
        img = F(15).render("target shape (hint)", True, COL_GOLD)
        img.set_alpha(int(220 * a01))
        fx.blit(img, img.get_rect(midtop=(W // 2, OY + 8)))

    def draw_drag_fx(self, fx, ox, oy):
        if not self.drag or self.win_overlay:
            return
        m = pygame.mouse.get_pos()
        c = px_to_cell(m)
        r = pygame.Rect(OX + c[0] * TILE + 5, OY + c[1] * TILE + 5, TILE - 10, TILE - 10)
        rrect(fx, (255, 255, 255, 26), r, 8, 3)
        rrect(fx, (255, 255, 255, 70), r, 8, 1)
        kind = self.drag["kind"]
        if kind == "pivot":
            d = self.drag
            for gc in (d.get("ghost") or []):
                x, y = cell_px(gc)
                pygame.draw.circle(fx, (255, 70, 60, 60), (x, y), BEAD_R)
                pygame.draw.circle(fx, (255, 110, 90, 150), (x, y), BEAD_R, 2)
            fl = d.get("flip")
            if fl is not None:
                x, y = cell_px(fl)
                a = int(90 + 90 * (0.5 + 0.5 * math.sin(self.phase * 6)))
                pygame.draw.circle(fx, (255, 204, 64, a), (x, y), BEAD_R + 6, 3)
            ap = cell_px(self.conf[d["anchor"]])
            ax, ay = ap[0] + ox, ap[1] + oy
            dx, dy = m[0] - ax, m[1] - ay
            dist = math.hypot(dx, dy)
            n = max(2, int(dist // 16))
            for t in range(n):
                if t % 2:
                    continue
                px = ax + dx * (t + 0.5) / n
                py = ay + dy * (t + 0.5) / n
                pygame.draw.circle(fx, (255, 255, 255, 80), (int(px), int(py)), 2)
            pygame.draw.circle(fx, (255, 255, 255, 110), (int(ax), int(ay)), BEAD_R + 8, 2)
        elif kind == "replan":
            d = self.drag
            cells = self.conf[d["lo"]:d["hi"] + 1]
            xs = [cell_px(cc)[0] for cc in cells]
            ys = [cell_px(cc)[1] for cc in cells]
            rect = pygame.Rect(min(xs) - TILE // 2 - 2, min(ys) - TILE // 2 - 2,
                               max(xs) - min(xs) + TILE + 4,
                               max(ys) - min(ys) + TILE + 4)
            rrect(fx, (120, 220, 200, 90), rect, 10, 2)
            ip = cell_px(self.conf[d["i"]])
            ix, iy = ip[0] + ox, ip[1] + oy
            dx, dy = m[0] - ix, m[1] - iy
            dist = math.hypot(dx, dy)
            n = max(2, int(dist // 14))
            for t in range(n):
                if t % 2:
                    continue
                px = ix + dx * (t + 0.5) / n
                py = iy + dy * (t + 0.5) / n
                pygame.draw.circle(fx, (120, 220, 200, 120), (int(px), int(py)), 2)
        else:
            for t, pc in enumerate(self.drag.get("path") or []):
                x, y = cell_px(pc)
                al = max(26, 150 - t * 14)
                pygame.draw.circle(fx, (120, 220, 200, al), (x, y), 5)
            hp = cell_px(self.conf[self.drag["i"]])
            pygame.draw.line(fx, (255, 255, 255, 60),
                             (int(hp[0] + ox), int(hp[1] + oy)), m, 2)

    def draw_banner(self, screen):
        if (not self.target or self.contacts < self.target or self.replay
                or self.win_overlay or self.tutorial):
            return
        a = 0.6 + 0.4 * math.sin(self.phase * 4)
        y = OY + GRID_H * TILE - 26
        g = ART.get("banner_glow")
        if g:
            screen.blit(g, (W // 2 - g.get_width() // 2, y - 36))
        txt = "TARGET REACHED  ·  energy -%d" % self.contacts
        img = F(24).render(txt, True, COL_GOLD)
        img.set_alpha(int(170 + 85 * a))
        r = img.get_rect(center=(W // 2, y))
        sh = F(24).render(txt, True, (8, 10, 16))
        screen.blit(sh, r.move(2, 2))
        screen.blit(img, r)
        if self.drag:
            draw_text(screen, "release to lock it in", 14, W // 2, y + 20,
                      COL_DIM, "tc", shadow=False)

    def draw_replay(self, screen):
        if not self.replay:
            return
        r = self.replay
        n = len(r["trace"])
        y = OY + 16
        img = F(20).render(r.get("title", "REPLAY"), True, COL_TEAL)
        screen.blit(img, img.get_rect(midtop=(W // 2, y)))
        draw_text(screen, "click or press any key to skip", 13, W // 2, y + 28,
                  COL_DIM, "tc", shadow=False)
        bw = 300
        x0 = W // 2 - bw // 2
        pygame.draw.rect(screen, (30, 40, 60), (x0, y + 50, bw, 8))
        w = int(bw * (r["idx"] / max(1, n - 1)))
        if w > 2:
            rrect(screen, COL_TEAL, (x0, y + 50, w, 8), 4)
        ens = r.get("energy") or []
        tps = r.get("temps") or []
        if len(ens) > 1:
            has_t = len(tps) > 1
            bx, bw2 = W // 2 - 160, 320
            bh = 40
            by = OY + GRID_H * TILE - (108 if has_t else 78)
            card = pygame.Rect(bx - 10, by - 22, bw2 + 20,
                               bh + (30 if has_t else 0) + 30)
            rrect(screen, (13, 18, 30), card, 8)
            draw_text(screen, "energy trace", 12, bx, by - 18, COL_DIM, "tl", shadow=False)
            mx = max(ens) or 1
            if self.target:
                ty = by + bh - bh * self.target / mx
                pygame.draw.line(screen, (170, 130, 44), (bx, ty), (bx + bw2, ty), 1)
            pts = []
            for i2, e in enumerate(ens):
                px = bx + bw2 * i2 / float(len(ens) - 1)
                py = by + bh - bh * e / float(mx)
                pts.append((px, py))
            pygame.draw.lines(screen, COL_TEAL, False, pts, 2)
            pygame.draw.circle(screen, (255, 255, 255),
                               (int(pts[-1][0]), int(pts[-1][1])), 3)
            if has_t:
                ty0, ty1 = by + bh + 12, by + bh + 32
                draw_text(screen, "temperature (hot - cool)", 12, bx, ty0 - 4,
                          (200, 130, 100), "tl", shadow=False)
                mt = max(tps) or 1.0
                pts2 = []
                for i2, t in enumerate(tps):
                    px = bx + bw2 * i2 / float(len(tps) - 1)
                    py = ty1 - (ty1 - ty0) * t / float(mt)
                    pts2.append((px, py))
                pygame.draw.lines(screen, COL_HOT, False, pts2, 2)

    def draw_combo(self, screen):
        if self.combo >= 2 and self.combo_t > 0:
            a = 0.55 + 0.45 * math.sin(self.phase * 5.0)
            img = F(22).render("COMBO x%d" % self.combo, True, COL_TEAL)
            img.set_alpha(int(150 + 105 * a))
            screen.blit(img, img.get_rect(midtop=(W // 2, OY + 30)))

    # -------------------------------------------------------- folding school
    def draw_tut_icon(self, surf, cx, cy):
        s = self.tut_step
        if s == 0:
            draw_bead(surf, cx - 16, cy, 13, "H")
            draw_bead(surf, cx + 16, cy, 13, "P")
        elif s == 1:
            draw_bead(surf, cx, cy, 13, "H")
            for ang in (0.5, 1.7, 2.9, 4.3, 5.6):
                wx = cx + 30 * math.cos(ang)
                wy = cy + 30 * math.sin(ang)
                pygame.draw.circle(surf, COL_WATER, (int(wx), int(wy)), 3)
        elif s == 2:
            draw_bead(surf, cx - 18, cy - 12, 11, "H", letters=False)
            draw_bead(surf, cx + 18, cy - 12, 11, "H", letters=False)
            pygame.draw.line(surf, COL_GOLD, (cx - 18, cy - 12), (cx + 18, cy - 12), 4)
        elif s == 3:
            draw_bead(surf, cx - 24, cy, 13, "H")
            pygame.draw.circle(surf, COL_TEAL, (cx - 24, cy), 20, 2)
            for t2 in range(4):
                px = cx + 4 + t2 * 10
                pygame.draw.line(surf, COL_TEAL, (px, cy - 7), (px + 6, cy), 2)
                pygame.draw.line(surf, COL_TEAL, (px + 6, cy), (px, cy + 7), 2)
        elif s == 4:
            draw_bead(surf, cx, cy, 13, "H")
            rr = 22
            for kk in range(8):
                ang = self.phase * 1.5 + kk * math.pi / 4
                pygame.draw.circle(surf, (255, 255, 255),
                                   (int(cx + rr * math.cos(ang)),
                                    int(cy + rr * math.sin(ang))), 2)
        elif s == 5:
            for j, kl in enumerate(("T", "H", "A", "V")):
                r = pygame.Rect(cx - 58 + j * 30, cy - 12, 26, 24)
                rrect(surf, (36, 48, 74), r, 6)
                rrect(surf, COL_TEAL, r, 6, 1)
                draw_text(surf, kl, 15, r.centerx, r.y + 3, COL_TEXT, "tc", shadow=False)
        else:
            pygame.draw.circle(surf, COL_GOLD, (int(cx), int(cy)), 22, 3)
            draw_star(surf, cx, cy, 10, COL_GOLD)

    def draw_lessons(self, screen):
        step = TUT_STEPS[self.tut_step]
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        card = LESSON_CARD
        rrect(fx, (6, 8, 14, 200), card.move(0, 4), 14)
        rrect(fx, (18, 24, 40, 228), card, 14)
        rrect(fx, COL_TEAL, card, 14, 2)
        draw_text(fx, "LESSON %d / %d" % (self.tut_step + 1, len(TUT_STEPS)), 13,
                  card.x + 18, card.y + 13, COL_TEAL, "tl", shadow=False)
        draw_text(fx, step["title"], 21, card.x + 130, card.y + 7, COL_GOLD, "tl")
        self.draw_tut_icon(fx, card.x + 46, card.y + 104)
        lines = []
        for t in step["text"]:
            lines.extend(wrap_text(t, 14, 590))
        y = card.y + 48
        for ln in lines[:5]:
            draw_text(fx, ln, 14, card.x + 92, y, COL_TEXT, "tl", shadow=False)
            y += 17
        if self.tut_obj_done:
            draw_text(fx, "DONE!", 15, card.x + 92, card.y + card.h - 26, COL_GOLD, "tl")
        else:
            draw_text(fx, step["obj"][1], 15, card.x + 92, card.y + card.h - 26,
                      COL_TEAL, "tl", shadow=False)
        screen.blit(fx, (0, 0))
        self.draw_button(screen, self.tut_next, "NEXT >", True,
                         self.tut_obj_done
                         or self.tut_next.collidepoint(pygame.mouse.get_pos()))
        hot = self.tut_skip.collidepoint(pygame.mouse.get_pos())
        draw_text(screen, "skip lessons", 13, self.tut_skip.x, self.tut_skip.y,
                  COL_TEXT if hot else COL_DIM, "tl", shadow=False)

    def draw_notes(self, screen):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        fx.fill((5, 8, 15, 185))
        screen.blit(fx, (0, 0))
        panel = self.notes_panel
        rrect(screen, (6, 8, 14), panel.move(0, 6), 16)
        rrect(screen, (18, 24, 40), panel, 14)
        toplight = panel.inflate(-16, -16)
        toplight.height = 64
        rrect(screen, (26, 35, 56), toplight, 10)
        rrect(screen, COL_GOLD, panel, 14, 2)
        draw_text(screen, "FIELD NOTES - the science of folding", 26, W // 2, 108,
                  COL_GOLD, "tc", shadow=False)
        self.notes_rows = []
        m = pygame.mouse.get_pos()
        y = 150
        for i, (title, _body) in enumerate(NOTES):
            rr = pygame.Rect(panel.x + 16, y, 250, 46)
            hot = rr.collidepoint(m)
            if i == self.notes_idx:
                rrect(screen, (36, 48, 74), rr, 8)
                rrect(screen, COL_TEAL, rr, 8, 2)
            elif hot:
                rrect(screen, (28, 38, 60), rr, 8)
            draw_text(screen, "%d." % (i + 1), 13, rr.x + 8, rr.y + 6,
                      COL_DIM, "tl", shadow=False)
            draw_text(screen, title, 15, rr.x + 30, rr.y + 5,
                      COL_TEXT if i == self.notes_idx else (150, 160, 178),
                      "tl", shadow=False)
            self.notes_rows.append(rr)
            y += 52
        title, body = NOTES[self.notes_idx]
        draw_text(screen, title, 24, panel.x + 292, 150, COL_GOLD, "tl")
        yy = 186
        for ln in wrap_text(body, 16, 510):
            draw_text(screen, ln, 16, panel.x + 292, yy, COL_TEXT, "tl", shadow=False)
            yy += 22
        self.draw_button(screen, self.notes_close, "CLOSE", True,
                         self.notes_close.collidepoint(m))
        draw_text(screen, "press S or click a topic", 13, W // 2,
                  panel.bottom - 26, COL_DIM, "tc", shadow=False)

    # ------------------------------------------------------------ analysis UI
    def draw_analysis(self, screen):
        an = self.compute_analysis()
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        fx.fill((5, 8, 15, 185))
        screen.blit(fx, (0, 0))
        panel = pygame.Rect(W // 2 - 380, 120, 760, 560)
        rrect(screen, (6, 8, 14), panel.move(0, 6), 16)
        rrect(screen, (18, 24, 40), panel, 14)
        toplight = panel.inflate(-16, -16)
        toplight.height = 60
        rrect(screen, (26, 35, 56), toplight, 10)
        rrect(screen, COL_GOLD, panel, 14, 2)
        x0 = panel.x + 24
        draw_text(screen, "FOLD ANALYSIS", 30, x0, 132, COL_GOLD, "tl")
        draw_text(screen, "how protein-like is your fold?", 14, x0, 164,
                  COL_DIM, "tl", shadow=False)
        # grade badge
        gcx, gcy = panel.right - 90, 160
        pygame.draw.circle(screen, (26, 35, 56), (gcx, gcy), 38)
        pygame.draw.circle(screen, COL_GOLD, (gcx, gcy), 38, 3)
        draw_text(screen, an["grade"], 44, gcx, gcy - 26, COL_GOLD, "tc", shadow=False)
        draw_text(screen, "grade", 12, gcx, gcy + 22, COL_DIM, "tc", shadow=False)
        rows = [
            ("H-H contacts", "%d / %s" % (self.contacts, self.target),
             "each gold link is worth -1 energy; the target is the native energy",
             clamp(an["ratio"], 0.0, 1.0)),
            ("Core packing", "%d / %d hydrophobics fully buried"
             % (an["buried"], an["nH"]),
             "a real protein's core is dry - every side of an H packed by chain",
             an["buried"] / float(max(1, an["nH"]))),
            ("Oily surface", "%d exposed hydrophobic faces" % an["exposed"],
             "open oily faces invite water and, in cells, aggregation", None),
            ("Footprint", "%d x %d grid · %d%% filled"
             % (an["w"], an["h"], int(an["fill"] * 100)),
             "compact folds fit more contacts into less space",
             clamp(an["fill"], 0.0, 1.0)),
            ("Strands", "%d strands · longest %d residues"
             % (an["strands"], an["longest"]),
             "straight runs are this game's beta-strands", None),
            ("Water contact",
             "%d specks touching H" % an["wet"] if self.show_water
             else "enable water (W) to measure",
             "a good hydrophobic core pushes the water specks away", None),
        ]
        y = 200
        for lab, val, note, frac in rows:
            draw_text(screen, lab, 16, x0, y, COL_TEXT, "tl", shadow=False)
            draw_text(screen, val, 16, x0 + 660, y, COL_GOLD, "tr", shadow=False)
            if frac is not None:
                rrect(screen, (30, 40, 60), (x0, y + 24, 300, 8), 4)
                if frac > 0.02:
                    rrect(screen, COL_GOLD, (x0, y + 24, int(300 * frac), 8), 4)
            for j, ln in enumerate(wrap_text(note, 13, 370)[:2]):
                draw_text(screen, ln, 13, x0 + 330, y + 1 + j * 15, COL_DIM,
                          "tl", shadow=False)
            y += 62
        draw_text(screen, "grade blends contacts vs target with core burial - "
                          "S needs a fully sealed hydrophobic core",
                  13, W // 2, panel.bottom - 44, COL_DIM, "tc", shadow=False)
        draw_text(screen, "X or click to close", 13, W // 2, panel.bottom - 24,
                  COL_DIM, "tc", shadow=False)

    def draw_top_hud(self, screen):
        bar = ART.get("bar_top")
        if bar:
            screen.blit(bar, (0, 0))
            sh = ART.get("shadow")
            if sh:
                screen.blit(sh, (0, HUD_TOP))
        else:
            pygame.draw.rect(screen, COL_PANEL, (0, 0, W, HUD_TOP))
            pygame.draw.line(screen, (30, 40, 60), (0, HUD_TOP - 2), (W, HUD_TOP - 2), 2)
        if self.mode == "campaign":
            draw_text(screen, "FOLD QUEST", 17, 24, 10, COL_TEAL, "tl", shadow=False)
            draw_text(screen, "LEVEL %d/%d" % (self.level_i + 1, len(LEVELS)),
                      17, 160, 10, COL_DIM, "tl", shadow=False)
        elif self.mode == "endless":
            draw_text(screen, "ENDLESS MODE", 17, 24, 10, COL_TEAL, "tl", shadow=False)
        elif self.mode == "daily":
            draw_text(screen, "DAILY FOLD", 17, 24, 10, COL_TEAL, "tl", shadow=False)
        else:
            draw_text(screen, "DESIGNER MODE", 17, 24, 10, COL_TEAL, "tl", shadow=False)
        if self.duel:
            col = COL_TEAL if self.duel_turn == 0 else COL_GOLD
            r = pygame.Rect(300, 8, 132, 26)
            rrect(screen, (22, 30, 48), r, 6)
            rrect(screen, col, r, 6, 1)
            draw_text(screen, "P%d'S TURN" % (self.duel_turn + 1), 15,
                      r.centerx, r.y + 4, col, "tc", shadow=False)
        draw_text(screen, self.level_name, 30, 24, 32, COL_TEXT)
        draw_text(screen, self.blurb, 15, 24, 72, COL_DIM, "tl", shadow=False)
        # sequence bar
        for i, (bx, by) in enumerate(self.seq_bead_pos()):
            kind = self.seq[i]
            draw_bead(screen, bx, by, 7, kind,
                      ring=(kind == "H" and i in self.contact_idx))
            if i == self.hover:
                pygame.draw.circle(screen, (255, 255, 255), (int(bx), int(by)), 11, 2)
            if i % 5 == 0:
                img = F(12).render(str(i), True, COL_DIM)
                screen.blit(img, img.get_rect(midtop=(bx, by + 11)))
        # energy block
        x0 = W - 340
        g = ART.get("energy_glow")
        if g:
            screen.blit(g, (x0 - 14, 12))
        draw_text(screen, "FREE ENERGY", 13, x0, 8, COL_DIM, "tl", shadow=False)
        col = tuple(int(cc + (255 - cc) * 0.7 * self.energy_pop) for cc in COL_GOLD)
        img = F(42).render("-%d" % self.contacts, True, col)
        if self.energy_pop > 0.02:
            try:
                img = pygame.transform.rotozoom(img, 0, 1.0 + 0.14 * self.energy_pop)
            except Exception:
                pass
        r = img.get_rect()
        r.midleft = (x0, 46)
        screen.blit(img, r)
        draw_text(screen, "H-H CONTACTS", 13, x0 + 170, 12, COL_DIM, "tl", shadow=False)
        if self.target is None:
            draw_text(screen, "AI folding...", 27, x0 + 170, 30, COL_DIM, "tl", shadow=False)
        else:
            draw_text(screen, "%d / %d" % (self.contacts, self.target), 27,
                      x0 + 170, 30, COL_TEXT)
        if self.target is not None:
            rrect(screen, (30, 40, 60), (x0, 74, 320, 10), 5)
            w = int(320 * clamp(self.contacts / float(self.target), 0.0, 1.0))
            if w > 2:
                rrect(screen, COL_GOLD, (x0, 74, w, 10), 5)
            if w > 8:
                tr = 4 + int(1.5 * (0.5 + 0.5 * math.sin(self.phase * 4)))
                pygame.draw.circle(screen, (255, 240, 180), (x0 + w - 3, 79), tr)
        if self.best_contacts is not None:
            line = "best known -%d" % self.best_contacts
            if (self.contacts >= self.best_contacts and self.target
                    and self.contacts >= self.target):
                line += "  · matched - gold fold!"
            draw_text(screen, line, 14, x0, 88, COL_DIM, "tl", shadow=False)
        else:
            draw_text(screen, "AI is thinking...", 14, x0, 88, COL_DIM, "tl", shadow=False)

    def draw_button(self, screen, r, label, enabled=True, hot=False, key=None):
        dy = -1 if hot else 0
        body = r.move(0, dy)
        rrect(screen, (7, 9, 16), r.move(0, 3), 10)
        bg = (40, 54, 84) if hot else ((25, 34, 56) if enabled else (16, 20, 30))
        rrect(screen, bg, body, 10)
        pygame.draw.line(screen, (66, 84, 122) if enabled else (30, 38, 54),
                         (body.x + 9, body.y + 3), (body.right - 9, body.y + 3), 1)
        pygame.draw.line(screen, (10, 13, 22),
                         (body.x + 9, body.bottom - 4), (body.right - 9, body.bottom - 4), 1)
        rrect(screen, COL_TEAL if hot else ((74, 94, 134) if enabled else (38, 47, 66)),
              body, 10, 2)
        draw_text(screen, label, 17, body.centerx, body.y + 7,
                  COL_TEXT if enabled else (92, 102, 122), "tc", shadow=False)
        if key:
            draw_text(screen, key, 12, body.right - 8, body.bottom - 16,
                      COL_DIM, "br", shadow=False)

    def draw_bottom_hud(self, screen):
        y0 = H - HUD_BOT
        bar = ART.get("bar_bot")
        if bar:
            screen.blit(bar, (0, y0))
            sh = ART.get("shadow_up")
            if sh:
                screen.blit(sh, (0, y0 - 14))
        else:
            pygame.draw.rect(screen, COL_PANEL, (0, y0, W, HUD_BOT))
            pygame.draw.line(screen, (30, 40, 60), (0, y0), (W, y0), 2)
        m = pygame.mouse.get_pos()
        for b in self.btns:
            r = b["rect"]
            bid = b["id"]
            label = b["label"]
            if bid == "mute":
                label = "SOUND OFF" if MUTED["on"] else "SOUND ON"
            enabled = True
            if bid == "prev":
                if self.mode != "campaign":
                    label = "< LEVELS"
                else:
                    enabled = self.level_i > 0
            elif bid == "next":
                if self.mode == "endless":
                    label = "NEW FOLD >"
                elif self.mode == "daily":
                    label = "DONE >"
                elif self.mode == "designer":
                    label = "DESIGN >"
                else:
                    enabled = (self.level_i < self.unlocked
                               and self.level_i < len(LEVELS) - 1)
            elif bid == "ai":
                enabled = self.best_conf is not None
                if not enabled:
                    label = "AI ..."
            self.draw_button(screen, r, label, enabled,
                             hot=(enabled and r.collidepoint(m)), key=b["key"])
        draw_text(screen, "MOVES %d" % self.moves, 17, W - 236, y0 + 18,
                  COL_TEXT, "tl", shadow=False)
        draw_text(screen, fmt_time(self.time), 17, W - 110, y0 + 18,
                  COL_TEXT, "tl", shadow=False)
        if self.par:
            txt = "PAR %d" % self.par
            if self.mode == "campaign":
                b = self.save.get("best", {}).get(str(self.level_i), {})
                if b.get("moves") is not None:
                    txt += " · BEST %d moves" % b["moves"]
            draw_text(screen, txt, 13, W - 236, y0 + 40, COL_DIM, "tl", shadow=False)

    def draw_floats(self, screen):
        for f in self.floats:
            img = F(20).render(f["txt"], True, f["col"])
            img.set_alpha(int(255 * clamp(f["t"] / 0.8, 0, 1)))
            screen.blit(img, img.get_rect(center=(int(f["x"]), int(f["y"]))))

    def draw_toasts(self, screen):
        if not self.toasts:
            return
        t = self.toasts[-1]
        a = clamp(t["t"] / 0.5, 0, 1)
        img = F(17).render(t["txt"], True, COL_TEXT)
        img.set_alpha(int(255 * a))
        pad = 12
        r = pygame.Rect(0, 0, img.get_width() + 2 * pad, img.get_height() + 10)
        r.midbottom = (W // 2, H - HUD_BOT - 6)
        rrect(screen, (13, 18, 30), r, 12)
        rrect(screen, (64, 80, 116), r, 12, 1)
        screen.blit(img, (r.x + pad, r.y + 5))

    def draw_particles(self, screen, off):
        ox, oy = off
        for p in self.particles:
            frac = clamp(p["life"] / p["maxlife"], 0, 1)
            if "spin" in p:
                L = p["size"] * 1.7 * frac + 1
                Wd = max(1.5, p["size"] * 0.75 * (0.25 + 0.75 * abs(math.cos(p["flutter"]))))
                a = p["angle"]
                ca, sa = math.cos(a), math.sin(a)
                pts = []
                for ux, uy in ((L, Wd), (L, -Wd), (-L, -Wd), (-L, Wd)):
                    pts.append((p["x"] + ux * ca - uy * sa + ox,
                                p["y"] + ux * sa + uy * ca + oy))
                pygame.draw.polygon(screen, p["col"], pts)
            else:
                vx, vy = p["vx"], p["vy"]
                sp = math.hypot(vx, vy) or 1.0
                tl = min(10.0, sp * 0.045)
                x, y = p["x"] + ox, p["y"] + oy
                pygame.draw.line(screen, p["col"], (x, y),
                                 (x - vx / sp * tl, y - vy / sp * tl),
                                 max(1, int(2 * frac)))
                pygame.draw.circle(screen, (255, 255, 255) if frac > 0.5 else p["col"],
                                   (int(x), int(y)), max(1, int(1.5 * frac)))

    def draw_paused(self, screen):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        fx.fill((5, 8, 15, 170))
        screen.blit(fx, (0, 0))
        draw_text(screen, "PAUSED", 54, W // 2, H // 2 - 60, COL_TEXT, "cc")
        a = 0.5 + 0.5 * math.sin(self.phase * 3)
        img = F(18).render("click or press any key to resume", True, COL_DIM)
        img.set_alpha(int(140 + 115 * a))
        screen.blit(img, img.get_rect(midtop=(W // 2, H // 2 + 10)))

    def draw_title(self, screen):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        seq, g = self.demo[self.demo_idx]
        pop = 0.7 + 0.3 * (1 - (1 - self.demo_pop) ** 2)
        pairs = contact_pairs(g, seq)
        cx, cy = W // 2, 412
        pts = [(cx + (p[0] - (GRID_W - 1) / 2.0) * 26,
                cy + (p[1] - (GRID_H - 1) / 2.0) * 26) for p in g]
        st = pygame.Rect(W // 2 - 310, 336, 620, 152)
        rrect(fx, (255, 255, 255, 12), st, 16)
        rrect(fx, (255, 255, 255, 30), st, 16, 2)
        glows = ART.get("glow", {})
        for i, (x, y) in enumerate(pts):
            lst = glows.get(seq[i])
            if lst:
                blit_center(fx, lst[1], x, y)
        for kk in range(len(g) - 1):
            p1, p2 = pts[kk], pts[kk + 1]
            base, hi = bond_style(seq[kk], seq[kk + 1])
            pygame.draw.line(fx, (0, 0, 0, 70), (p1[0], p1[1] + 3), (p2[0], p2[1] + 3), 7)
            pygame.draw.line(fx, base, p1, p2, 6)
            pygame.draw.line(fx, hi, (p1[0], p1[1] - 1), (p2[0], p2[1] - 1), 2)
        for (i, j) in pairs:
            p1, p2 = pts[i], pts[j]
            pygame.draw.line(fx, (255, 170, 40, 60), p1, p2, 11)
            a = 0.5 + 0.5 * math.sin(self.phase * 2.6 + i * 0.9)
            col = (int(185 + 70 * a), int(130 + 85 * a), int(40 + 60 * a))
            pygame.draw.line(fx, col, p1, p2, 3)
        screen.blit(fx, (0, 0))
        for i, (x, y) in enumerate(pts):
            draw_bead(screen, x, y, 10, seq[i],
                      ring=(seq[i] == "H" and any(i in pr for pr in pairs)),
                      scale=pop, letters=False)
        tg = ART.get("title_glow")
        if tg:
            screen.blit(tg, (W // 2 - tg.get_width() // 2, 88))
        draw_text(screen, "FOLD QUEST", 78, W // 2, 100, COL_TEXT, "tc")
        rrect(screen, COL_TEAL, (W // 2 - 130, 172, 260, 5), 2)
        draw_text(screen, "learn to fold proteins", 26, W // 2, 190,
                  COL_DIM, "tc", shadow=False)
        draw_text(screen, "hydrophobic-polar lattice model · folding school · daily · endless · designer · duels",
                  16, W // 2, 224, (100, 112, 134), "tc", shadow=False)
        # level chips + mode chips
        self.title_chips = []
        m = pygame.mouse.get_pos()
        nlev = len(LEVELS)
        cw, ch, gap = 56, 40, 10
        x = W // 2 - (nlev * cw + (nlev - 1) * gap + 14 + 104 + 10 + 92 + 10 + 104 + 10 + 84) // 2
        y = 548
        for i in range(nlev):
            r = pygame.Rect(x, y, cw, ch)
            unlocked = i <= self.unlocked
            hot = unlocked and r.collidepoint(m)
            body = r.move(0, -1 if hot else 0)
            rrect(screen, (7, 9, 16), r.move(0, 3), 8)
            rrect(screen, (36, 48, 74) if hot else (22, 30, 48), body, 8)
            rrect(screen, COL_TEAL if hot else ((60, 80, 110) if unlocked else (34, 42, 58)),
                  body, 8, 2)
            draw_text(screen, str(i + 1), 20, body.centerx, body.y + 4,
                      COL_TEXT if unlocked else (80, 90, 108), "tc", shadow=False)
            for s in range(3):
                sx = body.centerx + (s - 1) * 13
                col = COL_GOLD if s < int(self.save.get("stars", {}).get(str(i), 0)) \
                    else (52, 62, 84)
                draw_star(screen, sx, body.bottom - 8, 5, col)
            self.title_chips.append((r, i))
            x += cw + gap
        x += 4
        solved_today = today_str() in self.save.get("daily", {})
        for tag, label, cwid, accent in (
                ("random", "RANDOM", 104, COL_GOLD),
                ("daily", "DAILY", 92, COL_GOLD if solved_today else (110, 90, 40)),
                ("design", "DESIGN", 104, COL_TEAL),
                ("notes", "NOTES", 84, (110, 200, 190))):
            r = pygame.Rect(x, y, cwid, ch)
            hot = r.collidepoint(m)
            body = r.move(0, -1 if hot else 0)
            rrect(screen, (7, 9, 16), r.move(0, 3), 8)
            rrect(screen, (36, 48, 74) if hot else (22, 30, 48), body, 8)
            rrect(screen, accent if hot else (60, 80, 110), body, 8, 2)
            draw_text(screen, label, 16, body.centerx, body.y + 11,
                      accent if hot else COL_TEXT, "tc", shadow=False)
            if tag == "daily" and solved_today:
                draw_star(screen, body.right - 10, body.top + 9, 7, COL_GOLD)
            self.title_chips.append((r, tag))
            x += cwid + 10
        a = 0.55 + 0.45 * math.sin(self.phase * 3.0)
        img = F(24).render("CLICK A LEVEL OR PRESS ANY KEY", True, COL_GOLD)
        img.set_alpha(int(170 + 85 * a))
        screen.blit(img, img.get_rect(center=(W // 2, 612)))
        done = self.save.get("completed", 0)
        ek = self.save.get("endless", 0)
        nach = len(self.save.get("ach", {}))
        r = draw_text(screen, "%d/%d levels · %d endless folds · awards %d/%d  (TAB)"
                      % (done, nlev, ek, nach, len(ACH)),
                      16, W // 2, 642, COL_DIM, "tc", shadow=False)
        self.title_awards_rect = r.inflate(10, 8)
        if self.title_awards_rect.collidepoint(m):
            pygame.draw.line(screen, COL_TEAL,
                             (self.title_awards_rect.x + 14, self.title_awards_rect.bottom - 2),
                             (self.title_awards_rect.right - 14,
                              self.title_awards_rect.bottom - 2), 2)
        dst = daily_streak(self.save)
        draw_text(screen, "daily fold: %s · streak %d"
                  % ("solved" if solved_today else "not solved yet", dst),
                  14, W // 2, 664, COL_GOLD if solved_today else (110, 124, 150),
                  "tc", shadow=False)
        car = self.save.get("career", {})
        if car:
            draw_text(screen, "career: %d contacts · %d folds solved · %s folding time"
                      % (car.get("contacts", 0), car.get("folds", 0),
                         fmt_time(car.get("time", 0))),
                      14, W // 2, 684, (110, 124, 150), "tc", shadow=False)
        draw_text(screen, "Z undo · Y redo · T shake · H hint · A AI · V/O replays · E endless · D design · S notes · X analyze · G duel · M sound",
                  14, W // 2, H - 34, (100, 112, 134), "tc", shadow=False)

    def draw_achievements(self, screen):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        fx.fill((5, 8, 15, 175))
        screen.blit(fx, (0, 0))
        panel = pygame.Rect(W // 2 - 380, 110, 760, 600)
        rrect(screen, (6, 8, 14), panel.move(0, 6), 16)
        rrect(screen, (18, 24, 40), panel, 14)
        toplight = panel.inflate(-16, -16)
        toplight.height = 56
        rrect(screen, (26, 35, 56), toplight, 10)
        rrect(screen, COL_GOLD, panel, 14, 2)
        rrect(screen, (70, 90, 130), panel.inflate(-8, -8), 10, 1)
        got = self.save.get("ach", {})
        draw_text(screen, "AWARDS & STATS", 32, W // 2, 124, COL_GOLD, "tc", shadow=False)
        draw_text(screen, "%d / %d unlocked" % (len(got), len(ACH)), 15,
                  W // 2, 156, COL_DIM, "tc", shadow=False)
        for idx, (aid, name, desc) in enumerate(ACH):
            col_i = idx // 7
            row = idx % 7
            x = W // 2 - 350 + col_i * 362
            y = 176 + row * 48
            have = aid in got
            draw_star(screen, x + 12, y + 11, 9, COL_GOLD if have else (52, 62, 84))
            draw_text(screen, name, 16, x + 30, y,
                      COL_GOLD if have else (150, 160, 178), "tl", shadow=False)
            draw_text(screen, desc, 13, x + 30, y + 21,
                      COL_DIM if have else (92, 102, 120), "tl", shadow=False)
        pygame.draw.line(screen, (40, 52, 76), (W // 2 - 340, 502),
                         (W // 2 + 340, 502), 2)
        draw_text(screen, "CAREER", 15, W // 2 - 340, 510, COL_TEAL, "tl", shadow=False)
        car = self.save.get("career", {})
        stats_l = [("contacts made", car.get("contacts", 0)),
                   ("folds solved", car.get("folds", 0)),
                   ("moves made", car.get("moves", 0)),
                   ("folding time", fmt_time(car.get("time", 0)))]
        stats_r = [("endless folds", self.save.get("endless", 0)),
                   ("designs folded", self.save.get("designer", 0)),
                   ("daily streak", daily_streak(self.save)),
                   ("dailys solved", len(self.save.get("daily", {})))]
        y = 532
        for (lab, val) in stats_l:
            draw_text(screen, lab, 14, W // 2 - 340, y, COL_DIM, "tl", shadow=False)
            draw_text(screen, str(val), 14, W // 2 - 160, y, COL_TEXT, "tl", shadow=False)
            y += 24
        y = 532
        for (lab, val) in stats_r:
            draw_text(screen, lab, 14, W // 2 + 30, y, COL_DIM, "tl", shadow=False)
            draw_text(screen, str(val), 14, W // 2 + 190, y, COL_TEXT, "tl", shadow=False)
            y += 24
        draw_text(screen, "TAB or click to close", 14, W // 2, 668, COL_DIM, "tc", shadow=False)

    def draw_designer(self, screen):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        fx.fill((5, 8, 15, 185))
        screen.blit(fx, (0, 0))
        panel = pygame.Rect(W // 2 - 360, 150, 720, 480)
        rrect(screen, (6, 8, 14), panel.move(0, 6), 16)
        rrect(screen, (18, 24, 40), panel, 14)
        toplight = panel.inflate(-16, -16)
        toplight.height = 70
        rrect(screen, (26, 35, 56), toplight, 10)
        rrect(screen, COL_TEAL, panel, 14, 2)
        draw_text(screen, "DESIGN A PROTEIN", 34, W // 2, 166, COL_TEAL, "tc", shadow=False)
        draw_text(screen, "type H (hydrophobic) and P (polar) - 8 to 32 residues",
                  16, W // 2, 208, COL_DIM, "tc", shadow=False)
        seq = self.designer_seq
        n = len(seq)
        if n:
            sp = 26 if n <= 25 else max(16, int(660 / max(1, n - 1)))
            r = 12 if sp >= 24 else 9
            x0 = W // 2 - sp * (n - 1) // 2
            for i, ch in enumerate(seq):
                draw_bead(screen, x0 + i * sp, 296, r, ch)
            if (self.phase * 2.0) % 2.0 < 1.0:
                cx = x0 + (n - 1) * sp + sp // 2 + 8
                pygame.draw.line(screen, COL_TEAL, (cx, 284), (cx, 308), 3)
        else:
            draw_text(screen, "start typing...", 20, W // 2, 288, COL_DIM, "cc", shadow=False)
            if (self.phase * 2.0) % 2.0 < 1.0:
                pygame.draw.line(screen, COL_TEAL, (W // 2, 284), (W // 2, 308), 3)
        draw_text(screen, "%d / 32 residues" % n, 16, W // 2, 322,
                  COL_TEXT if n else COL_DIM, "tc", shadow=False)
        draw_text(screen, "H: %d   ·   P: %d" % (seq.count("H"), seq.count("P")),
                  16, W // 2, 344, COL_DIM, "tc", shadow=False)
        if self.designer_msg:
            draw_text(screen, self.designer_msg, 16, W // 2, 384, COL_RED, "tc")
        else:
            draw_text(screen, "ENTER to fold it  ·  BACKSPACE to erase  ·  ESC to cancel",
                      14, W // 2, 384, COL_DIM, "tc", shadow=False)
        valid = n >= 8 and seq.count("H") >= 3
        m = pygame.mouse.get_pos()
        self.draw_button(screen, self.design_fold, "FOLD IT", valid,
                         valid and self.design_fold.collidepoint(m))
        self.draw_button(screen, self.design_cancel, "CANCEL", True,
                         self.design_cancel.collidepoint(m))

    def draw_win(self, screen):
        fx = self.fx
        fx.fill((0, 0, 0, 0))
        fx.fill((5, 8, 15, 150))
        screen.blit(fx, (0, 0))
        panel = pygame.Rect(W // 2 - 310, 140, 620, 500)
        rrect(screen, (6, 8, 14), panel.move(0, 6), 16)
        rrect(screen, (18, 24, 40), panel, 14)
        toplight = panel.inflate(-16, -16)
        toplight.height = 86
        rrect(screen, (26, 35, 56), toplight, 10)
        rrect(screen, COL_GOLD if self.gold else COL_TEAL, panel, 14, 3)
        rrect(screen, (70, 90, 130), panel.inflate(-8, -8), 10, 1)
        fx.fill((0, 0, 0, 0))
        for kk in range(14):
            ang = self.phase * 0.3 + kk * math.pi / 7
            L2 = 150 + 10 * math.sin(self.phase * 2 + kk)
            x1 = W // 2 + math.cos(ang) * 60
            y1 = 205 + math.sin(ang) * 34
            x2 = W // 2 + math.cos(ang) * L2
            y2 = 205 + math.sin(ang) * 34 * L2 / 150.0
            pygame.draw.line(fx, (255, 204, 64, 28), (x1, y1), (x2, y2), 3)
        screen.blit(fx, (0, 0))
        hg = ART.get("head_glow")
        if hg:
            screen.blit(hg, (W // 2 - hg.get_width() // 2, 158))
        if self.duel:
            head = "PLAYER %d WINS!" % self.duel_winner
        else:
            super_fold = self.target is not None and self.contacts > self.target
            head = "FOLD SOLVED!" if self.mode != "campaign" \
                else ("SUPER-FOLD!" if super_fold else "NATIVE FOLD!")
        draw_text(screen, head, 42, W // 2, 152, COL_GOLD, "tc")
        gstars = ART.get("glow", {}).get("gold")
        for s in range(3):
            sc = clamp((self.stars_t - 0.15 * s) / 0.25, 0.0, 1.0)
            if sc <= 0:
                continue
            r = 4 + 12 * sc
            x = W // 2 + (s - 1) * 52
            if s < self.stars and gstars:
                blit_center(screen, gstars[1], x, 200)
            draw_star(screen, x, 200, r, COL_GOLD if s < self.stars else (62, 72, 94))
            if s < self.stars:
                draw_star(screen, x, 200, r * 0.55, (255, 240, 180))
        if self.gold:
            draw_star(screen, W // 2 - 152, 226, 10, COL_GOLD)
            draw_text(screen, "GOLD FOLD - matched the best known energy", 17,
                      W // 2 - 132, 218, COL_TEAL, "tl", shadow=False)
        if self.perfect:
            draw_text(screen, "PERFECT - the exact native fold!", 16,
                      W // 2, 240, COL_TEAL, "tc", shadow=False)
        if self.mode == "endless":
            sub = "Endless fold #%d" % self.endless_n
        elif self.mode == "daily":
            sub = "Daily fold - %s" % today_str()
        elif self.mode == "designer":
            sub = "Design #%d - your own protein" % self.designer_n
        else:
            sub = "Level %d - %s" % (self.level_i + 1, self.level_name)
        draw_text(screen, sub, 20, W // 2, 260, COL_DIM, "tc", shadow=False)
        pygame.draw.line(screen, (40, 52, 76), (W // 2 - 240, 288), (W // 2 + 240, 288), 2)
        rows = [
            ("H-H contacts", "%s / %s" % (self.contacts, self.target)),
            ("free energy", "-%d" % self.contacts),
            ("time", fmt_time(self.time)),
            ("moves", "%d / par %d  (hints: %d)" % (self.moves, self.par or 0, self.hints)),
        ]
        if self.duel:
            rows.append(("player 1 moves", str(self.duel_moves[0])))
            rows.append(("player 2 moves", str(self.duel_moves[1])))
        runs = self.strand_runs()
        if runs:
            ls = max(j - i + 1 for (i, j) in runs)
            if ls >= 4:
                rows.append(("longest strand", "%d residues" % ls))
        if self.mode == "campaign":
            b = self.save.get("best", {}).get(str(self.level_i), {})
            if b:
                rows.append(("your best", "%d moves · %s"
                             % (b.get("moves", 0), fmt_time(b.get("time", 0)))))
        if self.ai_assisted:
            rows.append(("note", "AI-assisted fold"))
        y = 296
        for lab, val in rows:
            draw_text(screen, lab, 17, W // 2 - 200, y, COL_DIM, "tl", shadow=False)
            draw_text(screen, val, 17, W // 2 + 40, y, COL_TEXT, "tl", shadow=False)
            y += 27
        yy = y + 6
        for ln in wrap_text("Fun fact: " + self.fact, 16, 500)[:2]:
            draw_text(screen, ln, 16, W // 2 - 250, yy, (110, 190, 175), "tl", shadow=False)
            yy += 20
        if self.mode == "endless":
            next_label = "NEW FOLD >"
        elif self.mode == "daily":
            next_label = "TITLE SCREEN"
        elif self.mode == "designer":
            next_label = "DESIGN ANOTHER"
        elif self.level_i >= len(LEVELS) - 1:
            next_label = "TITLE SCREEN"
        else:
            next_label = "NEXT LEVEL >"
        m = pygame.mouse.get_pos()
        has_trace = bool(self.ai_trace and len(self.ai_trace) >= 2)
        has_mine = bool(self.mytrace and len(self.mytrace) >= 2)
        self.draw_button(screen, self.win_keep, "KEEP FOLDING",
                         True, self.win_keep.collidepoint(m))
        self.draw_button(screen, self.win_mine, "MY REPLAY",
                         has_mine, has_mine and self.win_mine.collidepoint(m))
        self.draw_button(screen, self.win_watch, "AI REPLAY",
                         has_trace, has_trace and self.win_watch.collidepoint(m))
        self.draw_button(screen, self.win_next, next_label,
                         True, self.win_next.collidepoint(m))
        draw_text(screen, "X = fold analysis · O = your replay", 13, W // 2, 618,
                  COL_DIM, "tc", shadow=False)

    def set_cursor(self):
        try:
            hand = False
            if (self.state == "title" or self.designer_open or self.ach_open
                    or self.notes_open or self.analysis_open):
                hand = True
            elif self.win_overlay:
                m = pygame.mouse.get_pos()
                hand = (self.win_next.collidepoint(m) or self.win_keep.collidepoint(m)
                        or self.win_watch.collidepoint(m) or self.win_mine.collidepoint(m))
            elif not self.paused:
                m = pygame.mouse.get_pos()
                hand = (self.hover is not None
                        or any(b["rect"].collidepoint(m) for b in self.btns))
            cur = pygame.SYSTEM_C_HAND if hand else pygame.SYSTEM_C_ARROW
            if cur != self.cursor:
                pygame.mouse.set_cursor(cur)
                self.cursor = cur
        except Exception:
            pass

# ---------------------------------------------------------------------- main
def main():
    try:
        pygame.mixer.pre_init(44100, -16, 1, 512)
    except Exception:
        pass
    pygame.init()
    init_audio()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("FOLD QUEST v9 - learn to fold proteins")
    try:
        icon = pygame.Surface((32, 32), pygame.SRCALPHA)
        pygame.draw.circle(icon, COL_H_FILL, (16, 14), 12)
        pygame.draw.circle(icon, COL_H_RIM, (16, 14), 12, 3)
        pygame.draw.circle(icon, COL_P_FILL, (6, 25), 6)
        pygame.draw.circle(icon, COL_P_FILL, (26, 25), 6)
        pygame.display.set_icon(icon)
    except Exception:
        pass
    build_art()
    game = Game()
    game.screen = screen
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000.0, 0.05)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if game.on_key(ev) == "quit":
                    running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN:
                game.on_click(ev.pos, ev.button)
            elif ev.type == pygame.MOUSEBUTTONUP:
                game.on_release(ev.button)
            elif ev.type == pygame.MOUSEWHEEL:
                game.on_wheel(ev.y)
        game.update(dt)
        game.draw(screen)
        game.set_cursor()
        pygame.display.flip()
    persist(game.save)
    pygame.quit()


if __name__ == "__main__":
    main()