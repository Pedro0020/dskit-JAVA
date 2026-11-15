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
