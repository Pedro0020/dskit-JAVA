"""
agents.agents.architecture_agent — Dueño de los tests ArchUnit (solo language=java).

La regla que en producción decide si una arquitectura se mantiene o se pudre
es el límite de capas: un controller no debe inyectar repositories
directamente. El agente lo verifica de dos formas: estáticamente (imports) y
ejecutando los tests ArchUnit del template (src/test/java/**/*Architecture*Test.java).
"""

from __future__ import annotations

import re

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent


@register_agent
class ArchitectureAgent(BaseAgent):
    name = "architecture"
    description = (
        "Dueño de la arquitectura (ArchUnit): límites de capas, dependencias entre módulos y ciclos. "
        "Verifica imports estáticamente y ejecuta los tests ArchUnit."
    )
    capabilities = [
        "arquitectura", "archunit", "capas", "ciclos",
        "limite de capas", "layers", "controller", "repository",
    ]

    def action_aliases(self) -> dict:
        return {
            "check_layers": ["capas", "limite de capas", "dependencias entre capas"],
            "check_archunit_test": ["archunit", "test de arquitectura", "verifica archunit"],
            "run_architecture_tests": ["ejecuta los tests de arquitectura", "corre archunit"],
        }

    def actions(self) -> dict:
        return {
            "check_layers": self.check_layers,
            "check_archunit_test": self.check_archunit_test,
            "run_architecture_tests": self.run_architecture_tests,
        }

    def _require_java(self, action: str) -> AgentResult | None:
        if self.ctx.is_java:
            return None
        return AgentResult(
            False, self.name, action,
            "El dominio architecture (ArchUnit) solo existe en proyectos Java (language=java).",
        )

    def _layer_of(self, path) -> str:
        parts = set(path.parts)
        for capa in ("controller", "service", "repository", "domain", "config", "batch"):
            if capa in parts:
                return capa
        return "other"

    def check_layers(self) -> AgentResult:
        """
        Regla de capas estática: controller → repository directo (sin pasar por
        service) es la violación canónica. Se detecta por el import.
        """
        guard = self._require_java("check_layers")
        if guard is not None:
            return guard

        violaciones = []
        if self.ctx.java_src_dir.exists():
            for java in self.ctx.java_src_dir.rglob("*.java"):
                if "controller" not in java.parts:
                    continue
                texto = java.read_text(encoding="utf-8", errors="replace")
                for import_line in re.findall(r"^import\s+([\w.]+\.repository\.[\w.]+);", texto, re.MULTILINE):
                    violaciones.append({
                        "file": str(java.relative_to(self.ctx.root)),
                        "import": import_line,
                        "message": "controller importa repository directamente — la capa service es el único camino.",
                    })
        warnings = [f"{v['file']}: {v['message']} ({v['import']})" for v in violaciones]
        return AgentResult(
            not violaciones, self.name, "check_layers",
            f"{len(violaciones)} violación(es) de capas (controller→repository).",
            data={"violations": violaciones}, warnings=warnings,
        )

    def check_archunit_test(self) -> AgentResult:
        """Verifica que existe un test ArchUnit en src/test/java (extra use_archunit)."""
        guard = self._require_java("check_archunit_test")
        if guard is not None:
            return guard

        use_archunit = bool(self.ctx.config.extra.get("use_archunit", False))
        tests = []
        if self.ctx.java_test_dir.exists():
            tests = list(self.ctx.java_test_dir.rglob("*Architecture*Test.java"))
        if tests:
            return AgentResult(
                True, self.name, "check_archunit_test",
                f"{len(tests)} test(s) ArchUnit encontrado(s).",
                data=[str(t.relative_to(self.ctx.root)) for t in tests],
            )
        if not use_archunit:
            return AgentResult(
                True, self.name, "check_archunit_test",
                "use_archunit=false — no se exige test de arquitectura.",
                data=[],
            )
        return AgentResult(
            False, self.name, "check_archunit_test",
            "use_archunit=true pero no hay *Architecture*Test.java en src/test/java.",
            warnings=["Genera el test ArchUnit (o regenéralo con test_agent: las clases del template incluyen el esqueleto)."],
        )

    def run_architecture_tests(self) -> AgentResult:
        """Ejecuta los tests ArchUnit (`./mvnw test -Dtest=*Architecture*Test`)."""
        guard = self._require_java("run_architecture_tests")
        if guard is not None:
            return guard

        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.maven_tool import MavenTool

        try:
            result = MavenTool.run(self.ctx.root, ["test", "-Dtest=*Architecture*Test"], timeout=900)
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "run_architecture_tests", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "run_architecture_tests", str(exc))

        if result.ok:
            return AgentResult(True, self.name, "run_architecture_tests", "Tests ArchUnit en verde: las capas se respetan.")
        return AgentResult(
            False, self.name, "run_architecture_tests",
            "Los tests ArchUnit fallan: hay una dependencia que viola los límites.",
            data={"stderr": result.stderr[-1500:]},
        )
