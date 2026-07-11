"""
core/ — Módulos de baixo nível do CARO Framework

  ast_pptx.py        — Parser recursivo + AST
  template_cache.py  — Cache JSON
  template_reader.py — Agente leitura (6.1) + TemplateModel
  shape_editor.py    — Editor preservando formatação
  region_detector.py — Detecção automática de regiões
  layout_preserver.py — Preservação de layout
"""

from .ast_pptx import PptxAST, SlideNode, ShapeNode, RunNode, ParagraphNode
from .template_cache import TemplateCache
from .template_reader import TemplateReader, TemplateModel
from .shape_editor import ShapeEditor, TextReplacer, FormatPreserver
from .region_detector import RegionDetector, SlideRegionMap, RegionType

__all__ = [
    "PptxAST", "SlideNode", "ShapeNode", "RunNode", "ParagraphNode",
    "TemplateCache",
    "TemplateReader", "TemplateModel",
    "ShapeEditor", "TextReplacer", "FormatPreserver",
    "RegionDetector", "SlideRegionMap", "RegionType",
]
