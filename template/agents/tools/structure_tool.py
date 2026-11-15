"""
agents.tools.structure_tool — Memoria estructural de un proyecto Java (JAVA-016).

Construye el vault Obsidian (`docs/vault/`) de un proyecto Spring desde lo que
el código ya dice, sin dependencias ni LLM: paquetes, clases, imports
(aristas), capas, jobs de batch, migraciones y endpoints. Es el núcleo
determinista de la memoria del proyecto; graphify (opt-in) añade la capa
semántica encima del mismo vault.

Por qué determinista: el grafo estructural alimenta la documentación y la
gobernanza (un controller que importa un repository se ve como arista
cruzando capas). Un LLM en ese camino daría un resultado plausible y no
auditable; jdeps/parseo dan el hecho exacto.

Formatos leídos (verificados sobre el template, no supuestos):
- `.java`: `package x.y;`, `import a.b.C;`, `@RestController`,
  `@RequestMapping("/ruta")`, `@GetMapping(...)`, `new JobBuilder("nombre"`,
  `.chunk(`, `.tasklet(`.
- migraciones: `V<n>__*.sql` / `U<n>__*.sql` (Flyway) y `*.sql` (Liquibase).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from agents.tools.registry import register_tool

_LAYERS = ("controller", "service", "repository", "domain", "config", "batch")
_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_IMPORT_RE = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;", re.MULTILINE)
_MAPPING_RE = re.compile(r"@(Get|Post|Put|Delete|Patch)Mapping\(\s*\"([^\"]+)\"")
_CLASS_MAPPING_RE = re.compile(r"@RequestMapping\(\s*\"([^\"]+)\"")
_JOB_RE = re.compile(r'new JobBuilder\("([\w-]+)"')
_MIGRATION_RE = re.compile(r"^([VU])(\d+)__(.+)\.sql$")


@dataclass
class JavaClass:
    fqcn: str
    name: str
    package: str
    file: str
    layer: str
    imports: list[str] = field(default_factory=list)
    rest_controller: bool = False
    endpoints: list[tuple[str, str]] = field(default_factory=list)
    jobs: list[str] = field(default_factory=list)


@register_tool("structure")
class StructureTool:
    @staticmethod
    def scan(root: Path) -> dict:
        """
        Extrae la estructura del proyecto: clases, aristas, capas, jobs,
        endpoints, migraciones y violaciones de capas.
        """
        src = root / "src" / "main" / "java"
        classes: dict[str, JavaClass] = {}
        if src.exists():
            for java in sorted(src.rglob("*.java")):
                texto = java.read_text(encoding="utf-8", errors="replace")
                pkg_match = _PACKAGE_RE.search(texto)
                package = pkg_match.group(1) if pkg_match else ""
                name = java.stem
                fqcn = f"{package}.{name}" if package else name
                layer = next((capa for capa in _LAYERS if capa in package.split(".")), "other")
                cls = JavaClass(
                    fqcn=fqcn, name=name, package=package,
                    file=str(java.relative_to(root)), layer=layer,
                    imports=_IMPORT_RE.findall(texto),
                    rest_controller="@RestController" in texto or "@Controller" in texto,
                    jobs=_JOB_RE.findall(texto),
                )
                base = ""
                mapping = _CLASS_MAPPING_RE.search(texto)
                if mapping:
                    base = mapping.group(1).rstrip("/")
                cls.endpoints = [
                    (m.group(1).upper(), base + "/" + m.group(2).lstrip("/"))
                    for m in _MAPPING_RE.finditer(texto)
                ]
                classes[fqcn] = cls

        by_name = {c.name: c.fqcn for c in classes.values()}
        edges = []
        for cls in classes.values():
            for imp in cls.imports:
                target = by_name.get(imp.rsplit(".", 1)[-1])
                if target and target != cls.fqcn:
                    edges.append({"from": cls.fqcn, "to": target, "kind": "import"})
        edges.sort(key=lambda e: (e["from"], e["to"]))

        violations = [
            {"from": e["from"], "to": e["to"]}
            for e in edges
            if classes[e["from"]].layer == "controller" and classes[e["to"]].layer == "repository"
        ]

        jobs = sorted({job for c in classes.values() for job in c.jobs})
        endpoints = [
            {"class": c.fqcn, "method": method, "path": path}
            for c in classes.values()
            for (method, path) in c.endpoints
        ]
        endpoints.sort(key=lambda e: (e["path"], e["method"]))

        migrations = []
        for sub in (Path("src/main/resources/db/migration"), Path("src/main/resources/db/changelog")):
            d = root / sub
            if d.exists():
                for f in sorted(d.glob("*.sql")):
                    m = _MIGRATION_RE.match(f.name)
                    migrations.append({
                        "file": f.name,
                        "version": int(m.group(2)) if m else None,
                        "kind": m.group(1) if m else "liquibase",
                    })

        layers = sorted({c.layer for c in classes.values()})
        return {
            "classes": {fqcn: c.__dict__ for fqcn, c in classes.items()},
            "edges": edges,
            "layers": layers,
            "jobs": jobs,
            "endpoints": endpoints,
            "migrations": migrations,
            "violations": violations,
        }

    # -- vault ---------------------------------------------------------------
    @staticmethod
    def build_vault(root: Path, *, project_name: str, framework: str, db: str,
                    contracts: list[tuple[str, str]] | None = None) -> dict:
        """
        Escribe el vault determinista en `docs/vault/` y devuelve un resumen
        `{files: [...], nodes: N, edges: N}`. Idempotente: regenera el contenido.
        """
        data = StructureTool.scan(root)
        vault = root / "docs" / "vault"
        files: list[str] = []

        def write(rel: str, contenido: str) -> None:
            path = vault / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contenido.strip() + "\n", encoding="utf-8")
            files.append(str(path.relative_to(root)))

        classes = data["classes"]
        por_capa: dict[str, list[str]] = {}
        for fqcn, c in sorted(classes.items()):
            por_capa.setdefault(c["layer"], []).append(fqcn)

        # 00_META — punto de entrada
        mapa = "\n".join(
            f"- `{capa}`: " + ", ".join(f"`{n}`" for n in nombres)
            for capa, nombres in sorted(por_capa.items())
        ) or "- (sin clases todavía)"
        write(
            "00_META/IA_index.md",
            f"""# {project_name} — índice del proyecto

