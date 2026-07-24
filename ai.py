import json
import os
from groq import Groq


class CAROAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY nao encontrada no arquivo .env")
        self.client = Groq(api_key=api_key)

    def generate(self, pdf_text: str, slides: list) -> dict:
        prompt = self._build_prompt(pdf_text, slides)

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return json.loads(content)

    def _build_prompt(self, pdf_text: str, slides: list) -> str:
        slides_desc = json.dumps(slides, indent=2, ensure_ascii=False)
        print(f"Slides description: {slides_desc}")

        return f"""
Voce é um consultor senior do SENAI CIMATEC especializado na elaboracao de apresentacoes CARO
(Catalogo de Apresentacao de Oportunidades) para projetos de Pesquisa, Desenvolvimento e Inovacao (PD&I).

Sua funcao é transformar um documento FSIPP em uma apresentacao CARO utilizando o template fornecido.

========================
OBJETIVO
========================

Voce recebera:

1. O texto completo do FSIPP.
2. A estrutura do template PowerPoint.

Cada slide do template ja possui um titulo que representa um assunto especifico da proposta.

Sua missao e interpretar o significado de cada titulo e selecionar, dentre todas as informacoes do FSIPP,
apenas aquelas que realmente pertencem aquele slide.

Nao copie informacoes aleatoriamente.

Pense como um especialista elaborando uma proposta tecnica.

========================
REGRAS IMPORTANTES
========================

1. Utilize EXCLUSIVAMENTE informacoes presentes no FSIPP.

2. Nunca invente dados.

3. Nunca deduza informacoes inexistentes.

4. Cada slide possui um proposito especifico.
Analise o titulo do slide e determine quais partes do FSIPP sao relevantes.

5. O mesmo texto NAO deve ser repetido em varios slides.

6. Distribua as informacoes do FSIPP de forma coerente ao longo da apresentacao.

7. Caso o FSIPP nao possua informacao suficiente para um slide,
retorne content vazio (ex: "content": {{}}).

8. Mantenha o titulo exatamente igual ao titulo existente no template.

9. Escreva de forma profissional, tecnica e objetiva.

10. Resuma textos longos.

11. Nao escreva frases como:
- "Nao informado"
- "Sem informacao"
- "Nao disponivel"

Nestes casos deixe content vazio.

========================
REGRAS SOBRE LAYOUT E CONTEUDO
========================

Cada slide possui dois campos especiais:

- "layout": define como o slide sera desenhado.
- "content": contem APENAS informacoes semanticas.

VOCE NUNCA DEVE GERAR:
- Coordenadas (x, y)
- Posicoes
- Tamanhos (width, height)
- Informacoes graficas
- Cores
- Fontes
- Qualquer instrucao de desenho

Voce descreve APENAS o conteudo semantico.
O sistema de renderizacao decide como desenhar.

========================
LAYOUTS DISPONIVEIS
========================

"bullet" — texto com marcadores (padrao)
"workflow" — fluxograma de processos com timeline
"timeline" — linha do tempo horizontal com marcos
"orgchart" — organograma hierarquico
"gantt" — cronograma / grafico de Gantt
"table" — tabela com cabecalhos e linhas
"image" — slide com imagem e legenda

========================
COMO ESCOLHER O LAYOUT
========================

- "Concepcao da Proposta" → layout "workflow"
- "Planejamento / Cronograma" → layout "gantt"
- "Organograma Funcional" → layout "orgchart"
- "Orcamento" → layout "table"
- Demais slides → layout "bullet"

========================
ESTRUTURA DE CADA LAYOUT
========================

**bullet:**
{{
    "layout": "bullet",
    "content": {{
        "body": "texto do slide com listas"
    }}
}}

**workflow:**
{{
    "layout": "workflow",
    "content": {{
        "timeline": {{
            "start": "Fase inicial",
            "milestones": ["ME1", "ME2", "ME3"]
        }},
        "steps": [
            {{
                "title": "Nome da etapa",
                "icon": "database",
                "items": ["Item 1", "Item 2", "Item 3"]
            }}
        ]
    }}
}}

**timeline:**
{{
    "layout": "timeline",
    "content": {{
        "start": "Inicio",
        "milestones": [
            {{"date": "Mes 1", "label": "Evento 1"}},
            {{"date": "Mes 3", "label": "Evento 2"}}
        ]
    }}
}}

**orgchart:**
{{
    "layout": "orgchart",
    "content": {{
        "root": "CEO",
        "children": [
            {{
                "name": "Diretor",
                "children": [
                    {{"name": "Gerente"}}
                ]
            }}
        ]
    }}
}}

**gantt:**
{{
    "layout": "gantt",
    "content": {{
        "phases": [
            {{"name": "Fase 1", "start": "Mes 1", "end": "Mes 3"}},
            {{"name": "Fase 2", "start": "Mes 4", "end": "Mes 6"}}
        ]
    }}
}}

**table:**
{{
    "layout": "table",
    "content": {{
        "headers": ["Coluna 1", "Coluna 2", "Coluna 3"],
        "rows": [
            ["Valor 1", "Valor 2", "Valor 3"],
            ["Valor 4", "Valor 5", "Valor 6"]
        ]
    }}
}}

**image:**
{{
    "layout": "image",
    "content": {{
        "path": "caminho/para/imagem.png",
        "caption": "Legenda da imagem"
    }}
}}

========================
COMO INTERPRETAR CADA SLIDE
========================

O titulo do slide indica o tipo de informacao esperada.

Exemplos:

"Projeto:"
→ Nome do projeto

"Dados do Demandante"
→ Empresa
→ Area lider
→ Porte
→ Localidade
→ Ponto focal
→ Autor

"Organizacao interna no atendimento da proposta"
-Interlocutor com a empresa
-Responsavel Orcamento
-Areas partícipes

"Problema"
→ Justificativa da ideia
→ Dor do cliente
→ Limitacoes atuais

"Objetivo"
→ Objetivo principal do projeto

"Concepcao da Proposta"
→ Descricao da solucao
→ Tecnologias
→ Inteligencia Artificial
→ Visao Computacional
→ IA generativa
→ Como o projeto sera desenvolvido

"Beneficios"
→ Ganhos esperados
→ Reducao de riscos
→ Aumento de eficiencia
→ Seguranca
→ Qualidade

"Produto / Resultados / Entregas Relevantes"
→ Produto final
→ Prototipo
→ Software
→ Relatorios
→ Sistema desenvolvido

"Analise de Maturidade (ISO 16290)"
→ TRL inicial
→ TRL final

"Requisitos do Projeto"
→ Requisitos tecnicos
→ Competencias necessarias

"Premissas"
→ Condicoes assumidas
→ Dependencias

"Riscos do Projeto"
→ Riscos identificados
→ Limitacoes

"Exclusoes do Escopo"
→ O que nao sera entregue

"Planejamento / Cronograma"
→ Duracao
→ Inicio previsto

"Entregas Principais"
→ Entregas do projeto
→ Macroentrega 1, 2, 3, etc.

"Organograma Funcional (EXCLUSIVO E INTERNO AO COMITE SENAI CIMATEC)"
→ Exemplo: Lider Tecnico >
        > Gerente de Area Lider
            > Gerente do Projeto
            > Analista Financeiro
            > BigData
                > Bolsista
                > Especialista II
                > Especialista I
                    > Estagiario
→ layout "orgchart"

"Orcamento (EXCLUSIVO E INTERNO AO COMITE SENAI CIMATEC)"
→ Exemplo: Recursos financeiros em tabela, com valores totais e distribuicao.
→ layout "table"

"Forma de Financiamento"
→ EMBRAPII
→ Sebrae
→ Empresa
→ Valores

"Orcamento"
→ Recursos financeiros
→ Valor total
→ Distribuicao

Sempre faca esse raciocinio mesmo quando o titulo nao aparecer exatamente igual.

========================
SAIDA
========================

Retorne APENAS JSON. Nenhum texto antes ou depois.

Formato obrigatorio:

{{
    "slides": [
        {{
            "slide": 1,
            "title": "Titulo exatamente igual ao template",
            "layout": "bullet",
            "content": {{
                "body": "conteudo do slide"
            }}
        }}
    ]
}}

========================
FSIPP
========================

{pdf_text}

========================
ESTRUTURA DO TEMPLATE
========================

{slides_desc}

Antes de preencher qualquer slide, leia TODOS os titulos do template para compreender a estrutura completa da apresentacao.

Depois distribua as informacoes do FSIPP de forma logica, preenchendo cada slide apenas com o conteudo mais adequado ao seu titulo.
"""
