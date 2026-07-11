"""
tools/text_tools.py — Ferramentas de processamento de texto

Utilitários usados pelos agentes para manipular e validar texto:
  - truncate_smart: trunca respeitando palavras
  - normalize_bullets: normaliza listas de bullets
  - count_words / count_chars: métricas de texto
  - sanitize: remove caracteres problemáticos para PPTX
  - split_into_chunks: divide texto longo em partes para slides múltiplos
"""

from __future__ import annotations

import re
import unicodedata
from typing import List, Optional, Tuple


def truncate_smart(text: str, max_chars: int, suffix: str = "…") -> str:
    """
    Trunca texto em limite de caracteres sem cortar palavras ao meio.
    """
    if len(text) <= max_chars:
        return text
    limit = max_chars - len(suffix)
    truncated = text[:limit]
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.7:
        truncated = truncated[:last_space]
    return truncated.rstrip() + suffix


def normalize_bullets(
    items: List[str],
    max_per_slide: int = 8,
    max_chars_each: int = 200,
    strip_prefixes: bool = True,
) -> List[str]:
    """
    Normaliza uma lista de bullets:
      - Remove prefixos de marcador (•, -, *, 1., etc.)
      - Trunca bullets muito longos
      - Limita quantidade
      - Remove vazios
    """
    result = []
    prefix_pattern = re.compile(r"^[\•\-\*\–\—\►\▸\▶]\s+|^\d+[\.\)]\s+")

    for item in items:
        item = item.strip()
        if not item:
            continue
        if strip_prefixes:
            item = prefix_pattern.sub("", item).strip()
        if not item:
            continue
        if len(item) > max_chars_each:
            item = truncate_smart(item, max_chars_each)
        result.append(item)

    return result[:max_per_slide]


def sanitize_for_pptx(text: str) -> str:
    """
    Remove/substitui caracteres problemáticos para o PPTX:
      - Caracteres de controle (exceto \\n, \\t)
      - Caracteres Unicode fora do BMP (emojis complexos)
      - Aspas tipográficas → aspas simples
    """
    # Remover caracteres de controle (manter \n e \t)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C"
                   or ch in "\n\t")

    # Normalizar aspas
    text = text.replace("\u201c", '"').replace("\u201d", '"')  # " "
    text = text.replace("\u2018", "'").replace("\u2019", "'")  # ' '
    text = text.replace("\u2013", "-").replace("\u2014", "--")  # – —

    # Remover surrogates e chars fora do BMP (problemáticos no XML do PPTX)
    text = text.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    text = "".join(ch for ch in text if ord(ch) < 0xFFFF)

    return text


def split_into_chunks(
    items: List[str],
    max_per_chunk: int = 6,
) -> List[List[str]]:
    """
    Divide uma lista em chunks para distribuir entre slides múltiplos.
    Ex: 12 entregas → [[e1..e6], [e7..e12]]
    """
    if not items:
        return [[]]
    chunks = []
    for i in range(0, len(items), max_per_chunk):
        chunks.append(items[i : i + max_per_chunk])
    return chunks


def count_chars(text: str) -> int:
    return len(text)


def count_words(text: str) -> int:
    return len(text.split())


def key_values_to_text(pairs: List[Tuple[str, str]], sep: str = ": ") -> str:
    """Converte lista de pares (chave, valor) em texto formatado."""
    return "\n".join(f"{k}{sep}{v}" for k, v in pairs if k or v)


def extract_key_values_from_text(text: str) -> List[Tuple[str, str]]:
    """
    Tenta extrair pares chave:valor de texto livre.
    Ex: "Empresa: CARO Soluções\nContato: João" → [("Empresa","CARO Soluções"),...]
    """
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key and value and len(key) < 60:
                pairs.append((key, value))
    return pairs
