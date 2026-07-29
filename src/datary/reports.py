"""Local Markdown and JSON reports."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from datary import __version__
from datary.inspection import inspect_source
from datary.sessions import Session
from datary.utils import atomic_json


def report_data(session: Session) -> Dict[str, Any]:
    inspection = inspect_source(session)
    return {
        "datary_version": __version__,
        "session": session.manifest,
        "inspection": inspection.to_dict(),
        "integrity_errors": session.verify(),
        "warnings_and_assumptions": [
            "Statistics describe recorded data; they do not establish scientific validity.",
            "Quality checks are heuristics and require domain review.",
        ],
    }


def write_report(session: Session, output: Path, report_format: str = "markdown") -> Path:
    data = report_data(session)
    output.parent.mkdir(parents=True, exist_ok=True)
    if report_format == "json":
        atomic_json(output, data)
    elif report_format == "markdown":
        output.write_text(_markdown(data), encoding="utf-8", newline="\n")
    else:
        raise ValueError("report format must be markdown or json")
    return output


def _markdown(data: Dict[str, Any]) -> str:
    manifest = data["session"]
    inspection = data["inspection"]
    lines = [
        f"# Datary report: {_md(str(manifest['session_name']))}",
        "",
        f"- Datary version: `{data['datary_version']}`",
        f"- Started: `{manifest.get('started_at')}`",
        f"- Ended: `{manifest.get('ended_at')}`",
        f"- Input format: `{manifest.get('input_format')}`",
        f"- Records: {manifest.get('valid_record_count')} valid, {manifest.get('invalid_record_count')} invalid",
        "",
        "## Reproduction",
        "",
    ]
    for name, command in sorted(manifest.get("commands", {}).items()):
        lines.append(f"- {name}: `{_md(str(command))}`")
    lines += ["", "## Data schema", "", "| Field | Type | Unit |", "|---|---|---|"]
    for field, kind in inspection["fields"].items():
        lines.append(f"| {_md(field)} | {_md(kind)} | {_md(inspection['units'].get(field, ''))} |")
    lines += ["", "## Descriptive statistics", ""]
    for field, metric in inspection["metrics"].items():
        lines.append(f"### {_md(field)}")
        lines.append("")
        lines.append(f"- Mean: {metric.get('mean')}")
        lines.append(f"- Median: {metric.get('median')}")
        lines.append(f"- Range: {metric.get('minimum')} to {metric.get('maximum')}")
        lines.append("")
    lines += ["## Quality findings", ""]
    if not inspection["quality"]:
        lines.append("No heuristic findings.")
    for finding in inspection["quality"]:
        lines.append(f"- **{_md(finding['check_id'])}** ({finding['severity']}): {_md(finding['explanation'])} Field: `{_md(str(finding.get('field') or '-'))}`; affected: {_md(finding['affected'])}.")
    lines += ["", "## Input hashes", ""]
    for name, digest in sorted(manifest.get("hashes", {}).items()):
        lines.append(f"- `{_md(name)}`: `{digest}`")
    lines += ["", "## Warnings and assumptions", ""]
    lines.extend(f"- {_md(item)}" for item in data["warnings_and_assumptions"])
    lines += ["", "## Plots", "", "Plots are stored in the session `plots/` directory.", ""]
    return "\n".join(lines)


def _md(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`").replace("\n", " ")
