"""
agents.agents.dependency_agent — Analiza dependencias.

Python: pyproject.toml/uv.lock contra PyPI (OSV).
Java: pom.xml con `versions:display-dependency-updates` y OWASP
dependency-check contra la NVD.

Único agente del sistema (junto con `installer` en su parte de clonado) que
depende de acceso a internet — todos los demás trabajan solo con lo que ya
hay en el proyecto. Si no hay red, cada paquete falla individualmente (ver
`PackageStatus.error`) y el resto del chequeo continúa igual.
"""

from __future__ import annotations

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent
from agents.tools.dependency_tool import DependencyTool, parse_dependency_name, parse_pyproject_dependencies, parse_uv_lock_versions


# Líneas del informe de `versions:display-dependency-updates`, p. ej.:
#   com.h2database:h2 ................. 2.2.224 -> 2.3.232
def parse_maven_updates(text: str) -> list[dict]:
    """Extrae (artifact, versión actual -> disponible) del informe del versions-plugin."""
    updates = []
    for line in text.splitlines():
        if "->" not in line:
            continue
        left, _, right = line.partition("->")
        left = left.strip()
        if not left or not right.strip():
            continue
        # El nombre del artifact es el primer "token" antes de la línea de puntos
        # y la versión actual es el token final de `left`.
        parts = left.split()
        if not parts:
            continue
        artifact = parts[0]
        current = parts[-1]
        if artifact == current:  # sin versión actual visible, p. ej. "foo . 1.0"
            continue
        updates.append({
            "name": artifact,
            "current_version": current,
            "latest_version": right.strip().split()[0],
            "is_outdated": True,
        })
    return updates


