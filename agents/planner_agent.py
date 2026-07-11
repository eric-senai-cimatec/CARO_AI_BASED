"""
agents/planner_agent.py — Agente de Planejamento (Planner)

Recebe o ProposalContext (saída do AnalystAgent) e o TemplateModel
(saída do TemplateReader) e decide:
  - Quais slides do template usar
  - Quais slides ocultar/remover (ex: slides protegidos/internos)
  - Qual conteúdo vai em cada slide (mapeamento campo → slide)
  - Ordem final dos slides

Produz um SlidePlan — a "planta baixa" que o WriterAgent vai preencher
e o Builder vai renderizar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import config
from core.template_reader import TemplateModel
from .analyst_agent import ProposalContext
from .base_agent import AgentResult, BaseAgent

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


# ── Estruturas de planejamento ───────────────────────────────────────────────

@dataclass
class SlideInstruction:
    """Instrução de preenchimento para um slide específico."""
    slide_number: int
    slide_title_template: str       # título original do template (referência)
    content_field: str              # campo do ProposalContext a usar
    content_type: str               # "bullets" | "text" | "key_value" | "table" | "skip"
    include: bool = True            # se False, o slide será ocultado/removido
    notes: str = ""                 # instrução adicional para o WriterAgent
    target_shape_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slide_number": self.slide_number,
            "slide_title_template": self.slide_title_template,
            "content_field": self.content_field,
            "content_type": self.content_type,
            "include": self.include,
            "notes": self.notes,
            "target_shape_name": self.target_shape_name,
        }


@dataclass
class SlidePlan:
    """Plano completo de preenchimento da apresentação."""
    template_path: str
    total_slides_template: int
    instructions: List[SlideInstruction] = field(default_factory=list)
    slides_to_remove: List[int] = field(default_factory=list)
    reasoning: str = ""

    def get_instruction(self, slide_number: int) -> Optional[SlideInstruction]:
        for instr in self.instructions:
            if instr.slide_number == slide_number:
                return instr
        return None

    def get_active_instructions(self) -> List[SlideInstruction]:
        """Instruções de slides que serão preenchidos (não removidos)."""
        return [i for i in self.instructions
                if i.include and i.slide_number not in self.slides_to_remove]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_path": self.template_path,
            "total_slides_template": self.total_slides_template,
            "slides_to_remove": self.slides_to_remove,
            "reasoning": self.reasoning,
            "instructions": [i.to_dict() for i in self.instructions],
        }

    def describe(self) -> str:
        lines = [f"📋 PLANO DE SLIDES — {len(self.get_active_instructions())} slides ativos"]
        if self.slides_to_remove:
            lines.append(f"   Removidos: {self.slides_to_remove}")
        lines.append("")
        for instr in self.instructions:
            status = "✅" if instr.include else "⏭️ skip"
            lines.append(
                f"  {status} Slide {instr.slide_number:2d} [{instr.content_type:10s}] "
                f"← {instr.content_field or '(nenhum)'}"
            )
            if instr.notes:
                lines.append(f"       💡 {instr.notes}")
        return "\n".join(lines)


# ── Planner Agent ─────────────────────────────────────────────────────────────

class PlannerAgent(BaseAgent):
    """
    Agente de Planejamento — decide a estrutura final da apresentação.

    Combina:
      1. Conhecimento estático do template CARO (config.SLIDE_CONTENT_MAP)
      2. Análise do ProposalContext (quais dados existem)
      3. Lógica de negócio (slides protegidos nunca são tocados;
         slides condicionais como CBII/PI só entram se aplicável)
    """

    @property
    def system_prompt(self) -> str:
        return """Você é um planejador de propostas técnicas do SENAI CIMATEC, especialista 
no template CARO.

Sua função é decidir, para cada slide do template, se ele deve ser:
- PREENCHIDO com dados da proposta (include=true)
- MANTIDO COMO ESTÁ (slides internos/protegidos do comitê — nunca editar texto livre)
- REMOVIDO (slides condicionais que não se aplicam a este projeto, ex: CBII/PI 
  quando não é MPME/startup baiana)

