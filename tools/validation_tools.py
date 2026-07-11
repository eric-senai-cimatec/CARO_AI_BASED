"""
tools/validation_tools.py — Ferramentas de Validação

Valida entradas e saídas do pipeline:
  - validate_api_key: checa se a chave Groq está configurada
  - validate_template: checa se o template PPTX existe e é válido
  - validate_context: checa campos obrigatórios do ProposalContext
  - validate_output_path: checa se o diretório de saída é gravável
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def validate_api_key(api_key: Optional[str] = None) -> Tuple[bool, str]:
    """Verifica se a chave da API Groq está disponível."""
    key = api_key or os.getenv("GROQ_API_KEY", "")
    if not key:
        return False, (
            "GROQ_API_KEY não encontrada.\n"
            "Configure com: export GROQ_API_KEY='sua-chave'\n"
            "Ou crie um arquivo .env com GROQ_API_KEY=sua-chave"
        )
    if len(key) < 20:
        return False, f"GROQ_API_KEY parece inválida (muito curta: {len(key)} chars)"
    return True, f"API key OK ({key[:8]}...)"


def validate_template(template_path: str | Path) -> Tuple[bool, str]:
    """Verifica se o template PPTX existe e pode ser aberto."""
    path = Path(template_path)
    if not path.exists():
        return False, f"Template não encontrado: {path}"
    if path.suffix.lower() != ".pptx":
        return False, f"Arquivo não é um .pptx: {path.suffix}"
    if path.stat().st_size < 1000:
        return False, f"Template muito pequeno ({path.stat().st_size} bytes) — pode estar corrompido"
    try:
        from pptx import Presentation
        prs = Presentation(str(path))
        n = len(prs.slides)
        return True, f"Template OK: {path.name} ({n} slides)"
    except Exception as e:
        return False, f"Erro ao abrir template: {e}"


def validate_input_source(source: str | Path) -> Tuple[bool, str]:
    """Verifica se a fonte de entrada (PDF, TXT ou texto) é válida."""
    if isinstance(source, str) and not os.path.exists(source):
        if len(source) > 50:
            return True, f"Texto direto detectado ({len(source)} chars)"
        return False, "String muito curta para ser um FSIPP válido e não é um caminho de arquivo"

    path = Path(source)
    if not path.exists():
        return False, f"Arquivo não encontrado: {path}"
    if path.stat().st_size == 0:
        return False, f"Arquivo vazio: {path}"
    if path.suffix.lower() not in (".pdf", ".txt", ".md"):
        return False, f"Formato não suportado: {path.suffix} (use .pdf ou .txt)"
    return True, f"Arquivo OK: {path.name} ({path.stat().st_size // 1024} KB)"


def validate_output_path(output_path: str | Path) -> Tuple[bool, str]:
    """Verifica se o diretório de saída existe e é gravável."""
    path = Path(output_path)
    if path.suffix.lower() != ".pptx":
        return False, f"Saída deve ser um arquivo .pptx, não: {path.suffix}"
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        # Teste de escrita
        test_file = parent / ".write_test"
        test_file.touch()
        test_file.unlink()
        return True, f"Diretório de saída OK: {parent}"
    except PermissionError:
        return False, f"Sem permissão de escrita em: {parent}"


def validate_context(context) -> Tuple[bool, List[str]]:
    """
    Valida o ProposalContext para garantir que os campos mínimos estão presentes.

    Returns:
        (is_valid, list_of_missing_fields)
    """
    issues = []

    if not context.cliente.empresa:
        issues.append("cliente.empresa")
    if not context.projeto.titulo:
        issues.append("projeto.titulo")
    if not context.projeto.problema:
        issues.append("projeto.problema")
    if not context.projeto.objetivo:
        issues.append("projeto.objetivo")
    if context.projeto.prazo_meses <= 0:
        issues.append("projeto.prazo_meses")
    if not context.projeto.beneficios:
        issues.append("projeto.beneficios")
    if not context.entregas.entregas_macro:
        issues.append("entregas.entregas_macro")

    return len(issues) == 0, issues


def run_preflight_checks(
    template_path: str | Path,
    input_source: str | Path,
    output_path: str | Path,
    api_key: Optional[str] = None,
) -> Tuple[bool, List[str]]:
    """
    Executa todas as verificações de pré-voo antes de iniciar o pipeline.

    Returns:
        (all_ok, list_of_messages)
    """
    messages = []
    all_ok = True

    checks = [
        ("🔑 API Key", lambda: validate_api_key(api_key)),
        ("📄 Template", lambda: validate_template(template_path)),
        ("📥 Input", lambda: validate_input_source(input_source)),
        ("📤 Output", lambda: validate_output_path(output_path)),
    ]

    for label, check_fn in checks:
        try:
            ok, msg = check_fn()
            status = "✅" if ok else "❌"
            messages.append(f"{status} {label}: {msg}")
            if not ok:
                all_ok = False
        except Exception as e:
            messages.append(f"❌ {label}: Exceção — {e}")
            all_ok = False

    return all_ok, messages
