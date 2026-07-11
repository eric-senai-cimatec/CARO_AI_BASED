"""
agents/reviewer_agent.py — Agente Revisor (Reviewer)

Valida o WriterOutput contra os limites do template e a coerência geral,
sugerindo/aplicando ajustes automáticos:
  - Detecta overflow de texto (estoura limite de caracteres)
  - Detecta bullets vazios ou genéricos demais
  - Detecta inconsistências (ex: TRL atual > TRL final)
  - Aplica correções automáticas onde possível
  - Gera relatório de validação para o usuário
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List
import config
from core.template_reader import TemplateModel
from .analyst_agent import ProposalContext
from .base_agent import AgentResult, BaseAgent
from .writer_agent import SlideContent, WriterOutput
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


logger = logging.getLogger(__name__)


# ── Estruturas de validação ───────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    """Um problema encontrado durante a validação."""
    slide_number: int
    severity: str            # "error" | "warning" | "info"
    issue_type: str          # "overflow" | "empty" | "inconsistency" | "generic"
    message: str
    auto_fixed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ValidationReport:
    """Relatório completo de validação."""
    issues: List[ValidationIssue] = field(default_factory=list)
    total_slides_checked: int = 0
    slides_with_errors: int = 0
    slides_with_warnings: int = 0
    auto_fixes_applied: int = 0

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def is_clean(self) -> bool:
        return len(self.issues) == 0

    def add(self, issue: ValidationIssue):
        self.issues.append(issue)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_slides_checked": self.total_slides_checked,
            "slides_with_errors": self.slides_with_errors,
            "slides_with_warnings": self.slides_with_warnings,
            "auto_fixes_applied": self.auto_fixes_applied,
            "is_clean": self.is_clean,
            "issues": [i.to_dict() for i in self.issues],
        }

    def to_log_text(self) -> str:
        """Relatório de validação em texto — vira 7.4 Relatório de Validação."""
        lines = [
            "═" * 70,
            "RELATÓRIO DE VALIDAÇÃO — CARO Framework",
            "═" * 70,
            f"Slides verificados: {self.total_slides_checked}",
            f"Slides com erros: {self.slides_with_errors}",
            f"Slides com avisos: {self.slides_with_warnings}",
            f"Correções automáticas aplicadas: {self.auto_fixes_applied}",
            "",
        ]
        if not self.issues:
            lines.append("✅ Nenhum problema encontrado.")
        else:
            for issue in self.issues:
                icon = {"error": "❌", "warning": "⚠️ ", "info": "ℹ️ "}.get(issue.severity, "•")
                fixed = " [CORRIGIDO AUTOMATICAMENTE]" if issue.auto_fixed else ""
                lines.append(
                    f"{icon} Slide {issue.slide_number:2d} [{issue.issue_type}] "
                    f"{issue.message}{fixed}"
                )
        lines.append("═" * 70)
        return "\n".join(lines)


# ── Reviewer Agent ────────────────────────────────────────────────────────────

class ReviewerAgent(BaseAgent):
    """
    Agente Revisor — valida e corrige o WriterOutput.

    Pipeline de validação (6.1 + 6.2 + 6.3 da arquitetura):
      1. ValidatorTool — verifica limites de texto, altura, overflow
      2. AutoAdjustTool — ajusta/reduz/reformula automaticamente
      3. ReviewerAgent (este) — reavalia após ajustes, garante qualidade final
    """

    @property
    def system_prompt(self) -> str:
        return """Você é um revisor de qualidade de propostas técnicas do SENAI CIMATEC.

Sua função é avaliar se o conteúdo gerado para os slides está:
1. Coerente com o restante da proposta
2. Tecnicamente consistente (ex: TRL atual deve ser MENOR que TRL final)
3. Específico o suficiente (não genérico demais, tipo "Melhorar processos")
4. Livre de informação inventada ou contraditória

