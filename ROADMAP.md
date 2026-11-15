# Roadmap — dskit (backlog del template)

Backlog propio de dskit: las mejoras al *template* y a su sistema de agentes.
Sigue el formato del arnés (ID, título, criterios de aceptación) y la regla
del `lider`: primero al backlog, después se implementa con TDD y evidencia.

## Pendientes

### JAVA-001..JAVA-015 — Adaptación del arnés a Java (Spring Boot / Spring Batch)

Spec con decisiones y criterios: `SPEC-JAVA.md`. Estado y prioridad:

| ID | Tema | Estado | Prioridad |
|----|------|--------|-----------|
| JAVA-001 | Template copier Java (Maven, Spring Boot/Batch, H2, Flyway, wrapper) | Hecha | — |
| JAVA-001b | Build tool Gradle | Hecha (fase 1) | — |
| JAVA-002 | Puerta `./mvnw verify` + `contextLoads` | Hecha | — |
| JAVA-003 | Backlog semilla Java | Hecha | — |
| JAVA-004 | Prompts Java (lider/explorer/implementer/reviewer) | Hecha (004a–d) | — |
| JAVA-005a | Fixes language-aware (commit/doctor/env/untracked) | Hecha | — |
| JAVA-005b | Reescritura y poda de agentes (test/dependency/cicd/make/doc/plan) | Hecha | — |
| JAVA-005c | Reescritura JVM de refactor y graph (hueco del SPEC §3.5) | Hecha (excluidos en Java) | — |
| JAVA-006 | Agente `batch` | Hecha | — |
| JAVA-007 | Agente `migrations` | Hecha | — |
| JAVA-008 | Agente `security` | Hecha | — |
| JAVA-009 | Agente `api` Spring | Hecha | — |
| JAVA-010 | Agente `architecture` (ArchUnit) | Hecha | — |
| JAVA-011 | Agente `ops` / observabilidad | Hecha | — |
| JAVA-012 | Pipeline de calidad JVM: JaCoCo + Spotless (fase A) | Hecha | — |
| JAVA-012b | PIT + Error Prone + Trivy/SBOM (fase B) | Hecha | — |
| JAVA-012c | Fachada de calidad ampliada (migrations/batch-run/context-check/index-rag/knowledge + PMD en lint) | Hecha | — |
| JAVA-013 | CI Java del template + `smoke-java` | Hecha | — |
| JAVA-013b | CI Java ampliado (matriz JDK, evals del arnés en CI, SBOM+Trivy por push, artefacto PIT) | Hecha | — |
| JAVA-014 | Rúbrica Java (checks en `init.sh` + R-criterios) | Hecha (014a–c) | — |
| JAVA-015 | DX: reviewer como PR check, IntelliJ, fricción | Hecha | — |
| JAVA-016 | Memoria estructural Java: vault + grafo determinista + graphify opcional | Hecha | — |
| — | Release/publish del artefacto (GitHub Packages / Maven Central) | Descartado (decisión) | — |
| — | Eliminar el árbol Python | Hecha | — |
| — | Segunda ronda E2E (Postgres real, JDK 21, `copier update`) | Hecha | — |

Hitos: **H0** completado (backlog Java, fixes language-aware, v2.0.0);
**H1** completado (fase A + CI + fase B de calidad + poda/reescritura de
agentes + dominios Java); **H2** completado (prompts Java, CI ampliado,
rúbrica, DX, memoria estructural, Gradle fase 1, E2E JDK 21/Postgres/update y
template Java-only). Pendiente: Gradle fase 2 (otra versión) y JAVA-015 no
bloqueante (IntelliJ queda documentado en el README del proyecto generado).

Decisiones previas: plano de control Python + template Java (sin port a JVM),
núcleo de gobierno intacto, RAG no se toca. Los dominios críticos
(transacciones, semántica batch, migraciones, observabilidad, concurrencia) se
diseñan *con* el template, no después — son los que deciden si el arnés da
confianza real o falsa.

### Plan detallado de lo pendiente (Java)

> **Estado (15 Nov 2026): implementado.** 004a–d, 005c (refactor/graph
> excluidos en Java), 012c, 013b, 014a–c, 015 y 016 están hechos y verificados
> con renders limpios. Gradle queda en fase 1 (la fase 2 se hará en otra
> versión); release/publish descartado por decisión; el árbol Python se
> eliminó (template Java-only); el E2E con JDK 21 y `copier update` están
> verificados.

