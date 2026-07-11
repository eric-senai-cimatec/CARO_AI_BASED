#!/usr/bin/env python3
"""
main.py — CARO Framework CLI
Gerador Inteligente de Propostas Corporativas com IA (Groq)

Uso:
    python main.py --input fsipp.pdf --template templates/template.pptx
    python main.py --input ata.txt   --output output/CARO_Bobinas_AI.pptx
    python main.py --interactive
    python main.py --parse-only      templates/CARO_Bobinas.pptx
"""

from __future__ import annotations
import config

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# ── Garantir que o pacote é encontrado mesmo rodando pelo root ───────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


# ── Logging ───────────────────────────────────────────────────────────────────


def setup_logging(level: str = "INFO", log_file: Optional[Path] = None):
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO),
                        format=fmt, datefmt=datefmt, handlers=handlers)
    # Silenciar logs barulhentos de libs de terceiros
    for noisy in ("urllib3", "pdfminer", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


logger = logging.getLogger("caro.main")


# ── Banner ────────────────────────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════════════╗
║        CARO — Gerador Inteligente de Propostas com IA           ║
║        SENAI CIMATEC  |  Powered by Groq LLM                    ║
╚══════════════════════════════════════════════════════════════════╝
"""


# ── Modos de operação ─────────────────────────────────────────────────────────

def run_pipeline(args: argparse.Namespace) -> int:
    """Modo principal: FSIPP/Ata → PPTX."""
    from agents.orchestrator import Orchestrator

    print(BANNER)

    # Verificar API key
    api_key = args.api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        print("❌ GROQ_API_KEY não encontrada.")
        print("   Configure com: export GROQ_API_KEY='sua-chave'")
        print("   Ou passe: --api-key gsk_...")
        return 1

    template = Path(args.template)
    input_source = args.input
    output = Path(args.output) if args.output else None

    # Callback de progresso para o terminal
    def progress(step: str, pct: float, message: str):
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {pct*100:3.0f}%  {message:<50}",
              end="", flush=True)
        if pct >= 1.0:
            print()  # nova linha ao terminar

    orch = Orchestrator(
        template_path=template,
        groq_api_key=api_key,
        audit_enabled=not args.no_audit,
        progress_callback=progress,
        model=args.model,
    )

    result = orch.run(
        input_source=input_source,
        output_path=output,
        skip_preflight=args.skip_preflight,
        auto_fix=not args.no_autofix,
    )

    print()  # linha em branco após barra de progresso
    print(result.summary())

    if result.audit_dir:
        print(f"\n📁 Arquivos de auditoria: {result.audit_dir}")

    return 0 if result.success else 1


def run_interactive(args: argparse.Namespace) -> int:
    """Modo interativo: perguntas no terminal."""
    print(BANNER)
    print("Modo Interativo — CARO Framework\n")

    api_key = args.api_key or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        api_key = input("🔑 Cole sua GROQ_API_KEY: ").strip()
        if not api_key:
            print("❌ API key necessária.")
            return 1

    template = args.template
    if not template:
        default = str(config.DEFAULT_TEMPLATE_PATH)
        template = input(
            f"📊 Caminho do template PPTX [{default}]: ").strip() or default

    input_source = input(
        "📄 Caminho do FSIPP (PDF/TXT) ou cole o texto: ").strip()
    if not input_source:
        print("❌ Entrada necessária.")
        return 1

    output = input(
        f"📤 Caminho de saída [output/proposta.pptx]: ").strip() or "output/proposta.pptx"

    print()
    # Criar args modificado para reutilizar run_pipeline
    args.api_key = api_key
    args.template = template
    args.input = input_source
    args.output = output
    args.model = args.model or config.DEFAULT_MODEL
    args.no_audit = False
    args.no_autofix = False
    args.skip_preflight = False

    return run_pipeline(args)


def run_parse_only(args: argparse.Namespace) -> int:
    """Modo debug: apenas parseia o template e mostra a AST."""
    from core.ast_pptx import PptxAST
    from core.template_reader import TemplateReader
    from core.region_detector import RegionDetector

    path = Path(args.parse_only)
    print(BANNER)
    print(f"🔍 Analisando template: {path}\n")

    # AST
    print("── AST ─────────────────────────────────────────────────")
    ast = PptxAST.from_file(path)
    print(ast.summary())

    # Template Model
    print("\n── Template Model ──────────────────────────────────────")
    reader = TemplateReader()
    model = reader.read(path)
    print(model.describe_all())

    # Salvar AST em JSON se --output especificado
    if args.output:
        out = Path(args.output)
        ast.save_json(out)
        print(f"\n✅ AST salva em: {out}")

    return 0


def run_validate_only(args: argparse.Namespace) -> int:
    """Modo validação: apenas verifica pré-condições sem rodar o pipeline."""
    from tools.validation_tools import run_preflight_checks

    print(BANNER)
    print("🔍 Verificando configurações...\n")

    ok, messages = run_preflight_checks(
        template_path=args.template or config.DEFAULT_TEMPLATE_PATH,
        input_source=args.input or ".",
        output_path=args.output or "output/test.pptx",
        api_key=args.api_key or os.getenv("GROQ_API_KEY"),
    )

    for msg in messages:
        print(f"  {msg}")

    print()
    print("✅ Tudo pronto para rodar!" if ok else "❌ Corrija os problemas acima antes de rodar.")
    return 0 if ok else 1


def run_cache_info(args: argparse.Namespace) -> int:
    """Exibe informações do cache de AST."""
    from core.template_cache import TemplateCache

    cache = TemplateCache(cache_dir=config.CACHE_DIR)
    stats = cache.stats()
    entries = cache.list_entries()

    print(BANNER)
    print("📦 Cache Info\n")
    print(f"  Diretório: {stats['cache_dir']}")
    print(f"  Entradas:  {stats['total_entries']} total "
          f"({stats['valid_entries']} válidas, {stats['expired_entries']} expiradas)")
    print(f"  Max age:   {stats['max_age_hours']}h")
    print()

    if entries:
        print("  ┌──────────────┬──────────────────────────────────────┬──────────┐")
        print("  │ Hash         │ Arquivo                              │ Idade    │")
        print("  ├──────────────┼──────────────────────────────────────┼──────────┤")
        for e in entries:
            valid_mark = "✅" if e["valid"] else "🕐"
            fname = Path(e["file"]).name[:36]
            print(
                f"  │ {e['hash']:<12s} │ {fname:<36s} │ {e['age_hours']:5.1f}h {valid_mark} │")
        print("  └──────────────┴──────────────────────────────────────┴──────────┘")

    if args.clear_cache:
        n = cache.clear_all()
        print(f"\n🗑️  Cache limpo: {n} entradas removidas")

    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="caro",
        description="CARO Framework — Gerador Inteligente de Propostas Corporativas com IA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Gerar proposta a partir de FSIPP PDF
  python main.py --input fsipp_cliente.pdf --template templates/CARO_Bobinas.pptx

  # Gerar com saída e modelo específicos
  python main.py --input ata_reuniao.txt --output output/proposta_caro.pptx --model llama-3.3-70b-versatile

  # Modo interativo (perguntas no terminal)
  python main.py --interactive

  # Apenas analisar o template (debug)
  python main.py --parse-only templates/CARO_Bobinas.pptx --output .cache/ast.json

  # Verificar configuração sem rodar
  python main.py --validate --template templates/CARO_Bobinas.pptx

  # Ver status do cache
  python main.py --cache-info
        """,
    )

    # ── Modos de operação
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--interactive", action="store_true",
                      help="Modo interativo (perguntas no terminal)")
    mode.add_argument("--parse-only", metavar="PPTX",
                      help="Apenas parseia o template e exibe a AST (debug)")
    mode.add_argument("--validate", action="store_true",
                      help="Valida configurações sem rodar o pipeline")
    mode.add_argument("--cache-info", action="store_true",
                      help="Exibe informações do cache de AST")

    # ── Entradas
    parser.add_argument("--input", "-i", metavar="FILE_OR_TEXT",
                        help="FSIPP em PDF, TXT ou texto colado diretamente")
    parser.add_argument("--template", "-t", metavar="PPTX",
                        default=str(config.DEFAULT_TEMPLATE_PATH),
                        help=f"Template PPTX (padrão: {config.DEFAULT_TEMPLATE_PATH})")
    parser.add_argument("--output", "-o", metavar="PPTX",
                        help="Arquivo de saída .pptx (padrão: output/proposta_TIMESTAMP.pptx)")

    # ── Configuração
    parser.add_argument("--api-key", metavar="KEY",
                        help="Chave da API Groq (padrão: variável GROQ_API_KEY)")
    parser.add_argument("--model", metavar="MODEL",
                        default=config.DEFAULT_MODEL,
                        help=f"Modelo Groq (padrão: {config.DEFAULT_MODEL})")

    # ── Flags
    parser.add_argument("--no-audit", action="store_true",
                        help="Desabilitar salvamento de arquivos de auditoria")
    parser.add_argument("--no-autofix", action="store_true",
                        help="Desabilitar correções automáticas do Reviewer")
    parser.add_argument("--skip-preflight", action="store_true",
                        help="Pular verificações de pré-voo")
    parser.add_argument("--clear-cache", action="store_true",
                        help="Limpar cache de AST (usar com --cache-info)")
    parser.add_argument("--log-level", default=config.LOG_LEVEL,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Nível de log")
    parser.add_argument("--log-file", metavar="FILE",
                        help="Arquivo de log (além do stdout)")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Logging
    log_file = Path(args.log_file) if getattr(args, "log_file", None) else None
    setup_logging(args.log_level, log_file)

    # ── Roteamento de modos ───────────────────────────────────────────────────
    if args.interactive:
        return run_interactive(args)

    if args.parse_only:
        return run_parse_only(args)

    if args.validate:
        return run_validate_only(args)

    if args.cache_info:
        return run_cache_info(args)

    # Modo padrão: pipeline completo
    if not args.input:
        parser.print_help()
        print("\n❌ --input é obrigatório para rodar o pipeline.")
        return 1

    return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
