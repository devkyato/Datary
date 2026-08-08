"""Local Markdown and JSON reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

from datary import __version__
from datary.inspection import inspect_source
from datary.sessions import Session
from datary.utils import atomic_json, atomic_text, markdown_safe


def report_data(session: Session) -> Dict[str, Any]:
    inspection = inspect_source(session)
    plots_directory = session.path / "plots"
    plot_entries: list[Dict[str, Any]] = []
    if plots_directory.is_dir() and not plots_directory.is_symlink():
        for path in sorted(plots_directory.iterdir(), key=lambda item: item.name):
            if not path.is_file() or path.is_symlink():
                continue
            if path.suffix.lower() not in {".png", ".svg"}:
                continue
            metadata_path = path.with_suffix(path.suffix + ".meta.json")
            metadata: Dict[str, Any] = {}
            if (
                metadata_path.is_file()
                and not metadata_path.is_symlink()
                and metadata_path.stat().st_size <= 1_048_576
            ):
                try:
                    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    loaded = {}
                if isinstance(loaded, dict):
                    metadata = loaded
            plot_entries.append({"filename": path.name, "metadata": metadata})
    return {
        "datary_version": __version__,
        "session": session.manifest,
        "inspection": inspection.to_dict(),
        "integrity_errors": session.verify(),
        "plots": [entry["filename"] for entry in plot_entries],
        "plot_details": plot_entries,
        "warnings_and_assumptions": [
            "Statistics describe recorded data; they do not establish scientific validity.",
            "Quality checks are heuristics and require domain review.",
            "Plot downsampling preserves declared extrema but is visual evidence, not a new recording.",
        ],
    }


def write_report(session: Session, output: Path, report_format: str = "markdown") -> Path:
    data = report_data(session)
    output.parent.mkdir(parents=True, exist_ok=True)
    if report_format == "json":
        atomic_json(output, data)
    elif report_format == "markdown":
        atomic_text(output, _markdown(data))
    else:
        raise ValueError("report format must be markdown or json")
    return output


def _markdown(data: Dict[str, Any]) -> str:
    manifest = data["session"]
    inspection = data["inspection"]
    lines = [
        f"# Datary report: {_md(str(manifest['session_name']))}",
        "",
        f"- Datary version: {_code(data['datary_version'])}",
        f"- Recorded with Datary: {_code(manifest.get('datary_version'))}",
        f"- Session format: {_code(manifest.get('session_format_version'))}",
        f"- Started: {_code(manifest.get('started_at'))}",
        f"- Ended: {_code(manifest.get('ended_at'))}",
        f"- Input format: {_code(manifest.get('input_format'))}",
        f"- Records: {manifest.get('valid_record_count')} valid, {manifest.get('invalid_record_count')} invalid",
        "",
        "## Reproduction",
        "",
    ]
    lines.append(f"- Original command: {_code(manifest.get('original_command') or 'not supplied')}")
    lines.append(f"- Working directory: {_code(manifest.get('working_directory', '<redacted>'))}")
    lines.append(f"- Command context: {_md(str(manifest.get('command_context', '')))}")
    parameters = manifest.get("parameters", {})
    if parameters:
        lines.append("- Parameters:")
        for name, value in sorted(parameters.items()):
            lines.append(f"  - {_code(name)} = {_code(value)}")
    for name, command in sorted(manifest.get("commands", {}).items()):
        lines.append(f"- {_md(str(name))}: {_code(command)}")
    parser_warnings = manifest.get("parser_warnings", [])
    if parser_warnings:
        lines += ["", "### Parser warnings", ""]
        lines.extend(f"- {_md(str(warning))}" for warning in parser_warnings)
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
    lines += ["## Timing", ""]
    if inspection["timing"]:
        for name, value in sorted(inspection["timing"].items()):
            lines.append(f"- {_md(str(name))}: {_code(value)}")
    else:
        lines.append("No usable time field was supplied.")
    lines.append("")
    lines += ["## Engineering metrics", ""]
    if inspection.get("engineering"):
        for category, metrics in sorted(inspection["engineering"].items()):
            lines.append(f"### {_md(str(category).title())}")
            lines.append("")
            for name, value in sorted(metrics.items()):
                if name in {"assumptions", "warnings", "required_fields"}:
                    continue
                lines.append(f"- {_md(str(name))}: {_code(value)}")
            required = metrics.get("required_fields", {})
            if required:
                lines.append(
                    "- Required fields: "
                    + ", ".join(
                        f"{_md(str(role))}={_code(field)}"
                        for role, field in sorted(required.items())
                        if field is not None
                    )
                )
            for assumption in metrics.get("assumptions", []):
                lines.append(f"- Assumption: {_md(str(assumption))}")
            for warning in metrics.get("warnings", []):
                lines.append(f"- Warning: {_md(str(warning))}")
            lines.append("")
    else:
        lines.append("No control or network field roles were supplied.")
        lines.append("")
    lines += ["## Quality findings", ""]
    if not inspection["quality"]:
        lines.append("No heuristic findings.")
    for finding in inspection["quality"]:
        lines.append(
            f"- **{_md(finding['check_id'])}** ({finding['severity']}): {_md(finding['explanation'])} Field: {_code(finding.get('field') or '-')}; affected: {_md(finding['affected'])}."
        )
        lines.append(
            f"  - Evidence: {_code(finding.get('evidence'))}; "
            f"threshold: {_code(finding.get('threshold'))}"
        )
        assumptions = finding.get("assumptions") or []
        if assumptions:
            lines.append("  - Assumptions: " + "; ".join(_md(str(item)) for item in assumptions))
        lines.append(
            "  - Suggested investigation: "
            + _md(str(finding.get("suggested_investigation") or "Review the raw input."))
        )
    lines += ["", "## Input hashes", ""]
    for name, digest in sorted(manifest.get("hashes", {}).items()):
        lines.append(f"- {_code(name)}: {_code(digest)}")
    lines += ["", "## Integrity verification", ""]
    integrity_errors = data["integrity_errors"]
    if integrity_errors:
        lines.append("**FAILED:** this session did not pass integrity verification.")
        lines.extend(f"- {_md(str(item))}" for item in integrity_errors)
    else:
        lines.append("All manifest-listed artefacts passed SHA-256 corruption checks.")
    lines.append(
        "These checks detect accidental changes; they do not prove cryptographic authenticity."
    )
    lines += ["", "## Warnings and assumptions", ""]
    lines.extend(f"- {_md(item)}" for item in data["warnings_and_assumptions"])
    lines += ["", "## Plots", ""]
    plot_details = data.get("plot_details") or []
    if plot_details:
        for entry in plot_details:
            filename = entry["filename"]
            lines.append(f"- [{_md(str(filename))}](../plots/{quote(str(filename))})")
            metadata = entry.get("metadata") or {}
            downsample = metadata.get("downsample") or {}
            if downsample:
                lines.append(
                    "  - Downsample: "
                    f"algorithm={_code(downsample.get('algorithm'))}; "
                    f"applied={_code(downsample.get('applied'))}; "
                    f"original={_code(downsample.get('original_point_count'))}; "
                    f"plotted={_code(downsample.get('plotted_point_count'))}; "
                    f"max_points={_code(downsample.get('max_points'))}; "
                    f"preserved_extrema={_code(downsample.get('preserved_global_extrema'))}"
                )
                parameters = downsample.get("parameters") or {}
                if parameters.get("bucket_policy"):
                    lines.append(f"  - Policy: {_md(str(parameters['bucket_policy']))}")
    else:
        lines.append("No plots have been generated for this session.")
    lines.append("")
    return "\n".join(lines)


def _md(value: str) -> str:
    return markdown_safe(value)


def _code(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ")
    longest = 0
    current = 0
    for character in text:
        if character == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    fence = "`" * (longest + 1)
    content = f" {text} " if text.startswith(("`", " ")) or text.endswith(("`", " ")) else text
    return f"{fence}{content}{fence}"
