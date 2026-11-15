"""
agents.agents.security_agent — Dueño de la config de Spring Security (solo language=java).

La comprobación central es el gate de actuator exposure: una familia real de
CVEs nace de exponer management endpoints (env, beans, heapdump...) en
producción. Colabora con `secrets` (nunca loguea ni commitea secretos).
"""

from __future__ import annotations

import re
from pathlib import Path

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent

#: Endpoints sensibles: exponerlos en producción es la familia real de CVEs
#: de actuator exposure (env/beans/configprops/heapdump filtran secretos).
_SENSIBLES = {"env", "beans", "configprops", "heapdump", "threaddump", "mappings", "conditions"}


@register_agent
class SecurityAgent(BaseAgent):
    name = "security"
    description = (
        "Dueño de la configuración de seguridad (Spring Security, JWT, CORS, actuator exposure). "
        "Solo lee y reporta — nunca rota ni borra secretos."
    )
    capabilities = [
        "security", "seguridad", "actuator", "exposure", "jwt", "cors",
        "autenticacion", "spring security", "endpoints expuestos",
    ]

    def action_aliases(self) -> dict:
        return {
            "check_actuator_exposure": ["actuator", "exposure", "endpoints expuestos", "management"],
            "check_jwt": ["jwt", "token", "autenticacion"],
            "scan_hardcoded_secrets": ["secretos", "hardcoded", "credenciales en config"],
        }

    def actions(self) -> dict:
        return {
            "check_actuator_exposure": self.check_actuator_exposure,
            "check_jwt": self.check_jwt,
            "scan_hardcoded_secrets": self.scan_hardcoded_secrets,
        }

    def _require_java(self, action: str) -> AgentResult | None:
        if self.ctx.is_java:
            return None
        return AgentResult(
            False, self.name, action,
            "El dominio security (Spring) solo existe en proyectos Java (language=java).",
        )

    def _resources_yml(self) -> list[Path]:
        resources = self.ctx.root / "src" / "main" / "resources"
        if not resources.exists():
            return []
        return sorted(resources.rglob("application*.yml")) + sorted(resources.rglob("application*.properties"))

    # -- acciones -------------------------------------------------------------
    def check_actuator_exposure(self) -> AgentResult:
        """
        Gate de exposición: en el perfil base/producción los endpoints
        sensibles de actuator no pueden quedar públicos. La declaración se
        lee de application*.yml; `*` o una lista que incluya endpoints
        sensibles en el perfil base se rechaza.
        """
        guard = self._require_java("check_actuator_exposure")
        if guard is not None:
            return guard

        findings: list[dict] = []
        for path in self._resources_yml():
            texto = path.read_text(encoding="utf-8", errors="replace")
            if "management:" not in texto:
                continue
            bloque = re.search(r"management:.*?(?=\n\w|\Z)", texto, re.DOTALL)
            if not bloque:
                continue
            include = re.search(r"include:\s*([^\n]+)", bloque.group(0))
            if not include:
                continue
            raw = include.group(1).strip().strip('"').strip("'")
            # ${...} placeholders no se pueden juzgar estáticamente → aviso.
            if "${" in raw:
                findings.append({
                    "file": str(path.relative_to(self.ctx.root)), "include": raw,
                    "exposed_sensitive": [], "placeholder": True,
                })
                continue
            expuestos = set(t.strip().strip('"').strip("'") for t in raw.split(","))
            sensibles = expuestos & _SENSIBLES
            findings.append({
                "file": str(path.relative_to(self.ctx.root)), "include": raw,
                "exposed_sensitive": sorted(sensibles),
                "placeholder": False,
            })

        if not findings:
            return AgentResult(
                True, self.name, "check_actuator_exposure",
                "No hay cláusula management.endpoints.web.exposure.include declarada "
                "(o no hay application.yml) — actuator no expone nada por defecto.",
                data=[], warnings=["Sin exposure declarado: los endpoints quedan con el default seguro."],
            )

        problemas = [f for f in findings if f["exposed_sensitive"] or ("*" in f["include"])]
        warnings = [
            f"{f['file']}: include={f['include']} expone {', '.join(f['exposed_sensitive'])} — "
            "en producción eso filtra secretos (familia real de CVEs)."
            for f in problemas
        ] + [
            f"{f['file']}: include usa placeholders ({f['include']}) — verifica el valor en producción."
            for f in findings if f.get("placeholder")
        ]
        return AgentResult(
            not problemas, self.name, "check_actuator_exposure",
            f"{len(findings)} declaración(es) de exposure; {len(problemas)} problema(s).",
            data=findings, warnings=warnings,
        )

    def check_jwt(self) -> AgentResult:
        """Verifica el cableado JWT: starter resource-server + issuer declarado."""
        guard = self._require_java("check_jwt")
        if guard is not None:
            return guard

        pom = self.ctx.pom_file
        if not pom.exists():
            return AgentResult(False, self.name, "check_jwt", "No existe pom.xml.")
        texto = pom.read_text(encoding="utf-8", errors="replace")
        tiene_starter = "oauth2-resource-server" in texto or "spring-boot-starter-security" in texto

        issuer = False
        for path in self._resources_yml():
            yml = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"issuer-uri:|jwt:", yml):
                issuer = True

        ok = tiene_starter and issuer
        return AgentResult(
            ok, self.name, "check_jwt",
            f"JWT {'cableado' if ok else 'incompleto'}: starter={tiene_starter}, issuer={issuer}.",
            data={"starter": tiene_starter, "issuer": issuer},
            warnings=[] if ok else [
                "El proyecto usa Spring Security pero falta el starter oauth2-resource-server o el issuer-uri JWT."
            ] if tiene_starter else ["Sin starter de seguridad — JWT no aplica."],
        )

    def scan_hardcoded_secrets(self) -> AgentResult:
        """
        Literales con pinta de secreto en application*.yml (no placeholders
        ${...}). Regla del arnés: los secretos van en variables de entorno.
        """
        guard = self._require_java("scan_hardcoded_secrets")
        if guard is not None:
            return guard

        sospechosos = []
        patron = re.compile(r"^\s*(password|secret|token|api[_-]?key)\s*:\s*(\S.+)$", re.IGNORECASE | re.MULTILINE)
        for path in self._resources_yml():
            for m in patron.finditer(path.read_text(encoding="utf-8", errors="replace")):
                valor = m.group(2).strip()
                if valor.startswith("${") or valor.startswith(('"${', "'${")):
                    continue
                sospechosos.append({
                    "file": str(path.relative_to(self.ctx.root)),
                    "key": m.group(1),
                    "value": valor[:20] + ("…" if len(valor) > 20 else ""),
                })
        return AgentResult(
            not sospechosos, self.name, "scan_hardcoded_secrets",
            f"{len(sospechosos)} literal(es) con pinta de secreto en la config.",
            data=sospechosos,
            warnings=[
                f"{s['file']}: '{s['key']}' con literal — muévelo a variable de entorno (nunca al repo)."
                for s in sospechosos
            ],
        )
