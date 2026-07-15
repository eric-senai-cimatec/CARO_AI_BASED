import json
import os

from groq import Groq


class CAROAgent:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY não encontrada no arquivo .env")
        self.client = Groq(api_key=api_key)

    def generate(self, pdf_text: str, slides: list) -> dict:
        prompt = self._build_prompt(pdf_text, slides)

        response = self.client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        return json.loads(content)

    def _build_prompt(self, pdf_text: str, slides: list) -> str:
        slides_desc = json.dumps(slides, indent=2, ensure_ascii=False)

        return f"""Você é um especialista em elaboração de apresentações CARO.

Use exclusivamente as informações presentes no documento FSIPP abaixo para preencher o conteúdo dos slides.

Regras:
- Não invente conteúdo.
- Respeite o tema de cada slide descrito na estrutura fornecida.
- Escreva de forma objetiva.
- Utilize listas no body quando apropriado (cada item separado por quebra de linha).
- Deixe body vazio quando o FSIPP não possuir informação para aquele slide.
- Se o FSIPP não tiver informação alguma, retorne body vazio para todos os slides.

Retorne APENAS JSON, sem formatação adicional, no formato exato:
{{
  "slides": [
    {{
      "slide": 1,
      "title": "Título do slide",
      "body": "Conteúdo do slide"
    }}
  ]
}}

=== DOCUMENTO FSIPP ===
{pdf_text}

=== ESTRUTURA DOS SLIDES ===
{slides_desc}"""
