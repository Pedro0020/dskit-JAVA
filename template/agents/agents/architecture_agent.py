"""
agents.agents.architecture_agent — Dueño de los tests ArchUnit (solo language=java).

La regla que en producción decide si una arquitectura se mantiene o se pudre
es el límite de capas: un controller no debe inyectar repositories
directamente. El agente lo verifica de dos formas: estáticamente (imports) y
ejecutando los tests ArchUnit del template (src/test/java/**/*Architecture*Test.java).
"""

from __future__ import annotations

import os
import re

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent


@register_agent
class ArchitectureAgent(BaseAgent):
    name = "architecture"
    description = (
        "Dueño de la arquitectura (ArchUnit) y de la memoria estructural: límites de capas, "
        "dependencias entre módulos, ciclos y el vault determinista (IA_index, dominios, grafo)."
    )
    capabilities = [
        "arquitectura", "archunit", "capas", "ciclos",
        "limite de capas", "layers", "controller", "repository",
        "memoria estructural", "grafo de dependencias",
    ]

    def action_aliases(self) -> dict:
        return {
            "check_layers": ["capas", "limite de capas", "dependencias entre capas"],
            "check_archunit_test": ["archunit", "test de arquitectura", "verifica archunit"],
            "run_architecture_tests": ["ejecuta los tests de arquitectura", "corre archunit"],
            "build_vault": ["vault", "memoria estructural", "grafo de dependencias", "regenera la memoria"],
            "enrich_graphify": ["graphify", "capa semantica", "enriquece el grafo"],
        }

    def actions(self) -> dict:
        return {
            "check_layers": self.check_layers,
            "check_archunit_test": self.check_archunit_test,
            "run_architecture_tests": self.run_architecture_tests,
            "build_vault": self.build_vault,
            "enrich_graphify": self.enrich_graphify,
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

    # -- memoria estructural (JAVA-016) ---------------------------------------
    def build_vault(self) -> AgentResult:
        """
        Regenera el vault determinista (`docs/vault/`) desde el código:
        IA_index, arquitectura, fichas de dominio y grafo de dependencias.
        Sin LLM ni red — el grafo estructural es un hecho auditable.
        """
        guard = self._require_java("build_vault")
        if guard is not None:
            return guard

        from agents.contracts import contract_for
        from agents.core.registry import agent_registry
        from agents.tools.structure_tool import StructureTool

        agent_registry.discover()
        fichas = []
        for nombre in sorted(agent_registry.all()):
            contrato = contract_for(nombre)
            if contrato is not None:
                fichas.append((nombre, contrato.role))

        resultado = StructureTool.build_vault(
            self.ctx.root,
            project_name=self.ctx.config.project_name,
            framework=str(self.ctx.config.extra.get("framework", "spring-boot")),
            db=str(self.ctx.config.extra.get("db", "h2")),
            contracts=fichas,
        )
        return AgentResult(
            True, self.name, "build_vault",
            f"Vault regenerado: {len(resultado['files'])} fichero(s), "
            f"{resultado['nodes']} clase(s), {resultado['edges']} arista(s).",
            data=resultado,
            warnings=[
                f"{resultado['violations']} violación(es) de capas documentadas — ver 01_PROYECTO/arquitectura.md"
            ] if resultado["violations"] else [],
        )

    def enrich_graphify(self) -> AgentResult:
        """
        Capa semántica opcional (use_graphify=true): instala `graphifyy[gemini]`
        en un venv del workspace y construye el grafo LLM sobre el mismo vault.

        Requiere GEMINI_API_KEY. No es parte del núcleo: el gate y la memoria
        estructural no dependen de un LLM ni de la red.
        """
        guard = self._require_java("enrich_graphify")
        if guard is not None:
            return guard

        if not bool(self.ctx.config.extra.get("use_graphify", False)):
            return AgentResult(
                False, self.name, "enrich_graphify",
                "use_graphify=false — la capa semántica es opt-in. Regenera el proyecto con "
                "use_graphify=true (o usa solo `build_vault`, que no necesita llaves).",
            )
        if not os.environ.get("GEMINI_API_KEY"):
            return AgentResult(
                False, self.name, "enrich_graphify",
                "Falta GEMINI_API_KEY — graphify usa Gemini para la extracción semántica. "
                "Añádela a .env (ver .env.example) y vuelve a intentarlo.",
                needs=["GEMINI_API_KEY en el entorno"],
            )

        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.graphify_tool import GraphifyTool
        from agents.tools.process_tool import run_command

        venv = self.ctx.agent_workspace("graphify") / "venv"
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        try:
            if not python.exists():
                run_command(["uv", "venv", str(venv)], cwd=self.ctx.root, timeout=300)
                run_command(
                    ["uv", "pip", "install", "--python", str(python), "graphifyy[gemini]"],
                    cwd=self.ctx.root, timeout=900,
                )
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "enrich_graphify", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "enrich_graphify", str(exc))

        marker = GraphifyTool.out_dir(self.ctx.root) / ".graphify_python"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(python), encoding="utf-8")

        try:
            built = GraphifyTool.build(self.ctx.root, timeout=1800)
        except Exception as exc:  # noqa: BLE001 — un fallo de graphify es el resultado a reportar
            return AgentResult(False, self.name, "enrich_graphify", f"graphify build falló: {exc}")

        if built.returncode != 0:
            return AgentResult(
                False, self.name, "enrich_graphify",
                f"graphify build falló (rc={built.returncode}).",
                data={"stderr": built.stderr[-1500:]},
            )

        vault = self.ctx.root / "docs" / "vault"
        exported = GraphifyTool.export_obsidian(self.ctx.root, vault, timeout=600)
        return AgentResult(
            True, self.name, "enrich_graphify",
            "Grafo semántico construido y exportado al vault (capa opcional).",
            data={"graph_json": str(GraphifyTool.graph_json(self.ctx.root)),
                  "obsidian_rc": exported.returncode},
            warnings=[] if exported.returncode == 0 else [
                "graphify export obsidian falló; el grafo JSON sí se generó."
            ],
        )
