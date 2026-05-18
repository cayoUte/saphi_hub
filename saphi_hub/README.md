# Acadex API · Sprint 1

## Levantar el entorno

```bash
cp .env.example .env        # ajusta las variables
docker compose up --build   # levanta api + postgres
```

## Migraciones

```bash
docker compose exec api alembic revision --autogenerate -m "init"
docker compose exec api alembic upgrade head
```

## Endpoints disponibles

| Método | Ruta | Historia |
|--------|------|----------|
| POST | /auth/github | US-01 · inicia OAuth |
| GET  | /auth/github/callback | US-01 · callback |
| GET  | /auth/me | US-01 · perfil autenticado |
| POST | /institutions | US-19 · solicitar vinculación |
| POST | /institutions/{id}/approve | US-26 · aprobar con checklist |
| POST | /institutions/{id}/reject | US-26 · rechazar |

## Docs interactivas

[http://localhost:8000/docs](http://localhost:8000/docs)