Quando solicitado a reescrever um bullet/texto problemático, responda APENAS 
com o texto corrigido, mantendo o limite de caracteres indicado, sem aspas, 
sem markdown, sem comentários."""

    def run(
        self,
        writer_output: WriterOutput,
        context: ProposalContext,
        template_model: TemplateModel,
        auto_fix: bool = True,
    ) -> AgentResult:
        """
        Valida e corrige o WriterOutput.

        Args:
            writer_output: Saída do WriterAgent
            context: ProposalContext original
            template_model: TemplateModel para limites
            auto_fix: Se True, aplica correções automáticas

        Returns:
            AgentResult com content = tuple(WriterOutput corrigido, ValidationReport)
        """
        self.logger.info("🛡️  Validando conteúdo gerado...")

        report = ValidationReport()
        report.total_slides_checked = len(writer_output.slide_contents)

        slides_with_errors = set()
        slides_with_warnings = set()

        for slide_num, content in writer_output.slide_contents.items():
            cap = template_model.get_capacity(slide_num)
            issues = self._validate_slide(slide_num, content, cap)

            for issue in issues:
                # Auto-fix de overflow
                if auto_fix and issue.issue_type == "overflow":
                    fixed = self._auto_fix_overflow(content, cap)
                    if fixed:
                        issue.auto_fixed = True
                        report.auto_fixes_applied += 1

                report.add(issue)
                if issue.severity == "error":
                    slides_with_errors.add(slide_num)
                elif issue.severity == "warning":
                    slides_with_warnings.add(slide_num)

        # Validações de consistência cruzada (TRL, datas, etc.)
        consistency_issues = self._validate_consistency(context)
        for issue in consistency_issues:
            report.add(issue)
            if issue.severity == "error":
                slides_with_errors.add(issue.slide_number)
            elif issue.severity == "warning":
                slides_with_warnings.add(issue.slide_number)

        report.slides_with_errors = len(slides_with_errors)
        report.slides_with_warnings = len(slides_with_warnings)

        self.logger.info(
            f"✅ Validação concluída: {len(report.issues)} issues, "
            f"{report.auto_fixes_applied} correções aplicadas"
        )

        return AgentResult(
            agent_name=self.name,
            success=True,
            content=(writer_output, report),
        )

    # ── Validações por slide ──────────────────────────────────────────────────

    def _validate_slide(
        self, slide_num: int, content: SlideContent, cap
    ) -> List[ValidationIssue]:
        """Valida limites de texto/overflow de um slide."""
        issues = []

        max_chars = cap.body_max_chars if cap else config.TEXT_LIMITS["body_max_chars"]
        max_bullet_chars = config.TEXT_LIMITS["bullet_max_chars"]
        max_bullets = cap.max_bullets if cap else config.TEXT_LIMITS["bullets_per_slide_max"]

        # Texto corrido
        if content.text:
            if len(content.text) > max_chars:
                issues.append(ValidationIssue(
                    slide_number=slide_num,
                    severity="warning",
                    issue_type="overflow",
                    message=f"Texto excede limite ({len(content.text)}/{max_chars} chars)",
                ))

        # Bullets
        if content.bullets:
            if len(content.bullets) > max_bullets:
                issues.append(ValidationIssue(
                    slide_number=slide_num,
                    severity="warning",
                    issue_type="overflow",
                    message=f"Excesso de bullets ({len(content.bullets)}/{max_bullets})",
                ))
            for i, b in enumerate(content.bullets):
                if len(b) > max_bullet_chars:
                    issues.append(ValidationIssue(
                        slide_number=slide_num,
                        severity="warning",
                        issue_type="overflow",
                        message=f"Bullet {i+1} excede limite ({len(b)}/{max_bullet_chars} chars)",
                    ))
                if len(b.strip()) < 5:
                    issues.append(ValidationIssue(
                        slide_number=slide_num,
                        severity="error",
                        issue_type="empty",
                        message=f"Bullet {i+1} vazio ou muito curto",
                    ))

        # Conteúdo vazio em slide que deveria ter conteúdo
        is_empty = not content.text and not content.bullets and not content.key_values and not content.table_data
        if is_empty and content.content_type != "skip":
            issues.append(ValidationIssue(
                slide_number=slide_num,
                severity="error",
                issue_type="empty",
                message="Slide sem nenhum conteúdo gerado",
            ))

        # Conteúdo genérico (heurística simples)
        generic_phrases = ["melhorar processos", "aumentar eficiência", "diversos benefícios"]
        all_text = " ".join(content.bullets) + " " + (content.text or "")
        for phrase in generic_phrases:
            if phrase.lower() in all_text.lower():
                issues.append(ValidationIssue(
                    slide_number=slide_num,
                    severity="info",
                    issue_type="generic",
                    message=f"Conteúdo possivelmente genérico: {phrase!r}",
                ))

        return issues

    def _validate_consistency(self, context: ProposalContext) -> List[ValidationIssue]:
        """Valida consistência cruzada entre campos do ProposalContext."""
        issues = []

        if context.projeto.trl_atual >= context.projeto.trl_final:
            issues.append(ValidationIssue(
                slide_number=12,
                severity="error",
                issue_type="inconsistency",
                message=(
                    f"TRL atual ({context.projeto.trl_atual}) deve ser menor que "
                    f"TRL final ({context.projeto.trl_final})"
                ),
            ))

        if context.projeto.prazo_meses <= 0:
            issues.append(ValidationIssue(
                slide_number=7,
                severity="warning",
                issue_type="inconsistency",
                message="Prazo do projeto não foi identificado ou é zero",
            ))

        if not context.cliente.empresa:
            issues.append(ValidationIssue(
                slide_number=4,
                severity="error",
                issue_type="empty",
                message="Nome da empresa cliente não identificado",
            ))

        if len(context.projeto.beneficios) < 2:
            issues.append(ValidationIssue(
                slide_number=9,
                severity="warning",
                issue_type="empty",
                message=f"Poucos benefícios identificados ({len(context.projeto.beneficios)})",
            ))

        return issues

    # ── Auto-fix ──────────────────────────────────────────────────────────────

    def _auto_fix_overflow(self, content: SlideContent, cap) -> bool:
        """Tenta corrigir overflow automaticamente truncando/resumindo."""
        max_chars = cap.body_max_chars if cap else config.TEXT_LIMITS["body_max_chars"]
        max_bullet_chars = config.TEXT_LIMITS["bullet_max_chars"]
        max_bullets = cap.max_bullets if cap else config.TEXT_LIMITS["bullets_per_slide_max"]

        fixed_any = False

        if content.text and len(content.text) > max_chars:
            content.text = content.text[: max_chars - 1].rsplit(" ", 1)[0] + "…"
            content.truncated = True
            fixed_any = True

        if content.bullets:
            if len(content.bullets) > max_bullets:
                content.bullets = content.bullets[:max_bullets]
                fixed_any = True

            new_bullets = []
            for b in content.bullets:
                if len(b) > max_bullet_chars:
                    b = b[: max_bullet_chars - 1].rsplit(" ", 1)[0] + "…"
                    fixed_any = True
                new_bullets.append(b)
            content.bullets = new_bullets

        return fixed_any

    def reword_with_llm(self, text: str, max_chars: int, instruction: str = "") -> str:
        """API pública para reescrever texto problemático via LLM (uso externo/orquestrador)."""
        user_msg = f"""Reescreva o texto abaixo em até {max_chars} caracteres.
{instruction}

TEXTO:
{text}

Responda apenas com o texto reescrito."""
        result = self.call_llm(user_msg)
        if result.success and result.content:
            return result.content.strip().strip('"')[:max_chars]
        return text[:max_chars]
