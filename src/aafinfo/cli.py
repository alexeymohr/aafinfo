from __future__ import annotations

from pathlib import Path

import click

from aafinfo import __version__


@click.command(context_settings={"help_option_names": ["--help"]})
@click.argument(
    "file",
    required=True,
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
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
    file: Path,
    out_dir: Path,
    json_only: bool,
    filter_text: str | None,
    no_clips: bool,
    name_slug: str | None,
) -> None:
    """Inspect FILE and produce JSON/HTML reports."""
    _ = (file, out_dir, json_only, filter_text, no_clips, name_slug)
    click.echo("ok")
