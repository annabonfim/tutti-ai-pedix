"""Wraps the Groq LLM call for menu recommendations (RAG pattern)."""
from groq import Groq
from app.config import settings

SYSTEM_PROMPT = """Você é o Tutti, assistente virtual do Pedix, um sistema de \
comanda digital para restaurantes. Sua função é recomendar pratos do cardápio \
para os clientes de forma amigável, breve e útil.

Regras:
- Recomende APENAS itens que estejam no CARDÁPIO fornecido abaixo.
- Use a CATEGORIA, a DESCRIÇÃO (ingredientes) e as AVALIAÇÕES médias \
para escolher o melhor item.
- Se o cliente mencionar restrições (vegetariano, sem glúten, alergia, \
ingredientes específicos), VERIFIQUE NA DESCRIÇÃO e respeite-as.
- Responda em português, em no máximo 3 frases.
- Sempre cite o nome exato do prato e o preço (R$).
- Se nenhum item for adequado, sugira o mais bem avaliado da categoria \
mais próxima e explique brevemente."""


class GroqService:
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    def build_context(self, menu: list[dict], ratings: list[dict]) -> str:
        # --- Menu agrupado por categoria, com descrição ---
        by_cat: dict = {}
        for item in menu:
            cat = item.get("categoriaNome", "OUTROS")
            by_cat.setdefault(cat, []).append(item)

        menu_lines: list[str] = []
        for cat, items in by_cat.items():
            menu_lines.append(f"\n[{cat}]")
            for item in items:
                line = (
                    f"  - [{item.get('id')}] {item.get('nome')} "
                    f"| R$ {float(item.get('preco', 0)):.2f}"
                )
                desc = item.get("descricao")
                if desc:
                    line += f"\n      Ingredientes: {desc}"
                menu_lines.append(line)
        menu_text = "\n".join(menu_lines) or "Cardápio vazio."

        # --- Avaliações: média por item ---
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

        return (
            f"CARDÁPIO COMPLETO (apenas itens disponíveis):"
            f"{menu_text}\n\n"
            f"AVALIAÇÕES MÉDIAS:\n{ratings_text}"
        )

    def recommend(self, user_message: str, menu: list[dict], ratings: list[dict]) -> str:
        context = self.build_context(menu, ratings)
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