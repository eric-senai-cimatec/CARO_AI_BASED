# CARO — Gerador Inteligente de Propostas Corporativas com IA

> Framework de Engenharia de Propostas baseado em Multi-Agentes (LLM via Groq)  
> Converte um FSIPP ou resumo de ata de reunião em uma apresentação PPTX completa,  
> preservando 100% da identidade visual do template SENAI CIMATEC / CARO.

---

## Arquitetura

```
INPUT (FSIPP / Ata de Reunião)
       │
       ▼
┌──────────────┐
│  Orchestrator│  ← ponto de entrada principal
└──────┬───────┘
       │
       ├─► Analyst Agent   → analisa o tema e gera visão macro
       ├─► Planner Agent   → define seções, slides e estrutura
       ├─► Writer Agent    → gera conteúdo por slide
       └─► Reviewer Agent  → valida coerência e ajusta
              │
              ▼
┌──────────────────────┐
│   Builder & Renderer │
│  ┌───────────────┐   │
│  │ Template Engine│  │
│  │  6.1 Reader   │   │
│  │  6.2 Model    │   │
│  │  6.3 Cache    │   │
│  └───────────────┘   │
│  ┌───────────────┐   │
│  │ Content Mapper│   │
│  │ Shape Editor  │   │
│  └───────────────┘   │
└──────────┬───────────┘
           │
           ▼
      OUTPUT.pptx
```

---

## Quickstart

```bash
pip install -r requirements.txt

# Variável de ambiente
export GROQ_API_KEY="sua-chave-aqui"

# Gerar proposta a partir de FSIPP/Ata
python main.py \
  --template templates/CARO_Bobinas.pptx \
  --input docs/minha_ata.txt \
  --output output/proposta_cliente.pptx

# Interface interativa
python main.py --interactive
```

---

## Estrutura de Arquivos

```
caro_framework/
├── main.py                    # Ponto de entrada CLI
├── requirements.txt
├── README.md
├── config.py                  # Configurações globais
│
├── core/
│   ├── __init__.py
│   ├── ast_pptx.py            # AST do PowerPoint (parser recursivo)
│   ├── template_reader.py     # Agente leitura do template (6.1)
│   ├── template_model.py      # Modelo do template (6.2)
│   ├── template_cache.py      # Cache JSON (6.3)
│   ├── region_detector.py     # Detecção automática de regiões
│   ├── shape_editor.py        # Editor de shapes preservando formatação
│   └── layout_preserver.py    # Preservação de layout
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py          # Classe base dos agentes
│   ├── analyst_agent.py       # Analisa FSIPP/Ata e gera visão macro
│   ├── planner_agent.py       # Planeja estrutura de slides
│   ├── writer_agent.py        # Escreve conteúdo por slide
│   ├── reviewer_agent.py      # Revisa e ajusta o conteúdo
│   └── orchestrator.py        # Orquestrador multi-agente
│
├── tools/
│   ├── __init__.py
│   ├── tool_registry.py       # Registro de tools disponíveis
│   ├── pptx_tools.py          # Tools PPTX (ler, escrever, listar slides)
│   ├── text_tools.py          # Tools de texto (resumir, expandir)
│   └── validation_tools.py    # Tools de validação
│
├── templates/
│   └── CARO_Bobinas.pptx      # Template base (copie aqui)
│
├── output/                    # Propostas geradas
├── tests/
│   ├── test_ast.py
│   ├── test_agents.py
│   └── test_e2e.py
└── docs/
    └── exemplo_fsipp.txt      # Exemplo de FSIPP de entrada
```

---

## Tecnologias

| Componente | Tecnologia |
|---|---|
| LLM | Groq (llama-3.3-70b-versatile) |
| PPTX | python-pptx |
| Cache | JSON (filesystem) |
| CLI | argparse |
| Validação | Pydantic |
| Testes | pytest |

---

## Licença

Uso interno SENAI CIMATEC. Todos os direitos reservados.