Responda APENAS com JSON no formato:
{
  "slides_to_remove": [lista de números de slides a remover],
  "reasoning": "explicação curta da decisão"
}"""

    def run(
        self,
        context: ProposalContext,
        template_model: TemplateModel,
    ) -> AgentResult:
        """
        Gera o SlidePlan combinando regras estáticas + decisão do LLM
        para slides condicionais.

        Args:
            context: ProposalContext extraído pelo AnalystAgent
            template_model: TemplateModel lido pelo TemplateReader

        Returns:
            AgentResult com content = SlidePlan
        """
        self.logger.info("📐 Planejando estrutura de slides...")

        # 1. Construir instruções base a partir do mapeamento estático
        instructions = self._build_static_instructions(template_model)

        # 2. Perguntar ao LLM quais slides condicionais remover
        removal_decision = self._decide_removals(context, template_model)

        slides_to_remove = removal_decision.get("slides_to_remove", [])
        reasoning = removal_decision.get("reasoning", "")

        # Marcar slides removidos como include=False
        for instr in instructions:
            if instr.slide_number in slides_to_remove:
                instr.include = False

        plan = SlidePlan(
            template_path=template_model.file_path,
            total_slides_template=template_model.ast.slide_count,
            instructions=instructions,
            slides_to_remove=slides_to_remove,
            reasoning=reasoning,
        )

        self.logger.info(
            f"✅ Plano gerado: {len(plan.get_active_instructions())} slides ativos, "
            f"{len(slides_to_remove)} removidos"
        )

        return AgentResult(
            agent_name=self.name,
            success=True,
            content=plan,
        )

    # ── Construção de instruções ──────────────────────────────────────────────

    def _build_static_instructions(self, template_model: TemplateModel) -> List[SlideInstruction]:
        """
        Constrói as instruções de cada slide combinando:
          - config.SLIDE_CONTENT_MAP (mapeamento conhecido do template CARO)
          - config.PROTECTED_SLIDES (slides nunca editados por IA)
        """
        instructions = []
        total = template_model.ast.slide_count

        for slide_num in range(1, total + 1):
            slide = template_model.get_slide(slide_num)
            title_ref = slide.title if slide else ""

            mapped = config.SLIDE_CONTENT_MAP.get(slide_num)
            is_protected = slide_num in config.PROTECTED_SLIDES

            if is_protected:
                # Slide protegido: nunca editamos via IA (orçamento interno, refs visuais)
                instructions.append(SlideInstruction(
                    slide_number=slide_num,
                    slide_title_template=title_ref,
                    content_field="",
                    content_type="skip",
                    include=False,  # não editamos, mas mantemos no deck por padrão
                    notes="Slide protegido/interno — não editado automaticamente.",
                ))
                # Nota: include=False aqui significa "não editar texto",
                # mas o slide PERMANECE no arquivo final (builder só pula a edição).
                continue

            if mapped:
                content_type = self._infer_content_type(slide_num)
                instructions.append(SlideInstruction(
                    slide_number=slide_num,
                    slide_title_template=title_ref,
                    content_field=mapped.get("body") or mapped.get("title", ""),
                    content_type=content_type,
                    include=True,
                ))
            else:
                # Slide sem mapeamento conhecido — não editamos para não quebrar
                instructions.append(SlideInstruction(
                    slide_number=slide_num,
                    slide_title_template=title_ref,
                    content_field="",
                    content_type="skip",
                    include=False,
                    notes="Sem mapeamento de conteúdo conhecido.",
                ))

        return instructions

    def _infer_content_type(self, slide_num: int) -> str:
        """Infere o tipo de conteúdo esperado por slide com base em regras de negócio."""
        bullets_slides = {6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 23, 26, 27, 28, 36}
        key_value_slides = {4, 5}
        table_slides = {25}

        if slide_num in table_slides:
            return "table"
        if slide_num in key_value_slides:
            return "key_value"
        if slide_num in bullets_slides:
            return "bullets"
        if slide_num in (1, 2):
            return "text"
        if slide_num == 12:
            return "key_value"
        return "text"

    # ── Decisão de remoção via LLM ────────────────────────────────────────────

    def _decide_removals(
        self, context: ProposalContext, template_model: TemplateModel
    ) -> Dict[str, Any]:
        """Pergunta ao LLM quais slides condicionais remover."""

        candidate_slides = [13, 14, 15, 16, 17, 18, 24, 34, 35]
        slides_info = []
        for n in candidate_slides:
            slide = template_model.get_slide(n)
            if slide:
                slides_info.append(f"  Slide {n}: {slide.title[:80]}")

        user_msg = f"""RESUMO DA PROPOSTA:
{context.to_summary()}

SLIDES CONDICIONAIS DO TEMPLATE (avalie remoção):
{chr(10).join(slides_info)}

Contexto adicional:
- Empresa do cliente: {context.cliente.empresa}

Responda em JSON: {{"slides_to_remove": [...], "reasoning": "..."}}"""

        result = self.call_llm_json(user_msg)

        if not result.success:
            self.logger.warning(f"Falha ao decidir remoções via LLM: {result.error}. Usando default.")
            return {"slides_to_remove": [13, 14, 15, 16, 17, 18, 24], "reasoning": "Default fallback"}

        decision = self.extract_json(result.content)
        if not decision:
            return {"slides_to_remove": [13, 14, 15, 16, 17, 18, 24], "reasoning": "Parse fallback"}

        return decision
