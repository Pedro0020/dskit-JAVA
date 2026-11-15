"""
agents.agents.test_agent — Ejecuta la suite de tests y resume resultados/cobertura.

Python (language=python): pytest + pytest-cov (reportes en
`agents/workspace/test/`).
Java (language=java): `./mvnw test` + surefire + JaCoCo. Los reportes de
Maven viven en `target/` (directorio de build, gitignored), así que el
workspace solo se usa como fallback para copias intermedias.

Los artefactos de trabajo no van en la raíz del proyecto (a diferencia de
CHANGELOG.md o el workflow de CI, que sí tienen que vivir en una ruta fija
para funcionar).
"""

from __future__ import annotations

from pathlib import Path

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent
from agents.exceptions import MissingDependencyError, ToolExecutionError
from agents.tools.pytest_tool import PytestTool


{% raw %}_TEST_SKELETON = '''"""
Tests para {module_path}.
"""
import pytest
{imports}

{class_def}
    """Test básico para {module_name}."""

    def test_{module_name}_exists(self):
        """Verifica que el módulo se pueda importar."""
        try:
            {import_call}
        except ImportError as exc:
            pytest.fail(f"No se pudo importar: {{exc}}")

    def test_{module_name}_smoke(self, tmp_path):
        """Test de humo — verifica que las funciones principales existan."""
        pass
'''{% endraw %}

{% raw %}_JAVA_TEST_SKELETON = '''package {package};

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class {class_name}Test {{
    @Test
    void contextLoads() {{
        assertNotNull("{class_name}");
    }}
}}
'''{% endraw %}


