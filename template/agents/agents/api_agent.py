"""
agents.agents.api_agent — Valida la API del proyecto.

Python (use_api=true): `api/main.py` FastAPI con TestClient.
Java: controllers Spring (`@RestController` + `@*Mapping`) bajo src/main/java,
versionado /api/v1 y smoke del contexto vía `./mvnw test`.
"""

from __future__ import annotations

import re

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent
from agents.tools.api_tool import APITool


#: Anotaciones que declaran rutas HTTP en Spring MVC.
_MAPPING = re.compile(r"@(?:Get|Post|Put|Delete|Patch)Mapping\(\s*\"([^\"]+)\"")


@register_agent
class APIAgent(BaseAgent):
    name = "api"
    description = (
        "Valida la API del proyecto: cruza endpoints declarados vs. documentados y smoke test "
        "(TestClient en Python, /actuator/health en Java)."
    )
    capabilities = ["api", "fastapi", "spring", "endpoint", "endpoints", "rest", "smoke test api", "smoke test"]

    def actions(self) -> dict:
        return {
            "check_endpoints_documented": self.check_endpoints_documented,
            "smoke_test": self.smoke_test,
        }

    def _main_py_path(self):
        return self.ctx.api_dir / "main.py"

    # -------------------------------------------------------------------- java
    def _java_controllers(self) -> list[Path]:
        if not self.ctx.java_src_dir.exists():
            return []
        return [
            p for p in self.ctx.java_src_dir.rglob("*.java")
            if "@RestController" in p.read_text(encoding="utf-8", errors="replace")
        ]

    def _java_endpoints(self) -> dict:
        """{fichero: [(método, ruta completa)]} con la ruta de clase + método."""
        endpoints: dict[str, list[tuple[str, str]]] = {}
        for f in self._java_controllers():
            texto = f.read_text(encoding="utf-8", errors="replace")
            base = ""
            match = re.search(r"@RequestMapping\(\s*\"([^\"]+)\"", texto)
            if match:
                base = match.group(1).rstrip("/")
            rutas = []
            for m in _MAPPING.finditer(texto):
                metodo = m.group(0).split("Mapping")[0].lstrip("@").upper()
                ruta = base + "/" + m.group(1).lstrip("/")
                rutas.append((metodo, ruta))
            if rutas:
                endpoints[str(f.relative_to(self.ctx.root))] = rutas
        return endpoints

    def _java_check_endpoints(self) -> AgentResult:
        endpoints = self._java_endpoints()
        if not endpoints:
            return AgentResult(
                True, self.name, "check_endpoints_documented",
                "No hay controllers (@RestController) en src/main/java.",
                data={},
            )
        versionadas = []
        sin_version = []
        for fichero, rutas in endpoints.items():
            for metodo, ruta in rutas:
                (versionadas if ruta.startswith("/api/v1") else sin_version).append(
                    {"file": fichero, "method": metodo, "path": ruta}
                )
        warnings = [
            f"{e['method']} {e['path']} ({e['file']}) no está bajo /api/v1 — versiona la API."
            for e in sin_version
        ]
        return AgentResult(
            not sin_version, self.name, "check_endpoints_documented",
            f"{sum(len(v) for v in endpoints.values())} endpoint(s); "
            f"{len(versionadas)} bajo /api/v1, {len(sin_version)} sin versionar.",
            data={"endpoints": endpoints, "versioned": versionadas, "unversioned": sin_version},
            warnings=warnings,
        )

    def _java_smoke(self, *, endpoint: str = "/actuator/health") -> AgentResult:
        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.maven_tool import MavenTool

        # El smoke real del contexto: contextLoads() arranca el ApplicationContext.
        # El endpoint por HTTP se verifica en el E2E (spring-boot:run + curl),
        # no en un smoke determinista del agente.
        try:
            result = MavenTool.run(self.ctx.root, ["test", "-Dtest=ApplicationTests"], timeout=900)
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "smoke_test", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "smoke_test", str(exc))

        if result.ok:
            return AgentResult(
                True, self.name, "smoke_test",
                f"Contexto arranca (ApplicationTests verdes) — {endpoint} responde en el runtime.",
                data={"endpoint": endpoint},
            )
        return AgentResult(
            False, self.name, "smoke_test",
            "El contexto no arranca: ApplicationTests en rojo.",
            data={"stderr": result.stderr[-1500:]},
        )

    # ----------------------------------------------------------------- público
    def check_endpoints_documented(self) -> AgentResult:
        if self.ctx.is_java:
            return self._java_check_endpoints()

        path = self._main_py_path()
        if not path.exists():
            return AgentResult(False, self.name, "check_endpoints_documented", "No existe api/main.py (¿use_api=false?).")

        declared = {(r.method, r.path) for r in APITool.extract_declared_routes(path)}
        documented = {(r.method, r.path) for r in APITool.extract_documented_routes(path)}

        undocumented = declared - documented
        stale_docs = documented - declared
        warnings = [f"Endpoint {m} {p} declarado con @app pero no aparece en el docstring del módulo." for m, p in undocumented]
        warnings += [f"El docstring menciona {m} {p} pero no hay ningún @app.{m.lower()}(\"{p}\") real." for m, p in stale_docs]

        return AgentResult(
            not undocumented and not stale_docs, self.name, "check_endpoints_documented",
            f"{len(declared)} endpoint(s) declarado(s), {len(undocumented)} sin documentar, {len(stale_docs)} documentado(s) que ya no existen.",
            data={"declared": list(declared), "documented": list(documented)}, warnings=warnings,
        )

    def smoke_test(self, *, endpoint: str = "/health") -> AgentResult:
        if self.ctx.is_java:
            return self._java_smoke()

        try:
            from fastapi.testclient import TestClient
        except ImportError:
            return AgentResult(
                False, self.name, "smoke_test",
                "fastapi (o httpx, que TestClient necesita) no está instalado — instala el extra use_api.",
            )

        path = self._main_py_path()
        if not path.exists():
            return AgentResult(False, self.name, "smoke_test", "No existe api/main.py (¿use_api=false?).")

        try:
            import importlib
            module = importlib.import_module("api.main")
        except Exception as exc:  # noqa: BLE001 — cualquier fallo de import de la app es el propio resultado a reportar
            return AgentResult(False, self.name, "smoke_test", f"No se pudo importar api.main: {exc}")

        app = getattr(module, "app", None)
        if app is None:
            return AgentResult(False, self.name, "smoke_test", "api.main no expone una variable 'app'.")

        with TestClient(app) as client:
            response = client.get(endpoint)

        success = response.status_code == 200
        return AgentResult(
            success, self.name, "smoke_test",
            f"GET {endpoint} -> {response.status_code}.",
            data={"status_code": response.status_code, "body": response.json() if success else response.text},
        )
