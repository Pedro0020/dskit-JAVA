"""
agents.agents.batch_agent — Dueño del dominio Spring Batch (solo language=java).

Valida la configuración de jobs con las reglas que en producción deciden si
un batch da confianza o miente: restartability (JobRepository/`BATCH_*`),
autorun explícito, pasos con chunk/tasklet y escritores dentro de
transacción. Las acciones son deterministas y no necesitan la BD levantada.
"""

from __future__ import annotations

import re
from pathlib import Path

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent

#: Mensajes reales de Spring Batch → causa probable + qué mirar. La
#: explicación se devuelve textual, sin inventar el stack real.
_FALLOS_CONOCIDOS: dict[str, tuple[str, str]] = {
    r"A job instance already exists": (
        "restartability",
        "el job ya corrió con esos job parameters; sin incrementer/params nuevos Spring Batch no lo relanza. "
        "Añade un incrementer o nuevos parámetros.",
    ),
    r"Invalid object name 'BATCH_JOB_INSTANCE'": (
        "esquema BATCH_*",
        "faltan las tablas BATCH_* — spring.batch.jdbc.initialize-schema=always o migraciones que las creen.",
    ),
    r"Job name .* is not unique|No job found with name": (
        "nombre del job",
        "el nombre no coincide con ningún @Bean Job o hay dos con el mismo — revisa spring.batch.job.name.",
    ),
    r"TransactionRequiredException|no transaction is active": (
        "transacción",
        "un writer/processor corre fuera de transacción — Spring Batch exige PlatformTransactionManager en el step.",
    ),
}


