"""
core/template_reader.py — Agente de Leitura do Template (6.1)

Lê o template .pptx e extrai a estrutura completa:
  - Layout de cada slide
  - Posição e dimensões de cada shape
  - Formatação de fonte (tamanho, cor, bold, etc.)
  - Capacidades de cada slide (chars, bullets)
  - Metadados da identidade visual (cores, fontes dominantes)

Output:
  TemplateModel — modelo rico do template com acesso rápido por slide
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ast_pptx import (
    AlignEnum, GroupNode, ImageNode, PptxAST,
    RunNode, ShapeNode, SlideNode, TableNode, TextFrameNode,
)
from .template_cache import TemplateCache

logger = logging.getLogger(__name__)


# ── Modelos de capacidade ─────────────────────────────────────────────────────

@dataclass
class SlideCapacity:
    """Capacidade de um slide — limites de texto, bullets, etc."""
    slide_number: int
    layout_name: str
    title_max_chars: int = 120
    body_max_chars: int = 1200
    bullet_max_chars: int = 200
    max_bullets: int = 8
    has_title: bool = True
    has_body: bool = True
    has_date_field: bool = False
    body_shape_names: List[str] = field(default_factory=list)
    title_shape_names: List[str] = field(default_factory=list)
    image_slots: int = 0
    table_slots: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slide_number": self.slide_number,
            "layout_name": self.layout_name,
            "title_max_chars": self.title_max_chars,
            "body_max_chars": self.body_max_chars,
            "bullet_max_chars": self.bullet_max_chars,
            "max_bullets": self.max_bullets,
            "has_title": self.has_title,
            "has_body": self.has_body,
            "has_date_field": self.has_date_field,
            "body_shape_names": self.body_shape_names,
            "title_shape_names": self.title_shape_names,
            "image_slots": self.image_slots,
            "table_slots": self.table_slots,
        }


@dataclass
class FontProfile:
    """Perfil de fonte dominante extraído do template."""
    name: str = "Calibri"
    size_pt: float = 14.0
    color_hex: str = "#000000"
    bold: bool = False
    italic: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "size_pt": self.size_pt,
            "color_hex": self.color_hex,
            "bold": self.bold,
            "italic": self.italic,
        }


@dataclass
class TemplateIdentity:
    """Identidade visual extraída automaticamente do template."""
    primary_color_hex: str = "#003087"     # cor dominante
    secondary_color_hex: str = "#FFFFFF"   # cor secundária
    accent_color_hex: str = "#0066CC"      # destaque
    background_color_hex: str = "#FFFFFF"
    title_font: FontProfile = field(default_factory=FontProfile)
    body_font: FontProfile = field(default_factory=FontProfile)
    detected_colors: List[str] = field(default_factory=list)
    detected_fonts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_color_hex": self.primary_color_hex,
            "secondary_color_hex": self.secondary_color_hex,
            "accent_color_hex": self.accent_color_hex,
            "background_color_hex": self.background_color_hex,
            "title_font": self.title_font.to_dict(),
            "body_font": self.body_font.to_dict(),
            "detected_colors": self.detected_colors,
            "detected_fonts": self.detected_fonts,
        }


@dataclass
class EditableField:
    """
    Campo editável em um slide.
    Mapeia shape_name + paragraph_range para um campo de conteúdo.
    """
    field_id: str          # ex: "slide4_body", "slide1_title"
    slide_number: int
    shape_name: str
    shape_id: int
    field_type: str        # "title" | "body" | "date" | "subtitle"
    current_text: str = ""
    max_chars: int = 1200
    is_placeholder: bool = False
    placeholder_idx: Optional[int] = None
    font_profile: Optional[FontProfile] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "slide_number": self.slide_number,
            "shape_name": self.shape_name,
            "shape_id": self.shape_id,
            "field_type": self.field_type,
            "current_text": self.current_text,
            "max_chars": self.max_chars,
            "is_placeholder": self.is_placeholder,
            "placeholder_idx": self.placeholder_idx,
            "font_profile": self.font_profile.to_dict() if self.font_profile else None,
        }


# ── Template Reader ───────────────────────────────────────────────────────────

class TemplateReader:
    """
    Agente de Leitura do Template (6.1).

    Lê o .pptx usando a AST e extrai:
      1. Capacidade de cada slide (chars, bullets, campos)
      2. Identidade visual (cores, fontes)
      3. Mapeamento de campos editáveis por slide

    Uso:
        reader = TemplateReader(cache_dir=".cache")
        model = reader.read("templates/CARO_Bobinas.pptx")
        model.describe_slide(4)
    """

    def __init__(self, cache_dir: str | Path = ".cache", force_parse: bool = False):
        self.cache = TemplateCache(cache_dir=cache_dir)
        self.force_parse = force_parse

    def read(self, pptx_path: str | Path) -> "TemplateModel":
        """
        Lê o template e retorna um TemplateModel rico.

        Args:
            pptx_path: Caminho para o arquivo .pptx

        Returns:
            TemplateModel com todos os metadados extraídos
        """
        path = Path(pptx_path)

        if self.force_parse:
            self.cache.invalidate(path)

        logger.info(f"📖 Lendo template: {path.name}")
        ast = self.cache.get_or_parse(path)

        logger.info(f"🔍 Analisando estrutura: {ast.slide_count} slides")
        model = self._build_model(ast, path)

        logger.info(f"✅ Template modelado: {len(model.editable_fields)} campos editáveis")
        return model

    def _build_model(self, ast: PptxAST, path: Path) -> "TemplateModel":
        """Constrói o TemplateModel a partir da AST."""
        identity = self._extract_identity(ast)
        capacities = {}
        editable_fields = {}

        for slide in ast.slides:
            cap = self._analyze_slide_capacity(slide)
            capacities[slide.slide_number] = cap

            fields = self._extract_editable_fields(slide, identity)
            for f in fields:
                editable_fields[f.field_id] = f

        return TemplateModel(
            ast=ast,
            file_path=str(path),
            identity=identity,
            slide_capacities=capacities,
            editable_fields=editable_fields,
        )

    def _extract_identity(self, ast: PptxAST) -> TemplateIdentity:
        """Extrai a identidade visual do template analisando cores e fontes."""
        colors = []
        fonts = []
        title_profiles = []
        body_profiles = []

        for slide in ast.slides[:10]:  # Analisar primeiros 10 slides
            for shape in slide.shapes:
                if not isinstance(shape, ShapeNode):
                    continue
                if not shape.text_frame:
                    continue

                for para in shape.text_frame.paragraphs:
                    for run in para.runs:
                        if run.font_color_hex:
                            colors.append(run.font_color_hex)
                        if run.font_name:
                            fonts.append(run.font_name)

                        profile = FontProfile(
                            name=run.font_name or "Calibri",
                            size_pt=run.font_size_pt or 14.0,
                            color_hex=run.font_color_hex or "#000000",
                            bold=run.bold or False,
                            italic=run.italic or False,
                        )

                        if shape.is_placeholder and shape.placeholder_idx == 0:
                            title_profiles.append(profile)
                        elif shape.is_placeholder:
                            body_profiles.append(profile)

        # Cor dominante (mais frequente)
        from collections import Counter
        color_counts = Counter(colors)
        font_counts = Counter(fonts)

        primary_color = "#003087"
        if color_counts:
            # Preferir cores escuras/brand (não branco/preto puro)
            candidates = [c for c, _ in color_counts.most_common(10)
                          if c not in ("#FFFFFF", "#000000", "#FFFFFF")]
            primary_color = candidates[0] if candidates else "#003087"

        title_font = title_profiles[0] if title_profiles else FontProfile(
            name="Calibri", size_pt=24.0, bold=True
        )
        body_font = body_profiles[0] if body_profiles else FontProfile(
            name="Calibri", size_pt=14.0
        )

        unique_colors = list(dict.fromkeys(colors))[:20]
        unique_fonts = list(dict.fromkeys(fonts))[:10]

        return TemplateIdentity(
            primary_color_hex=primary_color,
            title_font=title_font,
            body_font=body_font,
            detected_colors=unique_colors,
            detected_fonts=unique_fonts,
        )

    def _analyze_slide_capacity(self, slide: SlideNode) -> SlideCapacity:
        """Analisa a capacidade de texto de um slide."""
        has_title = False
        has_body = False
        has_date = False
        title_shapes = []
        body_shapes = []
        image_slots = 0
        table_slots = 0

        for shape in slide.shapes:
            if isinstance(shape, ImageNode):
                image_slots += 1
            elif isinstance(shape, TableNode):
                table_slots += 1
            elif isinstance(shape, ShapeNode) and shape.text_frame:
                name_lower = shape.name.lower()
                if shape.is_placeholder and shape.placeholder_idx == 0:
                    has_title = True
                    title_shapes.append(shape.name)
                elif "título" in name_lower or "title" in name_lower:
                    has_title = True
                    title_shapes.append(shape.name)
                elif "data" in name_lower or "date" in name_lower:
                    has_date = True
                elif shape.is_placeholder or "conteúdo" in name_lower or "content" in name_lower:
                    has_body = True
                    body_shapes.append(shape.name)

        # Estimar capacidade pelo tamanho dos shapes
        body_max = 1200
        for shape in slide.shapes:
            if isinstance(shape, ShapeNode) and shape.text_frame:
                if shape.height_in and shape.width_in:
                    area = shape.height_in * shape.width_in
                    estimated = int(area * 150)  # ~150 chars por polegada²
                    if estimated > body_max:
                        body_max = min(estimated, 2000)

        return SlideCapacity(
            slide_number=slide.slide_number,
            layout_name=slide.layout_name,
            has_title=has_title,
            has_body=has_body or len(body_shapes) > 0,
            has_date_field=has_date,
            title_shape_names=title_shapes,
            body_shape_names=body_shapes,
            image_slots=image_slots,
            table_slots=table_slots,
            body_max_chars=body_max,
        )

    def _extract_editable_fields(
        self, slide: SlideNode, identity: TemplateIdentity
    ) -> List[EditableField]:
        """Extrai todos os campos editáveis de um slide."""
        fields = []

        for shape in slide.shapes:
            if not isinstance(shape, ShapeNode):
                continue
            if not shape.text_frame:
                continue

            text = shape.text_frame.full_text.strip()
            name_lower = shape.name.lower()

            # Determinar tipo do campo
            if shape.is_placeholder and shape.placeholder_idx == 0:
                field_type = "title"
                max_chars = 120
            elif "título" in name_lower or "title" in name_lower:
                field_type = "title"
                max_chars = 120
            elif "subtítulo" in name_lower or "subtitle" in name_lower:
                field_type = "subtitle"
                max_chars = 200
            elif "data" in name_lower or "date" in name_lower:
                field_type = "date"
                max_chars = 50
            elif shape.height_in and shape.height_in > 0.5:
                field_type = "body"
                max_chars = 1500
            else:
                continue  # Shape pequeno sem uso claro

            # Extrair perfil de fonte dominante do shape
            font_profile = None
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if run.font_name:
                        font_profile = FontProfile(
                            name=run.font_name,
                            size_pt=run.font_size_pt or 14.0,
                            color_hex=run.font_color_hex or "#000000",
                            bold=run.bold or False,
                            italic=run.italic or False,
                        )
                        break
                if font_profile:
                    break

            field_id = f"slide{slide.slide_number}_{field_type}_{shape.shape_id}"

            fields.append(EditableField(
                field_id=field_id,
                slide_number=slide.slide_number,
                shape_name=shape.name,
                shape_id=shape.shape_id,
                field_type=field_type,
                current_text=text,
                max_chars=max_chars,
                is_placeholder=shape.is_placeholder,
                placeholder_idx=shape.placeholder_idx,
                font_profile=font_profile or identity.body_font,
            ))

        return fields


# ── Template Model ────────────────────────────────────────────────────────────

class TemplateModel:
    """
    Modelo rico do template PPTX.

    Centraliza todo conhecimento sobre o template:
      - AST completa
      - Identidade visual
      - Capacidade de cada slide
      - Campos editáveis mapeados
    """

    def __init__(
        self,
        ast: PptxAST,
        file_path: str,
        identity: TemplateIdentity,
        slide_capacities: Dict[int, SlideCapacity],
        editable_fields: Dict[str, EditableField],
    ):
        self.ast = ast
        self.file_path = file_path
        self.identity = identity
        self.slide_capacities = slide_capacities
        self.editable_fields = editable_fields

    # ── Acesso rápido ─────────────────────────────────────────────────────────

    def get_slide(self, number: int) -> Optional[SlideNode]:
        return self.ast.get_slide(number)

    def get_capacity(self, slide_number: int) -> Optional[SlideCapacity]:
        return self.slide_capacities.get(slide_number)

    def get_fields_for_slide(self, slide_number: int) -> List[EditableField]:
        return [f for f in self.editable_fields.values()
                if f.slide_number == slide_number]

    def get_title_field(self, slide_number: int) -> Optional[EditableField]:
        for f in self.get_fields_for_slide(slide_number):
            if f.field_type == "title":
                return f
        return None

    def get_body_fields(self, slide_number: int) -> List[EditableField]:
        return [f for f in self.get_fields_for_slide(slide_number)
                if f.field_type == "body"]

    # ── Informações descritivas ───────────────────────────────────────────────

    def describe_slide(self, slide_number: int) -> str:
        """Descrição textual de um slide para uso nos agentes."""
        slide = self.get_slide(slide_number)
        if not slide:
            return f"Slide {slide_number} não encontrado."

        cap = self.get_capacity(slide_number)
        fields = self.get_fields_for_slide(slide_number)

        lines = [
            f"Slide {slide_number}: {slide.title[:60] if slide.title else '(sem título)'}",
            f"  Layout: {slide.layout_name}",
        ]
        if cap:
            lines += [
                f"  Tem título: {cap.has_title} | Tem corpo: {cap.has_body}",
                f"  Max chars corpo: {cap.body_max_chars} | Max bullets: {cap.max_bullets}",
                f"  Imagens: {cap.image_slots} | Tabelas: {cap.table_slots}",
            ]
        if fields:
            lines.append(f"  Campos editáveis ({len(fields)}):")
            for f in fields:
                lines.append(f"    [{f.field_type}] {f.shape_name!r}: {f.current_text[:60]!r}")

        return "\n".join(lines)

    def describe_all(self) -> str:
        """Descrição completa de todos os slides."""
        lines = [
            f"Template: {Path(self.file_path).name}",
            f"Slides: {self.ast.slide_count}",
            f"Identidade visual: {self.identity.primary_color_hex}",
            f"Fonte título: {self.identity.title_font.name} {self.identity.title_font.size_pt}pt",
            f"Fonte corpo: {self.identity.body_font.name} {self.identity.body_font.size_pt}pt",
            f"Total campos editáveis: {len(self.editable_fields)}",
            "",
            "── SLIDES ──────────────────────────────────────────────",
        ]
        for i in range(1, self.ast.slide_count + 1):
            lines.append(self.describe_slide(i))
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "slide_count": self.ast.slide_count,
            "identity": self.identity.to_dict(),
            "slide_capacities": {k: v.to_dict() for k, v in self.slide_capacities.items()},
            "editable_fields": {k: v.to_dict() for k, v in self.editable_fields.items()},
        }


# ── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python template_reader.py <template.pptx>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    reader = TemplateReader()
    model = reader.read(sys.argv[1])

    if len(sys.argv) > 2:
        slide_num = int(sys.argv[2])
        print(model.describe_slide(slide_num))
    else:
        print(model.describe_all())
