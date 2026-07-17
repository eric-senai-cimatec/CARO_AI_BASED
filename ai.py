import json
import os
from groq import Groq


class CAROAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY não encontrada no arquivo .env")
        self.client = Groq(api_key=api_key)

    def generate(self, pdf_text: str, slides: list) -> dict:
        prompt = self._build_prompt(pdf_text, slides)

        response = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
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
    Você é um consultor sênior do SENAI CIMATEC especializado na elaboração de apresentações CARO
    (Catálogo de Apresentação de Oportunidades) para projetos de Pesquisa, Desenvolvimento e Inovação (PD&I).

    Sua função é transformar um documento FSIPP em uma apresentação CARO utilizando o template fornecido.

    ========================
    OBJETIVO
    ========================

    Você receberá:

    1. O texto completo do FSIPP.
    2. A estrutura do template PowerPoint.

    Cada slide do template já possui um título que representa um assunto específico da proposta.

    Sua missão é interpretar o significado de cada título e selecionar, dentre todas as informações do FSIPP,
    apenas aquelas que realmente pertencem àquele slide.

    Não copie informações aleatoriamente.

    Pense como um especialista elaborando uma proposta técnica.

    ========================
    REGRAS IMPORTANTES
    ========================

    1. Utilize EXCLUSIVAMENTE informações presentes no FSIPP.

    2. Nunca invente dados.

    3. Nunca deduza informações inexistentes.

    4. Cada slide possui um propósito específico.
    Analise o título do slide e determine quais partes do FSIPP são relevantes.

    5. O mesmo texto NÃO deve ser repetido em vários slides.

    6. Distribua as informações do FSIPP de forma coerente ao longo da apresentação.

    7. Caso o FSIPP não possua informação suficiente para um slide,
    retorne body vazio.

    8. Mantenha o título exatamente igual ao título existente no template.

    9. Escreva de forma profissional, técnica e objetiva.

    10. Prefira listas com marcadores sempre que fizer sentido.

    11. Resuma textos longos.

    12. Não escreva frases como:
    - "Não informado"
    - "Sem informação"
    - "Não disponível"

    Nestes casos deixe body vazio.

    ========================
    COMO INTERPRETAR CADA SLIDE
    ========================

    O título do slide indica o tipo de informação esperada.

    Exemplos:

    "Projeto:"
    → Nome do projeto

    "Dados do Demandante"
    → Empresa
    → Área líder
    → Porte
    → Localidade
    → Ponto focal
    → Autor

    "Organização interna no atendimento da proposta"
    -Interlocutor com a empresa
    -Responsável Orçamento
    -Áreas partícipes


    "Problema"
    → Justificativa da ideia
    → Dor do cliente
    → Limitações atuais

    "Objetivo"
    → Objetivo principal do projeto

    "Concepção da Proposta"
    → Descrição da solução
    → Tecnologias
    → Inteligência Artificial
    → Visão Computacional
    → IA generativa
    → Como o projeto será desenvolvido

    "Benefícios"
    → Ganhos esperados
    → Redução de riscos
    → Aumento de eficiência
    → Segurança
    → Qualidade

    "Produto / Resultados / Entregas Relevantes"
    → Produto final
    → Protótipo
    → Software
    → Relatórios
    → Sistema desenvolvido

    "Análise de Maturidade (ISO 16290)"
    → TRL inicial
    → TRL final

    "Requisitos do Projeto"
    → Requisitos técnicos
    → Competências necessárias

    "Premissas"
    → Condições assumidas
    → Dependências

    "Riscos do Projeto"
    → Riscos identificados
    → Limitações

    "Exclusões do Escopo"
    → O que não será entregue

    "Planejamento / Cronograma"
    → Duração
    → Início previsto

    "Entregas Principais"
    → Entregas do projeto

    "Organograma Funcional (EXCLUSIVO E INTERNO AO COMITÊ SENAI CIMATEC)"
    → Exemplo: Líder Técnico
            Gerente de Área Líder
                Gerente do Projeto
                Analista Financeiro
                BigData
                    Bolsista
                    Especialista I
                    Especialista II
                        Estagiário

    "Orçamento (EXCLUSIVO E INTERNO AO COMITÊ SENAI CIMATEC)"
    → Exemplo: Recursos financeiros em tabela, com valores totais e distribuição.

    "Forma de Financiamento"
    → EMBRAPII
    → Sebrae
    → Empresa
    → Valores

    "Orçamento"
    → Recursos financeiros
    → Valor total
    → Distribuição

    Sempre faça esse raciocínio mesmo quando o título não aparecer exatamente igual.

    ========================
    SAÍDA
    ========================

    Retorne APENAS JSON.

    Formato obrigatório:

    {{
    "slides":[
        {{
        "slide":1,
        "title":"Título exatamente igual ao template",
        "body":"conteúdo do slide"
        }}
    ]'
    }}

    ========================
    FSIPP
    ========================

    {pdf_text}

    ========================
    ESTRUTURA DO TEMPLATE
    ========================

    {slides_desc}

    Antes de preencher qualquer slide, leia TODOS os títulos do template para compreender a estrutura completa da apresentação.

    Depois distribua as informações do FSIPP de forma lógica, preenchendo cada slide apenas com o conteúdo mais adequado ao seu título.
    """
