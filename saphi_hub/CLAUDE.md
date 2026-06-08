# Skill: Typing de Infraestructura Auth

Cuando el usuario pida tipar la capa de infraestructura del módulo auth,
lee `infra-typing.md` y sigue el proceso en orden.

Archivos a modificar:
- app/auth/infrastructure/persistence/encryption.py
- app/auth/infrastructure/persistence/mappers.py
- app/auth/routes/router.py
- app/auth/infrastructure/github/adapter.py

Reglas inamovibles:
- Pydantic solo en adapter.py y router.py (boundaries externos)
- mappers.py solo necesita dict[str, Any] y cast de SQLAlchemy
- El dominio (domain/) no se toca
- Verificar con pyright después de cada archivo antes de continuar

Después de cada cambio ejecuta:
  pyright app/auth/<archivo_modificado>.py

Al terminar:
  pyright app/auth/
  pytest tests/auth/ -v
