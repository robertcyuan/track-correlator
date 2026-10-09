#!/usr/bin/env python3
"""Score a correlator's output against ground truth.

Usage:
  score.py DATA_DIR OUTPUT.jsonl            score an existing output file
  score.py DATA_DIR --run "CMD ..."         pipe DATA_DIR/reports.jsonl through CMD, then score

DATA_DIR holds reports.jsonl and truth.jsonl (and optionally meta.json for a per-aircraft
breakdown). Each output line must be {"report": <input line index>, "track": <string|null>,
"at": <arr of the newest input report read when this line was written>}.

Contract checks (any failure means the run does not pass):
  - every report is answered exactly once
  - arr[report] <= at <= arr[report] + LATENCY
  - "at" never decreases from one output line to the next

Metrics:
  association  share of valid reports whose track's majority aircraft is their own aircraft
  id switches  number of times an aircraft's dominant track changes between consecutive
               SWITCH_WINDOW_S windows of arrival time; a single misassigned report near a
               crossing does not count, a swap or a new track for the same aircraft does
  merged       tracks containing at least MERGE_MIN reports of a second aircraft
  invalid      invalid reports (truth null) placed in a track whose majority is a real aircraft
"""

import argparse
import collections
import json
import pathlib
import subprocess
import sys

DEFAULT_LATENCY_S = 2.0
MERGE_MIN = 3
SWITCH_WINDOW_S = 10.0
DEFAULT_MIN_ASSOCIATION = 0.99
DEFAULT_MAX_SWITCHES_PER_AIRCRAFT = 1.0
DEFAULT_MAX_INVALID_ACCEPTED = 0.25


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def run_command(command, reports_path):
    with open(reports_path) as stdin:
        result = subprocess.run(command, shell=True, stdin=stdin, capture_output=True, text=True)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(f"command exited with {result.returncode}")
    return result.stdout.splitlines()


def check_contract(reports, lines, latency):
    errors = []
    answers = {}
    last_at = -float("inf")
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            answer = json.loads(line)
            index = answer["report"]
            track = answer["track"]
            at = float(answer["at"])
        except (ValueError, KeyError, TypeError) as error:
            errors.append(f"output line {number}: malformed ({error}): {line[:80]}")
            continue
        if not isinstance(index, int) or not 0 <= index < len(reports):
            errors.append(f"output line {number}: report index {index!r} out of range")
            continue
        if track is not None and not isinstance(track, str):
            errors.append(f"output line {number}: track must be a string or null")
            continue
        if index in answers:
            errors.append(f"report {index} answered twice")
            continue
        arr = reports[index]["arr"]
        if at < arr - 1e-6:
            errors.append(f"report {index} answered at {at} before it arrived at {arr}")
        if at > arr + latency + 1e-6:
            errors.append(f"report {index} answered {at - arr:.3f}s after arrival (limit {latency}s)")
        if at < last_at - 1e-6:
            errors.append(f"output line {number}: at {at} is earlier than the previous line ({last_at})")
        last_at = max(last_at, at)
        answers[index] = (track, at)
    missing = len(reports) - len(answers)
    if missing:
        errors.append(f"{missing} reports never answered")
    return answers, errors


