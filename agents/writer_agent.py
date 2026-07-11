"""
agents/writer_agent.py — Agente de Escrita (Writer)

Recebe o SlidePlan + ProposalContext e gera o conteúdo textual final
de cada slide, respeitando:
  - Limites de caracteres do slide (via TemplateModel.SlideCapacity)
  - Tom de voz formal/técnico do padrão SENAI CIMATEC
  - Formato esperado (bullets, texto corrido, key-value, tabela)

Produz um SlideContent por slide — pronto para o Builder renderizar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import config
from core.template_reader import TemplateModel
from .analyst_agent import ProposalContext
from .base_agent import AgentResult, BaseAgent
from .planner_agent import SlideInstruction, SlidePlan
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


logger = logging.getLogger(__name__)


# ── Estrutura de conteúdo de slide ────────────────────────────────────────────

@dataclass
class SlideContent:
    """Conteúdo final pronto para renderizar em um slide."""
    slide_number: int
    content_type: str                          # "bullets" | "text" | "key_value" | "table" | "skip"
    title: Optional[str] = None
    text: Optional[str] = None
    bullets: List[str] = field(default_factory=list)
    key_values: List[Tuple[str, str]] = field(default_factory=list)
    table_data: List[List[str]] = field(default_factory=list)
    date_field: Optional[str] = None
    char_count: int = 0
    truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "slide_number": self.slide_number,
            "content_type": self.content_type,
            "title": self.title,
            "text": self.text,
            "bullets": self.bullets,
            "key_values": self.key_values,
            "table_data": self.table_data,
            "char_count": self.char_count,
            "truncated": self.truncated,
        }


@dataclass
class WriterOutput:
    """Saída completa do WriterAgent — todos os slides preenchidos."""
    slide_contents: Dict[int, SlideContent] = field(default_factory=dict)

    def get(self, slide_number: int) -> Optional[SlideContent]:
        return self.slide_contents.get(slide_number)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in self.slide_contents.items()}

    def describe(self) -> str:
        lines = [f"✍️  CONTEÚDO ESCRITO — {len(self.slide_contents)} slides"]
        for num in sorted(self.slide_contents.keys()):
            sc = self.slide_contents[num]
            preview = sc.text or " / ".join(sc.bullets[:2]) or str(sc.key_values[:2])
            flag = " ⚠️TRUNCADO" if sc.truncated else ""
            lines.append(f"  Slide {num:2d} [{sc.content_type:10s}]{flag} {preview[:70]}")
        return "\n".join(lines)


# ── Writer Agent ──────────────────────────────────────────────────────────────

class WriterAgent(BaseAgent):
    """
    Agente de Escrita — gera o texto final de cada slide.

    Estratégia:
      1. Para campos diretos do ProposalContext (já são texto pronto), usa
         direto com leve formatação/ajuste de tom.
      2. Para campos que precisam ser sintetizados (ex: combinar problema +
         contexto em um parágrafo fluido), chama o LLM.
      3. Sempre valida contra os limites de caracteres do TemplateModel
         e trunca/resume se necessário (delegando ao ReviewerAgent depois).
    """

    @property
    def system_prompt(self) -> str:
        return """Você é um redator técnico do SENAI CIMATEC especializado em propostas
de P&D e inovação no padrão CARO.

Seu tom é: formal, técnico, objetivo, direto. Terceira pessoa. Sem gírias.
Use vocabulário de engenharia/P&D: "desenvolver", "implementar", "validar",
"infraestrutura tecnológica", "transferência de tecnologia".

Ao escrever bullets:
- Cada bullet é uma frase completa e autocontida.
- Não repita o título do slide dentro dos bullets.
- Seja específico e técnico, evite generalidades vagas.
- Respeite RIGOROSAMENTE o limite de caracteres informado.

Ao escrever parágrafos de texto corrido:
- Frases curtas e diretas.
- Parágrafos de 2-4 frases.
- Sempre dentro do limite de caracteres informado.

