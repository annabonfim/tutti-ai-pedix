"""POST /recommend — main endpoint for AI menu recommendations."""
import traceback
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator
from app.services.pedix_client import pedix_client
from app.services.groq_service import groq_service, ChatMessage

router = APIRouter(prefix="/recommend", tags=["recommendations"])


class RecommendRequest(BaseModel):
    message: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=2000,
        description="[LEGACY] Pedido single-shot. Use 'messages' para chat multi-turn.",
    )
    messages: Optional[list[ChatMessage]] = Field(
        default=None,
        max_length=20,
        description=(
            "Histórico da conversa (máx 20 mensagens). "
            "A última mensagem deve ter role='user'."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"message": "Quero algo doce de sobremesa"},
                {
                    "messages": [
                        {"role": "user", "content": "Sou vegetariano, o que sugere?"},
                        {"role": "assistant", "content": "Recomendo a Pizza Margherita (R$ 35,00)."},
                        {"role": "user", "content": "E de sobremesa?"},
                    ]
                },
            ]
        }
    }

    @model_validator(mode="after")
    def normalize_input(self) -> "RecommendRequest":
        if self.message is not None and self.messages is not None:
            raise ValueError("Envie apenas 'message' (legacy) OU 'messages', não ambos.")
        if self.message is None and self.messages is None:
            raise ValueError("Envie 'message' (legacy) ou 'messages'.")

        if self.message is not None:
            self.messages = [ChatMessage(role="user", content=self.message)]
            self.message = None

        if not self.messages:
            raise ValueError("'messages' não pode ser vazio.")
        if self.messages[-1].role != "user":
            raise ValueError("A última mensagem do histórico deve ter role='user'.")

        return self


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

    # 3. Chamar Groq com o contexto RAG + histórico de conversa
    try:
        text = groq_service.recommend(payload.messages, menu, ratings)
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