Desglose accionable de la auditoría del 15 Nov 2026 sobre un render Java
limpio: el build, la cobertura, el CI y los evals están en verde; lo que faltaba
era la **coherencia de los prompts** y la capa de gobierno específica de Java.

#### JAVA-004a — Prompts de los agentes que razonan
- `.opencode/agents/{lider,explorer,implementer,reviewer}.md` con
  condicionales `{% if language == 'java' %}`: rutas `src/main/java/` y
  `./mvnw verify` en lugar de `data/`/`pytest`; `implementer` con DI por
  constructor, `@Transactional`, records; `reviewer` con R-criterios Java
  (N+1, transacciones en writers, idempotencia/restartability, Bean
  Validation, `@ControllerAdvice`).
- `explorer.md` no puede ejemplificar delegaciones en `data` (podado en
  Java): ejemplos con `architecture`, `migrations`, `batch` y rutas `.java`.
- Los espejos `.claude/agents/*` se regeneran con `make assistants-sync`.

#### JAVA-004b — Documentación del plano de control
- `.opencode/agents/doc_agent.md`: en Java no hay Graphify — la fuente
  estructural es `code` (grep `src/main/java`).
- `agents/README.md`: dejar de describir `DataAgent`/`pyproject.toml` como
  parte del proyecto Java; tabla de agentes por lenguaje.

#### JAVA-004c — Workflows por dominio en el render Java
- `_exclude`: `data_workflow.md`, `ml_workflow.md` y `rag_workflow.md` no se
  copian cuando `language == 'java'` (los dominios no existen).
- `dev_workflow.md` y `harness_workflow.md`: ejemplos Java (`./mvnw verify`,
  `src/main/java/...`, `run batch ...`) detrás de condicionales.

#### JAVA-004d — Restos cosméticos
- `harness/featureslist.json` `$comment`: quitar "entrenando un modelo".
- `agents_reference.md`: las filas Python (data/ml/notebook) no se muestran
  en un render Java.

#### JAVA-005c — Reescritura JVM de refactor y graph (hueco del SPEC §3.5) — POSPUESTA
El SPEC lista `refactor` y `graph` entre los 10 agentes a reescribir; el
ROADMAP solo trackeó 6. Decisión pendiente: (a) reescribirlos para Java
(refactor: extracción de métodos/records/campos; graph: JDeps/ArchUnit) o
(b) excluirlos en renders Java y documentar la decisión. Nota: `graph`
(figuras ML) no tiene relación con la memoria del proyecto — la memoria va
en JAVA-016. Hasta decidir, no cuentan como hechos.

#### JAVA-014a — R-criterios Java en `agents/rubric.py`
- `CRITERIOS_REVISION` con la capa Java: transacciones (límites,
  auto-invocación), idempotencia/restartability batch, N+1, versionado de
  API, records/immutabilidad. GATE-1 ya ejecuta `mvnw verify` (cubre tests,
  cobertura y formato).

#### JAVA-014b — Casos canónicos con test
- Test que demuestre que `harness finish` rechaza un writer sin transacción
  y un job no reiniciable (métrica de éxito del SPEC §7).

#### JAVA-014c — Test de actuator exposure en el template
- Además del agente `security`, el template trae un test que falla si
  `management.endpoints.web.exposure.include` expone endpoints sensibles en
  el perfil base (criterio del SPEC §3.8).

#### JAVA-013b — CI Java ampliado
- Matriz de JDKs en el workflow del template; pasos de evals del arnés
  (harness + contracts + routing) como el branch Python; SBOM + Trivy en
  cada push; informe PIT como artefacto. Sin release/publish (pospuesto).

#### JAVA-016 — Memoria estructural Java (vault + grafo determinista + graphify opcional)
El vault Obsidian es la memoria del proyecto en Python (IA_index + fichas de
agentes + grafo de conocimiento). En Java se replica en dos capas:

- **Núcleo determinista (sin llaves ni red)**: generador stdlib que produce
  `docs/vault/` con `00_META/IA_index.md` (mapa de paquetes/dominios),
  `01_PROYECTO/` (arquitectura, decisiones), `02_DOMINIOS/` (fichas de jobs,
  migraciones, endpoints), `04_VISUALIZACIONES/grafo_conocimiento.md` y
  `05_AGENTES/`. El grafo sale de jdeps + el parseo de anotaciones que ya
  hacen los agentes (`architecture`, `batch`, `migrations`, `api`).
  Regeneración: `make knowledge`. Los agentes leen IA_index al activarse;
  `doc search` ya grepea el vault.
