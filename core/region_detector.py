"""
core/region_detector.py — Detecção Automática de Regiões

Analisa a geometria dos shapes de um slide e identifica
automaticamente as regiões de conteúdo:
  - Cabeçalho (header)
  - Título (title)
  - Corpo principal (body)
  - Rodapé (footer)
  - Sidebar/coluna lateral
  - Regiões de imagem
  - Regiões de tabela

Usa heurísticas de posição/tamanho para fazer a detecção.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .ast_pptx import GroupNode, ImageNode, ShapeNode, SlideNode, TableNode

logger = logging.getLogger(__name__)


class RegionType(str, Enum):
    HEADER   = "header"
    TITLE    = "title"
    SUBTITLE = "subtitle"
    BODY     = "body"
    FOOTER   = "footer"
    SIDEBAR  = "sidebar"
    IMAGE    = "image"
    TABLE    = "table"
    LOGO     = "logo"
    DATE     = "date"
    UNKNOWN  = "unknown"


@dataclass
class Region:
    """Uma região detectada em um slide."""
    region_type: RegionType
    shape_ids: List[int]
    shape_names: List[str]
    left_in: float = 0.0
    top_in: float = 0.0
    width_in: float = 0.0
    height_in: float = 0.0
    text_preview: str = ""
    confidence: float = 1.0  # 0.0 a 1.0

    @property
    def area(self) -> float:
        return self.width_in * self.height_in

    @property
    def center_x(self) -> float:
        return self.left_in + self.width_in / 2

    @property
    def center_y(self) -> float:
        return self.top_in + self.height_in / 2

    @property
    def right(self) -> float:
        return self.left_in + self.width_in

    @property
    def bottom(self) -> float:
        return self.top_in + self.height_in

    def to_dict(self) -> Dict[str, Any]:
        return {
            "region_type": self.region_type.value,
            "shape_ids": self.shape_ids,
            "shape_names": self.shape_names,
            "bounds": {
                "left": round(self.left_in, 3),
                "top": round(self.top_in, 3),
                "width": round(self.width_in, 3),
                "height": round(self.height_in, 3),
            },
            "text_preview": self.text_preview[:80],
            "confidence": round(self.confidence, 2),
        }


@dataclass
class SlideRegionMap:
    """Mapa completo de regiões de um slide."""
    slide_number: int
    slide_width_in: float
    slide_height_in: float
    regions: List[Region] = field(default_factory=list)

    def get_regions(self, region_type: RegionType) -> List[Region]:
        return [r for r in self.regions if r.region_type == region_type]

    def get_title(self) -> Optional[Region]:
        titles = self.get_regions(RegionType.TITLE)
        return titles[0] if titles else None

    def get_body(self) -> Optional[Region]:
        bodies = self.get_regions(RegionType.BODY)
        # Retornar o maior
        if not bodies:
            return None
        return max(bodies, key=lambda r: r.area)

    def get_body_all(self) -> List[Region]:
        return self.get_regions(RegionType.BODY)

    def describe(self) -> str:
        lines = [f"Slide {self.slide_number} — {len(self.regions)} regiões detectadas:"]
        for r in self.regions:
            lines.append(
                f"  [{r.region_type.value:10s}] {r.shape_names!r:40s} "
                f"conf={r.confidence:.1f} area={r.area:.1f}in² "
                f"text={r.text_preview[:30]!r}"
            )
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slide_number": self.slide_number,
            "slide_width_in": self.slide_width_in,
            "slide_height_in": self.slide_height_in,
            "regions": [r.to_dict() for r in self.regions],
        }


class RegionDetector:
    """
    Detecta automaticamente regiões de conteúdo em slides.

    Heurísticas usadas:
      1. Placeholder type (mais confiável quando disponível)
      2. Posição vertical (header: top<15%, footer: bottom>85%)
      3. Tamanho relativo (title: wide & short, body: tall)
      4. Nome do shape (keywords: título, body, conteúdo, etc.)
      5. Conteúdo de texto (palavras-chave)
    """

    def __init__(
        self,
        slide_width_in: float = 13.33,
        slide_height_in: float = 7.5,
    ):
        self.W = slide_width_in
        self.H = slide_height_in

        # Zonas verticais (fração da altura)
        self.HEADER_ZONE = 0.20    # top 20%
        self.FOOTER_ZONE = 0.85    # bottom 15%
        self.SIDEBAR_WIDTH = 0.25  # lateral 25%

    def detect(self, slide: SlideNode) -> SlideRegionMap:
        """
        Analisa um SlideNode e retorna o SlideRegionMap.

        Args:
            slide: SlideNode da AST

        Returns:
            SlideRegionMap com todas as regiões detectadas
        """
        region_map = SlideRegionMap(
            slide_number=slide.slide_number,
            slide_width_in=self.W,
            slide_height_in=self.H,
        )

        for shape in slide.shapes:
            region = self._classify_shape(shape)
            if region:
                region_map.regions.append(region)

        # Pós-processamento: resolver conflitos
        self._resolve_conflicts(region_map)

        return region_map

    def detect_all(self, slides: List[SlideNode]) -> Dict[int, SlideRegionMap]:
        """Detecta regiões em todos os slides."""
        return {s.slide_number: self.detect(s) for s in slides}

    # ── Classificação ─────────────────────────────────────────────────────────

    def _classify_shape(
        self, shape
    ) -> Optional[Region]:
        """Classifica um shape em uma RegionType."""

        # Imagens
        if isinstance(shape, ImageNode):
            return self._classify_image(shape)

        # Tabelas
        if isinstance(shape, TableNode):
            return self._classify_table(shape)

        # Grupos — tentar classificar pelo conteúdo dos filhos
        if isinstance(shape, GroupNode):
            return self._classify_group(shape)

        # Shapes de texto
        if isinstance(shape, ShapeNode):
            return self._classify_text_shape(shape)

        return None

    def _classify_text_shape(self, shape: ShapeNode) -> Optional[Region]:
        """Classifica um ShapeNode de texto."""
        if not shape.text_frame:
            return None

        left = shape.left_in or 0.0
        top = shape.top_in or 0.0
        w = shape.width_in or 0.0
        h = shape.height_in or 0.0
        text = shape.text_frame.full_text.strip()

        # Heurística 1: Placeholder type
        if shape.is_placeholder:
            ph_type = shape.placeholder_type or ""
            ph_idx = shape.placeholder_idx

            if ph_idx == 0 or "TITLE" in ph_type.upper():
                return self._make_region(RegionType.TITLE, shape, confidence=0.99)
            if ph_idx == 1 or "BODY" in ph_type.upper():
                return self._make_region(RegionType.BODY, shape, confidence=0.95)
            if "SUBTITLE" in ph_type.upper():
                return self._make_region(RegionType.SUBTITLE, shape, confidence=0.95)
            if "DATE" in ph_type.upper() or "FOOTER" in ph_type.upper():
                return self._make_region(RegionType.FOOTER, shape, confidence=0.9)

        # Heurística 2: Nome do shape
        name_lower = shape.name.lower()
        if any(k in name_lower for k in ["título", "title", "header"]):
            return self._make_region(RegionType.TITLE, shape, confidence=0.85)
        if any(k in name_lower for k in ["body", "conteúdo", "content", "texto"]):
            return self._make_region(RegionType.BODY, shape, confidence=0.85)
        if any(k in name_lower for k in ["subtítulo", "subtitle"]):
            return self._make_region(RegionType.SUBTITLE, shape, confidence=0.85)
        if any(k in name_lower for k in ["data", "date", "footer", "rodapé"]):
            return self._make_region(RegionType.FOOTER, shape, confidence=0.85)
        if any(k in name_lower for k in ["logo", "imagem logo"]):
            return self._make_region(RegionType.LOGO, shape, confidence=0.9)

        if not text:
            return None

        # Heurística 3: Posição vertical
        top_frac = top / self.H if self.H > 0 else 0
        bot_frac = (top + h) / self.H if self.H > 0 else 1
        left_frac = left / self.W if self.W > 0 else 0
        width_frac = w / self.W if self.W > 0 else 0

        if top_frac < self.HEADER_ZONE and width_frac > 0.5:
            region_type = RegionType.TITLE
            confidence = 0.75
        elif bot_frac > self.FOOTER_ZONE and h < 0.8:
            region_type = RegionType.FOOTER
            confidence = 0.7
        elif left_frac < self.SIDEBAR_WIDTH and h > 1.0:
            region_type = RegionType.SIDEBAR
            confidence = 0.6
        elif h > 1.5 and width_frac > 0.4:
            region_type = RegionType.BODY
            confidence = 0.7
        elif top_frac < 0.35 and h < 1.5 and width_frac > 0.4:
            region_type = RegionType.TITLE
            confidence = 0.65
        else:
            region_type = RegionType.UNKNOWN
            confidence = 0.4

        return self._make_region(region_type, shape, confidence=confidence)

    def _classify_image(self, shape: ImageNode) -> Optional[Region]:
        """Classifica uma imagem."""
        left = shape.left_in or 0.0
        top = shape.top_in or 0.0
        w = shape.width_in or 0.0
        h = shape.height_in or 0.0

        # Logo: pequeno, no topo
        if h < 1.5 and w < 3.0 and (top / self.H < 0.2 or top / self.H > 0.85):
            region_type = RegionType.LOGO
            confidence = 0.7
        else:
            region_type = RegionType.IMAGE
            confidence = 0.9

        return Region(
            region_type=region_type,
            shape_ids=[shape.shape_id],
            shape_names=[shape.name],
            left_in=left,
            top_in=top,
            width_in=w,
            height_in=h,
            confidence=confidence,
        )

    def _classify_table(self, shape: TableNode) -> Region:
        return Region(
            region_type=RegionType.TABLE,
            shape_ids=[shape.shape_id],
            shape_names=[shape.name],
            left_in=shape.left_in or 0.0,
            top_in=shape.top_in or 0.0,
            width_in=shape.width_in or 0.0,
            height_in=shape.height_in or 0.0,
            confidence=1.0,
        )

    def _classify_group(self, shape: GroupNode) -> Optional[Region]:
        """Classifica grupo pelo conteúdo dos filhos."""
        left = shape.left_in or 0.0
        top = shape.top_in or 0.0
        w = shape.width_in or 0.0
        h = shape.height_in or 0.0

        # Grupo no canto = provavelmente logo/decoração
        top_frac = top / self.H if self.H > 0 else 0
        if h < 2.0 and w < 4.0:
            region_type = RegionType.LOGO
            confidence = 0.5
        elif top_frac > self.FOOTER_ZONE:
            region_type = RegionType.FOOTER
            confidence = 0.6
        else:
            return None  # Grupos grandes são provavelmente decoração

        return Region(
            region_type=region_type,
            shape_ids=[shape.shape_id],
            shape_names=[shape.name],
            left_in=left,
            top_in=top,
            width_in=w,
            height_in=h,
            confidence=confidence,
        )

    def _make_region(self, region_type: RegionType, shape: ShapeNode, confidence: float) -> Region:
        text = ""
        if shape.text_frame:
            text = shape.text_frame.full_text.strip()[:80]

        return Region(
            region_type=region_type,
            shape_ids=[shape.shape_id],
            shape_names=[shape.name],
            left_in=shape.left_in or 0.0,
            top_in=shape.top_in or 0.0,
            width_in=shape.width_in or 0.0,
            height_in=shape.height_in or 0.0,
            text_preview=text,
            confidence=confidence,
        )

    def _resolve_conflicts(self, region_map: SlideRegionMap):
        """
        Resolve conflitos quando múltiplas regiões do mesmo tipo existem.
        Mantém a de maior confiança ou maior área.
        """
        # Se há múltiplos TITLEs, manter o de maior confiança
        titles = [r for r in region_map.regions if r.region_type == RegionType.TITLE]
        if len(titles) > 1:
            best = max(titles, key=lambda r: (r.confidence, r.area))
            for t in titles:
                if t is not best:
                    t.region_type = RegionType.SUBTITLE
                    t.confidence *= 0.8

        # Se há BODYs sobrepostos, manter maiores
        bodies = [r for r in region_map.regions if r.region_type == RegionType.BODY]
        bodies_sorted = sorted(bodies, key=lambda r: r.area, reverse=True)
        for i, b in enumerate(bodies_sorted):
            if i == 0:
                b.confidence = min(b.confidence * 1.1, 1.0)


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from .ast_pptx import PptxAST

    if len(sys.argv) < 2:
        print("Uso: python region_detector.py <template.pptx> [slide_number]")
        sys.exit(1)

    ast = PptxAST.from_file(sys.argv[1])
    detector = RegionDetector(
        slide_width_in=ast.slide_width_in,
        slide_height_in=ast.slide_height_in,
    )

    if len(sys.argv) > 2:
        num = int(sys.argv[2])
        slide = ast.get_slide(num)
        if slide:
            region_map = detector.detect(slide)
            print(region_map.describe())
    else:
        for slide in ast.slides[:10]:
            region_map = detector.detect(slide)
            print(region_map.describe())
            print()