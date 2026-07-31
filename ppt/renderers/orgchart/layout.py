from __future__ import annotations

from ppt.renderers.orgchart.models import OrgChart, OrgNode
from ppt.renderers.orgchart.utils import Dimensions, calc_node_width


class TreeLayout:
    def __init__(self, dims: Dimensions) -> None:
        self.dims = dims

    def layout(self, chart: OrgChart) -> None:
        if not chart.root:
            return
        self._assign_widths(chart.root)
        self._first_pass(chart.root)
        self._second_pass(chart.root, 0.0)
        self._fit_to_slide(chart)

    def _assign_widths(self, node: OrgNode) -> None:
        node.width = calc_node_width(node.text, self.dims)
        node.height = self.dims.node_height
        for child in node.children:
            self._assign_widths(child)

    def _first_pass(self, node: OrgNode) -> None:
        if not node.children:
            node.prelim = 0.0
            node.modifier = 0.0
            return
        for child in node.children:
            self._first_pass(child)
        self._position_children(node)
        first = node.children[0]
        last = node.children[-1]
        node.prelim = (first.prelim + last.prelim) / 2.0
        self._resolve_conflicts(node)

    def _position_children(self, node: OrgNode) -> None:
        x = 0.0
        for child in node.children:
            child.prelim = x + child.width / 2.0
            x += child.width + 20.0

    def _resolve_conflicts(self, node: OrgNode) -> None:
        for i in range(len(node.children) - 1):
            right = self._right_contour(node.children[i], 0.0)
            for j in range(i + 1, len(node.children)):
                left = self._left_contour(node.children[j], 0.0)
                gap = 15.0
                overlap = right - left + gap
                if overlap > 0:
                    self._shift(node.children[j], overlap)
                    right = self._right_contour(node.children[j], 0.0)

    def _right_contour(self, node: OrgNode, mod: float) -> float:
        m = mod + node.modifier
        right = node.prelim + m + node.width / 2.0
        for child in node.children:
            child_right = self._right_contour(child, m)
            if child_right > right:
                right = child_right
        return right

    def _left_contour(self, node: OrgNode, mod: float) -> float:
        m = mod + node.modifier
        left = node.prelim + m - node.width / 2.0
        for child in node.children:
            child_left = self._left_contour(child, m)
            if child_left < left:
                left = child_left
        return left

    def _shift(self, node: OrgNode, amount: float) -> None:
        node.prelim += amount
        node.modifier += amount
        for child in node.children:
            self._shift(child, amount)

    def _second_pass(self, node: OrgNode, mod: float) -> None:
        node.x = node.prelim + mod
        node.y = float(node.level) * (self.dims.node_height + 50.0) + self.dims.margin_top
        m = mod + node.modifier
        for child in node.children:
            self._second_pass(child, m)

    def _fit_to_slide(self, chart: OrgChart) -> None:
        if not chart.nodes:
            return
        min_x = min(n.x - n.width / 2.0 for n in chart.nodes)
        max_x = max(n.x + n.width / 2.0 for n in chart.nodes)
        tree_w = max_x - min_x
        avail = self.dims.usable_width
        if tree_w <= 0:
            return
        if tree_w > avail:
            scale = avail / tree_w
            for n in chart.nodes:
                n.x = self.dims.margin_left + (n.x - min_x) * scale + n.width / 2.0
        else:
            offset = self.dims.margin_left - min_x + (avail - tree_w) / 2.0
            for n in chart.nodes:
                n.x += offset
