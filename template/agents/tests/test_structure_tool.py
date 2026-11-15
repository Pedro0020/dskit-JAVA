from __future__ import annotations

from pathlib import Path

import pytest

from agents.config import ProjectConfig
from agents.context import SharedContext
from agents.tools.structure_tool import StructureTool


def _java_project(tmp_path: Path) -> Path:
    pkg = tmp_path / "src" / "main" / "java" / "com" / "ejemplo"
    (pkg / "controller").mkdir(parents=True)
    (pkg / "service").mkdir()
    (pkg / "repository").mkdir()
    (pkg / "batch").mkdir()
    (pkg / "controller" / "PedidoController.java").write_text(
        "package com.ejemplo.controller;\n"
        "import com.ejemplo.service.PedidoService;\n"
        "@RestController\n"
        "@RequestMapping(\"/api/v1/pedidos\")\n"
        "public class PedidoController {\n"
        "    @GetMapping(\"/{id}\")\n"
        "    public String get() { return \"\"; }\n"
        "}\n"
    )
    (pkg / "controller" / "RotoController.java").write_text(
        "package com.ejemplo.controller;\n"
        "import com.ejemplo.repository.PedidoRepository;\n"
        "@RestController\n"
        "public class RotoController {}\n"
    )
    (pkg / "service" / "PedidoService.java").write_text(
        "package com.ejemplo.service;\n"
        "import com.ejemplo.repository.PedidoRepository;\n"
        "public class PedidoService {}\n"
    )
    (pkg / "repository" / "PedidoRepository.java").write_text(
        "package com.ejemplo.repository;\npublic class PedidoRepository {}\n"
    )
    (pkg / "batch" / "DemoJobConfig.java").write_text(
        "package com.ejemplo.batch;\n"
        "public class DemoJobConfig {\n"
        "    @Bean Job demoJob() { return new JobBuilder(\"demoJob\", repo).start(step).build(); }\n"
        "}\n"
    )
    mig = tmp_path / "src" / "main" / "resources" / "db" / "migration"
    mig.mkdir(parents=True)
    (mig / "V1__init.sql").write_text("CREATE TABLE pedidos (id INT);\n")
    return tmp_path


def test_scan_extrae_clases_capas_y_aristas(tmp_path):
    data = StructureTool.scan(_java_project(tmp_path))
    assert "com.ejemplo.controller.PedidoController" in data["classes"]
    assert "controller" in data["layers"] and "repository" in data["layers"]
    pares = {(e["from"], e["to"]) for e in data["edges"]}
    assert ("com.ejemplo.service.PedidoService", "com.ejemplo.repository.PedidoRepository") in pares


def test_scan_detecta_violacion_controller_repository(tmp_path):
    data = StructureTool.scan(_java_project(tmp_path))
    assert any(
        v["from"] == "com.ejemplo.controller.RotoController" for v in data["violations"]
    )


def test_scan_extrae_jobs_endpoints_y_migraciones(tmp_path):
    data = StructureTool.scan(_java_project(tmp_path))
    assert data["jobs"] == ["demoJob"]
    assert any(e["path"] == "/api/v1/pedidos/{id}" for e in data["endpoints"])
    assert data["migrations"][0]["file"] == "V1__init.sql"


def test_scan_sin_src_devuelve_vacio(tmp_path):
    data = StructureTool.scan(tmp_path)
    assert data["classes"] == {}
    assert data["edges"] == []
    assert data["violations"] == []


def test_build_vault_escribe_la_estructura(tmp_path):
    root = _java_project(tmp_path)
    resultado = StructureTool.build_vault(
        root, project_name="Pedidos", framework="spring-boot-batch", db="h2",
        contracts=[("batch", "Dueño del batch"), ("architecture", "Dueño de las capas")],
    )
    vault = root / "docs" / "vault"
    for rel in (
        "00_META/IA_index.md",
        "01_PROYECTO/arquitectura.md",
        "02_DOMINIOS/batch.md",
        "02_DOMINIOS/migraciones.md",
        "02_DOMINIOS/api.md",
        "04_VISUALIZACIONES/grafo_conocimiento.md",
        "05_AGENTES/batch.md",
        ".obsidian/app.json",
    ):
        assert (vault / rel).exists(), f"falta {rel}"

    indice = (vault / "00_META/IA_index.md").read_text()
    assert "Pedidos" in indice and "controller" in indice
    arquitectura = (vault / "01_PROYECTO/arquitectura.md").read_text()
    assert "VIOLACIÓN" in arquitectura
    grafo = (vault / "04_VISUALIZACIONES/grafo_conocimiento.md").read_text()
    assert "```mermaid" in grafo and "PedidoService" in grafo
    assert resultado["nodes"] == 5
    assert resultado["violations"] == 1


def test_build_vault_es_idempotente(tmp_path):
    root = _java_project(tmp_path)
    r1 = StructureTool.build_vault(root, project_name="P", framework="spring-boot", db="h2")
    r2 = StructureTool.build_vault(root, project_name="P", framework="spring-boot", db="h2")
    assert r1["files"] == r2["files"]
    assert r1["nodes"] == r2["nodes"]


# -- accion del agente ---------------------------------------------------------


@pytest.fixture
def java_ctx(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\n")
    _java_project(tmp_path)
    return SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java"}))


def test_architecture_build_vault_genera_el_vault(java_ctx):
    from agents.agents.architecture_agent import ArchitectureAgent

    result = ArchitectureAgent(context=java_ctx).build_vault()
    assert result.success, result.message
    assert (java_ctx.root / "docs" / "vault" / "00_META" / "IA_index.md").exists()
    assert result.warnings, "una violación de capas debe avisar"


def test_architecture_build_vault_fuera_de_java_rechaza(context):
    from agents.agents.architecture_agent import ArchitectureAgent

    result = ArchitectureAgent(context=context).build_vault()
    assert not result.success


def test_architecture_enrich_graphify_opt_in(java_ctx):
    from agents.agents.architecture_agent import ArchitectureAgent

    result = ArchitectureAgent(context=java_ctx).enrich_graphify()
    assert not result.success
    assert "use_graphify=false" in result.message


def test_architecture_enrich_graphify_sin_clave_pide_key(tmp_path):
    from agents.agents.architecture_agent import ArchitectureAgent

    (tmp_path / ".copier-answers.yml").write_text("language: java\nuse_graphify: true\n")
    (tmp_path / "src" / "main" / "java").mkdir(parents=True)
    ctx = SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java", "use_graphify": True}))
    result = ArchitectureAgent(context=ctx).enrich_graphify()
    assert not result.success
    assert result.needs and "GEMINI_API_KEY" in result.message
