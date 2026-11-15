"""
agents.tools.maven_tool — Ejecuta el wrapper Maven y parsea sus reportes.

Los formatos están verificados generándolos de verdad antes de escribir este
módulo (no son una suposición sobre la documentación):
- Surefire (`target/surefire-reports/TEST-*.xml`): `<testsuite tests= errors=
  skipped= failures= time= name=>` con `<testcase classname= name=>` y un
  hijo `<failure>`/`<error>` por caso roto.
- JaCoCo CSV (`target/site/jacoco/jacoco.csv`): cabecera
  `GROUP,PACKAGE,CLASS,INSTRUCTION_MISSED,...,LINE_MISSED,LINE_COVERED`.

Solo usa la stdlib: el build lo hace Maven, el plano de control Python solo
lo invoca y resume.
"""

from __future__ import annotations

import os
import shutil
import csv
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from agents.tools.process_tool import ProcessResult, run_command
from agents.tools.registry import register_tool


@dataclass
class TestFailure:
    classname: str
    name: str
    message: str


@dataclass
class TestRunSummary:
    total: int
    failures: int
    errors: int
    skipped: int
    passed: int
    duration_seconds: float
    failed_tests: list[TestFailure] = field(default_factory=list)


@register_tool("maven")
class MavenTool:
    @staticmethod
    def mvnw_path(root: Path) -> Path:
        """Wrapper de Maven del proyecto (`mvnw` o `mvnw.cmd` en Windows)."""
        return root / ("mvnw.cmd" if os.name == "nt" else "mvnw")

    @staticmethod
    def run(
        root: Path,
        goals: list[str],
        *,
        timeout: int = 900,
        quiet: bool = False,
    ) -> ProcessResult:
        """
        Ejecuta `./mvnw <goals>` en `root` (o `mvn` del sistema si no hay
        wrapper). El wrapper es un script versionado en el repo; se invoca por
        ruta absoluta (run_command valida el binario con `which`, que no
        resuelve rutas relativas). En Windows, los `.cmd`/`.bat` no los puede
        lanzar CreateProcess directamente — se pasan por `cmd /c`, igual que
        el usuario lo haría a mano.
        """
        from agents.exceptions import MissingDependencyError

        prefix = ["-q"] if quiet else []
        mvnw = MavenTool.mvnw_path(root)
        if mvnw.exists():
            exe = str(mvnw.resolve())
        elif shutil.which("mvn"):
            exe = shutil.which("mvn") or "mvn"
        else:
            raise MissingDependencyError(
                "Ni el wrapper Maven (./mvnw) ni 'mvn' están disponibles — "
                "ejecuta 'make setup' o instala Maven."
            )
        args = [exe, *prefix, *goals]
        if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
            args = ["cmd", "/c", *args]
        return run_command(args, cwd=root, timeout=timeout)

    @staticmethod
    def parse_surefire_reports(reports_dir: Path) -> TestRunSummary:
        """
        Suma todos los `TEST-*.xml` de `target/surefire-reports/`.
        Lanza ValueError si no hay ningún reporte (Maven ni llegó a ejecutar
        tests — p. ej. error de compilación).
        """
        files = sorted(reports_dir.glob("TEST-*.xml"))
        if not files:
            raise ValueError(
                f"'{reports_dir}' no contiene reportes surefire (TEST-*.xml) — "
                "el build falló antes de ejecutar los tests."
            )

        total = failures = errors = skipped = 0
        duration = 0.0
        failed_tests: list[TestFailure] = []
        for path in files:
            suite = ET.parse(path).getroot()
            total += int(suite.get("tests", 0))
            failures += int(suite.get("failures", 0))
            errors += int(suite.get("errors", 0))
            skipped += int(suite.get("skipped", 0))
            duration += float(suite.get("time", 0.0))
            for testcase in suite.findall("testcase"):
                failure = testcase.find("failure")
                error = testcase.find("error")
                node = failure if failure is not None else error
                if node is not None:
                    failed_tests.append(TestFailure(
                        classname=testcase.get("classname", ""),
                        name=testcase.get("name", ""),
                        message=(node.get("message") or "").strip()[:500],
                    ))

        return TestRunSummary(
            total=total, failures=failures, errors=errors, skipped=skipped,
            passed=total - failures - errors - skipped,
            duration_seconds=duration, failed_tests=failed_tests,
        )

    @staticmethod
    def parse_jacoco_csv(path: Path) -> dict:
        """
        Cobertura por clase desde `target/site/jacoco/jacoco.csv`.
        Devuelve {"total_percent_covered": float|None, "per_file": {clase: pct}}.
        """
        per_file: dict[str, float] = {}
        covered_total = missed_total = 0
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                cls = row.get("CLASS", "")
                if not cls:
                    continue
                line_missed = int(row.get("LINE_MISSED", 0))
                line_covered = int(row.get("LINE_COVERED", 0))
                covered_total += line_covered
                missed_total += line_missed
                denom = line_missed + line_covered
                per_file[cls] = round(100.0 * line_covered / denom, 1) if denom else 100.0

        total_lines = covered_total + missed_total
        total = round(100.0 * covered_total / total_lines, 1) if total_lines else None
        return {"total_percent_covered": total, "per_file": per_file}
