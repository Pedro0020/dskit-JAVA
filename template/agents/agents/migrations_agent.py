"""
agents.agents.migrations_agent — Dueño de db/migration (solo language=java).

Gobierna las migraciones Flyway/Liquibase con las reglas que en producción
deciden si una migración es segura: una migración ya aplicada NO se edita
(checksum), el orden es estrictamente creciente y un undo destructivo exige
un script de rollback previo. El estado de checksums vive en su workspace
(agents/workspace/migrations/) — la primera ejecución lo graba y las
siguientes detectan ediciones.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from agents.core.base_agent import AgentResult, BaseAgent
from agents.core.registry import register_agent

_VALID_FILENAME = re.compile(r"^V(\d+)__(.+)\.sql$")
_ROLLBACK_FILENAME = re.compile(r"^U(\d+)__(.+)\.sql$")


@register_agent
class MigrationsAgent(BaseAgent):
    name = "migrations"
    description = (
        "Dueño de db/migration: crea migraciones versionadas, valida orden y checksums, "
        "y rechaza editar una migración ya aplicada."
    )
    capabilities = [
        "migracion", "migraciones", "flyway", "liquibase", "migration",
        "esquema", "ddl", "checksum", "version de esquema",
    ]

    def action_aliases(self) -> dict:
        return {
            "create": ["crea", "nueva migracion", "añade migracion"],
            "validate": ["valida", "revisa las migraciones", "comprueba"],
            "status": ["estado", "listar migraciones"],
            "undo": ["revierte", "rollback", "deshaz"],
        }

    def actions(self) -> dict:
        return {
            "create": self.create,
            "validate": self.validate,
            "status": self.status,
            "undo": self.undo,
        }

    def _require_java(self, action: str) -> AgentResult | None:
        if self.ctx.is_java:
            return None
        return AgentResult(
            False, self.name, action,
            "El dominio migrations solo existe en proyectos Java (language=java).",
        )

    def _migrations_dir(self) -> Path:
        migrations = str(self.ctx.config.extra.get("migrations", "flyway"))
        if migrations == "liquibase":
            return self.ctx.root / "src" / "main" / "resources" / "db" / "changelog"
        return self.ctx.root / "src" / "main" / "resources" / "db" / "migration"

    def _list_migrations(self) -> list[Path]:
        d = self._migrations_dir()
        if not d.exists():
            return []
        return sorted(d.glob("*.sql"))

    def _checksum_file(self) -> Path:
        return self.ctx.agent_workspace("migrations") / "checksums.json"

    def _known_checksums(self) -> dict[str, str]:
        path = self._checksum_file()
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _record_checksums(self, checksums: dict[str, str]) -> None:
        self._checksum_file().write_text(
            json.dumps(checksums, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    # -- acciones -------------------------------------------------------------
    def create(self, *, name: str, sql: str = "") -> AgentResult:
        """Crea la siguiente migración `V<n>__<name>.sql` (o cambioset Liquibase)."""
        guard = self._require_java("create")
        if guard is not None:
            return guard
        if not name:
            return AgentResult(
                False, self.name, "create", "Falta el nombre de la migración.",
                needs=["¿Qué nombre le pongo a la migración? (--name, p. ej. add_users)"],
            )
        if not re.match(r"^[a-z0-9_]+$", name):
            return AgentResult(
                False, self.name, "create",
                "El nombre solo admite minúsculas, dígitos y '_' (convención Flyway).",
            )

        existing = self._list_migrations()
        next_version = max(
            [int(m.group(1)) for f in existing if (m := _VALID_FILENAME.match(f.name))],
            default=0,
        ) + 1
        target = self._migrations_dir() / f"V{next_version}__{name}.sql"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return AgentResult(False, self.name, "create", f"Ya existe '{target.name}'.")

        body = sql.strip() or "-- TODO: escribe aquí la migración (idempotente si es posible)\n"
        if not body.endswith("\n"):
            body += "\n"
        target.write_text(body, encoding="utf-8")
        return AgentResult(
            True, self.name, "create",
            f"Migración creada en '{target.relative_to(self.ctx.root)}'.",
            data={"path": str(target.relative_to(self.ctx.root)), "version": next_version},
        )

    def validate(self) -> AgentResult:
        """
        Valida el directorio de migraciones: nombres V<n>__*, versiones
        crecientes sin huecos duplicados, y ninguna migración ya registrada
        ha cambiado de checksum (primera ejecución = registro).
        """
        guard = self._require_java("validate")
        if guard is not None:
            return guard

        files = self._list_migrations()
        if not files:
            return AgentResult(
                True, self.name, "validate",
                "No hay migraciones en " + str(self._migrations_dir().relative_to(self.ctx.root)) + ".",
                data={"migrations": [], "checks": []},
            )

        checks: list[dict] = []
        seen_versions: set[int] = set()
        for f in files:
            match = _VALID_FILENAME.match(f.name)
            if not match:
                checks.append({"id": f.name, "ok": False, "message": f"'{f.name}' no sigue V<n>__<desc>.sql"})
                continue
            version = int(match.group(1))
            if version in seen_versions:
                checks.append({"id": f.name, "ok": False, "message": f"versión {version} duplicada"})
            else:
                seen_versions.add(version)

        # Checksums: editar una migración registrada es un checksum roto.
        known = self._known_checksums()
        current = {f.name: self._sha256(f) for f in files}
        first_run = not known
        if not first_run:
            for name, digest in known.items():
                if name in current and current[name] != digest:
                    checks.append({
                        "id": name, "ok": False,
                        "message": f"checksum cambiado — '{name}' se editó después de registrarse; "
                                   "una migración aplicada no se reescribe: crea V<n+1>",
                    })
        self._record_checksums(current)

        ok = all(c["ok"] for c in checks)
        return AgentResult(
            ok, self.name, "validate",
            f"{len(files)} migración(es); {len(checks)} problema(s)."
            + (" Checksums registrados por primera vez." if first_run else ""),
            data={"migrations": [f.name for f in files], "checks": checks, "first_run": first_run},
            warnings=[c["message"] for c in checks if not c["ok"]],
        )

    def status(self) -> AgentResult:
        """Lista las migraciones en orden con su checksum corto."""
        guard = self._require_java("status")
        if guard is not None:
            return guard

        files = self._list_migrations()
        rows = [
            {"name": f.name, "version": m.group(1) if (m := _VALID_FILENAME.match(f.name)) else None,
             "sha256": self._sha256(f)[:12]}
            for f in files
        ]
        return AgentResult(
            True, self.name, "status",
            f"{len(rows)} migración(es) en {self._migrations_dir().relative_to(self.ctx.root)}.",
            data=rows,
        )

    def undo(self, *, target: str) -> AgentResult:
        """
        Rechaza el undo destructivo salvo que exista un script de rollback
        (Flyway `U<n>__*.sql` o un changeset liquibase de rollback).
        """
        guard = self._require_java("undo")
        if guard is not None:
            return guard
        if not target:
            return AgentResult(
                False, self.name, "undo", "Falta la migración objetivo.",
                needs=["¿Qué migración quieres revertir? (--target V<n>__name.sql)"],
            )

        d = self._migrations_dir()
        rollback = [f.name for f in d.glob("*.sql") if _ROLLBACK_FILENAME.match(f.name)] if d.exists() else []
        if not rollback:
            return AgentResult(
                False, self.name, "undo",
                f"No hay scripts de rollback (U<n>__*.sql) — un undo destructivo sin rollback "
                f"previo se rechaza. Escribe uno antes de revertir '{target}'.",
                needs=["un script de rollback U<n>__*.sql que deshaga la migración"],
            )
        return AgentResult(
            True, self.name, "undo",
            f"Rollback disponible para revertir '{target}': {', '.join(rollback)} — "
            "ejecútalo con la herramienta de migraciones (flyway undo / liquibase rollback), "
            "no borres la migración a mano.",
            data={"rollback_scripts": rollback},
        )
