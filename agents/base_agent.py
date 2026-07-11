"""
agents/base_agent.py — Classe Base dos Agentes

Todos os agentes herdam desta classe.
Fornece:
  - Cliente Groq (via OpenAI-compatible API)
  - Histórico de mensagens
  - Sistema de tools/functions
  - Retry com backoff
  - Logging estruturado
  - Serialização de resultados
"""

from __future__ import annotations

import json
import logging
import time
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import config
import sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent.parent))


logger = logging.getLogger(__name__)


# ── Modelos de mensagem ───────────────────────────────────────────────────────

@dataclass
class Message:
    role: str    # "system" | "user" | "assistant" | "tool"
    content: str
    tool_call_id: Optional[str] = None
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class AgentResult:
    """Resultado estruturado de uma execução de agente."""
    agent_name: str
    success: bool
    content: Any                     # Conteúdo principal (str, dict, list)
    raw_response: str = ""           # Resposta raw do LLM
    tokens_used: int = 0
    execution_time_s: float = 0.0
    retries: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent_name,
            "success": self.success,
            "content": self.content,
            "tokens_used": self.tokens_used,
            "execution_time_s": round(self.execution_time_s, 2),
            "retries": self.retries,
            "error": self.error,
        }


# ── Tool definition ───────────────────────────────────────────────────────────

