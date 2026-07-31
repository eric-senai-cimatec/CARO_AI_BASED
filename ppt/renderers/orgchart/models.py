from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class OrgNode:
    id: str
    text: str
    level: int = 0
    children: list["OrgNode"] = field(default_factory=list)
    parent_id: Optional[str] = None
    width: float = 0.0
    height: float = 0.0
    x: float = 0.0
    y: float = 0.0
    prelim: float = 0.0
    modifier: float = 0.0


@dataclass
class OrgEdge:
    source: str
    target: str


class OrgChart:
    def __init__(self, nodes: list[OrgNode], edges: list[OrgEdge]) -> None:
        self.nodes = nodes
        self.edges = edges
        self._root: Optional[OrgNode] = None
        self._node_map: dict[str, OrgNode] = {n.id: n for n in nodes}
        self._build_tree()

    def _build_tree(self) -> None:
        for edge in self.edges:
            parent = self._node_map.get(edge.source)
            child = self._node_map.get(edge.target)
            if parent and child:
                parent.children.append(child)
                child.parent_id = parent.id
                child.level = parent.level + 1
        for n in self.nodes:
            if n.parent_id is None:
                self._root = n
                break

    @property
    def root(self) -> Optional[OrgNode]:
        return self._root

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def max_depth(self) -> int:
        if not self.nodes:
            return 0
        return max(n.level for n in self.nodes)

    def get_nodes_at_level(self, level: int) -> list[OrgNode]:
        return [n for n in self.nodes if n.level == level]

    @classmethod
    def from_json(cls, data: dict) -> "OrgChart":
        nodes_raw = data.get("nodes", [])
        edges_raw = data.get("edges", [])
        if not nodes_raw and "root" in data:
            return cls._from_nested(data)
        nodes = [OrgNode(id=str(n["id"]), text=str(n["text"])) for n in nodes_raw]
        edges = [OrgEdge(source=str(e["from"]), target=str(e["to"])) for e in edges_raw]
        return cls(nodes, edges)

    @classmethod
    def _from_nested(cls, data: dict) -> "OrgChart":
        counter = [0]
        nodes: list[OrgNode] = []
        edges: list[OrgEdge] = []

        def walk(item: dict, pid: Optional[str]) -> None:
            counter[0] += 1
            nid = str(counter[0])
            name = str(item.get("name", item.get("text", "")))
            nodes.append(OrgNode(id=nid, text=name))
            if pid is not None:
                edges.append(OrgEdge(source=pid, target=nid))
            for child in item.get("children", []):
                walk(child, nid)

        if "children" in data:
            walk(data, None)
        else:
            for item in data.get("root", [data]):
                walk(item, None)
        return cls(nodes, edges)
