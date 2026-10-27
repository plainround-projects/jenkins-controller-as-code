"""pipeline/scripts/test-summary.sh: totals from JUnit XML, and a failing exit when a test failed."""

from __future__ import annotations

from pathlib import Path

from tests.support.shell import run


def report(directory: Path, name: str, tests: int, failures: int = 0, errors: int = 0, skipped: int = 0) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    header = f'<testsuite name="{name}" tests="{tests}" errors="{errors}" skipped="{skipped}" failures="{failures}">'
    (directory / f"TEST-{name}.xml").write_text(f'<?xml version="1.0"?>\n{header}\n</testsuite>\n')


def summarize(root: Path, *directories: Path) -> tuple[int, str]:
    result = run([str(root / "pipeline/scripts/test-summary.sh"), *map(str, directories)], check=False)
    return result.returncode, result.output


def test_it_adds_up_the_suites_of_each_directory(root: Path, tmp_path: Path) -> None:
    unit, integration = tmp_path / "unit", tmp_path / "it"
    report(unit, "a", 10)
    report(unit, "b", 7, skipped=1)
    report(integration, "c", 5)

    code, output = summarize(root, unit, integration)

    assert code == 0
    assert f"{unit}: 17 tests, 0 failed, 0 errors, 1 skipped" in output
    assert f"{integration}: 5 tests, 0 failed, 0 errors, 0 skipped" in output
    assert "total: 22 tests, 0 failed, 0 errors, 1 skipped" in output


def test_a_failure_or_an_error_makes_it_exit_1(root: Path, tmp_path: Path) -> None:
    unit = tmp_path / "unit"
    report(unit, "a", 10, failures=1)
    report(tmp_path / "other", "b", 3, errors=1)

    assert summarize(root, unit)[0] == 1
    assert summarize(root, tmp_path / "other")[0] == 1


def test_a_directory_without_reports_is_named_and_not_an_error(root: Path, tmp_path: Path) -> None:
    code, output = summarize(root, tmp_path / "empty")

    assert code == 0
    assert "no reports" in output


def test_no_arguments_is_a_usage_error(root: Path) -> None:
    assert summarize(root)[0] == 2
