from __future__ import annotations

import pytest

from agents.agents.ops_agent import OpsAgent
from agents.config import ProjectConfig
from agents.context import SharedContext


@pytest.fixture
def java_ctx(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\nuse_observability: true\n")
    (tmp_path / "pom.xml").write_text(
        "<project><dependencies>"
        "<dependency>spring-boot-starter-actuator</dependency>"
        "<dependency>micrometer-registry-prometheus</dependency>"
        "</dependencies></project>"
    )
    resources = tmp_path / "src" / "main" / "resources"
    resources.mkdir(parents=True)
    (resources / "application.yml").write_text("management:\n  endpoint:\n    health:\n      show-details: always\n")
    (resources / "logback-spring.xml").write_text("<pattern>%d %-5level [%thread] %X{traceId} %msg%n</pattern>")
    batch = tmp_path / "src" / "main" / "java" / "com" / "ejemplo" / "batch"
    batch.mkdir(parents=True)
    (batch / "DemoJobConfig.java").write_text("public class DemoJobConfig {\n}\n")
    return SharedContext(
        root=tmp_path,
        config=ProjectConfig(extra={"language": "java", "use_observability": True}),
    )


def test_ops_cableado_completo(java_ctx):
    result = OpsAgent(context=java_ctx).check_observability()
    assert result.success, result.warnings


def test_ops_sin_traceid_falla(java_ctx):
    logback = java_ctx.root / "src" / "main" / "resources" / "logback-spring.xml"
    logback.write_text("<pattern>%d %msg%n</pattern>")
    result = OpsAgent(context=java_ctx).check_observability()
    assert not result.success
    assert any(c["id"] == "traceid" and not c["ok"] for c in result.data["checks"])


def test_ops_sin_observabilidad_avisa(context, tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\nuse_observability: false\n")
    ctx = SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java", "use_observability": False}))
    result = OpsAgent(context=ctx).check_observability()
    assert result.success  # no es un fallo del proyecto: nace sin el extra
    assert result.data["enabled"] is False
    assert result.warnings


def test_ops_batch_sin_metricas(java_ctx):
    result = OpsAgent(context=java_ctx).check_batch_metrics()
    assert not result.success
    assert len(result.data["unmeasured"]) == 1


def test_ops_batch_con_timed(java_ctx):
    batch = java_ctx.root / "src" / "main" / "java" / "com" / "ejemplo" / "batch" / "DemoJobConfig.java"
    batch.write_text("@Timed(\"demo\") public class DemoJobConfig {}\n")
    result = OpsAgent(context=java_ctx).check_batch_metrics()
    assert result.success
