from fastapi import APIRouter

router = APIRouter()

# POST /institutions               → US-19: solicitar vinculación (role=institution)
# GET  /institutions               → admin: listar todas
# POST /institutions/{id}/approve  → US-26: admin aprueba con checklist
# POST /institutions/{id}/reject   → admin rechaza
