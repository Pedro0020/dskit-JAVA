# Workflow — Observabilidad (Actuator/Micrometer, Java)

Pipeline del dominio observabilidad. Dueño: agente `ops` (Actuator +
Micrometer + Logback).

## Flujo

1. **Cableado**: `run ops check_observability` — las cuatro piezas: actuator
   en el classpath, registry Prometheus, health en la config y `traceId` en
   el pattern de logs (MDC).
2. **Métricas de batch**: `run ops check_batch_metrics` — cada clase batch
   debe declarar `@Timed`/`MeterRegistry` (duración y tasa de error por step).

## Reglas duras (no negociables)

- **Sin health check real, no hay `done`**: la rúbrica del arnés exige algo
  más que `contextLoads` — el health debe estar cableado y expuesto.
- `use_observability=false` → el proyecto nace sin el extra: es un aviso,
  no un fallo (pero cierra features en rojo según la rúbrica).
- El agente no instrumenta código de negocio: reporta qué clases no miden.

## Evidencia

```bash
uv run --no-project python -m agents --json run ops check_observability
```

Rúbrica: servicio sin health check real → `harness finish` rechazado.
