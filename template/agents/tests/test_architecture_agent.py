from __future__ import annotations

import pytest

from agents.agents.architecture_agent import ArchitectureAgent
from agents.config import ProjectConfig
from agents.context import SharedContext


@pytest.fixture
def java_ctx(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\nuse_archunit: true\n")
    pkg = tmp_path / "src" / "main" / "java" / "com" / "ejemplo"
    (pkg / "controller").mkdir(parents=True)
    (pkg / "service").mkdir()
    (pkg / "repository").mkdir()
    (pkg / "controller" / "PedidoController.java").write_text(
        "package com.ejemplo.controller;\n"
        "import com.ejemplo.repository.PedidoRepository;\n"
        "public class PedidoController {}\n"
    )
    return SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java", "use_archunit": True}))


def test_architecture_detecta_controller_a_repository(java_ctx):
    result = ArchitectureAgent(context=java_ctx).check_layers()
    assert not result.success
    assert "repository" in result.data["violations"][0]["import"]


def test_architecture_sin_violaciones(java_ctx):
    controller = java_ctx.root / "src" / "main" / "java" / "com" / "ejemplo" / "controller" / "PedidoController.java"
    controller.write_text("package com.ejemplo.controller;\npublic class PedidoController {}\n")
    result = ArchitectureAgent(context=java_ctx).check_layers()
    assert result.success


def test_architecture_exige_test_archunit_si_use_archunit(java_ctx):
    result = ArchitectureAgent(context=java_ctx).check_archunit_test()
    assert not result.success


def test_architecture_encuentra_test_archunit(java_ctx):
    tests = java_ctx.root / "src" / "test" / "java" / "com" / "ejemplo"
    tests.mkdir(parents=True)
    (tests / "ArchitectureTest.java").write_text("class ArchitectureTest {}\n")
    result = ArchitectureAgent(context=java_ctx).check_archunit_test()
    assert result.success


def test_architecture_fuera_de_java_rechaza(context):
    result = ArchitectureAgent(context=context).check_layers()
    assert not result.success
    assert "java" in result.message
