"""HTTP client for the Pedix Java (Spring Boot) API on Azure.

Note: /api/item-cardapio is currently broken (LazyInitializationException
on CategoriaCardapio). We build the menu from /api/pedido-item instead,
which already has nomeItem and precoUnitario as denormalized fields.
"""
import httpx
from app.config import settings

HEALTH_ENDPOINT = "/api/health"
PEDIDO_ITEM_ENDPOINT = "/api/pedido-item"
CATEGORIES_ENDPOINT = "/api/categorias-cardapio"
RATINGS_ENDPOINT = "/api/avaliacoes"


class PedixClient:
    def __init__(self, base_url: str = settings.java_api_base_url):
        self.base_url = base_url.rstrip("/")
        self.timeout = 60.0  # Azure cold start can take 20-30s

    async def _get(self, path: str):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{path}")
            response.raise_for_status()
            return response.json()

    async def health(self) -> dict:
        return await self._get(HEALTH_ENDPOINT)

    async def get_pedido_items(self) -> list[dict]:
        return await self._get(PEDIDO_ITEM_ENDPOINT)

    async def get_categories(self) -> list[dict]:
        return await self._get(CATEGORIES_ENDPOINT)

    async def get_ratings(self) -> list[dict]:
        return await self._get(RATINGS_ENDPOINT)


pedix_client = PedixClient()