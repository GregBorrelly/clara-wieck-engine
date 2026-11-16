# Clara Wieck engine

The sheet-music reading engine for PlayMySheet, named after Clara Wieck (1819-1896), the pianist famous for reading anything put in front of her.

Reads sheet music images and PDFs and returns MusicXML. It's the reading engine behind
[PlayMySheet](../etude): the app sends pages here, checks every bar it gets back, and asks
Claude only about bars that don't add up.

It wraps [homr](https://github.com/liebharc/homr), an open-source reader that finds the
staves on a page, straightens them, and reads each one with a trained transformer. Models
run on the CPU with ONNX Runtime; no GPU and no outside service are needed.

## API

`POST /read`, either:
- multipart with a `file` field (PNG, JPEG, WebP, or PDF), or
- JSON `{"data": "<base64 or data URL>"}`

Optional `engine` (default `homr`). Optional `Authorization: Bearer <READER_TOKEN>` when the
server has `READER_TOKEN` set.

Response:

```json
{"engine": "homr", "pages": [
  {"page": 1, "musicxml": "<?xml ...", "seconds": 24.1,
   "systems": [{"left": 0.07, "top": 0.12, "right": 0.93, "bottom": 0.23}]}
]}
```

`systems` are where each line of music sits, as fractions of the page, top to bottom. The
MusicXML marks the same line breaks (`<print new-system="yes"/>`), so bars can be matched
to the image they came from. A page that fails returns `{"page": n, "error": "..."}` and
the other pages still come back.

`GET /health` lists the engines and whether a request is running.

PDFs are rendered at 300 dpi; photos larger than 4,200 px are scaled down. Pages are
read one at a time.

## Run it

    python -m venv .venv && .venv/bin/pip install -r requirements.txt
    .venv/bin/homr --init --no-title          # downloads the models once (about 150 MB)
    .venv/bin/uvicorn reader.app:app --port 8100

Or with Docker: `docker build -t playmysheet-reader . && docker run -p 8100:80 playmysheet-reader`.

Then start the app with `READER_URL=http://localhost:8100` (and the same `READER_TOKEN`
on both, if you set one).

Hosting: give it 2 CPUs and 4 GB of memory, which handles about two pages a minute. Measured
peak memory is about 1.5 GB on a 2200 x 3100 page and over 2 GB on larger ones, so 2 GB is only
enough for modest pages. Fly.io, Render and Railway run the Dockerfile as is. It also runs on
Vercel as a container (`vercel.json` selects the container build); the image is about 1 GB, which
needs Vercel's large-function support.

## Speed and accuracy

On a 2-core machine, about 20 to 30 seconds per page.

`bench/` measures accuracy on pieces whose notes are known: it engraves them from the
app's library with [Verovio](https://www.verovio.org) as A4 pages at 300 dpi, makes
phone-photo versions (tilt, perspective, uneven light, blur, JPEG), reads both, and scores
the result bar by bar against the original.

    .venv/bin/pip install -r requirements-bench.txt
    .venv/bin/python -m bench.run --app ../etude --pieces 6

See [BENCHMARK.md](BENCHMARK.md) for the latest numbers.

## Tests

    .venv/bin/python -m pytest tests            # fast, with a stand-in engine
    RUN_HOMR=1 .venv/bin/python -m pytest tests # also runs homr on a real page

## License

AGPL-3.0, because homr is AGPL-3.0. This service is kept separate from the app, which
talks to it over HTTP. If you run a modified version of this service for other people,
the AGPL asks you to offer them its source. (This is a summary, not legal advice.)

The model weights are homr's, downloaded from its GitHub releases. Verovio (LGPL-3.0) and
CairoSVG (LGPL-3.0) are used only by the benchmark.
