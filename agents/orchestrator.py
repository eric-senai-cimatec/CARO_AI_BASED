"""
agents/orchestrator.py — Orquestrador Multi-Agente

Ponto central de coordenação do pipeline CARO:

  INPUT (PDF/TXT/texto)
       │
       ▼ ① read_fsipp()
  [Texto extraído]
       │
       ▼ ② AnalystAgent.run()
  [ProposalContext]
       │
       ▼ ③ TemplateReader.read()
  [TemplateModel]
       │
       ▼ ④ PlannerAgent.run()
  [SlidePlan]
       │
       ▼ ⑤ WriterAgent.run()
  [WriterOutput]
       │
       ▼ ⑥ ReviewerAgent.run()
  [WriterOutput validado + ValidationReport]
       │
       ▼ ⑦ Builder.render()
  [.pptx gerado]

Cada etapa emite eventos de progresso (callback ou logging).
Salva JSON intermediário para auditoria/debug.
"""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pptx import Presentation
import sys
import config
from core.template_reader import TemplateReader, TemplateModel
from core.layout_preserver import LayoutPreserver
from tools.pdf_tools import read_fsipp
from tools.pptx_tools import PptxTools
from tools.text_tools import sanitize_for_pptx
from tools.validation_tools import run_preflight_checks, validate_context

from .analyst_agent import AnalystAgent, ProposalContext
from .base_agent import GroqClient
from .planner_agent import PlannerAgent, SlidePlan
from .reviewer_agent import ReviewerAgent, ValidationReport
from .writer_agent import WriterAgent, WriterOutput, SlideContent

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)

# Tipo de callback de progresso: fn(step: str, pct: float, message: str)
ProgressCallback = Callable[[str, float, str], None]


# ── Resultado final da orquestração ──────────────────────────────────────────

@dataclass
class OrchestratorResult:
    """Resultado completo da execução do pipeline."""
    success: bool
    output_path: Optional[Path] = None
    validation_report: Optional[ValidationReport] = None
    proposal_context: Optional[ProposalContext] = None
    slide_plan: Optional[SlidePlan] = None
    total_time_s: float = 0.0
    steps_completed: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    audit_dir: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output_path": str(self.output_path) if self.output_path else None,
            "total_time_s": round(self.total_time_s, 2),
            "steps_completed": self.steps_completed,
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def summary(self) -> str:
        ok = "✅" if self.success else "❌"
        lines = [
            f"{ok} Pipeline {'concluído' if self.success else 'falhou'} em {self.total_time_s:.1f}s",
            f"   Etapas: {' → '.join(self.steps_completed)}",
        ]
        if self.output_path:
            sz = self.output_path.stat().st_size // 1024 if self.output_path.exists() else 0
            lines.append(f"   Output: {self.output_path} ({sz} KB)")
        if self.errors:
            lines.append(f"   ❌ Erros: {len(self.errors)}")
            for e in self.errors:
                lines.append(f"      • {e}")
        if self.validation_report:
            lines.append(f"   🛡️  Validação: {len(self.validation_report.issues)} issues, "
                         f"{self.validation_report.auto_fixes_applied} correções automáticas")
        return "\n".join(lines)


# ── Builder ───────────────────────────────────────────────────────────────────

