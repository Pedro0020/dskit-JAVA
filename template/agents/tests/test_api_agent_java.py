from __future__ import annotations

import pytest

from agents.agents.api_agent import APIAgent
from agents.config import ProjectConfig
from agents.context import SharedContext


@pytest.fixture
def java_ctx(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\n")
    pkg = tmp_path / "src" / "main" / "java" / "com" / "ejemplo"
    (pkg / "controller").mkdir(parents=True)
    (pkg / "controller" / "PedidoController.java").write_text(
        'package com.ejemplo.controller;\n'
        '@RestController\n'
        '@RequestMapping("/api/v1/pedidos")\n'
        'public class PedidoController {\n'
        '    @GetMapping("/{id}")\n'
        '    public String get(String id) { return id; }\n'
        '}\n'
    )
    (pkg / "controller" / "LegacyController.java").write_text(
        'package com.ejemplo.controller;\n'
        '@RestController\n'
        'public class LegacyController {\n'
        '    @GetMapping("/viejos")\n'
        '    public String old() { return "ok"; }\n'
        '}\n'
    )
    return SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java"}))


def test_api_java_detecta_sin_versionar(java_ctx):
    result = APIAgent(context=java_ctx).check_endpoints_documented()
    assert not result.success
    assert len(result.data["unversioned"]) == 1
    assert result.data["unversioned"][0]["path"] == "/viejos"


def test_api_java_resuelve_ruta_con_base(java_ctx):
    result = APIAgent(context=java_ctx).check_endpoints_documented()
    versioned = result.data["versioned"]
    assert ("GET", "/api/v1/pedidos/{id}") in [(e["method"], e["path"]) for e in versioned]


def test_api_java_sin_controllers_ok(java_ctx):
    controller = java_ctx.root / "src" / "main" / "java" / "com" / "ejemplo" / "controller"
    for f in controller.glob("*.java"):
        f.unlink()
    result = APIAgent(context=java_ctx).check_endpoints_documented()
    assert result.success
    assert result.data == {}


def test_api_java_contador(java_ctx):
    result = APIAgent(context=java_ctx).check_endpoints_documented()
    total = sum(len(v) for v in result.data["endpoints"].values())
    assert total == 2
