"""
tools/ — Sistema de Tools do CARO Framework

  pdf_tools.py        — Leitura de FSIPP em PDF (pdfplumber + OCR fallback)
  pptx_tools.py       — Leitura/escrita segura de slides PPTX
  text_tools.py       — Manipulação de texto (truncar, normalizar, sanitizar)
  validation_tools.py — Validação de entradas/saídas do pipeline

Uso rápido:
    from tools import read_fsipp, run_preflight_checks, PptxTools
"""

from .pdf_tools import PDFReader, read_fsipp
from .pptx_tools import PptxTools
from .text_tools import (
    truncate_smart,
    normalize_bullets,
    sanitize_for_pptx,
    split_into_chunks,
    key_values_to_text,
)
from .validation_tools import (
    validate_api_key,
    validate_template,
    validate_context,
    run_preflight_checks,
)

__all__ = [
    "PDFReader", "read_fsipp",
    "PptxTools",
    "truncate_smart", "normalize_bullets", "sanitize_for_pptx",
    "split_into_chunks", "key_values_to_text",
    "validate_api_key", "validate_template", "validate_context",
    "run_preflight_checks",
]