Metadata: `language=java`, `framework={framework}`, `db={db}`.
Este vault es la memoria estructural del proyecto (JAVA-016); se regenera con
`make knowledge` y lo genera el agente `architecture`.

## Mapa de capas

{mapa}

## Secciones

- [[01_PROYECTO/arquitectura]] — capas, dependencias y violaciones
- [[02_DOMINIOS/batch]] — jobs y steps de Spring Batch
- [[02_DOMINIOS/migraciones]] — migraciones de esquema
- [[02_DOMINIOS/api]] — endpoints REST
- [[04_VISUALIZACIONES/grafo_conocimiento]] — grafo de dependencias
- `05_AGENTES/` — fichas de los agentes del arnés""",
        )

        # 01_PROYECTO — arquitectura
        edges_txt = "\n".join(
            f"- `{e['from']}` → `{e['to']}`" for e in data["edges"]
        ) or "- (sin dependencias internas todavía)"
        viol_txt = "\n".join(
            f"- **VIOLACIÓN**: `{v['from']}` (controller) importa `{v['to']}` (repository)"
            for v in data["violations"]
        ) or "- Ninguna: controller → service → repository se respeta."
        write(
            "01_PROYECTO/arquitectura.md",
            f"""# Arquitectura

## Capas presentes

{mapa}

## Dependencias entre clases

{edges_txt}

## Límites de capas

{viol_txt}""",
        )

        # 02_DOMINIOS
        jobs = data["jobs"]
        write(
            "02_DOMINIOS/batch.md",
            "# Batch\n\n"
            + ("Jobs declarados:\n\n" + "\n".join(f"- `{j}`" for j in jobs) if jobs
               else "No hay jobs de Spring Batch en este proyecto.")
            + "\n\nEl agente `batch` valida restartability, idempotencia y transacciones "
              "(`run batch validate_job`).",
        )
        migrations = data["migrations"]
        write(
            "02_DOMINIOS/migraciones.md",
            "# Migraciones\n\n"
            + ("\n".join(
                f"- `{m['file']}`" + (f" (versión {m['version']})" if m["version"] else "")
                for m in migrations) if migrations
               else "No hay migraciones en `src/main/resources/db/`.")
            + "\n\nEl agente `migrations` valida orden y checksums (`run migrations validate`).",
        )
        endpoints = data["endpoints"]
        write(
            "02_DOMINIOS/api.md",
            "# API\n\n"
            + ("\n".join(f"- `{e['method']} {e['path']}` — `{e['class']}`" for e in endpoints)
               if endpoints else "No hay controllers REST en este proyecto.")
            + "\n\nCriterio: todo endpoint vive bajo `/api/v1` (agente `api`).",
        )

        # 04_VISUALIZACIONES — grafo (mermaid lo renderiza Obsidian)
        mermaid_nodes = "\n".join(f"  {c['name']}" for c in classes.values())
        mermaid_edges = "\n".join(
            f"  {classes[e['from']]['name']} --> {classes[e['to']]['name']}"
            for e in data["edges"]
        )
        cuerpo_grafo = mermaid_edges or mermaid_nodes or "  vacio[sin clases]"
        write(
            "04_VISUALIZACIONES/grafo_conocimiento.md",
            f"""# Grafo de conocimiento

```mermaid
graph TD
{cuerpo_grafo}
```

## Nodos

{chr(10).join(f"- `{fqcn}` ({c['layer']})" for fqcn, c in sorted(classes.items())) or "- (sin clases)"}""",
        )

        # 05_AGENTES — fichas desde los contratos (una por rol)
        for name, role in sorted(contracts or []):
            write(f"05_AGENTES/{name}.md", f"# {name}\n\n{role}\n")

        # .obsidian mínimo para que Obsidian reconozca el vault
        write(".obsidian/app.json", "{}")

        return {"files": files, "nodes": len(classes), "edges": len(data["edges"]),
                "violations": len(data["violations"])}
