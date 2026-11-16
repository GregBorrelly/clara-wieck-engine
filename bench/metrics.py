"""Score a reading against the known notes.

Works on the app's score model (bars of events per hand). Bars are aligned first, so one
missed or extra bar costs that bar only instead of shifting every bar after it.
"""
from __future__ import annotations

from collections import Counter

BASE = {"w": 96, "h": 48, "q": 24, "e": 12, "s": 6, "t": 3}
PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def dur(d: str) -> float:
    v = BASE[d[0]]
    add, rest = v, d[1:]
    while rest.startswith("."):
        add /= 2
        v += add
        rest = rest[1:]
    return v * 2 / 3 if rest == "3" else v


def midi(p: str) -> int:
    step, rest = p[0], p[1:]
    alter = rest.count("#") - rest.count("b")
    return 12 * (int(rest.lstrip("#b")) + 1) + PC[step] + alter


def bar_notes(m: dict) -> Counter:
    """Notes in a bar as (hand, onset, midi, length)."""
    c: Counter = Counter()
    for lane in ("rh", "lh", "rh2", "lh2"):
        t = 0.0
        for ev in m.get(lane) or []:
            d = dur(ev["dur"])
            for p in ev.get("pitches") or []:
                c[(lane[:2], round(t), midi(p), round(d))] += 1
            t += d
    return c


def loose(c: Counter) -> Counter:
    """Pitch and position only: ignores which hand and how long."""
    out: Counter = Counter()
    for (hand, onset, m, d), n in c.items():
        out[(onset, m)] += n
    return out


def align(a: list[Counter], b: list[Counter]) -> list[tuple[int | None, int | None]]:
    """Needleman-Wunsch over bars; similarity = shared notes / all notes."""
    n, m = len(a), len(b)
    INF = float("inf")
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0

    def sim(x: Counter, y: Counter) -> float:
        tot = sum(x.values()) + sum(y.values())
        if tot == 0:
            return 1.0
        return 2 * sum((x & y).values()) / tot

    for i in range(n + 1):
        for j in range(m + 1):
            if i and j and cost[i - 1][j - 1] + (1 - sim(loose(a[i - 1]), loose(b[j - 1]))) < cost[i][j]:
                cost[i][j] = cost[i - 1][j - 1] + (1 - sim(loose(a[i - 1]), loose(b[j - 1])))
                back[i][j] = (i - 1, j - 1)
            if i and cost[i - 1][j] + 1 < cost[i][j]:
                cost[i][j] = cost[i - 1][j] + 1
                back[i][j] = (i - 1, j)
            if j and cost[i][j - 1] + 1 < cost[i][j]:
                cost[i][j] = cost[i][j - 1] + 1
                back[i][j] = (i, j - 1)
    path, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]
        path.append((i - 1 if pi == i - 1 else None, j - 1 if pj == j - 1 else None))
        i, j = pi, pj
    return path[::-1]


def compare(truth: dict, got: dict) -> dict:
    ta = [bar_notes(m) for m in truth["measures"]]
    ga = [bar_notes(m) for m in got["measures"]]
    pairs = align(ta, ga)
    exact = pitch = perfect = 0
    for i, j in pairs:
        if i is None or j is None:
            continue
        exact += sum((ta[i] & ga[j]).values())
        pitch += sum((loose(ta[i]) & loose(ga[j])).values())
        perfect += ta[i] == ga[j]
    nt, ng = sum(sum(c.values()) for c in ta), sum(sum(c.values()) for c in ga)
    f1 = lambda k: 2 * k / (nt + ng) if nt + ng else 1.0  # noqa: E731
    return {
        "notes": nt, "notes_read": ng,
        "notes_f1": round(f1(exact), 4),        # right pitch, position, length and hand
        "pitch_f1": round(f1(pitch), 4),        # right pitch and position
        "bars": len(ta), "bars_read": len(ga), "bars_perfect": perfect,
        "key_ok": truth.get("key") == got.get("key"), "time_ok": truth.get("time") == got.get("time"),
    }
