from __future__ import annotations

from dataclasses import dataclass

from pptx.dml.color import RGBColor
from pptx.util import Pt


@dataclass(frozen=True)
class ColorPalette:
    root_bg: RGBColor = RGBColor(0x1B, 0x3A, 0x5C)
    root_text: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)
    level_bg: RGBColor = RGBColor(0x2E, 0x86, 0xAB)
    level_text: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)
    leaf_bg: RGBColor = RGBColor(0xEB, 0xF5, 0xFB)
    leaf_text: RGBColor = RGBColor(0x33, 0x33, 0x33)
    line: RGBColor = RGBColor(0x99, 0x99, 0x99)
    border: RGBColor = RGBColor(0x1B, 0x3A, 0x5C)
    white: RGBColor = RGBColor(0xFF, 0xFF, 0xFF)
    dark: RGBColor = RGBColor(0x33, 0x33, 0x33)

_DEFAULT_PALETTE = ColorPalette()

@dataclass
class Dimensions:
    slide_width: float = 0.0
    slide_height: float = 0.0
    margin_left: float = 30.0
    margin_right: float = 30.0
    margin_top: float = 50.0
    margin_bottom: float = 20.0
    node_padding_x: float = 16.0
    node_padding_y: float = 8.0
    min_node_width: float = 80.0
    max_node_width: float = 200.0
    node_height: float = 36.0
    font_size: float = 9.0

    @property
    def usable_width(self) -> float:
        return self.slide_width - self.margin_left - self.margin_right

    @property
    def usable_height(self) -> float:
        return self.slide_height - self.margin_top - self.margin_bottom


def estimate_text_width(text: str, font_size_pt: float = 9.0) -> float:
    return max(len(text) * font_size_pt * 0.7, 60.0)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def calc_node_width(text: str, dims: Dimensions) -> float:
    w = estimate_text_width(text) + dims.node_padding_x * 2
    return clamp(w, dims.min_node_width, dims.max_node_width)


def get_level_color(node_level: int, is_root: bool, max_depth: int, palette: ColorPalette = _DEFAULT_PALETTE) -> tuple:
    if is_root:
        return palette.root_bg, palette.root_text
    if node_level >= max_depth:
        return palette.leaf_bg, palette.leaf_text
    fade = node_level / max(1, max_depth - 1) if max_depth > 1 else 0
    r = int(palette.level_bg[0] + (palette.leaf_bg[0] - palette.level_bg[0]) * fade)
    g = int(palette.level_bg[1] + (palette.leaf_bg[1] - palette.level_bg[1]) * fade)
    b = int(palette.level_bg[2] + (palette.leaf_bg[2] - palette.level_bg[2]) * fade)
    return RGBColor(r, g, b), palette.level_text
