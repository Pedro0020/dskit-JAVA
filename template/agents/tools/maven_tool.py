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

from agents.exceptions import MissingDependencyError
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
    #: Traducción de los goals que usan los agentes → tareas Gradle. Solo se
    #: cubre lo que el plano de control invoca de verdad; lo demás (PIT,
    #: versions, OWASP, PMD) es Maven-first (JAVA-001b fase 2).
    _GRADLE_MAP: dict[str, list[str]] = {
        "test": ["test"],
        "verify": ["build"],
        "compile": ["compileJava"],
        "clean": ["clean"],
        "validate": ["help"],
        "jacoco:report": ["jacocoTestReport"],
        "javadoc:javadoc": ["javadoc"],
    }

    @staticmethod
    def build_tool(root: Path) -> str:
        """`gradle` si el proyecto usa build.gradle (y no pom.xml); si no, `maven`."""
        if (root / "build.gradle").exists() and not (root / "pom.xml").exists():
            return "gradle"
        return "maven"

    @staticmethod
    def mvnw_path(root: Path) -> Path:
        """Wrapper del build tool del proyecto (mvnw o gradlew)."""
        if MavenTool.build_tool(root) == "gradle":
            return root / ("gradlew.bat" if os.name == "nt" else "gradlew")
        return root / ("mvnw.cmd" if os.name == "nt" else "mvnw")

    @staticmethod
    def surefire_dir(root: Path) -> Path:
        """Directorio de reportes JUnit (surefire en Maven, test-results en Gradle)."""
        if MavenTool.build_tool(root) == "gradle":
            return root / "build" / "test-results" / "test"
        return root / "target" / "surefire-reports"

    @staticmethod
    def jacoco_csv(root: Path) -> Path:
        """CSV de cobertura JaCoCo (misma herramienta, distinta ruta por build tool)."""
        if MavenTool.build_tool(root) == "gradle":
            return root / "build" / "reports" / "jacoco" / "test" / "jacocoTestReport.csv"
        return root / "target" / "site" / "jacoco" / "jacoco.csv"

    @staticmethod
    def pit_reports(root: Path) -> Path:
        if MavenTool.build_tool(root) == "gradle":
            return root / "build" / "reports" / "pitest"
        return root / "target" / "pit-reports"

    @classmethod
    def _translate_gradle(cls, goals: list[str]) -> list[str]:
        if not goals:
            return goals
        head, *rest = goals
        if head == "test":
            translated = ["test"]
            for arg in rest:
                if arg.startswith("-Dtest="):
                    valor = arg.split("=", 1)[1]
                    patron = valor if "*" in valor else f"*{valor}"
                    translated.append(f"--tests={patron}")
                elif arg.startswith("-Dgroups="):
                    translated.append("-Psmoke=true" if arg.endswith("smoke") else "")
                elif arg == "-DfailIfNoTests=false":
                    translated.append("-PfailIfNoTests=false")
            return [a for a in translated if a]
        if head == "spring-boot:run":
            args = [f"--{a[2:]}" for a in rest if a.startswith("-D")]
            return ["bootRun", f"--args={' '.join(args)}"] if args else ["bootRun"]
        if head == "compile" and "-Ptypecheck" in rest:
            raise MissingDependencyError(
                "El typecheck (Error Prone/NullAway) es Maven-first; en Gradle llega en JAVA-001b fase 2."
            )
        if head == "org.pitest:pitest-maven:mutationCoverage":
            raise MissingDependencyError(
                "PIT en Gradle es JAVA-001b fase 2 (plugin info.solidsoft.pitest)."
            )
        if head.startswith(("versions:", "org.owasp:", "org.apache.maven.plugins:")):
            raise MissingDependencyError(
                f"'{head}' es un goal de Maven: no está soportado en proyectos Gradle (JAVA-001b fase 2)."
            )
        return cls._GRADLE_MAP.get(head, [head]) + rest

    @staticmethod
    def run(
        root: Path,
        goals: list[str],
        *,
        timeout: int = 900,
        quiet: bool = False,
    ) -> ProcessResult:
        """
        Ejecuta el wrapper del build tool (`./mvnw` o `./gradlew`) con `goals`.

        En Gradle traduce los goals que el plano de control usa (test, verify,
        compile, jacoco, javadoc, bootRun) y rechaza con mensaje claro los que
        son Maven-first. En Windows, los `.cmd`/`.bat` no los puede lanzar
        CreateProcess directamente — se pasan por `cmd /c`.
        """
        gradle = MavenTool.build_tool(root) == "gradle"
        prefix = [] if gradle else (["-q"] if quiet else [])
        if gradle:
            goals = MavenTool._translate_gradle(goals)

        wrapper = MavenTool.mvnw_path(root)
        if wrapper.exists():
            exe = str(wrapper.resolve())
        elif shutil.which("mvn" if not gradle else "gradle"):
            exe = shutil.which("mvn" if not gradle else "gradle") or ("mvn" if not gradle else "gradle")
        else:
            raise MissingDependencyError(
                f"Ni el wrapper ({wrapper.name}) ni '{'gradle' if gradle else 'mvn'}' están disponibles — "
                "ejecuta 'make setup' o instala el build tool."
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

    @staticmethod
    def parse_pit_summary(path: Path) -> dict:
        """
        Resume `target/pit-reports/<ts>/mutations.xml` de PIT: score, killed,
        survived, timeout y detalle por mutación. PIT cuenta TIMED_OUT como
        detectada (el timeout del test es una detección).
        """
        root = ET.parse(path).getroot()
        detected = killed = survived = timed_out = 0
        detail = []
        for m in root.iter("mutation"):
            if m.get("detected") != "true":
                continue
            detected += 1
            status = m.get("status", "")
            if status == "SURVIVED":
                survived += 1
            else:
                killed += 1
                if status == "TIMED_OUT":
                    timed_out += 1
            detail.append({
                "source": m.findtext("sourceFile") or "?",
                "line": m.findtext("lineNumber") or "?",
                "status": status,
                "mutator": m.findtext("mutator") or "?",
            })
        score = round(100.0 * killed / detected, 1) if detected else 0.0
        return {
            "total": detected,
            "killed": killed,
            "survived": survived,
            "timeout": timed_out,
            "score": score,
            "detail": detail,
        }
