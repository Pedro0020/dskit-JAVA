# Workflow — Arquitectura (ArchUnit, Java)

Pipeline del dominio arquitectura. Dueño: agente `architecture` (tests
ArchUnit + límites de capas).

## Flujo

1. **Detección rápida (estática)**: `run architecture check_layers` — un
   controller que importa `…repository…` directamente es la violación
   canónica (la capa service es el único camino).
2. **Puerta real**: `run architecture run_architecture_tests` — ejecuta
   `./mvnw test -Dtest=*Architecture*Test` (el template trae
   `ArchitectureTest.java` con las capas Controller→Service→Repository y
   sin ciclos; `allowEmptyShould(true)` tolera un proyecto recién generado
   y empieza a morder con la primera clase).
3. **Ausencia de test**: `run architecture check_archunit_test` — con
   `use_archunit=true`, sin `*Architecture*Test.java` es un fallo.
4. **Memoria estructural**: `run architecture build_vault` (o `make knowledge`)
   regenera `docs/vault/`: IA_index con el mapa de capas, arquitectura con
   dependencias y violaciones, fichas de dominio, grafo mermaid y fichas de
   agentes. Es determinista y offline. Con `use_graphify=true`,
   `run architecture enrich_graphify` añade la capa semántica (GEMINI_API_KEY).

## Reglas duras (no negociables)

- **Un recurso, un dueño**: el agente no arregla la violación — reporta el
  import exacto y el implementer mueve la lógica al service.
- Multi-módulo: la propiedad por módulo vive en los contratos; `touched_files`
  acepta rutas por módulo.

## Evidencia

```bash
uv run --no-project python -m agents --json run architecture run_architecture_tests
```

Caso canónico con test: dependencia controller→repository directa viola el
límite y el test ArchUnit del template lo detecta.
