"""Datary command-line interface."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from datary import __version__
from datary.comparison import compare_sessions
from datary.config import default_workspace
from datary.conversion import convert_source
from datary.formats import SUPPORTED_FORMATS
from datary.generators import PROFILES, generate_records
from datary.inspection import inspect_source, load_source
from datary.models import RecordOptions
from datary.plotting import create_plot
from datary.recorder import record_stream
from datary.replay import replay_session
from datary.reports import write_report
from datary.sessions import Session, list_sessions
from datary.utils import parse_key_values, sparkline


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="datary", description="Local-first terminal laboratory for reproducible data.")
    root.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    root.add_argument("--workspace", type=Path, default=default_workspace(), help="session workspace (or DATARY_WORKSPACE)")
    commands = root.add_subparsers(dest="command", required=True)
    record = commands.add_parser("record", help="record a named session from standard input")
    record.add_argument("name")
    record.add_argument("--format", choices=SUPPORTED_FORMATS)
    record.add_argument("--time-field")
    record.add_argument("--param", action="append", default=[], metavar="KEY=VALUE")
    record.add_argument("--unit", action="append", default=[], metavar="FIELD=UNIT")
    record.add_argument("--command", dest="original_command")
    record.add_argument("--overwrite", action="store_true")
    record.add_argument("--include-path", action="store_true")
    record.add_argument("--max-line-bytes", type=int, default=1_048_576)
    record.add_argument("--max-fields", type=int, default=1000)
    inspect = commands.add_parser("inspect", help="inspect a session or data file")
    inspect.add_argument("source")
    inspect.add_argument("--format", choices=SUPPORTED_FORMATS)
    inspect.add_argument("--time-field")
    inspect.add_argument("--field")
    inspect.add_argument("--quality", action="store_true")
    inspect.add_argument("--plot", help="comma-separated fields")
    inspect.add_argument("--json", action="store_true")
    compare = commands.add_parser("compare", help="compare two or more sessions/files")
    compare.add_argument("sources", nargs="+")
    compare.add_argument("--field", action="append")
    compare.add_argument("--goal")
    compare.add_argument("--report", type=Path)
    compare.add_argument("--format", choices=("terminal", "json", "markdown", "csv"), default="terminal")
    replay = commands.add_parser("replay", help="replay a recorded session")
    replay.add_argument("session")
    replay.add_argument("--speed", type=float, default=1.0)
    replay.add_argument("--loop", action="store_true")
    replay.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    replay.add_argument("--no-timing", action="store_true")
    replay.add_argument("--virtual", action="store_true", help=argparse.SUPPRESS)
    report = commands.add_parser("report", help="generate a local report")
    report.add_argument("session")
    report.add_argument("--format", choices=("markdown", "json"), default="markdown")
    report.add_argument("--output", type=Path)
    generate = commands.add_parser("generate", help="generate deterministic synthetic data")
    generate.add_argument("profile", choices=PROFILES)
    generate.add_argument("--seed", type=int, default=0)
    generate.add_argument("--duration", type=float, default=10.0)
    generate.add_argument("--sample-rate", type=float, default=10.0)
    generate.add_argument("--noise", type=float, default=0.05)
    generate.add_argument("--missing-rate", type=float, default=0.0)
    generate.add_argument("--duplicate-rate", type=float, default=0.0)
    generate.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    generate.add_argument("--output", type=Path)
    generate.add_argument("--real-time", action="store_true")
    convert = commands.add_parser("convert", help="convert a supported local file")
    convert.add_argument("source", type=Path)
    convert.add_argument("--to", choices=("csv", "jsonl"), required=True)
    convert.add_argument("--format", choices=SUPPORTED_FORMATS)
    convert.add_argument("--output", type=Path)
    convert.add_argument("--overwrite", action="store_true")
    commands.add_parser("sessions", help="list sessions")
    doctor = commands.add_parser("doctor", help="check installation and session integrity")
    doctor.add_argument("--json", action="store_true")
    return root


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        return _dispatch(arguments)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except OSError:
            pass
        return 0
    except KeyboardInterrupt:
        print("datary: interrupted", file=sys.stderr)
        return 130
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"datary: error: {error}", file=sys.stderr)
        return 2


def _dispatch(args: argparse.Namespace) -> int:
    workspace = args.workspace
    if args.command == "record":
        path = record_stream(
            sys.stdin,
            RecordOptions(
                args.name, workspace, args.format, args.time_field, args.original_command,
                parse_key_values(args.param), parse_key_values(args.unit), args.overwrite,
                args.include_path, args.max_line_bytes, args.max_fields,
            ),
        )
        session = Session.open(path)
        print(f"Recorded {session.manifest['valid_record_count']} valid and {session.manifest['invalid_record_count']} invalid records in {path}")
    elif args.command == "inspect":
        inspection = inspect_source(_resolve(args.source, workspace), input_format=args.format, time_field=args.time_field)
        if args.json:
            print(json.dumps(inspection.to_dict(), indent=2, ensure_ascii=False))
        else:
            _print_inspection(inspection.to_dict(), args.field, args.quality)
        if args.plot:
            source = _resolve(args.source, workspace)
            records, _, _, _, manifest_time = load_source(source, args.format)
            session_path = Path(source) if Path(source).is_dir() else workspace
            output = session_path / "plots" / f"{'-'.join(args.plot.split(','))}.png"
            create_plot(records, args.plot.split(","), output, time_field=args.time_field or manifest_time)
            print(f"Plot: {output}")
    elif args.command == "compare":
        result = compare_sessions([_resolve(source, workspace) for source in args.sources], args.field, args.goal)
        rendered = _comparison_output(result.to_dict(), args.format)
        if args.report:
            args.report.write_text(rendered, encoding="utf-8")
        else:
            print(rendered)
    elif args.command == "replay":
        session = Session.open(_resolve(args.session, workspace))
        while True:
            replay_session(session, sys.stdout, speed=args.speed, no_timing=args.no_timing, virtual=args.virtual, output_format=args.format)
            if not args.loop:
                break
    elif args.command == "report":
        session = Session.open(_resolve(args.session, workspace))
        suffix = ".json" if args.format == "json" else ".md"
        output = args.output or session.path / "reports" / f"report{suffix}"
        write_report(session, output, args.format)
        print(output)
    elif args.command == "generate":
        _generate(args)
    elif args.command == "convert":
        output = args.output or args.source.with_suffix(".csv" if args.to == "csv" else ".jsonl")
        valid, invalid = convert_source(args.source, output, args.to, args.format, args.overwrite)
        print(f"Converted {valid} records ({invalid} invalid) to {output}", file=sys.stderr)
    elif args.command == "sessions":
        for session in list_sessions(workspace):
            print(f"{session.name}\t{session.manifest.get('valid_record_count', 0)}\t{session.manifest.get('ended_at', '')}")
    elif args.command == "doctor":
        checks = _doctor(workspace)
        print(json.dumps(checks, indent=2) if args.json else "\n".join(f"{'OK' if value else 'FAIL'}  {name}" for name, value in checks.items()))
        return 0 if all(checks.values()) else 1
    return 0


def _resolve(source: str, workspace: Path) -> Path:
    path = Path(source)
    return path if path.exists() else workspace / source


def _print_inspection(data: Dict[str, Any], selected: Optional[str], show_quality: bool) -> None:
    print(f"Source: {data['source']} ({data['format']})")
    print(f"Records: {data['record_count']} valid, {data['invalid_count']} invalid")
    for field in sorted(data["fields"]):
        if selected and field != selected:
            continue
        metric = data["metrics"].get(field)
        unit = f" [{data['units'][field]}]" if field in data["units"] else ""
        line = f"{field}{unit}: {data['fields'][field]}"
        if metric and metric.get("valid_count"):
            values = [metric[key] for key in ("minimum", "mean", "maximum") if metric.get(key) is not None]
            line += (
                f" min={metric['minimum']:.6g} mean={metric['mean']:.6g} "
                f"max={metric['maximum']:.6g} {sparkline(values, _ascii_terminal())}"
            )
        print(line)
    if data["timing"]:
        print(f"Timing: {json.dumps(data['timing'], sort_keys=True)}")
    if show_quality or data["quality"]:
        print(f"Quality findings: {len(data['quality'])}")
        for item in data["quality"]:
            separator = "-" if _ascii_terminal() else "—"
            print(f"  {item['severity']}: {item['check_id']} {item.get('field') or ''} {separator} {item['explanation']}")


def _comparison_output(data: Dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(data, indent=2, ensure_ascii=False)
    if fmt == "csv":
        lines = ["field,source,mean"]
        for field, detail in data["fields"].items():
            for source, value in detail["means"].items():
                lines.append(f"{_csv(field)},{_csv(source)},{value}")
        return "\n".join(lines) + "\n"
    lines = ["# Datary comparison", ""] if fmt == "markdown" else ["Datary comparison"]
    for field, detail in data["fields"].items():
        lines.append(f"{'## ' if fmt == 'markdown' else ''}{field}")
        for source, value in detail["means"].items():
            lines.append(f"- {source}: {value}" if fmt == "markdown" else f"  {source}: {value}")
    lines.extend(f"Warning: {warning}" for warning in data["warnings"])
    return "\n".join(lines)


def _csv(value: str) -> str:
    import io
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="").writerow([value])
    return buffer.getvalue()


def _generate(args: argparse.Namespace) -> None:
    records = generate_records(args.profile, seed=args.seed, duration=args.duration, sample_rate=args.sample_rate, noise=args.noise, missing_rate=args.missing_rate, duplicate_rate=args.duplicate_rate)
    output = args.output.open("w", encoding="utf-8", newline="") if args.output else sys.stdout
    close = args.output is not None
    try:
        first = True
        fields: List[str] = []
        writer: Optional[csv.DictWriter[str]] = None
        for record in records:
            if args.format == "jsonl":
                output.write(json.dumps(record, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
            else:
                if first:
                    fields = list(record)
                    writer = csv.DictWriter(output, fieldnames=fields)
                    writer.writeheader()
                assert writer is not None
                writer.writerow(record)
            output.flush()
            if args.real_time and not first:
                time.sleep(1 / args.sample_rate)
            first = False
    finally:
        if close:
            output.close()


def _doctor(workspace: Path) -> Dict[str, bool]:
    python_ok = sys.version_info >= (3, 9)
    workspace.mkdir(parents=True, exist_ok=True)
    writable = os.access(workspace, os.W_OK)
    plotting = False
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
        plotting = True
    except ImportError:
        pass
    integrity = all(not session.verify() for session in list_sessions(workspace))
    return {"python_3_9_or_newer": python_ok, "workspace_writable": writable, "plotting_available": plotting, "session_integrity": integrity, f"datary_{__version__}": True}


def _ascii_terminal() -> bool:
    encoding = sys.stdout.encoding or "ascii"
    try:
        "▁—".encode(encoding)
        return False
    except UnicodeEncodeError:
        return True
