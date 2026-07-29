import argparse
import yaml
from dotenv import load_dotenv

from reader import extract_text
from template_reader import extract_template
from ai import CAROAgent
from ppt.renderer import render


def main():
    env_path = load_dotenv(override=True)
    if not env_path:
        print("AVISO: Arquivo .env nao encontrado no diretorio atual.")

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    llm_config = config.get("llm", {})
    rag_config = config.get("rag", {})

    parser = argparse.ArgumentParser(description="CARO Presentation Generator")
    parser.add_argument("--input", required=True, help="Caminho do arquivo (PDF, DOCX ou TXT)")
    parser.add_argument("--template", required=True, help="Caminho do template PPTX")

    args = parser.parse_args()

    print("[1/5] Extraindo texto do documento...")
    texto = extract_text(args.input)

    print("[2/5] Lendo template PowerPoint...")
    slides = extract_template(args.template)

    agent_config = {
        "model": llm_config.get("model", "gpt-5-mini"),
        "temperature": llm_config.get("temperature", 0.7),
        "top_k": rag_config.get("top_k", 5),
        "collection_name": rag_config.get("collection_name", "fsipp_knowledge"),
        "chunk_size": rag_config.get("chunk_size", 1000),
        "chunk_overlap": rag_config.get("chunk_overlap", 200),
        "knowledge_base": rag_config.get("knowledge_base", "rag/rag.docx"),
    }

    print("[3/5] Inicializando agente IA e RAG...")
    agent = CAROAgent(agent_config)

    print("[4/5] Enviando para OpenAI...")
    conteudo = agent.generate(texto, slides)

    print("[5/5] Preenchendo template...")
    render(args.template, conteudo)

    print("[6/5] Concluído! Arquivo salvo em: output/apresentacao_caro.pptx")


if __name__ == "__main__":
    main()
