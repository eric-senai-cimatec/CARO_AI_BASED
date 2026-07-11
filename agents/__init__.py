"""
agents/ — Agentes de IA do CARO Framework

  base_agent.py     — Classe base + cliente Groq + tool calling
  analyst_agent.py  — Extrai ProposalContext do FSIPP/Ata (2.1)
  planner_agent.py  — Planeja estrutura de slides (2.2 / 5.1)
  writer_agent.py   — Gera conteúdo de cada slide (2.2 / 5.3)
  reviewer_agent.py — Valida e corrige o conteúdo (2.4 / 6.3)
  orchestrator.py   — Coordena todo o pipeline
"""

from .base_agent import BaseAgent, AgentResult, GroqClient, Message
from .analyst_agent import AnalystAgent, ProposalContext, ClientData, ProjectData
from .planner_agent import PlannerAgent, SlidePlan, SlideInstruction
from .writer_agent import WriterAgent, WriterOutput, SlideContent
from .reviewer_agent import ReviewerAgent, ValidationReport, ValidationIssue
from .orchestrator import Orchestrator, OrchestratorResult, Builder

__all__ = [
    "BaseAgent", "AgentResult", "GroqClient", "Message",
    "AnalystAgent", "ProposalContext", "ClientData", "ProjectData",
    "PlannerAgent", "SlidePlan", "SlideInstruction",
    "WriterAgent", "WriterOutput", "SlideContent",
    "ReviewerAgent", "ValidationReport", "ValidationIssue",
    "Orchestrator", "OrchestratorResult", "Builder",
]
