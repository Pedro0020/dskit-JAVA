from __future__ import annotations

import pytest

from agents.agents.batch_agent import BatchAgent
from agents.config import ProjectConfig
from agents.context import SharedContext


@pytest.fixture
def java_ctx(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\n")
    pkg = tmp_path / "src" / "main" / "java" / "com" / "ejemplo" / "batch"
    pkg.mkdir(parents=True)
    (pkg / "DemoJobConfig.java").write_text(
        'new JobBuilder("demoJob", jobRepository).start(demoStep)\n'
        "new StepBuilder(\"demoStep\", jobRepository).tasklet(...)\n"
    )
    resources = tmp_path / "src" / "main" / "resources"
    resources.mkdir(parents=True)
    (resources / "application.yml").write_text(
        "spring:\n  batch:\n    jdbc:\n      initialize-schema: always\n    job:\n      name: ${JOB_NAME:demoJob}\n"
    )
    return SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java"}))


def test_batch_validate_job_ok(java_ctx):
    result = BatchAgent(context=java_ctx).validate_job()
    assert result.success, result.warnings
    assert result.data["jobs"] == ["demoJob"]


def test_batch_validate_detecta_autorun_desactivado(java_ctx):
    yml = java_ctx.root / "src" / "main" / "resources" / "application.yml"
    yml.write_text(yml.read_text() + "    enabled: false\n")
    result = BatchAgent(context=java_ctx).validate_job()
    assert not result.success
    assert any(c["id"] == "autorun" and not c["ok"] for c in result.data["checks"])


def test_batch_run_job_sin_nombre_pide(java_ctx):
    result = BatchAgent(context=java_ctx).run_job(job="")
    assert not result.success
    assert result.needs


def test_batch_explain_failure_conocido(java_ctx):
    result = BatchAgent(context=java_ctx).explain_failure(error="A job instance already exists")
    assert result.success
    assert result.data and result.data[0]["causa"] == "restartability"


def test_batch_explain_failure_desconocido(java_ctx):
    result = BatchAgent(context=java_ctx).explain_failure(error="todo roto sin patrón")
    assert result.success
    assert result.data == []


def test_batch_checkpoint(java_ctx):
    result = BatchAgent(context=java_ctx).checkpoint()
    assert result.success
    assert result.data["default_job"] == "demoJob"


def test_batch_fuera_de_java_rechaza(context):
    result = BatchAgent(context=context).validate_job()
    assert not result.success
    assert "java" in result.message
