from __future__ import annotations

import pytest

from agents.agents.make_agent import MakeAgent
from agents.config import ProjectConfig
from agents.context import SharedContext


@pytest.fixture
def make_context(tmp_path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("""
.PHONY: all test clean
all: test
test:
	python -m pytest
clean:
	rm -rf __pycache__
""")
    return SharedContext(root=tmp_path, config=ProjectConfig(project_slug="mi_paquete"))


def test_list_targets_finds_targets(make_context):
    agent = MakeAgent(context=make_context)
    result = agent.list_targets()
    assert result.success
    assert "test" in result.data
    assert "clean" in result.data


def test_validate_valid_makefile(make_context):
    agent = MakeAgent(context=make_context)
    result = agent.validate()
    assert result.success


def test_check_pipeline_chain_missing(make_context):
    agent = MakeAgent(context=make_context)
    result = agent.check_pipeline_chain()
    assert not result.success


def test_suggest_targets(make_context):
    agent = MakeAgent(context=make_context)
    result = agent.suggest_targets()
    assert result.success


def test_validate_missing_makefile(tmp_path):
    ctx = SharedContext(root=tmp_path, config=ProjectConfig(project_slug="x"))
    agent = MakeAgent(context=ctx)
    result = agent.validate()
    assert not result.success


# ─── Rama Java: fachada sobre ./mvnw ────────────────────────────────────────


def _java_make_context(tmp_path):
    makefile = tmp_path / "Makefile"
    makefile.write_text("""
.PHONY: setup test verify check lint format clean typecheck mutation security audit crap
setup:
	@./mvnw -q dependency:go-offline
test:
	@./mvnw test
verify:
	@./mvnw verify
check: verify
lint:
	@./mvnw -q spotless:check
format:
	@./mvnw -q spotless:apply
typecheck:
	@./mvnw -q compile -Ptypecheck
mutation:
	@./mvnw pitest
security:
	@trivy fs .
audit:
	@./mvnw pmd:cpd-check
crap:
	@echo crap
clean:
	@./mvnw clean
""")
    return SharedContext(root=tmp_path, config=ProjectConfig(project_slug="x", extra={"language": "java"}))


def test_java_validate_fachada_completa(tmp_path):
    agent = MakeAgent(context=_java_make_context(tmp_path))
    result = agent.validate()
    assert result.success


def test_java_validate_falla_si_faltan_targets(tmp_path):
    ctx = _java_make_context(tmp_path)
    (ctx.root / "Makefile").write_text(".PHONY: test\ntest:\n\t@echo hola\n")
    agent = MakeAgent(context=ctx)
    result = agent.validate()
    assert not result.success
    assert any("verify" in w for w in result.warnings)


def test_java_check_pipeline_chain_usa_fachada(tmp_path):
    agent = MakeAgent(context=_java_make_context(tmp_path))
    result = agent.check_pipeline_chain()
    assert result.success
    assert "verify" in result.data["found"]


def test_java_suggest_targets_completa_sin_sugerencias(tmp_path):
    agent = MakeAgent(context=_java_make_context(tmp_path))
    result = agent.suggest_targets()
    assert result.success
    assert result.data["suggested"] == []
