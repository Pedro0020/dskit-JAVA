"""
test_rubric.py — Tests de la rúbrica del arnés (`agents/rubric.py`).

La rúbrica es la definición de «bien cerrado»: una checklist binaria coherente
(criterios con id único, pregunta cerrada, umbral en rango). Que se ENFORZA en
`harness.finish` se prueba en `test_harness_agent.py` — aquí se prueba que la
fuente de verdad es coherente, porque una regla mal declarada es peor que
ninguna (se aprende a ignorarla).
"""

from __future__ import annotations

from agents.rubric import (
    CATEGORIAS_DECISION,
    CRITERIOS_PUERTA,
    CRITERIOS_REVISION,
    UMBRAL_CERTEZA,
)

TODOS = CRITERIOS_PUERTA + CRITERIOS_REVISION


def test_umbral_de_certeza_es_politica_humana_en_rango():
    assert 0.0 < UMBRAL_CERTEZA <= 1.0, "un umbral fuera de rango no significa nada"


def test_ningun_criterio_repite_id():
    ids = [c[0] for c in TODOS]
    assert len(ids) == len(set(ids)), "un id duplicado rompe la trazabilidad del cierre"


def test_cada_criterio_es_una_pregunta_binaria():
    for cid, pregunta in TODOS:
        assert cid.startswith(("GATE-", "R-")), f"'{cid}': un criterio sin prefijo de capa no se puede auditar"
        assert "?" in pregunta, f"'{cid}': un criterio que no es una pregunta no es una rúbrica"


def test_la_puerta_y_la_revision_no_comparten_ids():
    puerta = {c[0] for c in CRITERIOS_PUERTA}
    revision = {c[0] for c in CRITERIOS_REVISION}
    assert puerta.isdisjoint(revision)


def test_la_puerta_es_mas_pequena_que_la_revision():
    # La puerta solo tiene lo que se puede automatizar en código; el criterio
    # de juicio vive en la revisión. Si la puerta crece sin control, se
    # convierte en una lista de prohibiciones que se aprende a esquivar.
    assert len(CRITERIOS_PUERTA) <= len(CRITERIOS_REVISION)


def test_las_categorias_de_decision_no_estan_vacias():
    assert CATEGORIAS_DECISION, "sin categorías no hay registro de decisiones"
    assert all(isinstance(c, str) and c for c in CATEGORIAS_DECISION)


# -- capa Java (JAVA-014a) -----------------------------------------------------


def test_rubrica_java_incluye_criterios_de_dominio():
    from agents.rubric import criterios_revision

    java = criterios_revision("java")
    ids = {c[0] for c in java}
    for esperado in ("R-J1", "R-J2", "R-J3", "R-J4", "R-J5"):
        assert esperado in ids, f"falta el criterio Java {esperado}"


def test_rubrica_python_no_incluye_criterios_java():
    from agents.rubric import criterios_revision

    assert criterios_revision("python") == CRITERIOS_REVISION
    assert not any(c[0].startswith("R-J") for c in criterios_revision("python"))


def test_rubrica_java_conserva_la_base_y_no_repite_ids():
    from agents.rubric import criterios_revision

    java = criterios_revision("java")
    ids = [c[0] for c in java]
    assert set(c[0] for c in CRITERIOS_REVISION).issubset(ids)
    assert len(ids) == len(set(ids)), "un id duplicado rompe la trazabilidad"


def test_criterios_java_son_preguntas_binarias():
    from agents.rubric import CRITERIOS_REVISION_JAVA

    for cid, pregunta in CRITERIOS_REVISION_JAVA:
        assert cid.startswith("R-J"), f"'{cid}': prefijo de dominio incorrecto"
        assert "?" in pregunta, f"'{cid}': un criterio que no es pregunta no es rúbrica"
