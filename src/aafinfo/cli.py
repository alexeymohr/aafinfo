from __future__ import annotations

import json
from pathlib import Path
import re

import click
from click.core import ParameterSource

from aafinfo._version import __version__
from aafinfo.engine import build_report
from aafinfo.errors import AAFInfoError


@click.command(context_settings={"help_option_names": ["--help"]})
@click.pass_context
@click.argument(
    "file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--out",
    "out_dir",
    default=Path("aafinfo-report"),
    metavar="<dir>",
    show_default="./aafinfo-report/",
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory for report artifacts.",
)
@click.option(
    "--json-only",
    is_flag=True,
    help="Write nothing; print JSON to stdout.",
)
@click.option(
    "--filter",
    "filter_text",
    metavar="<text>",
    help="Case-insensitive substring filter for the HTML clips table.",
)
@click.option(
    "--no-clips",
    is_flag=True,
    help="Exclude the per-clip table from the HTML report.",
)
@click.option(
    "--name",
    "name_slug",
    metavar="<slug>",
    help="Explicit slug for output filenames.",
)
@click.version_option(__version__, prog_name="aafinfo", message="%(prog)s %(version)s")
def main(
    ctx: click.Context,
    file: Path,
    out_dir: Path,
    json_only: bool,
    filter_text: str | None,
    no_clips: bool,
    name_slug: str | None,
) -> None:
    """Inspect FILE and produce JSON/HTML reports."""
    _ = (filter_text, no_clips)

    if json_only and ctx.get_parameter_source("out_dir") is not ParameterSource.DEFAULT:
        raise click.UsageError("--json-only cannot be used with --out.")

    try:
        report = build_report(file)
    except AAFInfoError as exc:
        click.echo(exc.message, err=True)
        if exc.detail:
            click.echo(f"detail: {exc.detail}", err=True)
        raise click.exceptions.Exit(2) from exc
    except Exception as exc:
        click.echo("Unhandled AAFinfo runtime error.", err=True)
        click.echo(f"detail: {exc}", err=True)
        raise click.exceptions.Exit(2) from exc

    json_payload = _report_json(report)
    if json_only:
        click.echo(json_payload)
        return

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = slugify(name_slug or file.stem)
        output_path = next_available_path(out_dir, report_stem(slug), ".json")
        output_path.write_text(json_payload + "\n", encoding="utf-8")
    except OSError as exc:
        click.echo(f"Cannot write report output: {out_dir}", err=True)
        click.echo(f"detail: {exc}", err=True)
        raise click.exceptions.Exit(2) from exc

    click.echo(str(output_path))


def _report_json(report: object) -> str:
    return json.dumps(
        report.model_dump(mode="json"),  # type: ignore[attr-defined]
        indent=2,
        sort_keys=True,
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "report"


def report_stem(slug: str) -> str:
    if slug == "report":
        return "report"
    return f"{slug}-report"


def next_available_path(directory: Path, stem: str, suffix: str) -> Path:
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = directory / f"{stem}-{counter:02d}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
