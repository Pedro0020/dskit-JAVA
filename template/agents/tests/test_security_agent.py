from __future__ import annotations

import pytest

from agents.agents.security_agent import SecurityAgent
from agents.config import ProjectConfig
from agents.context import SharedContext


@pytest.fixture
def java_ctx(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\n")
    resources = tmp_path / "src" / "main" / "resources"
    resources.mkdir(parents=True)
    (resources / "application.yml").write_text("spring:\n  application:\n    name: demo\n")
    return SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java"}))


def test_security_sin_exposure_es_seguro(java_ctx):
    result = SecurityAgent(context=java_ctx).check_actuator_exposure()
    assert result.success


def test_security_rechaza_wildcard(java_ctx):
    yml = java_ctx.root / "src" / "main" / "resources" / "application.yml"
    yml.write_text("management:\n  endpoints:\n    web:\n      exposure:\n        include: \"*\"\n")
    result = SecurityAgent(context=java_ctx).check_actuator_exposure()
    assert not result.success


def test_security_rechaza_endpoint_sensible(java_ctx):
    yml = java_ctx.root / "src" / "main" / "resources" / "application.yml"
    yml.write_text("management:\n  endpoints:\n    web:\n      exposure:\n        include: \"health,env\"\n")
    result = SecurityAgent(context=java_ctx).check_actuator_exposure()
    assert not result.success
    assert any("env" in f["exposed_sensitive"] for f in result.data)


def test_security_acepta_health_solo(java_ctx):
    yml = java_ctx.root / "src" / "main" / "resources" / "application.yml"
    yml.write_text("management:\n  endpoints:\n    web:\n      exposure:\n        include: \"health\"\n")
    result = SecurityAgent(context=java_ctx).check_actuator_exposure()
    assert result.success


def test_security_placeholder_pide_verificacion(java_ctx):
    yml = java_ctx.root / "src" / "main" / "resources" / "application.yml"
    yml.write_text("management:\n  endpoints:\n    web:\n      exposure:\n        include: \"${EXPOSURE:health}\"\n")
    result = SecurityAgent(context=java_ctx).check_actuator_exposure()
    assert result.success
    assert any(f.get("placeholder") for f in result.data)


def test_security_scan_detecta_literal(java_ctx):
    yml = java_ctx.root / "src" / "main" / "resources" / "application.yml"
    yml.write_text("app:\n  password: supersecreto\n")
    result = SecurityAgent(context=java_ctx).scan_hardcoded_secrets()
    assert not result.success
    assert result.data[0]["key"] == "password"


def test_security_scan_ignora_placeholder(java_ctx):
    yml = java_ctx.root / "src" / "main" / "resources" / "application.yml"
    yml.write_text("app:\n  password: ${DB_PASSWORD:postgres}\n")
    result = SecurityAgent(context=java_ctx).scan_hardcoded_secrets()
    assert result.success