- **graphify opcional (capa semántica)**: pregunta copier `use_graphify`
  (solo Java, off por defecto) + grupo uv `graphify` que instala
  `graphifyy[gemini]`. El mismo tooling existente (`graphify_tool`,
  `knowledge build`, `doc search`) enriquece el MISMO vault con la capa
  semántica del LLM (requiere GEMINI_API_KEY). No es el núcleo: el gate y
  la estructura no pueden depender de un LLM.
- Spike previo: confirmar que `graphifyy` indexa `.java` con calidad
  aceptable (1 render + 1 build del grafo).
- Complemento: `make index-rag` en la fachada Java (hoy rag_agent se
  renderiza pero el Makefile Java no expone el índice).

### OMP-007 — GStack: lock de pipeline

Dos `GStack.run()` concurrentes sobre el mismo árbol pueden pisarse los
cambios (uno commitea lo que el otro escribe). El pipeline toma un lock
exclusivo no bloqueante sobre `agents/workspace/gstack/.lock`.

**Criterios**
- `run()` toma `flock(LOCK_EX|LOCK_NB)`; si está tomado, devuelve
  `StackResult(success=False)` con el motivo, **sin ejecutar ningún paso**
- El lock se libera en `finally`; fallo al crear el lock (filesystem ro) deja
  pasar (fail-open, misma filosofía que `policy_guard`)
- `GStack(lock=False)` desactiva el bloqueo de forma explícita
- El evento queda anotado en `events.jsonl` (`pipeline_bloqueado`)
- Tests en `test_gstack_control.py`

### OMP-008 — Harness: la evidencia debe parecer salida de comando

`harness finish` aceptaba cualquier string no vacío como evidencia ("ok",
"hecho"). Ahora rechaza afirmaciones sueltas: la evidencia debe tener la
estructura de una salida de comando real (longitud y nº de palabras mínimos).
La verificación de que es *verdad* sigue siendo `init.sh` (gate); este check
solo obliga a documentar esa ejecución.

**Criterios**
- `_evidencia_plausible()`: rechaza texto < 24 chars o < 3 palabras
- `finish()` devuelve `success=false` + `needs` para "ok"/"hecho"/"los tests pasan"
- Tests existentes con `evidence="ok"` actualizados a salida real; nuevos
  tests de rechazo en `test_harness_agent.py`

### OMP-006 — Corpus: RL, metaheurísticas, modelos fundacionales y guardarraíles

Ampliar `docs/knowledge/` con los huecos de teoría profunda que el `lider` no
puede improvisar: aprendizaje por refuerzo, algoritmos genéticos / metaheurísticas
/ búsqueda, y modelos fundacionales (más allá de `llms-aplicados.md`). Añadir
nuevo fichero `ml/guardarraíles.md`.

**Criterios**
- `ml/reinforcement-learning.md`: MDP, value/policy iteration, DQN/PPO/SAC,
  off/on-policy, reward shaping, evaluación y su "cómo se rompe"
- `ml/metaheuristica.md`: algoritmos genéticos, recocido simulado, búsqueda
  local/global; cuándo usar frente a optimización basada en gradiente
- `ml/modelos-fundacionales.md`: pre-training, adapters, destilación,
  evaluación y coste de FMs — complementa, no duplica, a `llms-aplicados.md`
- `ml/guardarraíles.md`: capas de contención (frontera de entrada, filtros de
  salida, acciones limitadas, red teaming, monitoreo) — y referencia desde
  `fairness-y-seguridad.md`
- `docs/knowledge/index.md`, `sources.md` y `sources.json` registran los nuevos
  ficheros y sus topics/queries
- El RAG indexa los ficheros nuevos como `file_type: knowledge`

### OMP-001 — Git: split atómico de commits

`git` agent separa cambios no relacionados en commits atómicos ordenados
topológicamente; valida los tipos Conventional; excluye lock files; rechaza
ciclos. Inspirado en `omp commit`.

**Criterios**
- `git_tool` agrupa los cambios del árbol en áreas (fuente > tests > docs >
  config) y detecta conjuntos no relacionados
