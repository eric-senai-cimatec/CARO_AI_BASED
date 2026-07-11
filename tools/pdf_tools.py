"""
tools/pdf_tools.py — Leitura de FSIPP em PDF

Estratégia em cascata (Windows-friendly, sem dependências externas de sistema):
  1. PyMuPDF / fitz     — melhor qualidade, funciona em Windows nativamente
  2. pdfplumber         — alternativa com suporte a tabelas
  3. OCR via PyMuPDF    — rasteriza e usa pytesseract (PDFs escaneados)
  4. Fallback           — mensagem de erro clara com instruções

Uso:
    from tools.pdf_tools import read_fsipp
    text = read_fsipp("fsipp.pdf")   # PDF, TXT ou texto direto
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from PIL import Image
import io
from typing import Tuple
import fitz  # PyMuPDF
import pytesseract
import pdfplumber

logger = logging.getLogger(__name__)


class PDFReader:
    """
    Leitor de PDF multi-estratégia — funciona em Windows sem ferramentas de sistema.
    """

    def extract_text(self, pdf_path: str | Path) -> Tuple[str, str]:
        """
        Extrai texto do PDF usando a melhor estratégia disponível.

        Returns:
            (text, method_used)
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF não encontrado: {path}")

        size_kb = path.stat().st_size // 1024
        logger.info(f"📄 Extraindo texto: {path.name} ({size_kb} KB)")

        # 1. PyMuPDF (fitz) — melhor opção, funciona em Windows
        text, method = self._try_pymupdf(path)
        if text and len(text.strip()) > 100:
            logger.info(f"✅ Extraído via PyMuPDF: {len(text)} chars")
            return text, method

        # 2. pdfplumber
        text, method = self._try_pdfplumber(path)
        if text and len(text.strip()) > 100:
            logger.info(f"✅ Extraído via pdfplumber: {len(text)} chars")
            return text, method

        # 3. OCR via PyMuPDF (rasteriza) + pytesseract
        logger.warning("Texto nativo não encontrado — tentando OCR...")
        text, method = self._try_ocr_pymupdf(path)
        if text and len(text.strip()) > 50:
            logger.info(f"✅ Extraído via OCR: {len(text)} chars")
            return text, method

        # 4. Fallback
        msg = (
            f"[ERRO: Não foi possível extrair texto de '{path.name}'.\n"
            f"Instale PyMuPDF: pip install pymupdf\n"
            f"Ou converta para .txt e passe o .txt como input.]"
        )
        logger.error(msg)
        return msg, "fallback"

    def get_page_count(self, pdf_path: str | Path) -> int:
        path = Path(pdf_path)
        # Via PyMuPDF
        try:
            doc = fitz.open(str(path))
            n = len(doc)
            doc.close()
            return n
        except Exception:
            pass
        # Via pdfplumber
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                return len(pdf.pages)
        except Exception:
            return 0

    # ── Estratégias ───────────────────────────────────────────────────────────

    def _try_pymupdf(self, path: Path) -> Tuple[str, str]:
        """PyMuPDF (fitz) — extração de alta qualidade, funciona offline."""
        try:
            doc = fitz.open(str(path))
            pages_text = []
            for i, page in enumerate(doc):
                # Texto da página
                text = page.get_text("text")
                # Texto de tabelas (blocos ordenados)
                blocks = page.get_text("blocks")
                if not text.strip() and blocks:
                    text = "\n".join(
                        b[4].strip() for b in blocks if b[4].strip()
                    )
                if text.strip():
                    pages_text.append(f"[Página {i+1}]\n{text.strip()}")
            doc.close()
            return "\n\n".join(pages_text), "pymupdf"
        except Exception as e:
            logger.debug(f"PyMuPDF falhou: {e}")
            return "", "pymupdf"

    def _try_pdfplumber(self, path: Path) -> Tuple[str, str]:
        """pdfplumber — bom para PDFs com tabelas."""
        try:
            pages_text = []
            with pdfplumber.open(str(path)) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""

                    # Tabelas
                    try:
                        tables = page.extract_tables()
                        for table in (tables or []):
                            for row in table:
                                if row:
                                    row_text = " | ".join(
                                        str(c).strip() if c else "" for c in row
                                    )
                                    if row_text.strip():
                                        text += f"\n{row_text}"
                    except Exception:
                        pass

                    if text.strip():
                        pages_text.append(f"[Página {i+1}]\n{text.strip()}")
            return "\n\n".join(pages_text), "pdfplumber"
        except Exception as e:
            logger.debug(f"pdfplumber falhou: {e}")
            return "", "pdfplumber"

    def _try_ocr_pymupdf(self, path: Path) -> Tuple[str, str]:
        """OCR: rasteriza via PyMuPDF + pytesseract."""
        try:
            doc = fitz.open(str(path))
            texts = []
            for page in doc:
                mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = ~144 DPI
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("jpeg")
                img = Image.open(io.BytesIO(img_data))
                text = pytesseract.image_to_string(img, lang="por+eng")
                if text.strip():
                    texts.append(text.strip())
            doc.close()
            return "\n\n".join(texts), "ocr"
        except Exception as e:
            logger.debug(f"OCR falhou: {e}")
            return "", "ocr"


def read_fsipp(source: str | Path) -> str:
    """
    Lê um FSIPP de qualquer formato:
      - .pdf  → extrai texto via PDFReader (PyMuPDF → pdfplumber → OCR)
      - .txt/.md → lê diretamente
      - string pura (>50 chars) → retorna como está

    Args:
        source: Caminho para arquivo ou texto puro

    Returns:
        Texto extraído como string
    """
    # String pura (não é caminho de arquivo existente)
    if isinstance(source, str) and not os.path.exists(source) and len(source) > 50:
        logger.info(f"Usando texto fornecido diretamente ({len(source)} chars)")
        return source

    path = Path(source)

    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    if path.suffix.lower() == ".pdf":
        reader = PDFReader()
        text, method = reader.extract_text(path)
        pages = reader.get_page_count(path)
        logger.info(f"FSIPP PDF lido via {method}: {len(text)} chars, {pages} páginas")
        return text

    if path.suffix.lower() in (".txt", ".md", ".rst"):
        return path.read_text(encoding="utf-8", errors="replace")

    raise ValueError(
        f"Formato não suportado: {path.suffix}\n"
        f"Use .pdf, .txt, ou cole o texto diretamente."
    )
