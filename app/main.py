"""FastAPI entry point for the Pedix AI service."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import recommendations

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Serviço de IA para recomendação de pratos do Pedix.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommendations.router)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}