- Los lock files (`uv.lock`, `package-lock.json`…) quedan fuera del análisis
- El mensaje de cada commit pasa la validación de los 11 tipos Conventional
- El orden entre commits respeta dependencias (código antes que docs/tests)
- `--dry-run` propone el plan sin tocar nada; la ejecución real exige
  confirmación explícita (puerta de permisos)
- Los ciclos (un cambio que depende de otro incluido en un commit posterior)
  se rechazan antes de escribir nada

### OMP-002 — Memory: edición por id + scoping

`memory` agent gana `memory_edit` (update/forget/invalidate por id) y scope
(global/per-proyecto); los subagentes heredan la memoria del padre.
Inspirado en mnemopi.

**Criterios**
- `memory_edit --id <id> --action update|forget|invalidate` modifica el bank
  sin reescribir el resto
- El bank distingue scope `global` y `per-proyecto`; una búsqueda puede
  acotarse a uno
- Los subagentes lanzados por un agente heredan el scope del padre
- `memory status` refleja el scope y el número de entradas por kind

### OMP-003 — Reglas derivadas de fallos (patrón ttsr/omfg)

Documentar como patrón del arnés: una regla que solo cuesta cuando se viola,
derivada de un fallo real y validada contra el historial (habría disparado o
no). Inspirado en `ttsr`/`/omfg` de omp.

**Criterios**
- AGENTS.md documenta el patrón en "El arnés se automejora": regla → validar
  que habría disparado → registrar
- memory.md guarda las lecciones de omp.sh y los videos con qué adoptar y qué
  rechazar

### OMP-004 — Review: severidad y confianza en los hallazgos

`review` agent devuelve cada hallazgo con severidad P0-P3 y nivel de
confianza, y un veredicto correct/incorrect. Nada importante queda enterrado
en prosa. Inspirado en `/review` de omp.

**Criterios**
- Cada hallazgo de `review_package` lleva `severity` (P0-P3) y `confidence`
  (high/medium/low)
- El resultado incluye un veredicto y la lista ordenada por severidad
- Los tests cubren la asignación de severidad y el ordenado

### OMP-005 — RAG: extractores site-aware para URLs

`rag index_urls` detecta el dominio y extrae markdown estructurado con anclas
en vez de HTML genérico: GitHub (README/raw), Stack Overflow (pregunta +
respuestas) y arXiv (reutiliza `knowledge_tool`). Sin dependencias nuevas.

**Criterios**
- Una URL de GitHub/Stack Overflow/arXiv se indexa con estructura (título,
  secciones, código, enlaces) en lugar de texto plano
- El resto de URLs siguen usando el convertidor genérico actual
- Cada extractor es stdlib y está testado con HTML de ejemplo

### DOC-001 — Verificar el movimiento de la documentación a docs/

Cerrar la verificación del movimiento de `vault/` y `knowledge/` a `docs/`.

**Criterios**
- Render de prueba (estandar/completo) pasa `init.sh`, `make index-rag`,
  `rag search --file_type knowledge` y `doc vault_grep`
- `make docs` sigue compilando Sphinx
- Cero referencias de raíz a `vault/`/`knowledge/` fuera de `docs/` en el
  template renderizado

### DOC-002 — Lecciones de los videos y de omp.sh en memory.md

Registrar en `memory.md` el análisis de qué ideas encajan con la filosofía de
dskit (Pi, Oh-My-Pi, Oratomic-Caltech, Right-Harness, omp.sh) y cuáles se
descartan y por qué.

### OMP-010 — Trasgo: certeza como señal y codec §1 para ahorrar tokens

Incorporar de `jesusvilela/trasgo` (compresión de contexto en 3 ejemplos, sin
entrenar) las dos ideas que sobreviven la filosofía de dskit: la certeza
tipada (`μ.cert`) como puerta de cierre, y el packet compacto E/S/R/Δ/μ para
el handoff de subagentes. Solo se toca el flujo de agentes; **el RAG y el
corpus de papers no se tocan** (el usuario descarga papers a propósito).

**Criterios**
- `AgentResult.certainty` (0..1, default 1.0) retrocompatible; `dispatch`
  propaga la confianza del ruteo heurístico a la certeza del resultado
- `harness finish` rechaza cerrar si `certainty < 0.6` (explícito o heredado
  del último informe del reviewer), devolviendo `needs` — no cierra con dudas
