from fastapi import APIRouter

router = APIRouter()

# POST /auth/github          → inicia OAuth flow
# GET  /auth/github/callback → recibe code, crea user + github_profile
# GET  /auth/me              → devuelve usuario autenticado
