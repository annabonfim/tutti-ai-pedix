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
    pedido_items_considered: int


@router.post("", response_model=RecommendResponse)
async def recommend(payload: RecommendRequest):
    # 1. Fetch data from the Java API
    try:
        pedido_items = await pedix_client.get_pedido_items()
        ratings = await pedix_client.get_ratings()
        categories = await pedix_client.get_categories()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao consultar Pedix API: {type(e).__name__}: {e!r}",
        )

    # 2. Derive menu by deduplicating pedido_items per itemCardapioId
    menu_dict: dict = {}
    for pi in pedido_items:
        iid = pi.get("itemCardapioId")
        if iid is not None and iid not in menu_dict:
            menu_dict[iid] = {
                "id": iid,
                "nome": pi.get("nomeItem", "Sem nome"),
                "preco": pi.get("precoUnitario", 0),
            }
    menu = list(menu_dict.values())

    # 3. Call Groq with the RAG context
    try:
        text = groq_service.recommend(
            payload.message, menu, ratings, pedido_items, categories
        )
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
        pedido_items_considered=len(pedido_items),
    )