from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

from click.testing import CliRunner

from aafinfo.cli import (
    main,
    next_available_path,
    next_available_report_paths,
    report_stem,
    slugify,
)
from aafinfo.models import ReportModel


def _load_generator() -> ModuleType:
    generator_path = Path(__file__).resolve().parents[2] / "examples" / "_generate.py"
    spec = importlib.util.spec_from_file_location("aafinfo_fixture_generator_cli", generator_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generate_all = _load_generator().generate_all


def test_json_only_prints_schema_report(tmp_path: Path) -> None:
    fixture = generate_all(tmp_path / "fixtures")["simple_stereo"]

    result = CliRunner().invoke(main, [str(fixture), "--json-only"])

    assert result.exit_code == 0, result.output
    report = ReportModel.model_validate(json.loads(result.output))
    assert report.schema_version == 2
    assert report.composition.name == "simple_stereo"
    assert report.input.basename == "simple_stereo.aaf"


def test_out_writes_slugged_json_report(tmp_path: Path) -> None:
    fixture = generate_all(tmp_path / "fixtures")["multi_track"]
    out_dir = tmp_path / "out"

    result = CliRunner().invoke(main, [str(fixture), "--out", str(out_dir)])

    assert result.exit_code == 0, result.output
    json_path = out_dir / "multi-track-report.json"
    html_path = out_dir / "multi-track-report.html"
    assert result.output.splitlines() == [str(json_path), str(html_path)]
    report = ReportModel.model_validate_json(json_path.read_text(encoding="utf-8"))
    assert report.composition.name == "multi_track"
    assert html_path.exists()
    assert "multi_track" in html_path.read_text(encoding="utf-8")


def test_explicit_name_and_collision_numbering(tmp_path: Path) -> None:
    fixture = generate_all(tmp_path / "fixtures")["with_markers"]
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    existing = out_dir / "scene-12-report.json"
    existing.write_text("{}", encoding="utf-8")

    result = CliRunner().invoke(main, [str(fixture), "--out", str(out_dir), "--name", "Scene 12"])

    assert result.exit_code == 0, result.output
    json_path = out_dir / "scene-12-report-01.json"
    html_path = out_dir / "scene-12-report-01.html"
    assert result.output.splitlines() == [str(json_path), str(html_path)]
    assert json_path.exists()
    assert html_path.exists()
    assert existing.read_text(encoding="utf-8") == "{}"


def test_json_only_rejects_explicit_out(tmp_path: Path) -> None:
    fixture = generate_all(tmp_path / "fixtures")["simple_stereo"]

    result = CliRunner().invoke(main, [str(fixture), "--json-only", "--out", str(tmp_path / "out")])

    assert result.exit_code == 2
    assert "--json-only cannot be used with --out" in result.output


def test_parse_failure_exits_2(tmp_path: Path) -> None:
    not_aaf = tmp_path / "not-an-aaf.aaf"
    not_aaf.write_text("not an AAF", encoding="utf-8")

    result = CliRunner().invoke(main, [str(not_aaf), "--json-only"])

    assert result.exit_code == 2
    assert "Cannot parse input AAF" in result.output


def test_slug_and_collision_helpers(tmp_path: Path) -> None:
    assert slugify("  Scene 12 / VFX!") == "scene-12-vfx"
    assert slugify("...") == "report"
    assert report_stem("scene-12-vfx") == "scene-12-vfx-report"
    assert report_stem("report") == "report"

    first = next_available_path(tmp_path, "example-report", ".json")
    first.write_text("{}", encoding="utf-8")
    second = next_available_path(tmp_path, "example-report", ".json")

    assert first.name == "example-report.json"
    assert second.name == "example-report-01.json"

    paired_json, paired_html = next_available_report_paths(tmp_path, "paired-report")
    paired_html.write_text("<!doctype html>", encoding="utf-8")
    numbered_json, numbered_html = next_available_report_paths(tmp_path, "paired-report")

    assert paired_json.name == "paired-report.json"
    assert paired_html.name == "paired-report.html"
    assert numbered_json.name == "paired-report-01.json"
    assert numbered_html.name == "paired-report-01.html"
