# dskit-JAVA

Template y arnés de desarrollo para proyectos **Java con Spring Boot y Spring
Batch**. Puede:

- crear un proyecto nuevo con Maven o Gradle;
- incorporar el arnés a un proyecto Java existente sin reemplazar su código;
- gobernar el trabajo de agentes de IA con backlog, permisos, revisión y
  evidencia verificable;
- aplicar controles específicos para APIs, jobs batch, migraciones, seguridad,
  arquitectura y observabilidad.

[![CI](https://github.com/Pedro0020/dskit-JAVA/actions/workflows/ci.yml/badge.svg)](https://github.com/Pedro0020/dskit-JAVA/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

> dskit no es un chatbot ni sustituye al equipo. Es un plano de control que
> hace que el trabajo propuesto por agentes deje rastros y pase verificaciones
> reproducibles.

## ¿Qué problema resuelve?

Un asistente puede escribir código que parece correcto y aun así dejar:

- un job batch no reiniciable;
- una migración incompatible con producción;
- endpoints sin protección;
- dependencias entre capas no deseadas;
- tests que cubren líneas, pero no comportamiento.

dskit añade una puerta técnica (`init.sh`), un backlog con criterios de
aceptación, agentes especializados y una definición de `done` que exige
evidencia real.

## Cómo está construido: capas y responsabilidades

La idea central es separar **el producto Java** de **las herramientas que
gobiernan su desarrollo**. Esta separación permite usar dskit tanto para crear
una aplicación nueva como para incorporarlo a una aplicación que ya existe.

```text
┌─────────────────────────────────────────────────────────────┐
│ Asistente de IA                                             │
│ .opencode/agents/ · .claude/agents/                         │
│ Decide qué investigar, implementar o revisar                 │
└──────────────────────────────┬──────────────────────────────┘
                               │ delega acciones
┌──────────────────────────────▼──────────────────────────────┐
│ Plano de control                                             │
│ agents/                                                      │
│ Ejecuta comandos deterministas, aplica permisos y contratos  │
└──────────────────────────────┬──────────────────────────────┘
                               │ lee y actualiza
┌──────────────────────────────▼──────────────────────────────┐
│ Gobierno del trabajo                                         │
│ harness/ · init.sh                                           │
│ Backlog, estado, evidencia y puerta de calidad               │
└──────────────────────────────┬──────────────────────────────┘
                               │ verifica
┌──────────────────────────────▼──────────────────────────────┐
│ Producto                                                     │
│ src/ · pom.xml/build.gradle · src/test/                      │
│ Código Java, configuración, tests y dependencias             │
└─────────────────────────────────────────────────────────────┘
```

### 1. Código de aplicación: `src/`

Es el producto que el equipo quiere construir y operar. dskit no decide su
modelo de dominio ni lo sustituye:

| Ruta | Función | Por qué existe |
|---|---|---|
| `src/main/java/` | Código Java de producción | Contiene casos de uso, controllers, servicios, repositorios, jobs y configuración |
| `src/main/resources/` | `application.yml`, perfiles y migraciones | Separa configuración y esquema de base de datos del código |
| `src/test/java/` | Tests unitarios, de integración y de contexto | Demuestra que el comportamiento funciona, no solo que compila |
| `src/test/resources/` | Configuración aislada de tests | Evita que una prueba use accidentalmente recursos de producción |

En un proyecto web, el flujo habitual es `controller → service →
repository`. En un proyecto Batch, el flujo es `job → step → reader /
processor / writer`. En un proyecto web + Batch conviven ambos, pero deben
compartir el dominio sin mezclar responsabilidades.

### 2. Build y dependencias: `pom.xml` o `build.gradle`

El build es la fuente de verdad del proyecto Java:

- declara Spring Boot, Spring Batch y las librerías del dominio;
- compila el código;
- ejecuta los tests;
- aplica formato, cobertura y análisis estático;
- genera artefactos reproducibles.

Los wrappers (`mvnw` o `gradlew`) fijan la versión de la herramienta. Por eso
se usan en CI y en `init.sh`: el resultado no depende de lo que tenga instalado
globalmente cada desarrollador.

`Makefile` no reemplaza al build. Es una fachada con nombres fáciles de
recordar (`make test`, `make verify`, `make security`) que delega el trabajo en
Maven, Gradle o en un agente concreto.

### 3. Puerta de entrada: `init.sh`

`init.sh` es el punto de control antes de que un agente empiece a modificar el
proyecto. Comprueba, en este orden:

1. que Python y `uv` están disponibles para el plano de control;
2. que existe el JDK requerido;
3. que existe el wrapper de Maven o Gradle;
4. que están los ficheros mínimos del arnés;
5. que el backlog es válido;
6. que existe código y al menos un test Java;
7. que el build completo termina correctamente.

```bash
./init.sh          # comprobación completa
./init.sh --quick  # estructura, sin ejecutar el build
./init.sh --json   # resultado para herramientas y agentes
```

`--quick` sirve para diagnosticar estructura, pero no es suficiente para cerrar
una feature. La regla importante es: **si la puerta falla, el agente no debe
seguir implementando sobre un proyecto roto**.

### 4. Gobierno del trabajo: `harness/`

`harness/` contiene el estado de trabajo, no el código de negocio:

| Fichero | Contenido | Uso |
|---|---|---|
| `featureslist.json` | Backlog, dependencias, criterios y estados | Define qué se puede hacer después |
| `progress/current.md` | Feature activa | Permite retomar trabajo interrumpido |
| `progress/history.md` | Historial append-only | Conserva decisiones y evidencia de cierres |
| `progress/<agente>-<id>.md` | Informes de agentes | Evita depender de la memoria de una conversación |
| `memory.md` | Memoria operativa del proyecto | Guarda contexto estable para el arnés |

El backlog es útil porque convierte “mejora la aplicación” en una tarea
verificable: “el endpoint devuelve 400 para un payload inválido” o “relanzar el
job no duplica filas”.

El ciclo se ejecuta con el agente `harness`:

```bash
uv run --no-project python -m agents --json run harness next
uv run --no-project python -m agents --json run harness start --id VERIFY-001
uv run --no-project python -m agents --json run harness status
```

Solo `harness` debe escribir el backlog y el progreso. Así se evita que un
agente cambie el estado manualmente para aparentar que una tarea está
terminada.

### 5. Plano de control ejecutable: `agents/`

`agents/` contiene Python, pero no es la aplicación Java. Es la capa que
ejecuta operaciones repetibles sobre ella:

```text
agents/
├── agents/       implementaciones de agentes
├── tools/        operaciones pequeñas y deterministas
├── core/         ciclo común y registro
├── evals/        pruebas del propio arnés
├── prompts/      skills y workflows
├── contracts.py  dueño, rutas permitidas y acciones
├── permissions.py política de confirmaciones
├── context.py    rutas y configuración del proyecto
└── cli.py        interfaz de comandos
```

Cada agente tiene una responsabilidad concreta. Por ejemplo:

- `test` ejecuta y analiza tests;
- `dependency` revisa dependencias;
- `migrations` inspecciona Flyway/Liquibase;
- `batch` revisa jobs y restartability;
- `security` revisa exposición y configuración de seguridad;
- `architecture` aplica reglas de capas y construye el vault;
- `ops` revisa health, métricas y trazas.

La forma general de uso es:

```bash
uv run --no-project python -m agents list
uv run --no-project python -m agents describe migrations
uv run --no-project python -m agents --json run migrations validate
```

El resultado estructurado (`--json`) permite que otro agente lo consuma sin
tener que interpretar texto libre.

### 6. Agentes de razonamiento: `.opencode/` y `.claude/`

Estos directorios contienen instrucciones en Markdown para asistentes:

- `lider`: coordina el ciclo y decide qué agente debe actuar;
- `explorer`: investiga sin modificar código;
- `implementer`: implementa una feature y sus tests;
- `reviewer`: revisa diff, criterios y evidencia.

No son los ejecutores de seguridad. Un prompt puede proponer una acción, pero
la acción real pasa por `agents/`, contratos y permisos. Esta separación es
importante porque un modelo puede equivocarse o interpretar mal una
instrucción; el código determinista sigue siendo la última autoridad.

`make assistants-sync` mantiene los espejos para otros asistentes, y
`make skills` copia los workflows disponibles a `.opencode/skills/`.

### 7. Calidad por dominio

Los agentes Java existen porque un test genérico no detecta todos los fallos
importantes:

| Capa | Qué protege | Ejemplo de fallo que busca |
|---|---|---|
| API | Contrato HTTP | Cambiar una respuesta o aceptar datos inválidos sin detectarlo |
| Batch | Semántica operacional | Job no reiniciable, writer no idempotente o chunk sin transacción |
| Migrations | Evolución de datos | Editar una migración ya aplicada o romper checksums |
| Security | Frontera de confianza | Actuator público, JWT mal configurado o CORS excesivo |
| Architecture | Dependencias internas | Controller accediendo directamente al repository |
| Ops | Operación en producción | Servicio sin health real, métricas o `traceId` |

La finalidad no es añadir burocracia: es revisar los fallos que suelen aparecer
después de desplegar, cuando corregirlos es más caro.

### 8. Memoria y conocimiento

Hay tres memorias con funciones distintas:

- `harness/progress/`: qué trabajo está ocurriendo ahora;
- `agents/workspace/`: artefactos temporales de los agentes;
- `docs/vault/`: conocimiento estable de la arquitectura y los dominios.

`make knowledge` regenera el vault estructural a partir del código. Si se
activa RAG, `make index-rag` permite buscar sobre código, documentación, vault
e histórico. El RAG ayuda a encontrar información; no concede permisos ni
convierte contenido externo en instrucciones.

### 9. Seguridad y permisos

Los agentes clasifican acciones por riesgo:

- acciones reversibles: se ejecutan directamente;
- acciones destructivas: requieren confirmación;
- acciones críticas: requieren confirmar el objetivo exacto.

`policy_guard.py` añade una protección frente a comandos peligrosos del
asistente, como borrar fuera del proyecto, leer credenciales o hacer
`git push`. No es un sandbox: el aislamiento real debe proporcionarlo el
entorno de ejecución.

### 10. CI

`.github/workflows/ci.yml` valida dos cosas diferentes:

1. el template genera archivos sintácticamente válidos en sus combinaciones;
2. proyectos Java reales pasan build, tests, puerta y evals del arnés.

También se prueban ejemplos de adopción web y Batch. Esto evita que una
modificación del template funcione para un proyecto nuevo y rompa el caso de
uso más importante: incorporarlo a un proyecto existente.

## Dos formas de usarlo

### 1. Crear un proyecto nuevo

Requisitos:

- JDK 17, 21 o 25;
- Python 3.10+ y [uv](https://docs.astral.sh/uv/) para el arnés;
- [Copier](https://copier.readthedocs.io/);
- Bash (Git Bash o WSL en Windows);
- Docker solo para Testcontainers u otros servicios que lo requieran.

```bash
pip install copier
copier copy --trust gh:Pedro0020/dskit-JAVA mi-proyecto
cd mi-proyecto

./mvnw verify       # Maven
# o ./gradlew build # Gradle
./init.sh
```

El perfil interactivo permite elegir:

| Opción | Valores |
|---|---|
| Build | Maven o Gradle |
| Stack | Spring Boot web, Spring Batch o web + Batch |
| Java | 17, 21 o 25 |
| Base de datos | H2, PostgreSQL, MySQL o ninguna |
| Migraciones | Flyway, Liquibase o ninguna |
| Extras | seguridad, Testcontainers, PIT, ArchUnit, observabilidad, RAG y SDD |

### 2. Adoptar un proyecto existente

Esta es la opción adecuada si ya tienes una aplicación Spring Boot o Spring
Batch y no quieres regenerarla. El adoptador instala el plano de control, pero
deja intactos:

```text
src/
pom.xml o build.gradle
mvnw / gradlew
tests y configuración de la aplicación
```

Clona dskit y ejecuta:

```bash
git clone https://github.com/Pedro0020/dskit-JAVA.git
cd dskit-JAVA

uv run python tools/adopt.py /ruta/a/mi-proyecto --dry-run
uv run python tools/adopt.py /ruta/a/mi-proyecto
```

Detecta Maven/Gradle, versión de Java, paquete base, stack web/batch, base de
datos y migraciones. Si algo no puede detectarse, hay que proporcionarlo
explícitamente:

```bash
uv run python tools/adopt.py mi-proyecto \
  --java-version 21 \
  --base-package com.empresa.pedidos \
  --framework spring-boot-web+batch
```

El proyecto debe compilar y tener tests en verde antes de adoptarlo. Si ya
tiene un `Makefile`, los targets de dskit quedan separados en `dskit.mk`:

```make
include dskit.mk
```

La adopción crea `.copier-answers.yml`, conserva el build existente y genera un
backlog de adopción adecuado al stack:

- `JOB-001` para proyectos con Spring Batch;
- `API-001` para proyectos web;
- ambos cuando el proyecto combina web y Batch.

## El arnés de desarrollo

El flujo básico es:

```text
init.sh → backlog → explorar → implementar → revisar → evidencia → done
```

Antes de empezar:

```bash
./init.sh
```

Si la puerta falla, el agente debe parar. Para consultar el proyecto:

```bash
make backlog
make agents-list
make agents-doctor
make agents-eval
```

Una feature solo puede marcarse como `done` cuando:

1. `init.sh` termina correctamente;
2. los criterios de aceptación están satisfechos;
3. existe salida real de los comandos de verificación;
4. el reviewer no la ha rechazado;
5. el cierre queda registrado en `harness/progress/history.md`.

## Agentes disponibles

### Núcleo

`harness`, `git`, `test`, `review`, `doctor`, `plan`, `env`, `cicd`, `make`,
`doc`, `documentation`, `dependency`, `secrets` y `memory`.

### Dominios Java

| Agente | Responsabilidad |
|---|---|
| `api` | Controllers, DTOs, validación, versionado y errores HTTP |
| `batch` | Jobs, chunks, transacciones, reintentos, idempotencia y restartability |
| `migrations` | Flyway/Liquibase, orden, checksum y rollback |
| `security` | Spring Security, JWT/CORS y exposición de Actuator |
| `architecture` | Capas, ciclos y reglas ArchUnit |
| `ops` | Health checks, métricas, trazas y observabilidad |

### Extras opcionales

- `rag`: búsqueda sobre código, documentación, vault e histórico;
- `mutation`: PIT y métrica CRAP para comprobar la calidad de los tests;
- `graphify`: enriquecimiento semántico opcional del vault.

Lista los agentes realmente instalados con:

```bash
uv run --no-project python -m agents list
uv run --no-project python -m agents describe batch
```

## Comandos habituales

| Comando | Uso |
|---|---|
| `./init.sh` | Comprueba entorno, arnés, build y tests |
| `make test` | Ejecuta tests |
| `make verify` | Build completo, formato y cobertura |
| `make check` | Build más puerta del arnés |
| `make lint` | Spotless y PMD |
| `make typecheck` | Error Prone y NullAway en Maven |
| `make security` | Trivy y SBOM |
| `make mutation TARGET=...` | Mutation testing con PIT |
| `make batch-run JOB=...` | Ejecuta un job Batch |
| `make migrations` | Consulta el estado de migraciones |
| `make context-check` | Comprueba el ApplicationContext |
| `make knowledge` | Regenera `docs/vault/` |
| `make index-rag` | Indexa el proyecto en el RAG |

Los targets dependen del build seleccionado. Gradle tiene verificados
build, tests, cobertura y formato; algunas comprobaciones avanzadas siguen
siendo específicas de Maven.

## Estructura de un proyecto generado

```text
mi-proyecto/
├── src/main/java/              código Java
├── src/test/java/              tests
├── src/main/resources/         configuración y migraciones
├── agents/                     plano de control Python
├── harness/                    backlog y progreso
├── .opencode/agents/           agentes de razonamiento
├── init.sh                     puerta de entrada
├── Makefile                    fachada de comandos
└── pom.xml o build.gradle      build de la aplicación
```

## Documentación

- [AGENTS.md](AGENTS.md): protocolo operativo del arnés.
- [CREDITS.md](CREDITS.md) y [NOTICE](NOTICE): origen y atribución.
- [SECURITY.md](SECURITY.md): límites y recomendaciones de seguridad.
- [CONTRIBUTING.md](CONTRIBUTING.md): contribución al repositorio.

## Licencia y origen

Apache-2.0. dskit-JAVA es una obra derivada de
[dskit](https://github.com/cacelass/dskit), creado por `cacelass`. Se conservan
la licencia y la atribución exigidas por el proyecto original. Consulta
[CREDITS.md](CREDITS.md) y [NOTICE](NOTICE).
