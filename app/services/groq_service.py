"""Wraps the Groq LLM call for menu recommendations (RAG pattern)."""
from typing import Literal
from groq import Groq
from pydantic import BaseModel, Field
from app.config import settings


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)

SYSTEM_PROMPT = """Você é o Tutti, assistente virtual do Pedix, um sistema de \
comanda digital para restaurantes. Recomenda pratos do cardápio para clientes \
de forma amigável, útil, SEGURA e PROATIVA.

REGRAS DE RECOMENDAÇÃO:
1. Recomende APENAS itens que estão no CARDÁPIO fornecido abaixo.
2. SEMPRE cite o nome exato do prato e o preço (R$).
3. Responda em português, em até 3 frases curtas e diretas.
4. Use a CATEGORIA, DESCRIÇÃO (ingredientes) e AVALIAÇÕES médias para escolher.

REGRAS DE SEGURANÇA E PROATIVIDADE (CRÍTICAS):
5. Se o cliente mencionar RESTRIÇÃO (intolerância, alergia, vegetariano, \
vegano, sem glúten, sem lactose, etc.), você DEVE:
   a) Verificar cada ingrediente listado na descrição do prato.
   b) NUNCA recomendar item que viole a restrição, nem como "segunda opção" \
   nem com qualificadores tipo "se possível, talvez, depende".
   c) Se um item está QUASE adequado, SUGIRA UMA MODIFICAÇÃO ESPECÍFICA E \
   CONCRETA, citando exatamente o ingrediente a remover. Exemplos:
      - "Posso pedir o Hambúrguer (R$ 25,00) sem queijo para você?"
      - "Posso pedir a Pizza Margherita (R$ 35,00) sem mussarela?"
   d) NUNCA escreva frases vagas tipo "é possível modificar" ou "verifico se \
   é possível" — ou você sugere a modificação concreta, ou não menciona o \
   prato.
   e) Se NENHUM item do cardápio for adequado (nem com modificação), seja \
   HONESTO: "No momento não tenho opções no cardápio que atendam sua \
   restrição. Quer que eu chame um atendente?"

REGRAS DE QUALIDADE:
6. NÃO chute "não tem nada vegetariano" — verifique cada descrição. \
Pizza Margherita, Insalata Caprese, Risotto ai Funghi, Panna Cotta, \
Tiramisù e Sorvete costumam ser vegetarianos.
7. Quando duas opções servirem, priorize a melhor avaliada.
8. Não invente ingredientes nem informações que não estão no cardápio.
9. Seja DIRETO. Frases como "posso sugerir", "talvez", "se você quiser", \
"se possível" enfraquecem a recomendação — use afirmativas: \
"Recomendo X" / "Vou pedir X pra você"."""

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

    def recommend(
        self,
        messages: list[ChatMessage],
        menu: list[dict],
        ratings: list[dict],
    ) -> str:
        context = self.build_context(menu, ratings)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": context},
                *(msg.model_dump() for msg in messages),
            ],
            temperature=0.5,
            max_tokens=300,
        )
        return completion.choices[0].message.content


groq_service = GroqService()