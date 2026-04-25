from __future__ import annotations

from collections import defaultdict
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

from click.testing import CliRunner

from aafinfo import build_report
from aafinfo.cli import main
from aafinfo.models import ReportModel
from aafinfo.report import render_html


class ReportHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sections: list[str] = []
        self.tables: set[str] = set()
        self.table_text: dict[str, list[str]] = defaultdict(list)
        self.titles: list[str] = []
        self.script_count = 0
        self.link_count = 0
        self._table_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name: value or "" for name, value in attrs}
        if tag == "script":
            self.script_count += 1
        if tag == "link":
            self.link_count += 1
        if "title" in attrs_dict:
            self.titles.append(attrs_dict["title"])

        section = attrs_dict.get("data-section")
        if section is not None and tag in {"header", "section"}:
            self.sections.append(section)

        table = attrs_dict.get("data-table")
        if tag == "table" and table is not None:
            self.tables.add(table)
            self._table_stack.append(table)

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self._table_stack:
            self._table_stack.pop()

    def handle_data(self, data: str) -> None:
        if not self._table_stack:
            return
        text = data.strip()
        if text:
            self.table_text[self._table_stack[-1]].append(text)


def _load_generator() -> ModuleType:
    generator_path = Path(__file__).resolve().parents[2] / "examples" / "_generate.py"
    spec = importlib.util.spec_from_file_location("aafinfo_fixture_generator_html", generator_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generate_all = _load_generator().generate_all


def _parse(html: str) -> ReportHTMLParser:
    parser = ReportHTMLParser()
    parser.feed(html)
    return parser


def test_html_report_contains_documented_sections_and_tables(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path / "fixtures")["multi_track"])

    html = render_html(report)
    parser = _parse(html)

    assert parser.sections == [
        "header",
        "composition-summary",
        "tracks",
        "clips",
        "source-mobs",
        "markers",
        "warnings",
    ]
    assert {"tracks", "clips", "source-mobs", "markers"} <= parser.tables
    assert parser.script_count == 0
    assert parser.link_count == 0
    assert "@import" not in html
    assert "<style>" in html
    assert "multi_track.aaf" in html
    assert "dx_1.wav" in " ".join(parser.table_text["clips"])
    assert "mx_1-2.wav" in " ".join(parser.table_text["source-mobs"])
    assert "/Volumes/AAFinfo/dx_1.wav" in parser.titles


def test_html_clip_filter_is_render_time_only(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path / "fixtures")["multi_track"])

    html = render_html(report, filter_text="mx")
    parser = _parse(html)
    clips_text = " ".join(parser.table_text["clips"])

    assert "MX 1-2" in clips_text
    assert "mx_1-2.wav" in clips_text
    assert "DX 1" not in clips_text
    assert "sfx_1-2.wav" not in clips_text
    assert len(report.clips) == 10
    assert "1 of 10 clips matching" in html


def test_html_can_omit_clips_section(tmp_path: Path) -> None:
    report = build_report(generate_all(tmp_path / "fixtures")["simple_stereo"])

    html = render_html(report, include_clips=False)
    parser = _parse(html)

    assert "clips" not in parser.sections
    assert "clips" not in parser.tables


def test_cli_writes_json_and_filtered_html(tmp_path: Path) -> None:
    fixture = generate_all(tmp_path / "fixtures")["multi_track"]
    out_dir = tmp_path / "out"

    result = CliRunner().invoke(main, [str(fixture), "--out", str(out_dir), "--filter", "mx"])

    assert result.exit_code == 0, result.output
    json_path = out_dir / "multi-track-report.json"
    html_path = out_dir / "multi-track-report.html"
    assert result.output.splitlines() == [str(json_path), str(html_path)]
    report = ReportModel.model_validate(json.loads(json_path.read_text(encoding="utf-8")))
    html = html_path.read_text(encoding="utf-8")
    parser = _parse(html)

    assert len(report.clips) == 10
    assert "MX 1-2" in " ".join(parser.table_text["clips"])
    assert "DX 1" not in " ".join(parser.table_text["clips"])


def test_cli_no_clips_omits_html_clip_section_only(tmp_path: Path) -> None:
    fixture = generate_all(tmp_path / "fixtures")["simple_stereo"]
    out_dir = tmp_path / "out"

    result = CliRunner().invoke(main, [str(fixture), "--out", str(out_dir), "--no-clips"])

    assert result.exit_code == 0, result.output
    json_path = out_dir / "simple-stereo-report.json"
    html_path = out_dir / "simple-stereo-report.html"
    report = ReportModel.model_validate(json.loads(json_path.read_text(encoding="utf-8")))
    parser = _parse(html_path.read_text(encoding="utf-8"))

    assert len(report.clips) == 4
    assert "clips" not in parser.sections
    assert "source-mobs" in parser.sections
