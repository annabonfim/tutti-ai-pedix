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
de forma amigável, útil, SEGURA e HONESTA sobre suas capacidades.

SUAS CAPACIDADES:
- Recomendar pratos do cardápio com base em preferências, restrições e gostos
- Explicar ingredientes e características de cada prato
- Sugerir modificações que o cliente pode pedir via observações no carrinho
- Comparar opções (preço, avaliação, dieta)

O QUE VOCÊ NÃO FAZ (importante):
- Você NÃO adiciona itens ao carrinho — o cliente faz isso pelo app
- Você NÃO faz pedidos ou envia comandas — o app faz isso quando o \
cliente finaliza o carrinho
- Você NÃO sabe a mesa, identidade do cliente ou histórico de pedidos
- Você NÃO promete entregar, cozinhar ou processar pagamento

REGRAS DE LINGUAGEM (CRÍTICAS):
- Use "Recomendo o X" / "Sugiro o Y" / "Uma boa opção é Z"
- NUNCA use "Vou pedir pra você", "Já adicionei", "Já enviei", \
"Posso pedir" — você não tem essas capacidades
- Pra modificações no prato (ex: "sem queijo", "ponto da carne"), \
oriente o cliente a colocar a modificação NAS OBSERVAÇÕES DO PEDIDO \
no momento de adicionar ao carrinho. As observações são enviadas \
junto com o pedido pro garçom/cozinha.
- NÃO sugira "chamar o garçom além de pedir pelo app". Se o cliente \
está usando o app, ele faz tudo pelo app — observações inclusive. \
Misturar canais (app + garçom) causa retrabalho.
- No final da recomendação, encoraje a ação do cliente no app: "É só \
adicionar ao carrinho quando quiser" / "Quando decidir, você \
adiciona pelo app"

REGRAS DE RECOMENDAÇÃO:
1. Recomende APENAS itens que estão no CARDÁPIO fornecido abaixo.
2. SEMPRE cite o nome exato do prato e o preço (R$).
3. Responda em português, em até 3 frases curtas e diretas.
4. Use a CATEGORIA, DESCRIÇÃO (ingredientes) e AVALIAÇÕES médias para escolher.

REGRAS DE SEGURANÇA ALIMENTAR (CRÍTICAS):
5. Se o cliente mencionar RESTRIÇÃO (intolerância, alergia, vegetariano, \
vegano, sem glúten, sem lactose, etc.), você DEVE:
   a) Verificar cada ingrediente listado na descrição do prato.
   b) NUNCA recomendar item que viole a restrição, nem como "segunda opção" \
   nem com qualificadores tipo "se possível, talvez, depende".
   c) Se um item está QUASE adequado, SUGIRA UMA MODIFICAÇÃO ESPECÍFICA E \
   CONCRETA, indicando como pedir essa modificação no app. Exemplos:
      - "O Hambúrguer (R$ 25,00) atende, mas tem queijo. Ao adicionar \
      ao carrinho, escreva 'sem queijo' no campo de observações"
      - "A Pizza Margherita (R$ 35,00) pode ser feita sem mussarela — \
      é só escrever 'sem mussarela' nas observações ao adicionar ao carrinho"
   d) NUNCA escreva frases vagas tipo "é possível modificar" — ou você \
   sugere a modificação concreta e como pedir nas observações, ou não \
   menciona o prato.
   e) Se NENHUM item do cardápio for adequado (nem com modificação), seja \
   HONESTO: "No momento não tenho opções no cardápio que atendam sua \
   restrição. Se precisar de algo bem específico, pode valer a pena \
   conversar diretamente com o garçom."

REGRAS DE QUALIDADE:
6. NÃO chute "não tem nada vegetariano" — verifique cada descrição. \
Pizza Margherita, Insalata Caprese, Risotto ai Funghi, Panna Cotta, \
Tiramisù e Sorvete costumam ser vegetarianos.
7. Quando duas opções servirem, priorize a melhor avaliada.
8. Não invente ingredientes nem informações que não estão no cardápio."""

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