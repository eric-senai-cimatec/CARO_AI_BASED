import json
import os
from openai import OpenAI
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()


class CAROAgent:
    def __init__(self, config: dict):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY nao encontrada no arquivo .env")
        self.client = OpenAI(api_key=api_key)
        self.model = config.get("model")
        self.temperature = config.get("temperature")
        self.top_k = config.get("top_k")
        self.collection_name = config.get("collection_name")
        self.chunk_size = config.get("chunk_size")
        self.chunk_overlap = config.get("chunk_overlap")
        self.knowledge_base_path = config.get("knowledge_base")

        self.chroma_client = chromadb.Client()
        self.embed_func = embedding_functions.OpenAIEmbeddingFunction(
            api_key=api_key,
            model_name="text-embedding-ada-002",
        )
        self.collection = self._get_or_create_collection()

    def _get_or_create_collection(self):
        try:
            collection = self.chroma_client.get_collection(
                name=self.collection_name,
                embedding_function=self.embed_func,
            )
            if collection.count() > 0:
                return collection
        except Exception:
            pass
        collection = self.chroma_client.create_collection(
            name=self.collection_name,
            embedding_function=self.embed_func,
        )
        self._populate_rag(collection)
        return collection

    def _populate_rag(self, collection):
        if not os.path.exists(self.knowledge_base_path):
            return
        from reader import extract_text
        text = extract_text(self.knowledge_base_path)
        chunks = self._chunk_text(text)
        for i, chunk in enumerate(chunks):
            collection.add(
                documents=[chunk],
                ids=[f"chunk_{i}"],
            )

    def _chunk_text(self, text: str) -> list:
        words = text.split()
        chunks = []
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            if chunk_words:
                chunks.append(" ".join(chunk_words))
        return chunks

    def _retrieve(self, query: str, n_results: int = None) -> str:
        if n_results is None:
            n_results = self.top_k
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        documents = results.get("documents", [[]])[0]
        return "\n\n".join(documents)

    def generate(self, fsipp_text: str, slides: list) -> dict:
        rag_context = self._retrieve(fsipp_text)
        prompt = self._build_prompt(fsipp_text, slides, rag_context)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return json.loads(content)

    def _build_prompt(self, fsipp_text: str, slides: list, rag_context: str) -> str:
        slides_desc = json.dumps(slides, indent=2, ensure_ascii=False)
        print(f"Slides description: {slides_desc}")

        return f"""
Voce é um consultor senior do SENAI CIMATEC especializado na elaboracao de apresentacoes CARO
(Catalogo de Apresentacao de Oportunidades) para projetos de Pesquisa, Desenvolvimento e Inovacao (PD&I).

Sua funcao é transformar um documento FSIPP em uma apresentacao CARO utilizando o template fornecido.

USE INFORMACOES DO BANCO DE CONHECIMENTO RAG QUANDO COMPLEMENTAREM O CONTEUDO DO FSIPP.

========================
OBJETIVO
========================

Voce recebera:

1. O texto completo do FSIPP.
2. O contexto relevante do banco de conhecimento RAG.
3. A estrutura do template PowerPoint.

Cada slide do template ja possui um titulo que representa um assunto especifico da proposta.

Sua missao e interpretar o significado de cada titulo e selecionar, dentre todas as informacoes do FSIPP
e do banco de conhecimento RAG, apenas aquelas que realmente pertencem aquele slide.

Nao copie informacoes aleatoriamente.

Pense como um especialista elaborando uma proposta tecnica.

========================
REGRAS IMPORTANTES
========================

1. Utilize EXCLUSIVAMENTE informacoes presentes no FSIPP e no banco de conhecimento RAG.

2. Nao invente dados.

3. Nao deduza informacoes inexistentes.

4. Cada slide possui um proposito especifico.
Analise o titulo do slide e determine quais partes do FSIPP e do RAG sao relevantes.

5. O mesmo texto NAO deve ser repetido em varios slides.

6. Distribua as informacoes do FSIPP e do RAG de forma coerente ao longo da apresentacao.

7. Caso o FSIPP e o RAG nao possuam informacao suficiente para um slide,
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

"bullet" â€” texto com marcadores (padrao)
"workflow" â€” fluxograma de processos com timeline
"timeline" â€” linha do tempo horizontal com marcos
"orgchart" â€” organograma hierarquico
"gantt" â€” cronograma / grafico de Gantt
"table" â€” tabela com cabecalhos e linhas
"image" â€” slide com imagem e legenda

========================
COMO ESCOLHER O LAYOUT
========================

- "Concepcao da Proposta" → layout "workflow"
- "Planejamento / Cronograma" → layout "table"
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
        "nodes": [
            {{"id": "1", "text": "Lider Tecnico"}},
            {{"id": "2", "text": "Gerente Executivo"}},
            {{"id": "3", "text": "Gerente do Projeto"}},
            {{"id": "4", "text": "Financeiro"}},
            {{"id": "5", "text": "Big Data"}},
            {{"id": "6", "text": "Especialista II"}},
            {{"id": "7", "text": "Especialista I"}},
            {{"id": "8", "text": "Bolsista"}}
        ],
        "edges": [
            {{"from": "1", "to": "2"}},
            {{"from": "2", "to": "3"}},
            {{"from": "3", "to": "4"}},
            {{"from": "3", "to": "5"}},
            {{"from": "5", "to": "6"}},
            {{"from": "5", "to": "7"}},
            {{"from": "5", "to": "8"}}
        ]
    }}
}}

**gantt:**
{{
    "layout": "gantt",
    "content": {{
        "start_label": "março/2027",
        "phases": [
            {{"name": "Mês 1", "start": "Mês 1", "end": "Mês 1", "tasks": ["Atividade A", "Atividade B"]}},
            {{"name": "Mês 2-3", "start": "Mês 2", "end": "Mês 3", "tasks": ["Atividade C"]}}
        ]
    }}
}}

- "start_label": obrigatório. Ex: "março/2027"
- "phases": lista de fases com:
  - "name": nome da fase/mês (ex: "Mês 1", "Mês 2-4", "Fase de Desenvolvimento")
  - "start": número do mês inicial (ex: "Mês 1")
  - "end": número do mês final (ex: "Mês 3")
  - "tasks": array opcional de atividades descritivas para a fase

IMPORTANTE: Crie fases para CADA mês individualmente sempre que houver atividades
descritas no documento. Exemplo: se o cronograma descreve atividades para os meses
1 a 4, crie 4 fases (Mês 1, Mês 2, Mês 3, Mês 4) com suas respectivas tasks.
Se houver meses consecutivos com a mesma descriçÃ£o de atividade, agrupe em
uma Ãºnica fase (ex: "Mês 2-4").

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

Para "Planejamento / Cronograma", use o formato de tabela com mês e atividades:
{{
    "layout": "table",
    "content": {{
        "headers": ["Mês", "Atividades"],
        "rows": [
            ["Mês 1 (mar/2027)", "Descrição das atividades do Mês 1"],
            ["Mês 2 (abr/2027)", "Descrição das atividades do Mês 2"],
            ["Mês 3 (mai/2027)", "Descrição das atividades do Mês 3"]
        ]
    }}
}}

Crie uma linha para CADA mês do cronograma.
Na coluna "Mês" inclua o número do mês e o mês/ano real.
Na coluna "Atividades" descreva resumidamente as atividades daquele mês.

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
-Areas parti­cipes

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
→ Duração prevista (meses) — ex: 18 meses
→ Início previsto (mês/ano) — ex: março de 2027
→ Atividades descritas por mês
→ Crie uma linha na tabela para CADA mês do cronograma
→ layout "table" com headers ["Mês", "Atividades"]
"Entregas Principais"
→ Entregas do projeto
→ Macroentrega 1, 2, 3, etc.

"Organograma Funcional (EXCLUSIVO E INTERNO AO COMITE SENAI CIMATEC)"
→ Estrutura hierárquica com líderes, gerentes e analistas
→ layout "orgchart" com nodes e edges (formato array)
→ Exemplo: Líder Técnico > Gerente Área Líder > Gerente Projeto > [Financeiro, BigData] > [Especialistas, Bolsista]

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

{fsipp_text}

========================
CONHECIMENTO RAG
========================

{rag_context}

========================
ESTRUTURA DO TEMPLATE
========================

{slides_desc}

Antes de preencher qualquer slide, leia TODOS os titulos do template para compreender a estrutura completa da apresentacao.

Depois distribua as informacoes do FSIPP e do banco de conhecimento RAG de forma logica, preenchendo cada slide apenas com o conteudo mais adequado ao seu titulo.
"""