Você está preenchendo um slide ESPECÍFICO de uma proposta real para um comitê de
orçamentação. Não invente dados que não foram fornecidos no contexto."""

    def run(
        self,
        context: ProposalContext,
        plan: SlidePlan,
        template_model: TemplateModel,
    ) -> AgentResult:
        """
        Gera o conteúdo de todos os slides ativos do plano.

        Args:
            context: ProposalContext extraído
            plan: SlidePlan com instruções por slide
            template_model: TemplateModel para limites de caracteres

        Returns:
            AgentResult com content = WriterOutput
        """
        self.logger.info("✍️  Escrevendo conteúdo dos slides...")

        output = WriterOutput()
        active_instructions = plan.get_active_instructions()

        for instr in active_instructions:
            try:
                content = self._write_slide(instr, context, template_model)
                output.slide_contents[instr.slide_number] = content
                self.logger.debug(f"  Slide {instr.slide_number}: {content.content_type} ok")
            except Exception as e:
                self.logger.error(f"  Slide {instr.slide_number} falhou: {e}")
                output.slide_contents[instr.slide_number] = SlideContent(
                    slide_number=instr.slide_number,
                    content_type="skip",
                )

        self.logger.info(f"✅ {len(output.slide_contents)} slides escritos")

        return AgentResult(
            agent_name=self.name,
            success=True,
            content=output,
        )

    # ── Roteamento por slide ──────────────────────────────────────────────────

    def _write_slide(
        self,
        instr: SlideInstruction,
        context: ProposalContext,
        template_model: TemplateModel,
    ) -> SlideContent:
        """Roteia para o handler correto baseado no número do slide."""

        handlers = {
            1: self._write_capa,
            2: self._write_capa,
            4: self._write_demandante,
            5: self._write_organizacao,
            6: self._write_problema,
            7: self._write_objetivo,
            8: self._write_concepcao,
            9: self._write_beneficios,
            10: self._write_entregas_1,
            11: self._write_entregas_2,
            12: self._write_trl,
            19: self._write_riscos_tecnologicos,
            20: self._write_requisitos,
            21: self._write_premissas,
            22: self._write_premissas,
            23: self._write_premissas_ml,
            25: self._write_matriz_riscos,
            26: self._write_exclusoes,
            27: self._write_cronograma,
            28: self._write_macro_entregas,
            36: self._write_comentarios_finais,
        }

        handler = handlers.get(instr.slide_number)
        if handler:
            return handler(instr, context, template_model)

        return SlideContent(slide_number=instr.slide_number, content_type="skip")

    # ── Handlers específicos por slide ────────────────────────────────────────

    def _write_capa(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="text",
            title=context.projeto.titulo or "Título do Projeto",
            date_field=context.data_proposta or "",
        )

    def _write_demandante(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        c = context.cliente
        kv = [
            ("Empresa(s)", c.empresa or "—"),
            ("Contato", c.contato_telefone or "—"),
            ("Nome", c.contato_nome or "—"),
            ("E-mail", c.contato_email or "—"),
        ]
        text_block = f"Descrição básica:\n{c.descricao_empresa}" if c.descricao_empresa else ""

        return SlideContent(
            slide_number=instr.slide_number,
            content_type="key_value",
            key_values=kv,
            text=text_block,
        )

    def _write_organizacao(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        o = context.organizacao
        kv = [
            ("Interlocutor com a empresa", o.interlocutor or "—"),
            ("Responsável Orçamento", o.responsavel_orcamento or "—"),
        ]
        areas_text = ", ".join(o.areas_participantes) if o.areas_participantes else "—"
        kv.append(("Áreas partícipes", areas_text))

        return SlideContent(
            slide_number=instr.slide_number,
            content_type="key_value",
            key_values=kv,
        )

    def _write_problema(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        max_chars = cap.body_max_chars if cap else 1200

        text = context.projeto.problema
        if len(text) > max_chars * 1.3:
            text = self._llm_synthesize_paragraph(
                topic="Problema",
                raw_content=text,
                max_chars=max_chars,
                context=context,
            )

        return SlideContent(
            slide_number=instr.slide_number,
            content_type="text",
            text=text,
            char_count=len(text),
        )

    def _write_objetivo(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        max_chars = cap.body_max_chars if cap else 1200

        text = context.projeto.objetivo
        if context.projeto.prazo_meses and str(context.projeto.prazo_meses) not in text:
            text = f"Desenvolver, em {context.projeto.prazo_meses} meses, {text[0].lower()}{text[1:]}" if text else text

        if len(text) > max_chars * 1.3:
            text = self._llm_synthesize_paragraph(
                topic="Objetivo do projeto",
                raw_content=text,
                max_chars=max_chars,
                context=context,
            )

        return SlideContent(
            slide_number=instr.slide_number,
            content_type="text",
            text=text,
            char_count=len(text),
        )

    def _write_concepcao(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        # Slide 8 tem diagrama fixo no template — mantemos texto mínimo/genérico
        bullets = context.projeto.tecnologias[:6] if context.projeto.tecnologias else []
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_beneficios(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        bullets = self._cap_bullets(context.projeto.beneficios, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_entregas_1(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        all_entregas = context.entregas.entregas_detalhadas or context.entregas.entregas_macro
        first_half = all_entregas[: max(1, len(all_entregas) // 2)] if all_entregas else []
        bullets = self._cap_bullets(first_half, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_entregas_2(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        all_entregas = context.entregas.entregas_detalhadas or context.entregas.entregas_macro
        second_half = all_entregas[max(1, len(all_entregas) // 2):] if all_entregas else []
        bullets = self._cap_bullets(second_half, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_trl(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        kv = [
            ("TRL Atual", str(context.projeto.trl_atual or 3)),
            ("TRL Final (esperado)", str(context.projeto.trl_final or 6)),
        ]
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="key_value",
            key_values=kv,
        )

    def _write_riscos_tecnologicos(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        bullets = self._cap_bullets(context.projeto.riscos_tecnologicos, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_requisitos(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        bullets = self._cap_bullets(context.projeto.requisitos, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_premissas(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        bullets = self._cap_bullets(context.premissas, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_premissas_ml(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        source = context.premissas_ml or context.premissas
        bullets = self._cap_bullets(source, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_matriz_riscos(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        rows = [["Dimensão", "Critic.", "Risco Identificado", "Resposta", "Plano de Ação", "Respons."]]
        for r in context.riscos_projeto:
            rows.append([
                r.get("dimensao", ""), r.get("criticidade", ""),
                r.get("risco", ""), r.get("resposta", ""),
                r.get("plano_acao", ""), r.get("responsavel", ""),
            ])
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="table",
            table_data=rows,
        )

    def _write_exclusoes(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        bullets = self._cap_bullets(context.projeto.exclusoes_escopo, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_cronograma(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        # Slide 27 tem grade fixa de meses no template — texto livre é só apoio
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="text",
            text=context.entregas.cronograma_texto or "",
        )

    def _write_macro_entregas(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        bullets = self._cap_bullets(context.entregas.entregas_macro, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    def _write_comentarios_finais(self, instr, context: ProposalContext, tm: TemplateModel) -> SlideContent:
        cap = tm.get_capacity(instr.slide_number)
        defaults = [
            "Esta proposta de escopo, prazos e valores pode sofrer alteração;",
            "O embasamento para realização desta proposta foi realizado com base nas "
            "informações disponibilizadas pelo cliente;",
        ]
        source = context.comentarios_finais or defaults
        bullets = self._cap_bullets(source, cap)
        return SlideContent(
            slide_number=instr.slide_number,
            content_type="bullets",
            bullets=bullets,
        )

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _cap_bullets(self, items: List[str], cap) -> List[str]:
        """Corta lista de bullets para respeitar max_bullets e bullet_max_chars."""
        if not items:
            return []
        max_bullets = config.TEXT_LIMITS["bullets_per_slide_max"]
        max_chars = config.TEXT_LIMITS["bullet_max_chars"]
        if cap and hasattr(cap, "max_bullets"):
            max_bullets = cap.max_bullets or max_bullets

        result = []
        for item in items[:max_bullets]:
            if len(item) > max_chars:
                item = item[: max_chars - 1].rsplit(" ", 1)[0] + "…"
            result.append(item)
        return result

    def _llm_synthesize_paragraph(
        self,
        topic: str,
        raw_content: str,
        max_chars: int,
        context: ProposalContext,
    ) -> str:
        """Usa o LLM para resumir/sintetizar um parágrafo dentro do limite."""
        user_msg = f"""Reescreva o texto abaixo sobre "{topic}" para caber em NO MÁXIMO 
{max_chars} caracteres, mantendo o tom técnico e formal, sem perder informação essencial.

TEXTO ORIGINAL:
{raw_content}

Responda APENAS com o texto reescrito, sem aspas, sem markdown, sem explicações."""

        result = self.call_llm(user_msg)
        if result.success and result.content:
            text = result.content.strip().strip('"')
            if len(text) <= max_chars * 1.1:
                return text

        # Fallback: truncar diretamente
        if len(raw_content) > max_chars:
            return raw_content[: max_chars - 1].rsplit(" ", 1)[0] + "…"
        return raw_content
