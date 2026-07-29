# CARO.AI — Gerador de Apresentações de CARO com IA.

Pipeline automatizado que lê um documento **FSIPP** (PDF, DOCX ou TXT), utiliza **RAG com ChromaDB** e a API **OpenAI** para gerar uma apresentação **CARO** preenchida automaticamente a partir de um template PowerPoint.

---

## Fluxo de Funcionamento

```text
[1/6] Extrair texto do documento FSIPP    (reader.py)
        |
        v
[2/6] Ler template PPTX                  (template_reader.py)
        |
        v
[3/6] Carregar conhecimento RAG + ChromaDB  (ai.py)
        |
        v
[4/6] Gerar conteúdo com OpenAI        (ai.py)
        |
        v
[5/6] Preencher template com conteúdo  (renderer.py)
        |
        v
[6/6] Salvar -> output/apresentação_caro.pptx
```

---

## Estrutura do Projeto

```text
.
+-- main.py              # Ponto de entrada (CLI)
+-- config.yaml          # Configuração do LLM e RAG
+-- reader.py            # Extrai texto de PDF, DOCX e TXT
+-- template_reader.py   # Lê placeholders do template PPTX
+-- ai.py                # Cliente OpenAI + RAG com ChromaDB
+-- renderer.py          # Preenche os slides com o conteúdo gerado
+-- requirements.txt     # Dependências do projeto
+-- .env                 # Chave da API OpenAI (OPENAI_API_KEY)
+-- rag/                 # Banco de conhecimento para RAG (rag.docx)
+-- templates/           # Diretório com templates .pptx
+-- output/              # Diretório com apresentações geradas
+-- env/                 # Ambiente virtual Python
```

---

## Pré-requisitos

- Python 3.11+
- Conta na [OpenAI](https://platform.openai.com) com chave de API

---

## Instalação

```powershell
# Criar e ativar ambiente virtual
python -m venv env
.\env\Scripts\Activate.ps1

# Instalar dependências
pip install -r requirements.txt
```

### Configurar a chave da API

Edite o arquivo `.env` e adicione sua chave da OpenAI:

```env
OPENAI_API_KEY=sk-sua-chave-aqui
```

> **Importante:** O arquivo `.env` deve estar sem BOM (Byte Order Mark). Ao salvar, use codificação **UTF-8 sem BOM**.

---

## Configuração (`config.yaml`)

O arquivo `config.yaml` permite configurar o modelo LLM e os parâmetros de RAG:

```yaml
llm:
  provider: openai
  model: gpt-4o
  temperature: 0.7

rag:
  knowledge_base: rag/rag.docx
  collection_name: fsipp_knowledge
  chunk_size: 1000
  chunk_overlap: 200
  top_k: 5
```

| Seção | Campo | Descrição | Padrão |
|-------|-------|-----------|--------|
| llm | model | Modelo OpenAI a utilizar | `gpt-4o` |
| llm | temperature | Temperatura da geração | `0.7` |
| rag | knowledge_base | Caminho para o documento de conhecimento | `rag/rag.docx` |
| rag | collection_name | Nome da coleção ChromaDB | `fsipp_knowledge` |
| rag | chunk_size | Tamanho de cada chunk em palavras | `1000` |
| rag | chunk_overlap | Sobreposição entre chunks | `200` |
| rag | top_k | Número de chunks recuperados | `5` |

---

## Uso

```powershell
python main.py --input fsipp.pdf --template templates/template.pptx
python main.py --input fsipp.docx --template templates/template.pptx
python main.py --input fsipp.txt --template templates/template.pptx
```

### Parâmetros

| Argumento    | Obrigatório | Descrição                                 |
|-------------|-------------|-------------------------------------------|
| `--input`   | Sim         | Caminho do arquivo FSIPP (PDF, DOCX ou TXT) |
| `--template`| Sim         | Caminho do template PowerPoint (.pptx) |

---

## Como Funciona

### 1. `reader.py` — Extração de texto

Lê o arquivo FSIPP e extrai todo o texto. Suporta:

- **PDF** via PyMuPDF (`fitz`)
- **DOCX** via python-docx
- **TXT** via leitura direta de arquivo

### 2. `template_reader.py` — Leitura do template

Percorre os slides do template PowerPoint e identifica placeholders de título e corpo, registrando posição e tamanho.

### 3. `ai.py` — Agente IA com RAG

- Inicializa o **ChromaDB** com o banco de conhecimento RAG (`rag/rag.docx`)
- Divide o conteúdo em **chunks** e gera **embeddings** usando `text-embedding-ada-002`
- Envia o texto do FSIPP junto com os **chunks relevantes** do RAG para o modelo OpenAI (configurado em `config.yaml`)
- Retorna um **JSON estruturado** com títulos e conteúdos para cada slide

### 4. `renderer.py` — Renderização

Percorre cada slide do template e substitui o texto do título e do primeiro placeholder de corpo pelos valores gerados pela IA. Salva o resultado em `output/apresentacao_caro.pptx`.

### 5. RAG — Retrieval-Augmented Generation

O ChromaDB armazena **chunks** do documento de conhecimento (`rag/rag.docx`) com embeddings OpenAI. Na geração, os chunks mais relevantes são recuperados e incluídos como **contexto adicional** no prompt, garantindo respostas mais precisas e fundamentadas.

---

## Dependências

| Pacote           | Versão mínima  | Descrição                                  |
|------------------|----------------|--------------------------------------------|
| `python-pptx`   | `>=1.0.0`     | Manipulação de arquivos PowerPoint        |
| `PyMuPDF`       | `>=1.24.0`    | Extração de texto de PDFs                 |
| `openai`        | `>=1.0.0`     | Cliente da API OpenAI (v2)                |
| `chromadb`      | `>=0.4.0`     | Banco vetorial para RAG                   |
| `pyyaml`        | `>=6.0`       | Leitura de arquivos YAML                  |
| `python-dotenv` | `>=1.0.0`     | Gestão de variáveis de ambiente           |
| `python-docx`   | `>=0.8.11`    | Extração de texto de arquivos DOCX        |

---

## Modelos de IA

### LLM (OpenAI)

- **Provedor:** OpenAI
- **Modelo:** `gpt-4o` (configurável via `config.yaml`)
- **Formato de resposta:** JSON estruturado

### Embeddings (OpenAI)

- **Modelo:** `text-embedding-ada-002`
- **Uso:** Geração de embeddings para o banco vetorial ChromaDB

---

## Banco de Conhecimento RAG

O documento `rag/rag.docx` contém informações de referência sobre os níveis **TRL (Technology Readiness Level)** segundo a norma **ISO 16290**, utilizados como conhecimento complementar durante a geração da apresentação.

---

## Licença

Projeto interno — SENAI CIMATEC.
