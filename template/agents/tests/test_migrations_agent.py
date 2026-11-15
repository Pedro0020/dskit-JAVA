from __future__ import annotations

import pytest

from agents.agents.migrations_agent import MigrationsAgent
from agents.config import ProjectConfig
from agents.context import SharedContext


@pytest.fixture
def java_ctx(tmp_path):
    (tmp_path / ".copier-answers.yml").write_text("language: java\nmigrations: flyway\n")
    mig = tmp_path / "src" / "main" / "resources" / "db" / "migration"
    mig.mkdir(parents=True)
    (mig / "V1__init.sql").write_text("CREATE TABLE pedidos (id INT);\n")
    return SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java", "migrations": "flyway"}))


def test_migrations_create_numera_siguiente(java_ctx):
    result = MigrationsAgent(context=java_ctx).create(name="add_users")
    assert result.success
    created = java_ctx.root / "src" / "main" / "resources" / "db" / "migration" / "V2__add_users.sql"
    assert created.exists()


def test_migrations_create_rechaza_nombre_invalido(java_ctx):
    result = MigrationsAgent(context=java_ctx).create(name="Add Users")
    assert not result.success


def test_migrations_validate_registra_y_detecta_edicion(java_ctx):
    agent = MigrationsAgent(context=java_ctx)
    assert agent.validate().success  # primer run: registra checksums

    mig = java_ctx.root / "src" / "main" / "resources" / "db" / "migration" / "V1__init.sql"
    mig.write_text("CREATE TABLE pedidos (id INT, extra TEXT);\n")
    result = agent.validate()
    assert not result.success
    assert any("checksum" in c["message"] for c in result.data["checks"])


def test_migrations_validate_nombre_fuera_de_convencion(java_ctx):
    mig = java_ctx.root / "src" / "main" / "resources" / "db" / "migration"
    (mig / "sueltas.sql").write_text("SELECT 1;\n")
    result = MigrationsAgent(context=java_ctx).validate()
    assert not result.success


def test_migrations_undo_sin_rollback_rechaza(java_ctx):
    result = MigrationsAgent(context=java_ctx).undo(target="V1__init.sql")
    assert not result.success
    assert result.needs


def test_migrations_undo_con_rollback_pasa(java_ctx):
    mig = java_ctx.root / "src" / "main" / "resources" / "db" / "migration"
    (mig / "U1__init.sql").write_text("DROP TABLE pedidos;\n")
    result = MigrationsAgent(context=java_ctx).undo(target="V1__init.sql")
    assert result.success


def test_migrations_status_lista(java_ctx):
    result = MigrationsAgent(context=java_ctx).status()
    assert result.success
    assert [r["name"] for r in result.data] == ["V1__init.sql"]
