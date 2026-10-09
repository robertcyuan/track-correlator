# Track correlator

Several ground receivers listen to aircraft and forward what they hear to a central service. The
same aircraft is usually heard by more than one receiver. The correlator decides, report by report,
which aircraft each report belongs to, and gives each aircraft one stable track.

## Input

One JSON report per line on stdin, in the order the reports reach the correlator:

```json
{"arr":36004.518,"rx":"R3","t":36003.263,"id":"AFAA7C","lat":47.065481,"lon":7.428459,"alt":784.9}
```

| Field | Meaning |
|---|---|
| `arr` | Arrival time at the correlator, in seconds, on the correlator's clock. Never decreases from one line to the next. |
| `rx` | Name of the receiver that heard the aircraft. |
| `t` | Time the receiver heard the aircraft, in seconds, on the receiver's own clock. |
| `id` | Identifier broadcast by the aircraft. Optional. |
| `lat`, `lon` | Position in degrees (WGS84). |
| `alt` | Altitude in metres. Optional. |

Things that happen in the data. Not all of them appear in the sample:

- Receiver clocks are not synchronised with each other or with the correlator.
- Network delays vary, and a receiver sometimes delivers a burst of late reports after a connection stall.
- Some aircraft broadcast no identifier. Their position is measured by the receiver, which is less accurate.
- Some aircraft change their identifier from time to time.
- Two aircraft can broadcast the same identifier.
- Aircraft sometimes fly close to each other.
- Aircraft can go unheard for a while, for example behind terrain.
- A few reports carry a corrupted position.

## Output

For each report, write one JSON line on stdout:

```json
{"report":1,"track":"T7","at":36004.518}
```

| Field | Meaning |
|---|---|
| `report` | 0-based line number of the report in the input. |
| `track` | Your name for the track the report belongs to, or `null` to reject the report. |
| `at` | The time at which you made this decision, on the input's `arr` clock (see below). |

### Time and the `at` field

The input is a recording, so your program reads it much faster than real time, and wall-clock time
says nothing about how long a report waited for its answer. Time is therefore the `arr` values
themselves: reading a report with a given `arr` means the clock has reached that `arr`.
`at` is the time at which you answer. It shows how long you held each report back.

Rules:

- Answer every report exactly once. Answers do not have to follow input order.
- Answer each report within 2 seconds of its own arrival: `arr <= at <= arr + 2`.
- `at` never decreases from one output line to the next.
- An answer written before reading a report has `at` no later than that report's `arr`: you cannot
  answer at a time the clock has not reached yet.
- Memory use must stay bounded on an input of any length.

## Build and run

The program must build and pass its tests with the provided Dockerfile, unmodified:

```sh
docker build -t correlator .
docker run --rm -i correlator < data/sample/reports.jsonl > output.jsonl
```
Add dependencies through CMake (`FetchContent`, pinned to a tag or commit) or a vcpkg manifest
(`vcpkg.json` with a `builtin-baseline`). Explain each dependency in one line in your README.

## Scoring

`data/sample` holds a sample input and its ground truth (`truth.jsonl`: the aircraft behind each
report, `null` for a corrupted one). Score your output with:

```sh
python3 tools/score.py data/sample output.jsonl
# or build and score in one go:
python3 tools/score.py data/sample --run "docker run --rm -i correlator"
```

The scorer checks the output rules above and reports:

- **association**: share of reports placed in the track that mostly holds their aircraft
- **id switches**: how often an aircraft's track changes over time (swaps, or a new track for the same aircraft)
- **invalid accepted**: corrupted reports placed in a real aircraft's track
