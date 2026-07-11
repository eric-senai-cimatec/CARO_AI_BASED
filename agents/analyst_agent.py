"""
agents/analyst_agent.py — Agente Analista (2.1)

Analisa o documento de entrada (FSIPP ou Ata de Reunião) e extrai:
  - Dados do cliente (empresa, contato, responsável)
  - Problema/desafio descrito
  - Objetivo do projeto
  - Informações técnicas relevantes
  - Benefícios esperados
  - Requisitos identificados
  - TRL atual e esperado
  - Prazo e cronograma
  - Informações de orçamento

Gera um ProposalContext rico que alimenta os agentes seguintes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .base_agent import AgentResult, BaseAgent

logger = logging.getLogger(__name__)


# ── Estrutura de dados da proposta ───────────────────────────────────────────

@dataclass
class ClientData:
    """Dados do cliente/demandante."""
    empresa: str = ""
    contato_nome: str = ""
    contato_email: str = ""
    contato_telefone: str = ""
    descricao_empresa: str = ""
    setor: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProjectData:
    """Dados técnicos do projeto."""
    titulo: str = ""
    problema: str = ""
    objetivo: str = ""
    prazo_meses: int = 0
    trl_atual: int = 0
    trl_final: int = 0
    tecnologias: List[str] = field(default_factory=list)
    areas_conhecimento: List[str] = field(default_factory=list)
    requisitos: List[str] = field(default_factory=list)
    beneficios: List[str] = field(default_factory=list)
    riscos_tecnologicos: List[str] = field(default_factory=list)
    exclusoes_escopo: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class DeliverableData:
    """Entregas e macroentregas do projeto."""
    entregas_macro: List[str] = field(default_factory=list)
    entregas_detalhadas: List[str] = field(default_factory=list)
    marcos: List[str] = field(default_factory=list)
    cronograma_texto: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class OrganizationData:
    """Organização interna do atendimento."""
    interlocutor: str = ""
    responsavel_orcamento: str = ""
    areas_participantes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class ProposalContext:
    """
    Contexto completo da proposta — output do AnalystAgent.
    É o objeto central que percorre todo o pipeline.
    """
    # Meta
    raw_input: str = ""
    input_type: str = "unknown"    # "fsipp" | "ata" | "texto_livre"
    data_proposta: str = ""

    # Dados extraídos
    cliente: ClientData = field(default_factory=ClientData)
    projeto: ProjectData = field(default_factory=ProjectData)
    entregas: DeliverableData = field(default_factory=DeliverableData)
    organizacao: OrganizationData = field(default_factory=OrganizationData)

    # Premissas
    premissas: List[str] = field(default_factory=list)
    premissas_ml: List[str] = field(default_factory=list)

    # Riscos
    riscos_projeto: List[Dict[str, str]] = field(default_factory=list)

    # Comentários finais
    comentarios_finais: List[str] = field(default_factory=list)

    # Forma de financiamento e PI
    forma_financiamento: str = ""
    acordo_pi: str = ""

    # Análise de confiança
    confidence_score: float = 0.0
    missing_fields: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_input_preview": self.raw_input[:200] + "..." if len(self.raw_input) > 200 else self.raw_input,
            "input_type": self.input_type,
            "data_proposta": self.data_proposta,
            "cliente": self.cliente.to_dict(),
            "projeto": self.projeto.to_dict(),
            "entregas": self.entregas.to_dict(),
            "organizacao": self.organizacao.to_dict(),
            "premissas": self.premissas,
            "premissas_ml": self.premissas_ml,
            "riscos_projeto": self.riscos_projeto,
            "comentarios_finais": self.comentarios_finais,
            "confidence_score": self.confidence_score,
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
        }

    def to_summary(self) -> str:
        """Resumo textual do contexto para usar nos prompts dos agentes."""
        return f"""
PROPOSTA: {self.projeto.titulo}
CLIENTE: {self.cliente.empresa} | Contato: {self.cliente.contato_nome}
PRAZO: {self.projeto.prazo_meses} meses
TRL: {self.projeto.trl_atual} → {self.projeto.trl_final}
ÁREA: {", ".join(self.projeto.areas_conhecimento)}
TECNOLOGIAS: {", ".join(self.projeto.tecnologias)}

PROBLEMA:
{self.projeto.problema}

OBJETIVO:
{self.projeto.objetivo}

BENEFÍCIOS:
{chr(10).join(f"• {b}" for b in self.projeto.beneficios)}

REQUISITOS:
{chr(10).join(f"• {r}" for r in self.projeto.requisitos)}

ENTREGAS MACRO:
{chr(10).join(f"• {e}" for e in self.entregas.entregas_macro)}

RISCOS:
{chr(10).join(f"• {r}" for r in self.projeto.riscos_tecnologicos)}

PREMISSAS:
{chr(10).join(f"• {p}" for p in self.premissas[:5])}
""".strip()


# ── Analyst Agent ─────────────────────────────────────────────────────────────

class AnalystAgent(BaseAgent):
    """
    Agente Analista (2.1) — Lê o FSIPP/Ata e extrai o ProposalContext.

    Usa o LLM para:
      1. Identificar o tipo de documento
      2. Extrair dados estruturados
      3. Inferir campos faltantes com lógica de negócio
      4. Calcular confidence score
    """

    EXTRACTION_SCHEMA = {
        "type": "object",
        "properties": {
            "input_type": {
                "type": "string",
                "enum": ["fsipp", "ata", "texto_livre"],
                "description": "Tipo do documento de entrada"
            },
            "data_proposta": {
                "type": "string",
                "description": "Data da proposta (ex: Outubro de 2025)"
            },
            "cliente": {
                "type": "object",
                "properties": {
                    "empresa": {"type": "string"},
                    "contato_nome": {"type": "string"},
                    "contato_email": {"type": "string"},
                    "contato_telefone": {"type": "string"},
                    "descricao_empresa": {"type": "string"},
                    "setor": {"type": "string"}
                }
            },
            "projeto": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "problema": {"type": "string"},
                    "objetivo": {"type": "string"},
                    "prazo_meses": {"type": "integer"},
                    "trl_atual": {"type": "integer", "minimum": 1, "maximum": 9},
                    "trl_final": {"type": "integer", "minimum": 1, "maximum": 9},
                    "tecnologias": {"type": "array", "items": {"type": "string"}},
                    "areas_conhecimento": {"type": "array", "items": {"type": "string"}},
                    "requisitos": {"type": "array", "items": {"type": "string"}},
                    "beneficios": {"type": "array", "items": {"type": "string"}},
                    "riscos_tecnologicos": {"type": "array", "items": {"type": "string"}},
                    "exclusoes_escopo": {"type": "array", "items": {"type": "string"}}
                }
            },
            "entregas": {
                "type": "object",
                "properties": {
                    "entregas_macro": {"type": "array", "items": {"type": "string"}},
                    "entregas_detalhadas": {"type": "array", "items": {"type": "string"}},
                    "marcos": {"type": "array", "items": {"type": "string"}},
                    "cronograma_texto": {"type": "string"}
                }
            },
            "organizacao": {
                "type": "object",
                "properties": {
                    "interlocutor": {"type": "string"},
                    "responsavel_orcamento": {"type": "string"},
                    "areas_participantes": {"type": "array", "items": {"type": "string"}}
                }
            },
            "premissas": {"type": "array", "items": {"type": "string"}},
            "premissas_ml": {"type": "array", "items": {"type": "string"}},
            "riscos_projeto": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "dimensao": {"type": "string"},
                        "criticidade": {"type": "string"},
                        "risco": {"type": "string"},
                        "resposta": {"type": "string"},
                        "plano_acao": {"type": "string"},
                        "responsavel": {"type": "string"}
                    }
                }
            },
            "comentarios_finais": {"type": "array", "items": {"type": "string"}},
            "missing_fields": {"type": "array", "items": {"type": "string"}},
            "confidence_score": {"type": "number", "minimum": 0, "maximum": 1}
        }
    }

    @property
    def system_prompt(self) -> str:
        return """Você é um analista especializado em propostas de P&D e inovação do SENAI CIMATEC.

Sua função é extrair TODOS os dados relevantes de um documento de entrada (FSIPP, ata de reunião 
ou texto livre de cliente) para gerar uma proposta corporativa completa no padrão CARO.

REGRAS:
1. Extraia EXATAMENTE o que está no documento. Não invente dados.
2. Para campos não encontrados, use string vazia "" ou lista vazia [].
3. Se um campo pode ser inferido com alta confiança, infira e marque em warnings.
4. Identifique o tipo do documento: fsipp, ata ou texto_livre.
5. Calcule confidence_score: 1.0 = todos os campos essenciais presentes.
6. Campos essenciais: empresa, problema, objetivo, prazo_meses, titulo.
7. Liste em missing_fields todos os campos obrigatórios ausentes.
8. Responda APENAS com JSON válido, sem markdown, sem texto extra.

CAMPOS ESSENCIAIS DA PROPOSTA CARO:
- cliente.empresa, cliente.contato_nome
- projeto.titulo, projeto.problema, projeto.objetivo
- projeto.prazo_meses, projeto.trl_atual, projeto.trl_final
- projeto.beneficios (mínimo 3)
- projeto.requisitos (mínimo 2)
- entregas.entregas_macro (mínimo 1)
- premissas (mínimo 3)"""

    def run(self, document_text: str, document_type: str = "auto") -> AgentResult:
        """
        Analisa o documento e extrai ProposalContext.

        Args:
            document_text: Texto do FSIPP, ata ou documento de entrada
            document_type: "auto", "fsipp", "ata" ou "texto_livre"

        Returns:
            AgentResult com content = ProposalContext
        """
        self.logger.info(
            f"🔍 Analisando documento ({len(document_text)} chars)...")

        # Prompt principal de extração
        user_msg = f"""Analise o documento abaixo e extraia todos os dados estruturados.
Tipo esperado: {document_type}

DOCUMENTO:
───────────────────────────────────────────────────────
{document_text}
───────────────────────────────────────────────────────