@register_agent
class DependencyAgent(BaseAgent):
    name = "dependency"
    description = (
        "Detecta versiones de dependencias desactualizadas (PyPI en Python, Maven Central en "
        "Java) y vulnerabilidades conocidas (OSV / OWASP dependency-check). Necesita acceso a internet."
    )
    capabilities = [
        "dependencias", "paquetes obsoletos", "versiones desactualizadas", "vulnerabilidad",
        "pypi", "maven", "owasp", "actualizar dependencias",
    ]

    def action_aliases(self) -> dict:
        return {
            "check_outdated": ["revisa", "desactualizadas", "obsoletas", "actualizar"],
            "check_vulnerabilities": ["vulnerabilidad", "vulnerabilidades", "seguridad"],
            "check_lock_sync": ["sincronizado", "sincronia", "lock"],
        }

    def actions(self) -> dict:
        return {
            "check_outdated": self.check_outdated,
            "check_vulnerabilities": self.check_vulnerabilities,
            "check_lock_sync": self.check_lock_sync,
        }

    def _declared_dependencies(self) -> list[str] | None:
        if not self.ctx.pyproject_file.exists():
            return None
        return parse_pyproject_dependencies(self.ctx.pyproject_file.read_text(encoding="utf-8"))

    def _locked_versions(self) -> dict[str, str]:
        lock_path = self.ctx.root / "uv.lock"
        if not lock_path.exists():
            return {}
        return parse_uv_lock_versions(lock_path.read_text(encoding="utf-8"))

    # -------------------------------------------------------------------- java
    def _java_check_outdated(self, *, include_cadence: bool = False) -> AgentResult:
        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.maven_tool import MavenTool

        if not self.ctx.pom_file.exists():
            return AgentResult(False, self.name, "check_outdated", "No existe pom.xml en la raíz del proyecto.")
        try:
            result = MavenTool.run(
                self.ctx.root,
                ["versions:display-dependency-updates", "-DprocessDependencyManagement=false"],
                timeout=600,
            )
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "check_outdated", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "check_outdated", str(exc))

        if not result.ok:
            return AgentResult(
                False, self.name, "check_outdated",
                f"versions:display-dependency-updates falló (rc={result.returncode}).",
                data={"stderr": result.stderr[-1000:]},
            )

        results = parse_maven_updates(result.stdout)
        return AgentResult(
            True, self.name, "check_outdated",
            f"{len(results)} dependencia(s) con versión más nueva disponible en Maven Central.",
            data=results,
        )

    def _java_check_vulnerabilities(self) -> AgentResult:
        import json

        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.maven_tool import MavenTool

        if not self.ctx.pom_file.exists():
            return AgentResult(False, self.name, "check_vulnerabilities", "No existe pom.xml en la raíz del proyecto.")
        try:
            result = MavenTool.run(
                self.ctx.root,
                [
                    "org.owasp:dependency-check-maven:12.1.0:check",
                    "-DfailBuildOnCVSS=0",
                    "-Dformat=JSON",
                    "-DskipTestScope=true",
                ],
                timeout=1800,
            )
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "check_vulnerabilities", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "check_vulnerabilities", str(exc))

        report_path = self.ctx.root / "target" / "dependency-check-report.json"
        if not report_path.exists():
            return AgentResult(
                False, self.name, "check_vulnerabilities",
                "OWASP dependency-check no generó informe (rc=%s) — la NVD puede tardar la primera vez."
                % result.returncode,
                data={"stderr": result.stderr[-1000:]},
            )

        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AgentResult(False, self.name, "check_vulnerabilities", "No se pudo leer dependency-check-report.json.")

        findings = [
            {
                "name": dep.get("fileName", "?"),
                "version": dep.get("version", "?"),
                "vulnerabilities": [
                    {"id": v.get("name", "?"), "severity": v.get("severity", "?")}
                    for v in dep.get("vulnerabilities", [])
                ],
            }
            for dep in report.get("dependencies", [])
            if dep.get("vulnerabilities")
        ]
        return AgentResult(
            True, self.name, "check_vulnerabilities",
            f"{len(findings)} dependencia(s) con vulnerabilidades conocidas según la NVD.",
            data=findings,
        )

    def _java_check_lock_sync(self) -> AgentResult:
        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.maven_tool import MavenTool

        # Maven no tiene lock file: la "sincronía" equivalente es que el modelo
        # del POM sea válido y resuelva (validate + effective-pom sin errores).
        try:
            result = MavenTool.run(self.ctx.root, ["validate"], quiet=True)
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "check_lock_sync", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "check_lock_sync", str(exc))

        if result.ok:
            return AgentResult(
                True, self.name, "check_lock_sync",
                "pom.xml válido — Maven no usa lock file; la convergencia de versiones la vigila el enforcer/versions-plugin.",
            )
        return AgentResult(
            False, self.name, "check_lock_sync",
            "pom.xml no pasa el validate de Maven.",
            data={"stderr": result.stderr[-1000:]},
        )

    # ----------------------------------------------------------------- público
    def check_outdated(self, *, include_cadence: bool = False) -> AgentResult:
        """
        Python: compara uv.lock contra PyPI. Java: `versions:display-dependency-updates`
        contra Maven Central.

        `include_cadence` solo aplica a Python (estimación de cadencia de releases).
        """
        if self.ctx.is_java:
            return self._java_check_outdated()

        specs = self._declared_dependencies()
        if specs is None:
            return AgentResult(False, self.name, "check_outdated", "No existe pyproject.toml en la raíz del proyecto.")
        if not specs:
            return AgentResult(True, self.name, "check_outdated", "No hay dependencias declaradas en [project.dependencies].", data=[])

        locked = self._locked_versions()
        results = []
        warnings = []
        for spec in specs:
            status = DependencyTool.check_package(
                spec, locked_version=locked.get(parse_dependency_name(spec)),
                include_vulnerabilities=False, include_cadence=include_cadence,
            )
            results.append(status.__dict__)
            if status.error:
                warnings.append(f"{status.name}: {status.error}")

        if not locked:
            warnings.append(
                "No se encontró uv.lock — sin él, 'is_outdated' compara la versión declarada en pyproject.toml "
                "de forma poco fiable (a menudo sin pin exacto). Ejecuta 'uv lock' para un chequeo preciso."
            )

        n_outdated = sum(1 for r in results if r["is_outdated"] is True)
        return AgentResult(
            True, self.name, "check_outdated",
            f"{len(results)} dependencia(s) revisada(s), {n_outdated} desactualizada(s) (según lo que se pudo determinar).",
            data=results, warnings=warnings,
        )

    def check_vulnerabilities(self) -> AgentResult:
        """Python: OSV vía PyPI. Java: OWASP dependency-check contra la NVD."""
        if self.ctx.is_java:
            return self._java_check_vulnerabilities()

        specs = self._declared_dependencies()
        if specs is None:
            return AgentResult(False, self.name, "check_vulnerabilities", "No existe pyproject.toml en la raíz del proyecto.")

        locked = self._locked_versions()
        if not locked:
            return AgentResult(
                False, self.name, "check_vulnerabilities",
                "No se encontró uv.lock — sin la versión exacta instalada no se puede consultar "
                "vulnerabilidades de forma fiable. Ejecuta 'uv lock' primero.",
            )

        findings = []
        warnings = []
        for spec in specs:
            name = parse_dependency_name(spec)
            version = locked.get(name)
            if not version:
                warnings.append(f"'{name}' no aparece en uv.lock con una versión exacta — omitido.")
                continue
            vulns = DependencyTool.fetch_vulnerabilities(name, version)
            if vulns:
                findings.append({"name": name, "version": version, "vulnerabilities": vulns})

        return AgentResult(
            True, self.name, "check_vulnerabilities",
            f"{len(findings)} paquete(s) con vulnerabilidades conocidas de {len(specs)} revisado(s).",
            data=findings, warnings=warnings,
        )

    def check_lock_sync(self) -> AgentResult:
        """
        Python: `uv lock --check`. Java: `./mvnw validate` (Maven no tiene
        lock file; la convergencia la vigila el enforcer).
        """
        if self.ctx.is_java:
            return self._java_check_lock_sync()

        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.process_tool import run_command

        try:
            result = run_command(["uv", "lock", "--check"], cwd=self.ctx.root, timeout=60)
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "check_lock_sync", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "check_lock_sync", str(exc))

        if result.ok:
            return AgentResult(True, self.name, "check_lock_sync", "uv.lock está sincronizado con pyproject.toml.")
        return AgentResult(
            False, self.name, "check_lock_sync",
            "uv.lock está desactualizado respecto a pyproject.toml — ejecuta 'uv lock'.",
            data={"stderr": result.stderr},
        )
