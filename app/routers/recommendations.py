"""POST /recommend — main endpoint for AI menu recommendations."""
import traceback
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.pedix_client import pedix_client
from app.services.groq_service import groq_service

router = APIRouter(prefix="/recommend", tags=["recommendations"])


class RecommendRequest(BaseModel):
    message: str = Field(
        ..., min_length=1, max_length=500,
        description="O pedido do cliente em linguagem natural",
        examples=["Quero algo doce de sobremesa"],
    )


class RecommendResponse(BaseModel):
    recommendation: str
    menu_size: int
    ratings_considered: int


@router.post("", response_model=RecommendResponse)
async def recommend(payload: RecommendRequest):
    # 1. Buscar dados na Java API (endpoints públicos)
    try:
        menu_raw = await pedix_client.get_menu()
        ratings = await pedix_client.get_ratings()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao consultar Pedix API: {type(e).__name__}: {e!r}",
        )

    # 2. Filtrar apenas itens disponíveis no momento
    menu = [item for item in menu_raw if item.get("disponivel", True)]

    # 3. Chamar Groq com o contexto RAG
    try:
        text = groq_service.recommend(payload.message, menu, ratings)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao chamar Groq: {type(e).__name__}: {e!r}",
        )

    return RecommendResponse(
        recommendation=text,
        menu_size=len(menu),
        ratings_considered=len(ratings),
    )