@dataclass
class ToolDefinition:
    """Define uma tool disponível para o agente."""
    name: str
    description: str
    parameters: Dict[str, Any]        # JSON Schema
    handler: Callable[..., Any]       # Função Python que executa a tool

    def to_groq_format(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


# ── Cliente Groq ──────────────────────────────────────────────────────────────

class GroqClient:
    """
    Cliente leve para a API da Groq (compatível com OpenAI).
    Usa requests puro para evitar dependência pesada.
    """

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", config.GROQ_API_KEY)
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY não encontrada. "
                "Defina a variável de ambiente GROQ_API_KEY."
            )

    def chat(
        self,
        messages: List[Dict],
        model: str = config.DEFAULT_MODEL,
        max_tokens: int = config.MAX_TOKENS_DEFAULT,
        temperature: float = config.TEMPERATURE_DEFAULT,
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        response_format: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Chama a API de chat da Groq.

        Returns:
            dict com keys: content, finish_reason, usage, tool_calls
        """
        import urllib.request

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        if response_format:
            payload["response_format"] = response_format

        data = json.dumps(payload).encode("utf-8")
        # AJUSTE AQUI: Adicione o User-Agent simulando um cliente real
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) CARO-Framework/1.0"
        }

        req = urllib.request.Request(
            f"{self.BASE_URL}/chat/completions",
            data=data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_SECONDS) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8")
            raise RuntimeError(f"Groq API error {e.code}: {body}") from e

        choice = result["choices"][0]
        msg = choice["message"]

        return {
            "content": msg.get("content") or "",
            "finish_reason": choice.get("finish_reason", ""),
            "tool_calls": msg.get("tool_calls"),
            "usage": result.get("usage", {}),
        }

    def chat_json(
        self,
        messages: List[Dict],
        model: str = config.DEFAULT_MODEL,
        max_tokens: int = config.MAX_TOKENS_DEFAULT,
        temperature: float = config.TEMPERATURE_DEFAULT,
    ) -> Dict[str, Any]:
        """Chat que garante resposta em JSON."""
        return self.chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={"type": "json_object"},
        )


# ── Classe Base ───────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    Classe base para todos os agentes do CARO Framework.

    Subclasses devem implementar:
      - system_prompt property
      - run() method
    """

    def __init__(
        self,
        name: str,
        model: str = config.DEFAULT_MODEL,
        max_tokens: int = config.MAX_TOKENS_DEFAULT,
        temperature: float = config.TEMPERATURE_DEFAULT,
        max_retries: int = config.MAX_RETRIES,
        groq_client: Optional[GroqClient] = None,
    ):
        self.name = name
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.client = groq_client or GroqClient()
        self._history: List[Message] = []
        self._tools: Dict[str, ToolDefinition] = {}
        self.logger = logging.getLogger(f"caro.agent.{name}")

    # ── Abstract ──────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Prompt de sistema do agente."""
        ...

    @abstractmethod
    def run(self, *args, **kwargs) -> AgentResult:
        """Executa a tarefa principal do agente."""
        ...

    # ── Tools ─────────────────────────────────────────────────────────────────

    def register_tool(self, tool: ToolDefinition):
        """Registra uma tool disponível para o agente."""
        self._tools[tool.name] = tool
        self.logger.debug(f"Tool registrada: {tool.name}")

    def call_llm(
        self,
        user_message: str,
        system_override: Optional[str] = None,
        use_tools: bool = False,
        json_mode: bool = False,
        extra_context: Optional[str] = None,
    ) -> AgentResult:
        """
        Chama o LLM com retry automático.

        Args:
            user_message: Mensagem do usuário
            system_override: Sobrescreve o system prompt para esta chamada
            use_tools: Ativar ferramentas nesta chamada
            json_mode: Forçar resposta em JSON
            extra_context: Contexto adicional injetado antes da mensagem do usuário

        Returns:
            AgentResult com a resposta
        """
        start_time = time.time()
        system = system_override or self.system_prompt

        # Construir mensagens
        messages = [{"role": "system", "content": system}]

        # Histórico (opcional — apenas últimas N mensagens)
        for msg in self._history[-10:]:
            messages.append(msg.to_dict())

        if extra_context:
            messages.append({
                "role": "user",
                "content": f"[CONTEXTO ADICIONAL]\n{extra_context}"
            })

        messages.append({"role": "user", "content": user_message})

        tools_defs = None
        if use_tools and self._tools:
            tools_defs = [t.to_groq_format() for t in self._tools.values()]

        last_error = None
        for attempt in range(self.max_retries):
            try:
                if json_mode:
                    resp = self.client.chat_json(
                        messages=messages,
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                    )
                else:
                    resp = self.client.chat(
                        messages=messages,
                        model=self.model,
                        max_tokens=self.max_tokens,
                        temperature=self.temperature,
                        tools=tools_defs,
                    )

                # Processar tool calls se houver
                if resp.get("tool_calls"):
                    resp = self._handle_tool_calls(messages, resp)

                elapsed = time.time() - start_time
                usage = resp.get("usage", {})
                tokens = usage.get("total_tokens", 0)

                self.logger.debug(
                    f"LLM ok — {tokens} tokens, {elapsed:.1f}s, attempt={attempt+1}"
                )

                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    content=resp["content"],
                    raw_response=resp["content"],
                    tokens_used=tokens,
                    execution_time_s=elapsed,
                    retries=attempt,
                )

            except Exception as e:
                last_error = e
                wait = config.RETRY_DELAY_SECONDS * (2 ** attempt)
                self.logger.warning(
                    f"LLM error attempt {attempt+1}/{self.max_retries}: {e}. "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)

        elapsed = time.time() - start_time
        return AgentResult(
            agent_name=self.name,
            success=False,
            content=None,
            error=str(last_error),
            execution_time_s=elapsed,
            retries=self.max_retries,
        )

    def call_llm_json(self, user_message: str, **kwargs) -> AgentResult:
        """Atalho para call_llm com json_mode=True."""
        return self.call_llm(user_message, json_mode=True, **kwargs)

    # ── Tool Handling ─────────────────────────────────────────────────────────

    def _handle_tool_calls(
        self,
        messages: List[Dict],
        response: Dict,
    ) -> Dict:
        """
        Processa tool calls retornadas pelo LLM.
        Executa as funções e retorna a resposta final.
        """
        tool_calls = response["tool_calls"]
        messages_with_tools = messages.copy()

        # Adicionar resposta do assistente com tool_calls
        messages_with_tools.append({
            "role": "assistant",
            "content": response.get("content") or "",
            "tool_calls": tool_calls,
        })

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args_str = tc["function"].get("arguments", "{}")
            tc_id = tc["id"]

            self.logger.debug(f"Tool call: {fn_name}({fn_args_str[:100]})")

            # Executar tool
            tool_result = self._execute_tool(fn_name, fn_args_str)

            messages_with_tools.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })

        # Nova chamada ao LLM com resultados das tools
        final_resp = self.client.chat(
            messages=messages_with_tools,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return final_resp

    def _execute_tool(self, fn_name: str, fn_args_str: str) -> Any:
        """Executa uma tool pelo nome."""
        if fn_name not in self._tools:
            return {"error": f"Tool '{fn_name}' não encontrada"}
        try:
            args = json.loads(fn_args_str)
            result = self._tools[fn_name].handler(**args)
            return result if result is not None else {"ok": True}
        except Exception as e:
            self.logger.error(f"Tool '{fn_name}' error: {e}")
            return {"error": str(e)}

    # ── Histórico ─────────────────────────────────────────────────────────────

    def add_to_history(self, role: str, content: str):
        self._history.append(Message(role=role, content=content))

    def clear_history(self):
        self._history = []

    def get_history_text(self) -> str:
        return "\n".join(f"[{m.role}] {m.content[:200]}" for m in self._history)

    # ── Parse helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def extract_json(text: str) -> Optional[Dict]:
        """Extrai JSON de uma resposta de texto (trata markdown code blocks)."""
        import re
        text = text.strip()

        # Tentar parse direto
        try:
            return json.loads(text)
        except Exception:
            pass

        # Tentar extrair de ```json ... ```
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        # Tentar encontrar { ... } ou [ ... ]
        m = re.search(r"(\{[\s\S]+\}|\[[\s\S]+\])", text)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass

        return None

    @staticmethod
    def parse_bullets(text: str) -> List[str]:
        """Extrai lista de bullets de texto com •, -, * ou numeração."""
        import re
        lines = text.strip().split("\n")
        bullets = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Remover marcadores comuns
            line = re.sub(r"^[\•\-\*\–\—]\s+", "", line)
            line = re.sub(r"^\d+[\.\)]\s+", "", line)
            if line:
                bullets.append(line)
        return bullets

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r}, model={self.model!r})"
