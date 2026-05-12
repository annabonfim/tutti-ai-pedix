"""Wraps the Groq LLM call for menu recommendations (RAG pattern)."""
from groq import Groq
from app.config import settings

SYSTEM_PROMPT = """Você é o assistente virtual do Pedix, um sistema de comanda \
digital para restaurantes. Sua função é recomendar pratos do cardápio para os \
clientes de forma amigável, breve e útil.

Regras:
- Recomende APENAS itens que estejam no CARDÁPIO fornecido abaixo.
- Use as AVALIAÇÕES (notas dos clientes) e a POPULARIDADE (pedidos) \
para identificar pratos populares e bem avaliados.
- Se o cliente mencionar restrições (vegetariano, sem glúten, alergia), respeite-as.
- Responda em português, em no máximo 3 frases.
- Sempre cite o nome exato do prato e o preço (R$).
- Se nenhum item for adequado, sugira o mais bem avaliado."""


class GroqService:
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    def build_context(
        self,
        menu: list[dict],
        ratings: list[dict],
        pedido_items: list[dict],
        categories: list[dict],
    ) -> str:
        # --- Categories ---
        cat_text = "\n".join(
            f"- {c.get('nome')}: {c.get('descricao', '')}"
            for c in categories
        ) or "Sem categorias."

        # --- Menu ---
        menu_text = "\n".join(
            f"- [{item.get('id')}] {item.get('nome')} | R$ {float(item.get('preco', 0)):.2f}"
            for item in menu
        ) or "Cardápio vazio."

        # --- Ratings: average per item ---
        rating_sums: dict = {}
        rating_counts: dict = {}
        for r in ratings:
            iid = r.get("itemCardapioId")
            nota = r.get("nota")
            if iid is not None and nota is not None:
                rating_sums[iid] = rating_sums.get(iid, 0) + float(nota)
                rating_counts[iid] = rating_counts.get(iid, 0) + 1

        ratings_lines = []
        for item in menu:
            iid = item.get("id")
            if iid in rating_counts:
                avg = rating_sums[iid] / rating_counts[iid]
                ratings_lines.append(
                    f"- {item.get('nome')}: {avg:.1f}/5 ({rating_counts[iid]} avaliações)"
                )
        ratings_text = "\n".join(ratings_lines) or "Sem avaliações."

        # --- Popularity from pedido_items ---
        pop_counts: dict = {}
        pop_names: dict = {}
        for pi in pedido_items:
            iid = pi.get("itemCardapioId")
            qty = pi.get("quantidade", 1) or 1
            if iid is not None:
                pop_counts[iid] = pop_counts.get(iid, 0) + qty
                pop_names[iid] = pi.get("nomeItem", "?")

        top = sorted(pop_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        pop_text = "\n".join(
            f"- {pop_names[iid]}: pedido {c}x" for iid, c in top
        ) or "Sem histórico."

        return (
            f"CATEGORIAS DO CARDÁPIO:\n{cat_text}\n\n"
            f"CARDÁPIO:\n{menu_text}\n\n"
            f"AVALIAÇÕES MÉDIAS:\n{ratings_text}\n\n"
            f"MAIS PEDIDOS:\n{pop_text}"
        )

    def recommend(
        self,
        user_message: str,
        menu: list[dict],
        ratings: list[dict],
        pedido_items: list[dict],
        categories: list[dict],
    ) -> str:
        context = self.build_context(menu, ratings, pedido_items, categories)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": context},
                {"role": "user", "content": user_message},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        return completion.choices[0].message.content


groq_service = GroqService()