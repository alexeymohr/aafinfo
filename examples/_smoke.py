from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from aafinfo.models import ReportModel

from _generate import FIXTURE_NAMES, generate_all


def main() -> None:
    """Run the installed CLI against all generated fixtures."""
    cli_path = _cli_path()
    with tempfile.TemporaryDirectory(prefix="aafinfo-smoke-") as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        fixtures = generate_all(temp_dir / "fixtures")
        output_dir = temp_dir / "reports"

        for name in FIXTURE_NAMES:
            fixture = fixtures[name]
            result = subprocess.run(
                [str(cli_path), str(fixture), "--out", str(output_dir)],
                check=False,
                capture_output=True,
                text=True,
            )
            _assert_success(result, fixture)
            json_path, html_path = _output_paths(result.stdout, fixture)
            _assert_artifacts(json_path, html_path, fixture)
            print(f"ok {fixture.name}")


def _cli_path() -> Path:
    candidate = Path(sys.executable).with_name("aafinfo")
    if candidate.exists():
        return candidate

    resolved = shutil.which("aafinfo")
    if resolved is not None:
        return Path(resolved)

    raise RuntimeError("Cannot find aafinfo CLI on PATH.")


def _assert_success(result: subprocess.CompletedProcess[str], fixture: Path) -> None:
    if result.returncode == 0:
        return
    raise RuntimeError(
        f"aafinfo failed for {fixture} with exit code {result.returncode}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def _output_paths(stdout: str, fixture: Path) -> tuple[Path, Path]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if len(lines) != 2:
        raise RuntimeError(f"Expected two output paths for {fixture}, got: {stdout!r}")

    json_path = Path(lines[0])
    html_path = Path(lines[1])
    if json_path.suffix != ".json" or html_path.suffix != ".html":
        raise RuntimeError(f"Unexpected artifact suffixes for {fixture}: {lines!r}")
    return json_path, html_path


def _assert_artifacts(json_path: Path, html_path: Path, fixture: Path) -> None:
    if not json_path.exists():
        raise RuntimeError(f"Missing JSON artifact for {fixture}: {json_path}")
    if not html_path.exists():
        raise RuntimeError(f"Missing HTML artifact for {fixture}: {html_path}")

    report = ReportModel.model_validate_json(json_path.read_text(encoding="utf-8"))
    if report.input.basename != fixture.name:
        raise RuntimeError(
            f"JSON basename mismatch for {fixture}: {report.input.basename!r}"
        )

    html = html_path.read_text(encoding="utf-8")
    if fixture.name not in html:
        raise RuntimeError(f"HTML artifact does not name fixture {fixture.name}: {html_path}")
    lowered = html.lower()
    if "<script" in lowered or "<link" in lowered or "@import" in html:
        raise RuntimeError(f"HTML artifact is not self-contained: {html_path}")


if __name__ == "__main__":
    main()
