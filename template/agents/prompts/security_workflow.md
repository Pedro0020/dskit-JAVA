# Workflow — Seguridad (Spring Security, Java)

Pipeline del dominio seguridad. Dueño: agente `security` (config Spring
Security + `application.yml`).

## Flujo

1. **Gate de exposure**: `run security check_actuator_exposure` — en el perfil
   base/producción, `management.endpoints.web.exposure.include` no puede ser
   `*` ni incluir endpoints sensibles (`env`, `beans`, `configprops`,
   `heapdump`...). Es una familia real de CVEs.
2. **JWT**: `run security check_jwt` — starter resource-server + issuer-uri.
3. **Secretos**: `run security scan_hardcoded_secrets` — literales en
   `application*.yml` que deberían ser `${...}`.

## Reglas duras (no negociables)

- **Nunca loguear ni commitear secretos** (colabora con `secrets`; la
  redacción ya tapa credenciales antes del log de auditoría).
- Los placeholders `${...}` no se juzgan estáticamente: se devuelve aviso
  "verifica en producción", no un veredicto.
- El agente solo lee y reporta: rotar/borrar secretos es decisión del humano.

## Evidencia

```bash
uv run --no-project python -m agents --json run security check_actuator_exposure
```

Rúbrica: exposure sensible en producción → `harness finish` rechazado.
