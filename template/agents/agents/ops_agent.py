"""
agents.agents.ops_agent — Dueño de la observabilidad (solo language=java).

Actuator + Micrometer + logging estructurado. La rúbrica del arnés: un
servicio sin health check real (más allá de contextLoads) no se puede dar por
`done` — este agente verifica que el cableado de observabilidad existe y está
declarado, con métricas por step de batch y traceId en los logs (MDC).
"""

from __future__ import annotations

import re
from pathlib import Path

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent


@register_agent
class OpsAgent(BaseAgent):
    name = "ops"
    description = (
        "Dueño de la observabilidad: Actuator, Micrometer/Prometheus, logging estructurado "
        "con traceId (MDC) y métricas de batch."
    )
    capabilities = [
        "observabilidad", "ops", "micrometer", "prometheus",
        "health check", "traceid", "logging", "mdc",
        "metricas de batch",
    ]

    def action_aliases(self) -> dict:
        return {
            "check_observability": ["observabilidad", "health", "metricas", "actuator"],
            "check_batch_metrics": ["metricas de batch", "steps medidos"],
        }

    def actions(self) -> dict:
        return {
            "check_observability": self.check_observability,
            "check_batch_metrics": self.check_batch_metrics,
        }

    def _require_java(self, action: str) -> AgentResult | None:
        if self.ctx.is_java:
            return None
        return AgentResult(
            False, self.name, action,
            "El dominio ops (observabilidad) solo existe en proyectos Java (language=java).",
        )

    def _yml_text(self) -> str:
        path = self.ctx.root / "src" / "main" / "resources" / "application.yml"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    def _logback_config(self) -> str:
        path = self.ctx.root / "src" / "main" / "resources" / "logback-spring.xml"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    def check_observability(self) -> AgentResult:
        """Cableado de observabilidad: actuator, prometheus, health y traceId en logs."""
        guard = self._require_java("check_observability")
        if guard is not None:
            return guard

        use_observability = bool(self.ctx.config.extra.get("use_observability", False))
        pom = self.ctx.pom_file
        pom_text = pom.read_text(encoding="utf-8", errors="replace") if pom.exists() else ""
        yml = self._yml_text()
        logback = self._logback_config()

        checks = [
            {"id": "actuator", "ok": "spring-boot-starter-actuator" in pom_text,
             "message": "actuator en el classpath"},
            {"id": "prometheus", "ok": "micrometer-registry-prometheus" in pom_text,
             "message": "registry Prometheus (Micrometer)"},
            {"id": "health", "ok": "management.endpoint.health" in yml or "management:" in yml,
             "message": "config management presente (health expuesto)"},
            {"id": "traceid", "ok": "%X{traceId}" in logback or "traceId" in yml,
             "message": "traceId en el pattern de logs (MDC)"},
        ]

        if not use_observability:
            return AgentResult(
                True, self.name, "check_observability",
                "use_observability=false — el servicio nace sin observabilidad; "
                "sin health check real no se puede cerrar una feature como done.",
                data={"checks": checks, "enabled": False},
                warnings=["Activa use_observability o añade actuator para cumplir la rúbrica."],
            )

        ok = all(c["ok"] for c in checks)
        return AgentResult(
            ok, self.name, "check_observability",
            f"{sum(c['ok'] for c in checks)}/{len(checks)} piezas de observabilidad presentes.",
            data={"checks": checks, "enabled": True},
            warnings=[c["message"] for c in checks if not c["ok"]],
        )

    def check_batch_metrics(self) -> AgentResult:
        """Métricas por step de batch: @Timed/MeterRegistry en las clases batch."""
        guard = self._require_java("check_batch_metrics")
        if guard is not None:
            return guard

        batch_files = sorted(self.ctx.java_src_dir.glob("**/batch/*.java")) if self.ctx.java_src_dir.exists() else []
        if not batch_files:
            return AgentResult(
                True, self.name, "check_batch_metrics",
                "No hay dominio batch en este proyecto.",
                data=[],
            )

        medidos, sin_medir = [], []
        for java in batch_files:
            texto = java.read_text(encoding="utf-8", errors="replace")
            (medidos if "@Timed" in texto or "MeterRegistry" in texto else sin_medir).append(
                str(java.relative_to(self.ctx.root))
            )

        return AgentResult(
            not sin_medir, self.name, "check_batch_metrics",
            f"{len(medidos)} clase(s) batch con métricas; {len(sin_medir)} sin medir.",
            data={"measured": medidos, "unmeasured": sin_medir},
            warnings=[
                f"{f} no declara métricas (@Timed/MeterRegistry) — sin duración/tasa de error por step."
                for f in sin_medir
            ],
        )
