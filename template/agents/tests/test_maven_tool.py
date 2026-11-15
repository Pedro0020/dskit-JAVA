from __future__ import annotations

from pathlib import Path

import pytest

from agents.agents.dependency_agent import parse_maven_updates
from agents.tools.maven_tool import MavenTool


def _surefire(tmp_path: Path, *contents: str) -> Path:
    reports = tmp_path / "surefire-reports"
    reports.mkdir()
    for i, content in enumerate(contents):
        (reports / f"TEST-Clase{i}.xml").write_text(content)
    return reports


def test_parse_surefire_all_passing(tmp_path: Path):
    reports = _surefire(
        tmp_path,
        '<testsuite name="Clase0" tests="3" failures="0" errors="0" skipped="0" time="1.5">'
        '<testcase classname="a.Clase0" name="uno"/></testsuite>',
    )
    result = MavenTool.parse_surefire_reports(reports)
    assert result.total == 3
    assert result.passed == 3
    assert result.failures == 0
    assert result.duration_seconds == 1.5


def test_parse_surefire_sums_multiple_files(tmp_path: Path):
    reports = _surefire(
        tmp_path,
        '<testsuite name="A" tests="2" failures="1" errors="0" skipped="0" time="1.0">'
        '<testcase classname="a.A" name="falla"><failure message="AssertionError">x</failure></testcase></testsuite>',
        '<testsuite name="B" tests="1" failures="0" errors="1" skipped="1" time="0.2">'
        '<testcase classname="b.B" name="error"><error message="Exception">y</error></testcase></testsuite>',
    )
    result = MavenTool.parse_surefire_reports(reports)
    assert result.total == 3
    assert result.failures == 1
    assert result.errors == 1
    assert result.skipped == 1
    assert result.passed == 0
    assert len(result.failed_tests) == 2


def test_parse_surefire_no_reports_raises(tmp_path: Path):
    empty = tmp_path / "surefire-reports"
    empty.mkdir()
    with pytest.raises(ValueError, match="surefire"):
        MavenTool.parse_surefire_reports(empty)


def test_parse_jacoco_csv(tmp_path: Path):
    csv_path = tmp_path / "jacoco.csv"
    csv_path.write_text(
        "GROUP,PACKAGE,CLASS,INSTRUCTION_MISSED,INSTRUCTION_COVERED,BRANCH_MISSED,BRANCH_COVERED,"
        "LINE_MISSED,LINE_COVERED,COMPLEXITY_MISSED,COMPLEXITY_COVERED,METHOD_MISSED,METHOD_COVERED\n"
        "g,p,com.ejemplo.Uno,0,10,0,0,2,8,0,0,0,0\n"
        "g,p,com.ejemplo.Dos,10,0,0,0,10,0,0,0,0,0\n",
    )
    report = MavenTool.parse_jacoco_csv(csv_path)
    assert report["per_file"]["com.ejemplo.Uno"] == 80.0
    assert report["per_file"]["com.ejemplo.Dos"] == 0.0
    assert report["total_percent_covered"] == 40.0


def test_parse_jacoco_csv_empty_classes(tmp_path: Path):
    csv_path = tmp_path / "jacoco.csv"
    csv_path.write_text(
        "GROUP,PACKAGE,CLASS,INSTRUCTION_MISSED,INSTRUCTION_COVERED,BRANCH_MISSED,BRANCH_COVERED,"
        "LINE_MISSED,LINE_COVERED,COMPLEXITY_MISSED,COMPLEXITY_COVERED,METHOD_MISSED,METHOD_COVERED\n"
    )
    report = MavenTool.parse_jacoco_csv(csv_path)
    assert report["total_percent_covered"] is None
    assert report["per_file"] == {}


def test_parse_maven_updates_extracts_lines():
    text = (
        "The following dependencies in Dependency Management have newer versions:\n"
        "  com.h2database:h2 ................. 2.2.224 -> 2.3.232\n"
        "  org.flywaydb:flyway-core ......... 10.20.1 -> 11.1.0\n"
        "  [INFO] No dependencies in Dependency Management have newer versions.\n"
    )
    updates = parse_maven_updates(text)
    assert len(updates) == 2
    assert updates[0]["name"] == "com.h2database:h2"
    assert updates[0]["current_version"] == "2.2.224"
    assert updates[0]["latest_version"] == "2.3.232"
    assert all(u["is_outdated"] for u in updates)


def test_parse_maven_updates_no_arrows():
    assert parse_maven_updates("nada que ver\n") == []


def test_parse_pit_summary(tmp_path: Path):
    report = tmp_path / "mutations.xml"
    report.write_text(
        '<mutations>'
        '<mutation detected="true" status="KILLED"><sourceFile>Servicio.java</sourceFile><lineNumber>10</lineNumber><mutator>CONDITIONALS_BOUNDARY</mutator></mutation>'
        '<mutation detected="true" status="SURVIVED"><sourceFile>Servicio.java</sourceFile><lineNumber>12</lineNumber><mutator>INVERT_NEGS</mutator></mutation>'
        '<mutation detected="true" status="TIMED_OUT"><sourceFile>Servicio.java</sourceFile><lineNumber>14</lineNumber><mutator>MATH</mutator></mutation>'
        '<mutation detected="false" status="NO_COVERAGE"><sourceFile>Servicio.java</sourceFile><lineNumber>20</lineNumber><mutator>X</mutator></mutation>'
        '</mutations>'
    )
    summary = MavenTool.parse_pit_summary(report)
    assert summary["total"] == 3
    assert summary["killed"] == 2  # KILLED + TIMED_OUT
    assert summary["survived"] == 1
    assert summary["timeout"] == 1
    assert summary["score"] == 66.7
    assert len(summary["detail"]) == 3
