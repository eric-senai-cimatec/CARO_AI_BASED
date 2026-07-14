"""
config.py — Configurações globais do CARO Framework
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Carregar variáveis de ambiente
load_dotenv()

# ── Diretórios base ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / ".cache"
DOCS_DIR = BASE_DIR / "docs"

# Criar diretórios se não existirem
for d in [TEMPLATES_DIR, OUTPUT_DIR, CACHE_DIR, DOCS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ── Groq / LLM ───────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

# Modelos disponíveis na Groq (2025)
GROQ_MODELS = {
    "fast": "openai/gpt-oss-120b",
    "balanced": "openai/gpt-oss-120b",
    "powerful": "openai/gpt-oss-120b",
    "coder": "openai/gpt-oss-120b",
}

# Nome exato aceito pela API Groq (sem prefixo "meta-llama/")
DEFAULT_MODEL = os.getenv("GROQ_MODEL", GROQ_MODELS["balanced"])
MAX_TOKENS_DEFAULT = 4096
TEMPERATURE_DEFAULT = 0.7
TEMPERATURE_CREATIVE = 0.7


# ── Template defaults ────────────────────────────────────────────────────────
DEFAULT_TEMPLATE_NAME = "CARO_Bobinas.pptx"
DEFAULT_TEMPLATE_PATH = TEMPLATES_DIR / DEFAULT_TEMPLATE_NAME

# Mapeamento de seções padrão da proposta CARO
CARO_SECTIONS = [
    "titulo",           # Slide 1/2 — capa
    "informacao",       # Slide 3 — confidencialidade
    "demandante",       # Slide 4 — dados do cliente
    "organizacao",      # Slide 5 — organização interna
    "problema",         # Slide 6 — problema/desafio
    "objetivo",         # Slide 7 — objetivo
    "concepcao",        # Slide 8 — concepção da proposta
    "beneficios",       # Slide 9 — benefícios
    "entregas",         # Slide 10/11 — entregas
    "maturidade",       # Slide 12 — análise TRL
    "riscos",           # Slide 19 — riscos tecnológicos
    "requisitos",       # Slide 20 — requisitos
    "premissas",        # Slides 21/22/23 — premissas
    "riscos_projeto",   # Slide 25 — matriz de riscos
    "exclusoes",        # Slide 26 — exclusões de escopo
    "cronograma",       # Slide 27 — planejamento
    "macro_entregas",   # Slide 28 — entregas principais
    "orcamento",        # Slides 30/31 — orçamento
    "comentarios",      # Slide 36 — comentários finais
    "obrigado",         # Slide 37 — encerramento
]

# Slides que NÃO devem ser editados automaticamente (apenas visuais/internos)
PROTECTED_SLIDES = []  # [3, 13, 14, 15, 16, 17, 18, 24, 29, 32, 33, 34, 35]

# Mapeamento slide → campo principal de conteúdo
SLIDE_CONTENT_MAP = {
    1: {"title": "titulo_projeto", "subtitle": "tipo_proposta", "date": "data"},
    2: {"title": "titulo_projeto", "subtitle": "tipo_proposta", "date": "data"},
    4: {"title": "Dados do Demandante", "body": "dados_demandante"},
    5: {"title": "Organização interna no atendimento da proposta", "body": "organizacao_interna"},
    6: {"title": "Problema", "body": "problema"},
    7: {"title": "Objetivo", "body": "objetivo"},
    8: {"title": "Concepção da Proposta", "body": "concepcao"},
    9: {"title": "Benefícios", "body": "beneficios"},
    10: {"title": "Produto / Resultados / Entregas Relevantes do Projeto Orçado", "body": "entregas_1"},
    11: {"title": "Produto / Resultados / Entregas Relevantes do Projeto Orçado", "body": "entregas_2"},
    12: {"title": "Análise de Maturidade (ISO 16290)", "body": "trl"},
    19: {"title": "Riscos Tecnológicos", "body": "riscos_tecnologicos"},
    20: {"title": "Requisitos do projeto", "body": "requisitos"},
    21: {"title": "Premissas", "body": "premissas_1"},
    22: {"title": "Premissas", "body": "premissas_2"},
    23: {"title": "Premissas (Machine Learning)", "body": "premissas_ml"},
    25: {"title": "Riscos do projeto", "body": "riscos_projeto"},
    26: {"title": "Exclusões do Escopo", "body": "exclusoes"},
    27: {"title": "Planejamento / Cronograma", "body": "cronograma"},
    28: {"title": "Entregas Principais", "body": "macro_entregas"},
    36: {"title": "Comentários finais", "body": "comentarios_finais"},
    37: {"title": "Obrigado!", "body": None},
}


# ── Limites de texto por slide ────────────────────────────────────────────────
TEXT_LIMITS = {
    "title_max_chars": 120,
    "body_max_chars": 1500,
    "bullet_max_chars": 200,
    "bullets_per_slide_max": 8,
}


# ── Cache ────────────────────────────────────────────────────────────────────
CACHE_ENABLED = True
CACHE_VERSION = "1.0.0"

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "caro_framework.log"

# ── Retry / Resilience ───────────────────────────────────────────────────────
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2
LLM_TIMEOUT_SECONDS = 60
