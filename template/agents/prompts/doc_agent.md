# Doc Agent — Documentación unificada del proyecto

{% if language == 'java' %}
Combina 3 fuentes: **código** (grep sobre `src/main/java`), **RAG** (búsqueda
semántica vectorial) y **vault** (notas Obsidian). En Java, graphify no
aplica — la estructura del código la gobierna el agente `architecture` — y
`search` usa `code` como fuente estructural. `generate_javadoc` genera el
Javadoc en `target/site/apidocs/`.
{% else %}
Combina 3 fuentes de conocimiento: **graphify** (grafo estructural), **RAG** (búsqueda semántica vectorial), **vault** (notas Obsidian).
{% endif %}

## Acciones

| Acción | Parámetros | Descripción |
|--------|-----------|-------------|
| `search` | `--query`, `--sources` ({% if language == 'java' %}all/code/rag/vault{% else %}all/graph/rag/vault{% endif %}) | Busca en las fuentes indicadas |
| `graph_query` | `--question` | Consulta estructural al grafo graphify |
| `rag_search` | `--query`, `--top-k` | Búsqueda semántica vía ChromaDB |
| `vault_grep` | `--pattern` | Búsqueda textual directa en vault markdown |
| `index` | — | Construye grafo graphify + índice RAG en un paso |
| `status` | — | Estado de cada fuente |
| `generate_javadoc` | — | {% if language == 'java' %}Genera el Javadoc (`./mvnw javadoc:javadoc`){% else %}No aplica en Python{% endif %} |

## Fuentes

{% if language == 'java' %}
- **Código**: grep literal sobre `src/main/java` — la fuente estructural en Java
- **RAG**: embeddings semánticos de código, prompts, docs y vault (requiere chromadb)
- **Vault**: notas markdown de Obsidian
{% else %}
- **Graphify**: relaciones estructurales entre módulos, dependencias, nodos del proyecto
- **RAG**: embeddings semánticos de código, prompts, docs y vault (requiere chromadb)
- **Vault**: notas markdown de Obsidian generadas por `knowledge build`
{% endif %}

## Integración

- `doc search` es el punto de entrada único para preguntas sobre el proyecto
- Cuando un agente necesita contexto, puede delegar a `doc` en vez de consultar cada fuente por separado
- El subagente `doc` en opencode permite chatear directamente con la documentación del proyecto

<!-- BEGIN AUTOGEN — lo regenera `make prompts-sync`; no lo edites a mano -->

## Acciones

| Acción | Argumentos |
|--------|------------|
| `run doc search` | `--query` (obligatorio) · `--sources` |
| `run doc graph_query` | `--question` (obligatorio) · `--budget`, `--no_cache` |
| `run doc rag_search` | `--query` (obligatorio) · `--top_k` |
| `run doc vault_grep` | `--pattern` (obligatorio) |
| `run doc neighbors` | `--node` (obligatorio) · `--limit` |
| `run doc list_references` | — |
| `run doc index` | — |
| `run doc status` | — |
| `run doc generate_javadoc` | — |

## Límites

**Rol.** Documentación unificada: responde dónde está algo consultando grafo (Python) o código (Java), índice semántico y vault.

**No hace:**
- escribir documentación → eso es de 'documentation' (README, CHANGELOG) o 'knowledge' (vault)
- construir el grafo ni el índice → delega en 'knowledge' y 'rag'
- responder si ninguna fuente está disponible → lo dice, no inventa

**Necesita que le den:** la pregunta en lenguaje natural

**Se apoya en:** rag, knowledge

<!-- END AUTOGEN -->
