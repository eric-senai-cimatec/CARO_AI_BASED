"""
core/template_cache.py — Cache JSON da AST do template

Persiste e recupera a AST do PowerPoint em JSON para evitar
re-parse a cada execução. Usa hash MD5 do arquivo como chave.

Classes:
  TemplateCache — gerenciador de cache com invalidação automática
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .ast_pptx import PptxAST

logger = logging.getLogger(__name__)


class CacheEntry:
    """Entrada de cache com metadados."""

    def __init__(self, ast: PptxAST, cached_at: float, cache_version: str):
        self.ast = ast
        self.cached_at = cached_at
        self.cache_version = cache_version

    @property
    def age_seconds(self) -> float:
        return time.time() - self.cached_at

    @property
    def age_hours(self) -> float:
        return self.age_seconds / 3600


class TemplateCache:
    """
    Cache JSON para a AST do template PPTX.

    Funciona como um dicionário persistente:
      key   = hash MD5 do arquivo .pptx
      value = JSON serializado da PptxAST

    Uso:
        cache = TemplateCache(cache_dir=".cache")
        ast = cache.get_or_parse("template.pptx")
        cache.invalidate("template.pptx")
    """

    CACHE_VERSION = "1.0.0"
    META_FILE = "cache_index.json"

    def __init__(
        self,
        cache_dir: str | Path = ".cache",
        max_age_hours: float = 24 * 7,  # 1 semana
        enabled: bool = True,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours
        self.enabled = enabled
        self._index: Dict[str, Dict[str, Any]] = self._load_index()

    # ── API pública ──────────────────────────────────────────────────────────

    def get_or_parse(self, pptx_path: str | Path) -> PptxAST:
        """
        Retorna a AST do template — do cache se disponível, ou faz parse.

        Args:
            pptx_path: Caminho para o arquivo .pptx

        Returns:
            PptxAST: Árvore de sintaxe abstrata da apresentação
        """
        path = Path(pptx_path)
        if not path.exists():
            raise FileNotFoundError(f"Template não encontrado: {path}")

        file_hash = self._hash_file(path)

        if self.enabled:
            cached = self._load(file_hash)
            if cached is not None:
                logger.info(
                    f"✅ Cache hit: {path.name} "
                    f"(age={cached.age_hours:.1f}h, hash={file_hash[:8]}...)"
                )
                return cached.ast

        # Parse e armazenar
        logger.info(f"🔄 Parsing template: {path.name}")
        ast = PptxAST.from_file(path)

        if self.enabled:
            self._store(file_hash, ast, str(path))
            logger.info(f"💾 AST cached: {path.name}")

        return ast

    def get(self, pptx_path: str | Path) -> Optional[PptxAST]:
        """Retorna AST do cache ou None se não encontrado/expirado."""
        path = Path(pptx_path)
        file_hash = self._hash_file(path)
        entry = self._load(file_hash)
        return entry.ast if entry else None

    def store(self, pptx_path: str | Path, ast: PptxAST) -> Path:
        """Armazena AST no cache manualmente."""
        path = Path(pptx_path)
        file_hash = self._hash_file(path)
        return self._store(file_hash, ast, str(path))

    def invalidate(self, pptx_path: str | Path) -> bool:
        """Invalida o cache de um template específico."""
        path = Path(pptx_path)
        file_hash = self._hash_file(path)
        if file_hash in self._index:
            cache_file = self.cache_dir / f"{file_hash}.json"
            if cache_file.exists():
                cache_file.unlink()
            del self._index[file_hash]
            self._save_index()
            logger.info(f"🗑  Cache invalidado: {path.name}")
            return True
        return False

    def clear_all(self) -> int:
        """Limpa todo o cache. Retorna número de entradas removidas."""
        count = 0
        for hash_key in list(self._index.keys()):
            cache_file = self.cache_dir / f"{hash_key}.json"
            if cache_file.exists():
                cache_file.unlink()
                count += 1
        self._index = {}
        self._save_index()
        logger.info(f"🗑  Cache limpo: {count} entradas removidas")
        return count

    def list_entries(self) -> list[Dict[str, Any]]:
        """Lista todas as entradas do cache."""
        entries = []
        for hash_key, meta in self._index.items():
            age_h = (time.time() - meta.get("cached_at", 0)) / 3600
            entries.append({
                "hash": hash_key[:8] + "...",
                "file": meta.get("file_path", ""),
                "age_hours": round(age_h, 1),
                "version": meta.get("cache_version", "?"),
                "valid": age_h < self.max_age_hours,
            })
        return entries

    def stats(self) -> Dict[str, Any]:
        """Retorna estatísticas do cache."""
        entries = self.list_entries()
        valid = sum(1 for e in entries if e["valid"])
        return {
            "total_entries": len(entries),
            "valid_entries": valid,
            "expired_entries": len(entries) - valid,
            "cache_dir": str(self.cache_dir),
            "max_age_hours": self.max_age_hours,
            "enabled": self.enabled,
        }

    # ── Internos ──────────────────────────────────────────────────────────────

    def _hash_file(self, path: Path) -> str:
        import hashlib
        return hashlib.md5(path.read_bytes()).hexdigest()

    def _cache_path(self, file_hash: str) -> Path:
        return self.cache_dir / f"{file_hash}.json"

    def _load(self, file_hash: str) -> Optional[CacheEntry]:
        if file_hash not in self._index:
            return None

        meta = self._index[file_hash]
        cached_at = meta.get("cached_at", 0)
        cache_version = meta.get("cache_version", "")

        # Verificar versão
        if cache_version != self.CACHE_VERSION:
            logger.debug(f"Cache version mismatch ({cache_version} != {self.CACHE_VERSION})")
            return None

        # Verificar expiração
        age_hours = (time.time() - cached_at) / 3600
        if age_hours > self.max_age_hours:
            logger.debug(f"Cache expirado ({age_hours:.1f}h > {self.max_age_hours}h)")
            return None

        # Carregar arquivo JSON
        cache_file = self._cache_path(file_hash)
        if not cache_file.exists():
            logger.debug(f"Arquivo de cache não encontrado: {cache_file}")
            return None

        try:
            ast = PptxAST.load_json(cache_file)
            return CacheEntry(ast=ast, cached_at=cached_at, cache_version=cache_version)
        except Exception as e:
            logger.warning(f"Erro ao carregar cache: {e}")
            return None

    def _store(self, file_hash: str, ast: PptxAST, file_path: str) -> Path:
        cache_file = self._cache_path(file_hash)

        try:
            ast.save_json(cache_file)
            self._index[file_hash] = {
                "file_path": file_path,
                "cached_at": time.time(),
                "cache_version": self.CACHE_VERSION,
                "slide_count": ast.slide_count,
            }
            self._save_index()
            return cache_file
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
            raise

    def _load_index(self) -> Dict[str, Any]:
        index_file = self.cache_dir / self.META_FILE
        if index_file.exists():
            try:
                return json.loads(index_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self):
        index_file = self.cache_dir / self.META_FILE
        index_file.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )