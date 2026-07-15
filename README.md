# CARO.AI - Gerador de Apresentações de CARO com IA.

Pipeline automatizado que extrai o conteúdo de um documento **FSIPP** (PDF), analisa a estrutura de um **template PowerPoint** e utiliza **IA (Groq)** para gerar uma apresentação **CARO** preenchida automaticamente.

## Fluxo de Funcionamento

```
[1/5] Extrair texto do PDF (pdf_reader.py)
        │
        ▼
[2/5] Ler template PPTX (template_reader.py)
        │
        ▼
[3/5] Enviar para IA Groq (ai.py)
        │
        ▼
[4/5] Preencher template com conteúdo gerado (renderer.py)
        │
        ▼
[5/5] Salvar → output/apresentacao_caro.pptx
```

## Estrutura do Projeto

```
├── main.py              # Ponto de entrada (CLI)
├── pdf_reader.py        # Extrai texto de PDFs com PyMuPDF
├── template_reader.py   # Lê placeholders do template PPTX
├── ai.py                # Cliente Groq (LLaMA) para gerar conteúdo
├── renderer.py          # Preenche os slides com o conteúdo gerado
├── requirements.txt     # Dependências do projeto
├── .env                 # Chave da API Groq (GROQ_API_KEY)
├── templates/           # Diretório com templates .pptx
├── output/              # Diretório com apresentações geradas
└── env/                 # Ambiente virtual Python
```

## Pré-requisitos

- Python 3.11+
- Conta na [Groq](https://console.groq.com) com chave de API

## Instalação

```bash
# Criar e ativar ambiente virtual
python -m venv env
.\env\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt

# Configurar chave da API
# Edite o arquivo .env e adicione:
# GROQ_API_KEY=sua_chave_aqui
```

## Uso

```bash
python main.py --input fsipp.pdf --template templates/template.pptx
```

Parâmetros:
- `--input` — Caminho do arquivo FSIPP em PDF
- `--template` — Caminho do template PowerPoint (.pptx)

## Como Funciona

1. **pdf_reader.py** — Lê o PDF do FSIPP e extrai todo o texto usando PyMuPDF (`fitz`).
2. **template_reader.py** — Percorre os slides do template e identifica placeholders de título e corpo, registrando posição e tamanho.
3. **ai.py** — Envia o texto do FSIPP e a estrutura dos slides para o modelo `meta-llama/llama-4-scout-17b-16e-instruct` via Groq. A IA retorna um JSON com títulos e conteúdos para cada slide, seguindo regras como não inventar informações e usar listas no corpo quando apropriado.
4. **renderer.py** — Percorre cada slide do template e substitui o texto do título e do primeiro placeholder de corpo pelos valores gerados pela IA, salvando o resultado em `output/apresentacao_caro.pptx`.

## Modelo de IA Utilizado

- **Provedor:** Groq
- **Modelo:** `meta-llama/llama-4-scout-17b-16e-instruct`
- **Formato de resposta:** JSON estruturado