- `harness record` acepta `--packet` (JSON §1 validado: ejes E/S/R/Δ/μ/§,
  `μ.rol` obligatorio, `μ.cert` 0..1) y lo escribe como frontmatter; la prosa
  sigue conviviendo como `--content`
- `harness next` resume el precedente con el packet (Δ + μ.cert) en vez del
  extracto crudo de 200 caracteres
- `audit` guarda `certainty` en cada entrada; `audit suggest` flagea "éxito
  con certeza baja" como señal de mejora
- `--json` omite `message` cuando `data` lo codifica (no pagar dos veces)
- Boot seed de 3 ejemplos en `harness_workflow.md`; espejo `.claude` sincronizado
- Tests: umbral en finish, validación de packet, propagación en dispatch,
  formato `--json`

### OMP-011 — Plan `scope`: entrevista → objetivo + tickets, sin PRD

Convertir la hoja en blanco del arranque (`references/00-objetivo.md` vacío,
backlog sin rellenar) en un formulario guiado. **No es un agente `product` ni
escribe el PRD** — el PRD vivo (`documentation update_prd`) ya nace del
objetivo + backlog y duplicarlo sería rehacer SCOPE-001 (ver lección en
memory.md). La entrevista adaptativa se implementa como acción nueva del
agente `plan`, que ya tiene toda la maquinaria (`needs`, `answer`, borrador).

**Criterios**
- `plan scope` devuelve las preguntas vía `needs` (pregunta, métrica de éxito
  con umbral numérico, datos de partida, criterio de parada — obligatorias;
  usuarios, alcance, riesgos — opcionales); nunca repite lo ya respondido y
  para en el mínimo
- `plan scope_answer` valida que la métrica sea numérica con umbral (el
  criterio #2 de SCOPE-001 — "que funcione bien" no pasa) y acepta
  `aceptar_riesgos`/`descartar_riesgos` para decidir los riesgos detectados
- **Detección de riesgos**: una heurística determinista identifica riesgos en
  las respuestas (login → SQLi, fuga de credenciales; pago → fraude; datos
  personales → GDPR...). `scope_commit` REHÚSA sembrar hasta que el usuario
  decide cada riesgo detectado; los aceptados se siembran como `RISK-NNN`
  "Mitigar: X", los descartados no
- `plan scope_commit` REHÚSA sin las respuestas obligatorias; escribe
  `references/00-objetivo.md` con el spec enriquecido y siembra el backlog en
  orden lógico (SCOPE-001 → RESEARCH-001 → EDA-001 → DATA-001 → FEAT-001 →
  MODEL-001, después las propuestas y los riesgos aceptados) delegando en
  `harness add` (idempotente)
- **Se propone solo**: la primera vez que `harness next` corre en un proyecto
  recién generado (sin `references/00-objetivo.md`), propone `run plan scope`
  — el ticket SCOPE-001 del backlog lo formaliza en su criterio
- El PRD no se entrevista: lo genera `documentation update_prd`, que ahora
  incluye la sección "Riesgos y mitigaciones" (vista de los tickets RISK-*)
- Tests en `test_plan_agent.py` y `test_documentation_agent.py`: detección de
  riesgos, gate de decisión obligatoria, sembrado solo de aceptados,
  no-duplicación, PRD con riesgos

## Cerradas

| ID | Título | Estado |
|----|--------|--------|
| DOC-001 | Verificar el movimiento de la documentación a docs/ | ✅ tests 606, renders OK, init.sh OK, RAG sin duplicados |
| OMP-001 | Git: split atómico de commits | ✅ 10 tests |
| OMP-002 | Memory: edición por id + scoping | ✅ 18 tests |
| OMP-003 | Reglas derivadas de fallos (patrón ttsr) | ✅ documentado en AGENTS.md + memory.md |
| OMP-004 | Review: severidad y confianza | ✅ 6 tests |
| OMP-005 | RAG: extractores site-aware | ✅ 14 tests |
| DOC-002 | Lecciones de los videos y de omp.sh en memory.md | ✅ memory.md |
| OMP-006 | Corpus: RL, metaheurísticas, modelos fundacionales y guardarraíles | ✅ 4 ficheros + refs corregidas + sources.json |
| OMP-010 | Trasgo: certeza como señal y codec §1 | ✅ 21 tests nuevos · 632 totales · CI verde |
| OMP-011 | Plan `scope`: entrevista → objetivo + tickets | ✅ 13 tests · detección de riesgos + gate de decisión · PRD con riesgos |
