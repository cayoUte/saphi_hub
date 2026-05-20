"""
Crea un usuario admin inicial.
Uso: docker compose exec api python scripts/create_admin.py
"""
import uuid
from shared.db.session import SessionLocal
from auth.models.user import User, UserRole

db = SessionLocal()
admin = User(
    id=uuid.uuid4(),
    role=UserRole.admin,
    email="admin@acadex.dev",
    display_name="Admin",
    slug="admin",
)
db.add(admin)
db.commit()
print(f"✓ Admin creado: {admin.email}")
db.close()
