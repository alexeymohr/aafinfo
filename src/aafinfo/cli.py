from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import itertools
import json
from pathlib import Path
import re
import sys
from threading import Event, Thread
import time
from typing import TextIO

import click
from click.core import ParameterSource

from aafinfo._version import __version__
from aafinfo.engine import build_report
from aafinfo.errors import AAFInfoError
from aafinfo.models import ReportModel
from aafinfo.report import render_html


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
    "--json",
    "--json-only",
    "json_only",
    is_flag=True,
    help="Write nothing; print JSON to stdout. Synonym: --json-only.",
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
    if json_only and ctx.get_parameter_source("out_dir") is not ParameterSource.DEFAULT:
        raise click.UsageError("--json/--json-only cannot be used with --out.")

    try:
        with spinner("Inspecting AAF"):
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
        with spinner("Writing report"):
            out_dir.mkdir(parents=True, exist_ok=True)
            slug = slugify(name_slug or file.stem)
            json_path, html_path = next_available_report_paths(out_dir, report_stem(slug))
            html_payload = render_html(
                report,
                filter_text=filter_text,
                include_clips=not no_clips,
            )
            json_path.write_text(json_payload + "\n", encoding="utf-8")
            html_path.write_text(html_payload + "\n", encoding="utf-8")
    except OSError as exc:
        click.echo(f"Cannot write report output: {out_dir}", err=True)
        click.echo(f"detail: {exc}", err=True)
        raise click.exceptions.Exit(2) from exc
    except Exception as exc:
        click.echo("Cannot render report output.", err=True)
        click.echo(f"detail: {exc}", err=True)
        raise click.exceptions.Exit(2) from exc

    click.echo(str(json_path))
    click.echo(str(html_path))


@contextmanager
def spinner(
    message: str = "Working",
    delay: float = 0.1,
    *,
    stream: TextIO | None = None,
    enabled: bool | None = None,
) -> Iterator[None]:
    stream = stream or sys.stderr
    if enabled is None:
        enabled = stream.isatty()
    if not enabled:
        yield
        return

    stop_event = Event()

    def run_spinner() -> None:
        frames = itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")
        while not stop_event.is_set():
            stream.write(f"\r{next(frames)} {message}...")
            stream.flush()
            time.sleep(delay)

        stream.write("\r" + " " * (len(message) + 10) + "\r")
        stream.flush()

    thread = Thread(target=run_spinner, daemon=True)

    try:
        thread.start()
        yield
    finally:
        stop_event.set()
        thread.join()


def _report_json(report: ReportModel) -> str:
    return json.dumps(
        report.model_dump(mode="json"),
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


def next_available_report_paths(directory: Path, stem: str) -> tuple[Path, Path]:
    json_path = directory / f"{stem}.json"
    html_path = directory / f"{stem}.html"
    if not json_path.exists() and not html_path.exists():
        return json_path, html_path

    counter = 1
    while True:
        json_path = directory / f"{stem}-{counter:02d}.json"
        html_path = directory / f"{stem}-{counter:02d}.html"
        if not json_path.exists() and not html_path.exists():
            return json_path, html_path
        counter += 1
