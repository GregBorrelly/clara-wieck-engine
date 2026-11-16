# Benchmark

Run on 15 November 2026 with homr 0.7.1 on a 2-core CPU machine, using `python -m bench.run`.
Pieces come from PlayMySheet's library, so their notes are known. Each was engraved by
Verovio as A4 pages at 300 dpi ("clean"), then made to look like a phone photo ("photo":
paper tint, perspective, a 2-3 degree tilt, uneven light, blur, noise, JPEG at quality 70).

"Notes" counts a note right only if its pitch, position in the bar, length and hand all
match. "Pitches" ignores length and hand. Bars are aligned first, so one missed bar
doesn't count against every bar after it.

| Piece | Version | Notes | Pitches | Bars exactly right | Key | Time | Seconds per page |
|---|---|---|---|---|---|---|---|
| Mozart, Menuett K. 2 | clean | 96% | 96% | 21 / 24 | right | right | 21 |
| | photo | 96% | 96% | 21 / 24 | right | right | 19 |
| Bach, Polonaise in G minor | clean | 93% | 94% | 12 / 16 | right | right | 20 |
| | photo | 93% | 94% | 12 / 16 | right | right | 19 |
| Bach, French Suite no. 6 (excerpt) | clean | 88% | 89% | 9 / 24 | right | right | 28 |
| | photo | 91% | 91% | 9 / 24 | right | right | 27 |
| Kinkel, Du nahst | clean | 86% | 87% | 5 / 24 | right | right | 37 |
| | photo | 85% | 86% | 5 / 24 | right | right | 43 |
| Satie, Le porteur de grosses pierres | clean | 40% | 47% | 8 / 32 | right | right | 25 |

The run stopped before Satie's photo and a sixth piece: the test machine ran out of memory
while also running the app and a browser. The runner now saves results after each piece.

What this says:
- On typical engraved piano music, about 9 notes in 10 come out exactly right, and photos
  are about as good as clean pages. Key and time signatures were right every time.
- Whole bars are harder: one wrong note spoils a bar, so busier pieces (Kinkel's song
  accompaniment, Bach's two-part writing) have few perfect bars despite high note scores.
  That's what the app's bar checks and review panel are for.
- Satie writes much of this piece without barlines, which this engine (and the scoring)
  handle badly. Unusual notation is the weak spot.

Also tried by hand on a real 1970 scanned piano arrangement (6-page PDF, not included for
copyright reasons): all staves and systems found on the three music pages, key and time
signatures right including a change of key, 40 bars read. After the app's checks, 5 of
the 40 bars were flagged as not adding up; each was a genuine misread or a free-time
cadenza.
