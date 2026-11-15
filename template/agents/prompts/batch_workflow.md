# Workflow — Dominio Spring Batch (Java)

Pipeline del dominio batch: del ticket del backlog al job verificado en
producción. Dueño del dominio: agente `batch` (`src/main/java/**/batch/`).

## Flujo

1. **Validar antes de tocar**: `run batch validate_job` — autorun explícito,
   esquema `BATCH_*` (initialize-schema o migración), steps con chunk/tasklet.
2. **Ejecutar sobre dataset controlado**: `run batch run_job --job <nombre>` —
   evidencia real para `harness finish` (regla OMP-008: salida de comando, no
   "funciona").
3. **Fallo**: `run batch explain_failure --error "<stack>"` traduce los
   mensajes conocidos (job instance already exists, BATCH_* ausente,
   TransactionRequired).
4. **Estado**: `run batch checkpoint` — jobs, job por defecto, esquema.

## Reglas duras (no negociables)

- **Restartability**: un job que no se puede relanzar con nuevos parámetros
  no es un job — exige incrementer o job parameters distintos.
- **Idempotencia**: relanzar con los mismos parámetros NO duplica filas
  (unique constraints + writers idempotentes).
- **Transacciones**: writer/processor dentro del `PlatformTransactionManager`
  del step — un writer sin transacción es el caso canónico de rechazo del
  reviewer.
- El agente no toca entidades de dominio (→ `migrations`/implementer).

## Evidencia

```bash
uv run --no-project python -m agents --json run batch validate_job
uv run --no-project python -m agents --json run batch run_job --job demoJob
```

Rúbrica: un job con writer sin transacción → `harness finish` rechazado
(GATE-1 + R-criterios Java).