@register_agent
class BatchAgent(BaseAgent):
    name = "batch"
    description = (
        "Dueño del dominio Spring Batch: valida jobs (restartability, idempotencia, transacciones), "
        "los ejecuta y explica fallos de JobExecution/StepExecution."
    )
    capabilities = [
        "batch", "job", "step", "chunk", "tasklet", "restartability",
        "job parameters", "spring batch", "esquema batch", "idempotencia",
    ]

    def action_aliases(self) -> dict:
        return {
            "validate_job": ["valida", "revisa el job", "comprueba el batch"],
            "run_job": ["ejecuta el job", "corre el job", "lanza el job"],
            "explain_failure": ["explica el fallo", "que significa", "por que falla"],
            "checkpoint": ["estado del job", "configuracion batch"],
        }

    def actions(self) -> dict:
        return {
            "validate_job": self.validate_job,
            "run_job": self.run_job,
            "explain_failure": self.explain_failure,
            "checkpoint": self.checkpoint,
        }

    def _require_java(self, action: str) -> AgentResult | None:
        if self.ctx.is_java:
            return None
        return AgentResult(
            False, self.name, action,
            "El dominio batch solo existe en proyectos Java (language=java).",
        )

    # -- lectura del dominio --------------------------------------------------
    def _batch_files(self) -> list[Path]:
        if not self.ctx.java_src_dir.exists():
            return []
        return sorted(self.ctx.java_src_dir.glob("**/batch/*.java"))

    def _application_yml(self) -> str:
        path = self.ctx.root / "src" / "main" / "resources" / "application.yml"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    def _job_names(self) -> list[str]:
        nombres = []
        for f in self._batch_files():
            texto = f.read_text(encoding="utf-8", errors="replace")
            for match in re.finditer(r'new JobBuilder\("([^"]+)"', texto):
                nombres.append(match.group(1))
        return sorted(set(nombres))

    # -- acciones -------------------------------------------------------------
    def validate_job(self) -> AgentResult:
        """Checks estáticos de restartability/idempotencia sobre la config batch."""
        guard = self._require_java("validate_job")
        if guard is not None:
            return guard

        files = self._batch_files()
        if not files:
            return AgentResult(
                True, self.name, "validate_job",
                "No hay configuración batch (src/main/java/**/batch/) que validar.",
                data={"jobs": [], "checks": []},
            )

        yml = self._application_yml()
        checks: list[dict] = []
        jobs = self._job_names()

        # 1. Autorun explícito: sin `job.enabled` desactivado en el perfil base.
        enabled_disabled = re.search(
            r"^\s*enabled:\s*false\s*$", yml, re.MULTILINE
        )
        checks.append({
            "id": "autorun",
            "ok": enabled_disabled is None,
            "message": "spring.batch.job.enabled=false en el perfil base desactiva el autorun"
            if enabled_disabled else "autorun de jobs sin override explícito",
        })

        # 2. Esquema BATCH_*: initialize-schema o migraciones dueñas del esquema.
        initialize = re.search(r"initialize-schema:\s*(always|embedded)", yml)
        checks.append({
            "id": "esquema",
            "ok": initialize is not None,
            "message": "initialize-schema=always|embedded presente" if initialize
            else "no se ve initialize-schema — confirma que una migración crea las tablas BATCH_*",
        })

        # 3. Pasos declarados con chunk/tasklet.
        texto_total = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)
        has_step = bool(re.search(r"new StepBuilder|\.tasklet\(|\.chunk\(", texto_total))
        checks.append({
            "id": "steps",
            "ok": has_step,
            "message": "hay steps con chunk/tasklet" if has_step else "no se ven steps (chunk/tasklet)",
        })

        ok = all(c["ok"] for c in checks)
        warnings = [c["message"] for c in checks if not c["ok"]]
        return AgentResult(
            ok, self.name, "validate_job",
            f"{len(jobs)} job(s) encontrados; {sum(c['ok'] for c in checks)}/{len(checks)} checks superados.",
            data={"jobs": jobs, "checks": checks}, warnings=warnings,
        )

    def run_job(self, *, job: str, dry_run: bool = False) -> AgentResult:
        """Ejecuta un job con spring-boot:run (nombre obligatorio)."""
        guard = self._require_java("run_job")
        if guard is not None:
            return guard
        if not job:
            return AgentResult(
                False, self.name, "run_job", "Falta el nombre del job.",
                needs=["¿Qué job quieres ejecutar? (--job <nombre>)"],
            )

        from agents.exceptions import MissingDependencyError, ToolExecutionError
        from agents.tools.maven_tool import MavenTool

        if dry_run:
            return AgentResult(True, self.name, "run_job", f"[dry-run] ./mvnw spring-boot:run -Dspring-batch.job.name={job}")

        try:
            result = MavenTool.run(
                self.ctx.root,
                ["spring-boot:run", f"-Dspring-batch.job.name={job}"],
                timeout=1800,
            )
        except MissingDependencyError as exc:
            return AgentResult(False, self.name, "run_job", str(exc))
        except ToolExecutionError as exc:
            return AgentResult(False, self.name, "run_job", str(exc))

        if result.ok:
            return AgentResult(True, self.name, "run_job", f"Job '{job}' completado.", data={"job": job})
        explicacion = self.explain_failure(error=result.stderr[-2000:])
        return AgentResult(
            False, self.name, "run_job",
            f"Job '{job}' falló (rc={result.returncode}). {explicacion.message}",
            data={"job": job, "stderr": result.stderr[-2000:]},
            warnings=explicacion.warnings,
        )

    def explain_failure(self, *, error: str) -> AgentResult:
        """Traduce mensajes conocidos de Spring Batch a causa probable."""
        guard = self._require_java("explain_failure")
        if guard is not None:
            return guard
        if not error or not error.strip():
            return AgentResult(False, self.name, "explain_failure", "Pasa el texto del fallo (--error).")

        explicaciones = []
        for patron, (causa, detalle) in _FALLOS_CONOCIDOS.items():
            if re.search(patron, error):
                explicaciones.append({"causa": causa, "detalle": detalle})
        if not explicaciones:
            return AgentResult(
                True, self.name, "explain_failure",
                "Sin coincidencia con los fallos conocidos — pasa el stack completo al humano.",
                data=[],
            )
        return AgentResult(
            True, self.name, "explain_failure",
            f"{len(explicaciones)} causa(s) probable(s): "
            + "; ".join(e["causa"] for e in explicaciones) + ".",
            data=explicaciones,
        )

    def checkpoint(self) -> AgentResult:
        """Estado declarado del dominio: jobs, autorun y parámetros."""
        guard = self._require_java("checkpoint")
        if guard is not None:
            return guard

        yml = self._application_yml()
        job_name = None
        match = re.search(r"name:\s*\$\{JOB_NAME:([\w-]+)\}", yml)
        if match:
            job_name = match.group(1)
        data = {
            "jobs": self._job_names(),
            "default_job": job_name,
            "initialize_schema": bool(re.search(r"initialize-schema:", yml)),
        }
        return AgentResult(
            True, self.name, "checkpoint",
            f"{len(data['jobs'])} job(s); default '{job_name or '—'}'.",
            data=data,
        )
