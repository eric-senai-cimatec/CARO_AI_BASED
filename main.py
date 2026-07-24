import argparse
from dotenv import load_dotenv

from pdf_reader import extract_pdf_text
from template_reader import extract_template
from ai import CAROAgent
from ppt.renderer import render


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="CARO Presentation Generator")
    parser.add_argument("--input", required=True, help="Caminho do arquivo FSIPP PDF")
    parser.add_argument("--template", required=True, help="Caminho do template PPTX")

    args = parser.parse_args()

    print("[1/5] Extraindo texto do PDF...")
    texto = extract_pdf_text(args.input)

    print("[2/5] Lendo template PowerPoint...")
    slides = extract_template(args.template)

    print("[3/5] Enviando para IA (Groq)...")
    agent = CAROAgent()
    conteudo = agent.generate(texto, slides)

    print("[4/5] Preenchendo template...")
    render(args.template, conteudo)

    print("[5/5] Concluído! Arquivo salvo em: output/apresentacao_caro.pptx")


if __name__ == "__main__":
    main()