@register_agent
class TestAgent(BaseAgent):
    __test__ = False  # pytest recolecta por defecto clases 'Test*' — esta no lo es, es un agente.

    name = "test"
    description = (
        "Ejecuta la suite de tests (pytest en Python, ./mvnw test en Java), "
        "resume fallos y cobertura, detecta módulos sin test y genera esqueletos."
    )
    capabilities = ["test", "tests", "pytest", "cobertura", "coverage", "corre los tests", "generar test", "junit", "mvnw"]

    def action_aliases(self) -> dict:
        return {
            "run_smoke_tests": ["smoke", "humo", "tests marcados"],
            "coverage_report": ["cobertura", "coverage"],
            "list_untested_modules": ["sin probar", "sin test", "modulos sin cubrir"],
            "generate_test_skeletons": ["generar test", "crear test", "esqueleto", "skeleton"],
        }

    def actions(self) -> dict:
        return {
            "run_tests": self.run_tests,
            "run_smoke_tests": self.run_smoke_tests,
            "coverage_report": self.coverage_report,
            "list_untested_modules": self.list_untested_modules,
            "generate_test_skeletons": self.generate_test_skeletons,
        }

    # ------------------------------------------------------------------ python
    def _run_and_summarize(self, *, markers: str | None) -> AgentResult:
        workdir = self.ctx.agent_workspace("test")
        junit_path = workdir / "junit.xml"

        try:
            process = PytestTool.run(self.ctx.root, junit_xml_path=junit_path, markers=markers)
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "run_tests", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "run_tests", str(exc))

        if not junit_path.exists():
            # pytest puede fallar antes de escribir el XML (error de colección, sintaxis rota, etc.)
            return AgentResult(
                False, self.name, "run_tests",
                "pytest no llegó a generar el reporte JUnit — probablemente un error de colección.",
                data={"stdout": process.stdout[-2000:], "stderr": process.stderr[-2000:]},
            )

        summary = PytestTool.parse_junit_xml(junit_path)
        warnings = [f"{f.classname}::{f.name}: {f.message}" for f in summary.failed_tests]

        return AgentResult(
            summary.failures == 0 and summary.errors == 0, self.name, "run_tests",
            f"{summary.passed}/{summary.total} pasaron, {summary.failures} fallo(s), "
            f"{summary.errors} error(es), {summary.skipped} omitido(s) en {summary.duration_seconds:.1f}s.",
            data=summary.__dict__, warnings=warnings,
        )

    def _python_coverage_report(self) -> AgentResult:
        module = self.ctx.config.project_slug
        if not module:
            return AgentResult(False, self.name, "coverage_report", "project_slug está vacío — revisa .copier-answers.yml.")

        workdir = self.ctx.agent_workspace("test")
        coverage_path = workdir / "coverage.json"
        try:
            PytestTool.run_with_coverage(self.ctx.root, module=module, coverage_json_path=coverage_path)
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "coverage_report", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "coverage_report", str(exc))

        if not coverage_path.exists():
            return AgentResult(False, self.name, "coverage_report", "No se generó coverage.json — revisa que pytest-cov esté instalado.")

        report = PytestTool.parse_coverage_json(coverage_path)
        low_coverage = {f: pct for f, pct in report["per_file"].items() if pct < 60}
        warnings = [f"{f}: {pct:.0f}% de cobertura" for f, pct in low_coverage.items()]

        return AgentResult(
            True, self.name, "coverage_report",
            f"Cobertura total: {report['total_percent_covered']:.1f}%. {len(low_coverage)} archivo(s) por debajo del 60%.",
            data=report, warnings=warnings,
        )

    # -------------------------------------------------------------------- java
    def _java_run_tests(self, *, groups: str | None) -> AgentResult:
        from agents.tools.maven_tool import MavenTool

        goals = ["test"] if groups is None else ["test", f"-Dgroups={groups}"]
        try:
            process = MavenTool.run(self.ctx.root, goals)
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "run_tests", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "run_tests", str(exc))

        reports_dir = self.ctx.root / "target" / "surefire-reports"
        try:
            summary = MavenTool.parse_surefire_reports(reports_dir)
        except ValueError as exc:
            return AgentResult(
                False, self.name, "run_tests", str(exc),
                data={"stdout": process.stdout[-2000:], "stderr": process.stderr[-2000:]},
            )

        warnings = [f"{f.classname}::{f.name}: {f.message}" for f in summary.failed_tests]
        return AgentResult(
            summary.failures == 0 and summary.errors == 0, self.name, "run_tests",
            f"{summary.passed}/{summary.total} pasaron, {summary.failures} fallo(s), "
            f"{summary.errors} error(es), {summary.skipped} omitido(s) en {summary.duration_seconds:.1f}s.",
            data=summary.__dict__, warnings=warnings,
        )

    def _java_coverage_report(self) -> AgentResult:
        from agents.tools.maven_tool import MavenTool

        # `verify` dispara el check de JaCoCo con el umbral de pom.xml además
        # de generar el CSV — una puerta de cobertura real, no solo un informe.
        try:
            MavenTool.run(self.ctx.root, ["jacoco:report"])
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "coverage_report", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "coverage_report", str(exc))

        csv_path = self.ctx.root / "target" / "site" / "jacoco" / "jacoco.csv"
        if not csv_path.exists():
            return AgentResult(False, self.name, "coverage_report", "No se generó jacoco.csv — ejecuta primero './mvnw test'.")

        report = MavenTool.parse_jacoco_csv(csv_path)
        low_coverage = {f: pct for f, pct in report["per_file"].items() if pct < 60}
        warnings = [f"{f}: {pct:.0f}% de cobertura" for f, pct in low_coverage.items()]
        total = report["total_percent_covered"]
        return AgentResult(
            True, self.name, "coverage_report",
            f"Cobertura total: {total if total is not None else 'n/d'}%. {len(low_coverage)} clase(s) por debajo del 60%.",
            data=report, warnings=warnings,
        )

    def _java_untested(self) -> AgentResult:
        src_dir, test_dir = self.ctx.java_src_dir, self.ctx.java_test_dir
        if not src_dir.exists():
            return AgentResult(False, self.name, "list_untested_modules", f"No existe '{src_dir.relative_to(self.ctx.root)}'.")

        classes = {p.stem for p in src_dir.rglob("*.java")}
        test_stems = {
            p.stem.removesuffix("Test").removesuffix("Tests")
            for p in test_dir.rglob("*.java")
        } if test_dir.exists() else set()

        untested = sorted(classes - test_stems)
        return AgentResult(
            True, self.name, "list_untested_modules",
            f"{len(untested)} de {len(classes)} clase(s) sin test homónimo aparente.",
            data=untested,
            warnings=["Heurística por nombre de archivo, no mide cobertura real — ver docstring del método."] if untested else [],
        )

    def _java_skeletons(self, *, dry_run: bool = False) -> AgentResult:
        result = self._java_untested()
        untested: list[str] = result.data or []
        if not untested:
            return AgentResult(True, self.name, "generate_test_skeletons", "Todas las clases tienen test aparente.", data=[])

        if not self.ctx.java_test_dir.exists():
            self.ctx.java_test_dir.mkdir(parents=True)

        created: list[str] = []
        for class_name in untested:
            # Espeja el paquete: el test va en src/test/java/<mismo paquete>/.
            matches = list(self.ctx.java_src_dir.rglob(f"{class_name}.java"))
            package = str(self.ctx.config.extra.get("base_package", ""))
            if matches:
                src_file = matches[0]
                package = ".".join(src_file.relative_to(self.ctx.java_src_dir).parts[:-1])
            test_path = self.ctx.java_test_dir / Path(package.replace(".", "/")) / f"{class_name}Test.java"
            if test_path.exists():
                continue

            content = _JAVA_TEST_SKELETON.format(package=package, class_name=class_name)
            if not dry_run:
                test_path.parent.mkdir(parents=True, exist_ok=True)
                test_path.write_text(content, encoding="utf-8")
                created.append(str(test_path.relative_to(self.ctx.root)))

        dry_msg = " [dry-run]" if dry_run else ""
        return AgentResult(
            True, self.name, "generate_test_skeletons",
            f"{len(created)}/{len(untested)} esqueleto(s) de test creado(s).{dry_msg}",
            data={"created": created, "untested": untested, "dry_run": dry_run},
            warnings=[] if created else [f"No se creó ningún test (dry_run={dry_run}). Usa dry_run=False para generarlos."],
        )

    # ----------------------------------------------------------------- público
    def run_tests(self) -> AgentResult:
        if self.ctx.is_java:
            return self._java_run_tests(groups=None)
        return self._run_and_summarize(markers=None)

    def run_smoke_tests(self) -> AgentResult:
        """Python: tests @pytest.mark.smoke. Java: tests con @Tag("smoke") (surefire -Dgroups)."""
        if self.ctx.is_java:
            return self._java_run_tests(groups="smoke")
        return self._run_and_summarize(markers="smoke")

    def coverage_report(self) -> AgentResult:
        if self.ctx.is_java:
            return self._java_coverage_report()
        return self._python_coverage_report()

    def list_untested_modules(self) -> AgentResult:
        """
        Heurística de convención de nombres: una clase `Foo` se considera "con
        test" si existe `FooTest.java`/`FooTests.java` (Java) o
        `tests/test_foo.py` (Python). No mide cobertura real (usa
        `coverage_report` para eso) — es una señal rápida, no un veredicto.
        """
        if self.ctx.is_java:
            return self._java_untested()

        package_dir = self.ctx.package_dir
        if not package_dir.exists():
            return AgentResult(False, self.name, "list_untested_modules", f"No existe '{package_dir}'.")

        module_stems = {
            p.stem for p in package_dir.rglob("*.py")
            if p.stem != "__init__" and "__pycache__" not in p.parts
        }
        test_stems = {
            p.stem.removeprefix("test_") for p in self.ctx.tests_dir.rglob("test_*.py")
        } if self.ctx.tests_dir.exists() else set()

        untested = sorted(module_stems - test_stems)
        return AgentResult(
            True, self.name, "list_untested_modules",
            f"{len(untested)} de {len(module_stems)} módulo(s) sin test homónimo aparente.",
            data=untested,
            warnings=["Heurística por nombre de archivo, no mide cobertura real — ver docstring del método."] if untested else [],
        )

    def generate_test_skeletons(self, *, dry_run: bool = False) -> AgentResult:
        """
        Genera esqueletos de test para módulos/clases sin test aparente.

        Python: `tests/test_<modulo>.py` por módulo sin homónimo. Java:
        `src/test/java/<paquete>/<Clase>Test.java` espejando el paquete.
        """
        if self.ctx.is_java:
            return self._java_skeletons(dry_run=dry_run)

        result = self.list_untested_modules()
        untested: list[str] = result.data or []
        if not untested:
            return AgentResult(True, self.name, "generate_test_skeletons", "Todos los módulos tienen test aparente.", data=[])

        if not self.ctx.tests_dir.exists():
            self.ctx.tests_dir.mkdir(parents=True)

        created: list[str] = []
        for module_stem in untested:
            test_path = self.ctx.tests_dir / f"test_{module_stem}.py"
            if test_path.exists():
                continue

            module_path = f"{self.ctx.config.project_slug}.{module_stem}"
            module_name = module_stem.replace("_", " ").title().replace(" ", "")

            content = _TEST_SKELETON.format(
                module_path=module_path,
                imports=f"from {module_path} import ...",
                class_def=f"class Test{module_name}:",
                module_name=module_name,
                import_call=f"import {module_path}",
            )

            if not dry_run:
                test_path.write_text(content, encoding="utf-8")
                created.append(str(test_path.relative_to(self.ctx.root)))

        dry_msg = " [dry-run]" if dry_run else ""
        return AgentResult(
            True, self.name, "generate_test_skeletons",
            f"{len(created)}/{len(untested)} esqueleto(s) de test creado(s).{dry_msg}",
            data={"created": created, "untested": untested, "dry_run": dry_run},
            warnings=[] if created else [f"No se creó ningún test (dry_run={dry_run}). Usa dry_run=False para generarlos."],
        )