class Builder:
    """
    Renderiza o WriterOutput no template PPTX real.

    Copia o template para um arquivo de trabalho e aplica cada
    SlideContent usando o PptxTools/ShapeEditor.
    """

    def __init__(self, template_path: str | Path):
        self.template_path = Path(template_path)
        self.layout_preserver = LayoutPreserver()

    def render(
        self,
        writer_output: WriterOutput,
        plan: SlidePlan,
        template_model: TemplateModel,
        output_path: str | Path,
        context: ProposalContext,
    ) -> Path:
        """
        Aplica o WriterOutput ao template e salva o PPTX final.

        Args:
            writer_output: Conteúdo gerado pelos agentes
            plan: SlidePlan com instruções por slide
            template_model: Modelo do template
            output_path: Caminho do arquivo de saída
            context: ProposalContext (para campos de data, título global, etc.)

        Returns:
            Path do arquivo .pptx gerado
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Copiar template para arquivo de trabalho
        shutil.copy2(str(self.template_path), str(output))
        logger.info(f"🏗️  Builder: template copiado para {output.name}")

        prs = Presentation(str(output))
        tools = PptxTools(prs, template_model)

        slides_written = 0
        slides_skipped = 0

        for slide_num in range(1, template_model.ast.slide_count + 1):
            instr = plan.get_instruction(slide_num)
            content = writer_output.get(slide_num)

            # Slide protegido ou sem conteúdo → manter intacto
            if not instr or not instr.include or not content:
                slides_skipped += 1
                continue
            if content.content_type == "skip":
                slides_skipped += 1
                continue

            try:
                self._apply_content(tools, slide_num, content, context)
                slides_written += 1
                logger.debug(
                    f"  ✅ Slide {slide_num} renderizado ({content.content_type})")
            except Exception as e:
                logger.warning(f"  ⚠️  Slide {slide_num} erro: {e}")
                slides_skipped += 1

        tools.save(output)
        logger.info(
            f"✅ Builder concluído: {slides_written} slides escritos, "
            f"{slides_skipped} mantidos intactos"
        )
        return output

    def _apply_content(
        self,
        tools: PptxTools,
        slide_num: int,
        content: SlideContent,
        context: ProposalContext,
    ):
        """Aplica um SlideContent ao slide correspondente."""

        # 1. Título (se fornecido)
        if content.title:
            title = sanitize_for_pptx(content.title)
            tools.write_slide_title(slide_num, title)

        # 2. Data (slides de capa)
        if content.date_field is not None and slide_num in (1, 2):
            tools.write_slide_date(
                slide_num, sanitize_for_pptx(content.date_field))

        # 3. Conteúdo principal
        if content.content_type == "bullets" and content.bullets:
            bullets = [sanitize_for_pptx(b)
                       for b in content.bullets if b.strip()]
            tools.write_slide_body(slide_num, bullets=bullets)

        elif content.content_type == "text" and content.text:
            text = sanitize_for_pptx(content.text)
            tools.write_slide_body(slide_num, text=text)

        elif content.content_type == "key_value" and content.key_values:
            # Escrever pares chave:valor como bullets formatados
            bullets = [
                f"{sanitize_for_pptx(k)}: {sanitize_for_pptx(v)}"
                for k, v in content.key_values
                if k or v
            ]
            if content.text:
                bullets.append(sanitize_for_pptx(content.text))
            tools.write_slide_body(slide_num, bullets=bullets)

        elif content.content_type == "table" and content.table_data:
            tools.write_table(slide_num, content.table_data)


# ── Orchestrator ──────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Orquestrador principal do pipeline CARO.

    Coordena todos os agentes e o builder para transformar
    um FSIPP/Ata em uma proposta PPTX completa.

    Uso:
        orch = Orchestrator(
            template_path="templates/CARO_Bobinas.pptx",
            groq_api_key="gsk_...",
        )
        result = orch.run(
            input_source="fsipp_cliente.pdf",
            output_path="output/proposta_cliente.pptx",
        )
        print(result.summary())
    """

    def __init__(
        self,
        template_path: str | Path = None,
        groq_api_key: Optional[str] = None,
        cache_dir: str | Path = None,
        audit_enabled: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
        model: str = config.DEFAULT_MODEL,
    ):
        self.template_path = Path(
            template_path or config.DEFAULT_TEMPLATE_PATH)
        self.cache_dir = Path(cache_dir or config.CACHE_DIR)
        self.audit_enabled = audit_enabled
        self.progress_cb = progress_callback or self._default_progress
        self.model = model

        # Inicializar cliente Groq compartilhado
        self.groq_client = GroqClient(api_key=groq_api_key)

        # Inicializar agentes
        self.analyst = AnalystAgent(
            "analyst",  model=model, groq_client=self.groq_client)
        self.planner = PlannerAgent(
            "planner",  model=model, groq_client=self.groq_client)
        self.writer = WriterAgent(
            "writer",    model=model, groq_client=self.groq_client)
        self.reviewer = ReviewerAgent(
            "reviewer", model=model, groq_client=self.groq_client)

        # Template reader (usa cache)
        self.template_reader = TemplateReader(cache_dir=self.cache_dir)

        # Builder
        self.builder = Builder(self.template_path)

        logger.info(
            f"Orchestrator pronto | template={self.template_path.name} | model={model}")

    # ── Pipeline principal ────────────────────────────────────────────────────

    def run(
        self,
        input_source: str | Path,
        output_path: str | Path = None,
        skip_preflight: bool = False,
        auto_fix: bool = True,
    ) -> OrchestratorResult:
        """
        Executa o pipeline completo: FSIPP → PPTX.

        Args:
            input_source: Caminho para PDF/TXT ou texto direto
            output_path: Caminho para o .pptx de saída
            skip_preflight: Pular verificações de pré-voo
            auto_fix: Aplicar correções automáticas de validação

        Returns:
            OrchestratorResult com o resultado completo
        """
        start_time = time.time()
        result = OrchestratorResult(success=False)

        # Output padrão
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = config.OUTPUT_DIR / f"proposta_CARO_{ts}.pptx"
        output_path = Path(output_path)

        # Diretório de auditoria
        if self.audit_enabled:
            audit_dir = config.OUTPUT_DIR / f"audit_{output_path.stem}"
            audit_dir.mkdir(parents=True, exist_ok=True)
            result.audit_dir = audit_dir

        try:
            # ── Preflight ─────────────────────────────────────────────────────
            if not skip_preflight:
                self._emit("preflight", 0.0, "Verificando configurações...")
                ok, messages = run_preflight_checks(
                    template_path=self.template_path,
                    input_source=input_source,
                    output_path=output_path,
                    api_key=self.groq_client.api_key,
                )
                for msg in messages:
                    logger.info(msg)
                if not ok:
                    errors = [m for m in messages if m.startswith("❌")]
                    result.errors = errors
                    return result
                result.steps_completed.append("preflight")

            # ── Etapa 1: Ler FSIPP ────────────────────────────────────────────
            self._emit("read_input", 0.05, "Lendo documento de entrada...")
            raw_text = read_fsipp(input_source)
            if not raw_text or len(raw_text) < 50:
                result.errors.append("Documento de entrada vazio ou ilegível")
                return result
            logger.info(f"📄 Texto extraído: {len(raw_text)} chars")
            self._save_audit(audit_dir if self.audit_enabled else None,
                             "01_raw_input.txt", raw_text)
            result.steps_completed.append("read_input")

            # ── Etapa 2: Ler Template ─────────────────────────────────────────
            self._emit("read_template", 0.1, "Lendo template PPTX...")
            template_model = self.template_reader.read(self.template_path)
            logger.info(f"📊 Template: {template_model.ast.slide_count} slides")
            result.steps_completed.append("read_template")

            # ── Etapa 3: Analyst Agent ────────────────────────────────────────
            self._emit("analyst", 0.2, "Analisando documento com IA...")
            analyst_result = self.analyst.run(raw_text)
            if not analyst_result.success:
                result.errors.append(
                    f"AnalystAgent falhou: {analyst_result.error}")
                return result

            context: ProposalContext = analyst_result.content
            result.proposal_context = context
            self._save_audit(audit_dir if self.audit_enabled else None,
                             "02_proposal_context.json",
                             json.dumps(context.to_dict(), ensure_ascii=False, indent=2))

            # Validar contexto mínimo
            ctx_ok, missing = validate_context(context)
            if not ctx_ok:
                result.warnings.append(f"Campos faltantes: {missing}")
                logger.warning(f"⚠️  Contexto incompleto — faltam: {missing}")
            result.steps_completed.append("analyst")

            # ── Etapa 4: Planner Agent ────────────────────────────────────────
            self._emit("planner", 0.40, "Planejando estrutura de slides...")
            planner_result = self.planner.run(context, template_model)
            if not planner_result.success:
                result.errors.append(
                    f"PlannerAgent falhou: {planner_result.error}")
                return result

            plan: SlidePlan = planner_result.content
            result.slide_plan = plan
            self._save_audit(audit_dir if self.audit_enabled else None,
                             "03_slide_plan.json",
                             json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
            logger.info(f"\n{plan.describe()}")
            result.steps_completed.append("planner")

            # ── Etapa 5: Writer Agent ─────────────────────────────────────────
            self._emit("writer", 0.55, "Escrevendo conteúdo dos slides...")
            writer_result = self.writer.run(context, plan, template_model)
            if not writer_result.success:
                result.errors.append(
                    f"WriterAgent falhou: {writer_result.error}")
                return result

            writer_output: WriterOutput = writer_result.content
            self._save_audit(audit_dir if self.audit_enabled else None,
                             "04_writer_output.json",
                             json.dumps(writer_output.to_dict(), ensure_ascii=False, indent=2))
            logger.info(f"\n{writer_output.describe()}")
            result.steps_completed.append("writer")

            # ── Etapa 6: Reviewer Agent ───────────────────────────────────────
            self._emit("reviewer", 0.72, "Validando e ajustando conteúdo...")
            reviewer_result = self.reviewer.run(
                writer_output, context, template_model, auto_fix=auto_fix
            )
            if not reviewer_result.success:
                result.warnings.append(
                    f"ReviewerAgent falhou: {reviewer_result.error}")
                # Continuar mesmo com falha no revisor
            else:
                writer_output, validation_report = reviewer_result.content
                result.validation_report = validation_report
                self._save_audit(audit_dir if self.audit_enabled else None,
                                 "05_validation_report.txt",
                                 validation_report.to_log_text())
                logger.info(f"\n{validation_report.to_log_text()}")
                for issue in validation_report.issues:
                    if issue.severity == "error" and not issue.auto_fixed:
                        result.warnings.append(
                            f"Slide {issue.slide_number}: {issue.message}"
                        )
            result.steps_completed.append("reviewer")

            # ── Etapa 7: Builder → PPTX ──────────────────────────────────────
            self._emit("builder", 0.85, "Renderizando apresentação PPTX...")
            final_path = self.builder.render(
                writer_output=writer_output,
                plan=plan,
                template_model=template_model,
                output_path=output_path,
                context=context,
            )
            result.output_path = final_path
            result.steps_completed.append("builder")

            # ── Finalizado ────────────────────────────────────────────────────
            result.success = True
            result.total_time_s = time.time() - start_time
            self._emit("done", 1.0,
                       f"Concluído em {result.total_time_s:.1f}s → {final_path.name}")
            logger.info(f"\n{result.summary()}")
            return result

        except KeyboardInterrupt:
            result.errors.append("Interrompido pelo usuário")
            result.total_time_s = time.time() - start_time
            return result
        except Exception as e:
            logger.exception(f"Erro inesperado no pipeline: {e}")
            result.errors.append(f"Erro inesperado: {e}")
            result.total_time_s = time.time() - start_time
            return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _emit(self, step: str, pct: float, message: str):
        """Emite evento de progresso."""
        logger.info(f"[{pct*100:3.0f}%] {message}")
        if self.progress_cb:
            try:
                self.progress_cb(step, pct, message)
            except Exception:
                pass

    def _default_progress(self, step: str, pct: float, message: str):
        """Progress callback padrão — só log."""
        pass

    def _save_audit(self, audit_dir: Optional[Path], filename: str, content: str):
        """Salva arquivo de auditoria/debug."""
        if audit_dir is None:
            return
        try:
            (audit_dir / filename).write_text(content, encoding="utf-8")
        except Exception as e:
            logger.debug(f"Auditoria falhou para {filename}: {e}")