def score(reports, truths, answers):
    truth_of = {t["report"]: t["aircraft"] for t in truths}
    track_members = collections.defaultdict(collections.Counter)
    for index, (track, _) in answers.items():
        if track is not None and truth_of[index] is not None:
            track_members[track][truth_of[index]] += 1
    majority = {track: members.most_common(1)[0][0] for track, members in track_members.items()}

    valid = [i for i in range(len(reports)) if truth_of[i] is not None]
    invalid = [i for i in range(len(reports)) if truth_of[i] is None]
    correct = 0
    per_aircraft = collections.defaultdict(
        lambda: {"reports": 0, "correct": 0, "switches": [], "tracks": set(), "windows": {}}
    )
    for i in valid:
        aircraft = truth_of[i]
        track = answers.get(i, (None, None))[0]
        stats = per_aircraft[aircraft]
        stats["reports"] += 1
        if track is not None and majority.get(track) == aircraft:
            correct += 1
            stats["correct"] += 1
        if track is None:
            continue
        stats["tracks"].add(track)
        window = int(reports[i]["arr"] // SWITCH_WINDOW_S)
        stats["windows"].setdefault(window, collections.Counter())[track] += 1

    for stats in per_aircraft.values():
        dominant = [(w, c.most_common(1)[0][0]) for w, c in sorted(stats["windows"].items())]
        for (_, previous), (window, current) in zip(dominant, dominant[1:]):
            if previous != current:
                stats["switches"].append(window * SWITCH_WINDOW_S)

    merged = [
        track
        for track, members in track_members.items()
        if len(members) > 1 and members.most_common(2)[1][1] >= MERGE_MIN
    ]
    invalid_accepted = sum(
        1 for i in invalid if (track := answers.get(i, (None, None))[0]) is not None and track in majority
    )
    return {
        "reports": len(reports),
        "valid_reports": len(valid),
        "association": correct / len(valid) if valid else 1.0,
        "aircraft": len(per_aircraft),
        "id_switches": sum(len(s["switches"]) for s in per_aircraft.values()),
        "tracks": len({track for track, _ in answers.values() if track is not None}),
        "merged_tracks": len(merged),
        "invalid_reports": len(invalid),
        "invalid_accepted": invalid_accepted,
        "per_aircraft": per_aircraft,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("data_dir", type=pathlib.Path)
    parser.add_argument("output", nargs="?", type=pathlib.Path)
    parser.add_argument("--run", metavar="CMD", help="command reading reports on stdin, writing answers on stdout")
    parser.add_argument("--save", type=pathlib.Path, help="with --run: also write the command's output here")
    parser.add_argument("--latency", type=float, default=DEFAULT_LATENCY_S)
    parser.add_argument("--min-association", type=float, default=DEFAULT_MIN_ASSOCIATION)
    parser.add_argument("--max-switches-per-aircraft", type=float, default=DEFAULT_MAX_SWITCHES_PER_AIRCRAFT)
    parser.add_argument("--max-invalid-accepted", type=float, default=DEFAULT_MAX_INVALID_ACCEPTED)
    parser.add_argument("--details", action="store_true", help="print per-aircraft results")
    args = parser.parse_args()
    if (args.output is None) == (args.run is None):
        parser.error("give exactly one of OUTPUT or --run")

    reports = read_jsonl(args.data_dir / "reports.jsonl")
    truths = read_jsonl(args.data_dir / "truth.jsonl")
    if args.run:
        lines = run_command(args.run, args.data_dir / "reports.jsonl")
        if args.save:
            args.save.write_text("\n".join(lines) + "\n")
    else:
        lines = args.output.read_text().splitlines()

    answers, errors = check_contract(reports, lines, args.latency)
    result = score(reports, truths, answers)

    print(f"reports            {result['reports']} ({result['invalid_reports']} invalid)")
    print(f"aircraft           {result['aircraft']}")
    print(f"tracks             {result['tracks']}")
    print(f"association        {result['association']:.2%}")
    print(f"id switches        {result['id_switches']}")
    print(f"merged tracks      {result['merged_tracks']}")
    print(f"invalid accepted   {result['invalid_accepted']} / {result['invalid_reports']}")
    print(f"contract errors    {len(errors)}")
    for error in errors[:10]:
        print(f"  {error}")
    if len(errors) > 10:
        print(f"  ... {len(errors) - 10} more")

    if args.details:
        meta_path = args.data_dir / "meta.json"
        meta = {}
        if meta_path.exists():
            meta = {a["name"]: a for a in json.loads(meta_path.read_text())["aircraft"]}
        print("\naircraft  kind      reports  assoc    tracks  switches at (arr)")
        ranked = sorted(result["per_aircraft"].items(), key=lambda item: -len(item[1]["switches"]))
        for name, stats in ranked:
            info = meta.get(name, {})
            kind = info.get("kind", "?")
            note = f"  [{info['note']}]" if info.get("note") else ""
            switches = ", ".join(f"{t:.1f}" for t in stats["switches"][:6])
            if len(stats["switches"]) > 6:
                switches += ", ..."
            print(
                f"{name:9} {kind:9} {stats['reports']:7}  {stats['correct'] / stats['reports']:6.1%}"
                f"  {len(stats['tracks']):6}  {len(stats['switches']):3} {switches}{note}"
            )

    invalid_ratio = result["invalid_accepted"] / result["invalid_reports"] if result["invalid_reports"] else 0.0
    passed = (
        not errors
        and result["association"] >= args.min_association
        and result["id_switches"] <= args.max_switches_per_aircraft * result["aircraft"]
        and invalid_ratio <= args.max_invalid_accepted
    )
    print(f"\n{'PASS' if passed else 'FAIL'}")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
