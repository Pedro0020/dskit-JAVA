from __future__ import annotations


# -- navegacion del grafo: absorbida de `docsearch` -----------------------------
# `doc.graph_query` y `docsearch.search` consultaban el mismo grafo con cache.
# Se conservo la implementacion de docsearch (no cachea los fallos) y se
# trajeron sus acciones de navegacion.

def test_graph_query_falla_sin_grafo(context):
    from agents.agents.doc_agent import DocAgent

    result = DocAgent(context=context).graph_query(question="test")
    assert not result.success


def test_neighbors_falla_sin_grafo(context):
    from agents.agents.doc_agent import DocAgent

    result = DocAgent(context=context).neighbors(node="algo")
    assert not result.success


def test_list_references_falla_sin_grafo(context):
    from agents.agents.doc_agent import DocAgent

    result = DocAgent(context=context).list_references()
    assert not result.success


# -- rama Java: la fuente estructural es el codigo, no graphify ------------------


def _java_doc_context(tmp_path):
    from agents.config import ProjectConfig
    from agents.context import SharedContext

    (tmp_path / ".copier-answers.yml").write_text("language: java\n")
    pkg = tmp_path / "src" / "main" / "java" / "com" / "ejemplo"
    pkg.mkdir(parents=True)
    (pkg / "Servicio.java").write_text("public class Servicio {\n    // calcular pedido\n}\n")
    return SharedContext(root=tmp_path, config=ProjectConfig(extra={"language": "java"}))


def test_java_search_encuentra_en_codigo(tmp_path):
    from agents.agents.doc_agent import DocAgent

    agent = DocAgent(context=_java_doc_context(tmp_path))
    result = agent.search(query="pedido")
    assert result.success
    assert any(r["source_type"] == "code" for r in result.data)


def test_java_generate_javadoc_requiere_java(tmp_path):
    from agents.agents.doc_agent import DocAgent

    # En un proyecto Python (sin language=java) la accion rechaza con motivo.
    from agents.config import ProjectConfig
    from agents.context import SharedContext

    ctx = SharedContext(root=tmp_path, config=ProjectConfig())
    result = DocAgent(context=ctx).generate_javadoc()
    assert not result.success