Responda APENAS com JSON seguindo exatamente o schema fornecido.
Não adicione texto antes ou depois do JSON."""

        result = self.call_llm_json(user_msg)

        if not result.success:
            return result

        # Parse do JSON extraído
        extracted = self.extract_json(result.content)
        if not extracted:
            self.logger.error(f"Falha ao parsear JSON: {result.content[:200]}")
            result.success = False
            result.error = "JSON parsing failed"
            return result

        # Construir ProposalContext
        context = self._build_context(extracted, document_text)
        result.content = context
        result.metadata["extracted_raw"] = extracted

        self.logger.info(
            f"✅ Contexto extraído: confidence={context.confidence_score:.2f}, "
            f"missing={context.missing_fields}"
        )

        return result

    # ── Helpers de cast seguro ────────────────────────────────────────────────

    @staticmethod
    def _safe_int(value, default: int) -> int:
        """int() robusto — trata '', None, floats e strings numéricas do LLM."""
        if value is None or value == "":
            return default
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_float(value, default: float) -> float:
        if value is None or value == "":
            return default
        try:
            return float(str(value).strip())
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_list(value, default=None) -> list:
        """Garante lista — o LLM às vezes retorna None, string ou lista vazia."""
        if default is None:
            default = []
        if isinstance(value, list):
            return [str(v).strip() for v in value if v is not None and str(v).strip()]
        if isinstance(value, str) and value.strip():
            import re
            items = re.split(r"[\n;]+", value)
            return [i.strip() for i in items if i.strip()]
        return default

    @staticmethod
    def _safe_str(value, default: str = "") -> str:
        if value is None:
            return default
        return str(value).strip()

    # ── Build context ─────────────────────────────────────────────────────────

    def _build_context(self, data: Dict, raw_input: str) -> ProposalContext:
        """Constrói ProposalContext a partir dos dados extraídos — robusto a campos malformados."""
        # Garantir que sub-dicts existem e são dicts (LLM pode retornar None)
        cliente_raw = data.get("cliente") or {}
        projeto_raw = data.get("projeto") or {}
        entregas_raw = data.get("entregas") or {}
        org_raw = data.get("organizacao") or {}

        if not isinstance(cliente_raw, dict):
            cliente_raw = {}
        if not isinstance(projeto_raw, dict):
            projeto_raw = {}
        if not isinstance(entregas_raw, dict):
            entregas_raw = {}
        if not isinstance(org_raw, dict):
            org_raw = {}

        cliente = ClientData(
            empresa=self._safe_str(cliente_raw.get("empresa")),
            contato_nome=self._safe_str(cliente_raw.get("contato_nome")),
            contato_email=self._safe_str(cliente_raw.get("contato_email")),
            contato_telefone=self._safe_str(
                cliente_raw.get("contato_telefone")),
            descricao_empresa=self._safe_str(
                cliente_raw.get("descricao_empresa")),
            setor=self._safe_str(cliente_raw.get("setor")),
        )

        projeto = ProjectData(
            titulo=self._safe_str(projeto_raw.get("titulo")),
            problema=self._safe_str(projeto_raw.get("problema")),
            objetivo=self._safe_str(projeto_raw.get("objetivo")),
            prazo_meses=self._safe_int(projeto_raw.get("prazo_meses"), 0),
            trl_atual=self._safe_int(projeto_raw.get("trl_atual"), 3),
            trl_final=self._safe_int(projeto_raw.get("trl_final"), 6),
            tecnologias=self._safe_list(projeto_raw.get("tecnologias")),
            areas_conhecimento=self._safe_list(
                projeto_raw.get("areas_conhecimento")),
            requisitos=self._safe_list(projeto_raw.get("requisitos")),
            beneficios=self._safe_list(projeto_raw.get("beneficios")),
            riscos_tecnologicos=self._safe_list(
                projeto_raw.get("riscos_tecnologicos")),
            exclusoes_escopo=self._safe_list(
                projeto_raw.get("exclusoes_escopo")),
        )

        # Garantir consistência de TRL (atual deve ser < final)
        if projeto.trl_atual > 0 and projeto.trl_atual >= projeto.trl_final:
            projeto.trl_final = min(projeto.trl_atual + 2, 9)

        entregas = DeliverableData(
            entregas_macro=self._safe_list(entregas_raw.get("entregas_macro")),
            entregas_detalhadas=self._safe_list(
                entregas_raw.get("entregas_detalhadas")),
            marcos=self._safe_list(entregas_raw.get("marcos")),
            cronograma_texto=self._safe_str(
                entregas_raw.get("cronograma_texto")),
        )

        organizacao = OrganizationData(
            interlocutor=self._safe_str(org_raw.get("interlocutor")),
            responsavel_orcamento=self._safe_str(
                org_raw.get("responsavel_orcamento")),
            areas_participantes=self._safe_list(
                org_raw.get("areas_participantes")),
        )

        # riscos_projeto é lista de dicts — validar estrutura
        riscos_raw = data.get("riscos_projeto") or []
        riscos = [r for r in riscos_raw if isinstance(
            r, dict)] if isinstance(riscos_raw, list) else []

        return ProposalContext(
            raw_input=raw_input,
            input_type=self._safe_str(data.get("input_type"), "texto_livre"),
            data_proposta=self._safe_str(data.get("data_proposta")),
            cliente=cliente,
            projeto=projeto,
            entregas=entregas,
            organizacao=organizacao,
            premissas=self._safe_list(data.get("premissas")),
            premissas_ml=self._safe_list(data.get("premissas_ml")),
            riscos_projeto=riscos,
            comentarios_finais=self._safe_list(data.get("comentarios_finais")),
            confidence_score=self._safe_float(
                data.get("confidence_score"), 0.5),
            missing_fields=self._safe_list(data.get("missing_fields")),
        )
