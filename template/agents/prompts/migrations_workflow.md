# Workflow — Migraciones (Flyway/Liquibase, Java)

Pipeline del dominio migraciones. Dueño: agente `migrations`
(`src/main/resources/db/migration/` o `db/changelog/`).

## Flujo

1. **Crear**: `run migrations create --name <desc>` — numera la siguiente
   `V<n>__<desc>.sql` con el prefijo correcto (nunca a mano).
2. **Validar**: `run migrations validate` — convención de nombres, versiones
   crecientes sin duplicados y **checksums** (el workspace del agente
   registra el hash; una edición posterior se detecta).
3. **Estado**: `run migrations status`.
4. **Revertir**: `run migrations undo --target V<n>__*.sql` — solo con script
   de rollback `U<n>__*.sql` previo.

## Reglas duras (no negociables)

- **Una migración ya aplicada NO se edita.** Checksum cambiado → crear
  `V<n+1>`, nunca reescribir `V<n>`.
- **Sin out-of-order**: el orden es estrictamente creciente.
- **Undo destructivo exige rollback**: sin `U<n>__*.sql`, el undo se rechaza
  con `needs`.
- La aplicación real contra la BD es del build (`./mvnw flyway:migrate`) o del
  humano — el agente no toca la BD de producción.

## Evidencia

```bash
uv run --no-project python -m agents --json run migrations validate
uv run --no-project python -m agents --json run migrations create --name add_users
```

Criterio de backlog: "migración aplicada limpiamente en base vacía y en base
con datos" — evidencia: `./mvnw verify` con el datasource de test.
