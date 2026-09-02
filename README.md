# CLARO ONE

**Continuidade de contexto entre canais**

Protótipo acadêmico funcional que demonstra uma ideia simples: o contexto pertence ao cliente e ao atendimento, não ao canal. Uma ligação simulada é transcrita, interpretada e convertida em uma CCE (Cápsula de Contexto Efêmera), que pode ser retomada pelo WhatsApp simulado, transformada em navegação no Minha Claro e apresentada como informação operacional no Cockpit.

> Protótipo acadêmico — todos os clientes e dados são fictícios. Não há integração com sistemas reais da Claro.

## Experiências

- **Telefone / URA:** CPF, setor, ligação simulada, upload e duas etapas reais de IA.
- **WhatsApp:** o contexto vira conversa e encaminhamento, sem repetir o problema.
- **Minha Claro:** o contexto vira navegação para a funcionalidade adequada.
- **Cockpit:** snapshot, entidades dinâmicas, timeline real, transcrição e ações.
- **Debug:** JSON persistido e reset da demonstração.

## Arquitetura

```text
Áudio
  ↓
IA DE TRANSCRIÇÃO (faster-whisper: áudio → texto)
  ↓
Transcrição + setor da URA
  ↓
IA DE CONTEXTO (Ollama/Qwen: texto → case estruturado)
  ↓
CCE no SQLite + timeline de eventos
  ↓
Telefone / WhatsApp / Minha Claro / Cockpit
```

As duas IAs são deliberadamente independentes:

- `services/transcription_service.py` somente converte áudio em texto.
- `services/context_service.py` converte texto + URA em `ContextCase` validado pelo Pydantic.
- `services/cce_service.py` concentra criação, consulta, TTL, suspensão, retomada, resolução e eventos.
- `routes/api.py` expõe a API sem concentrar as regras de domínio.

O SQLite usa foreign keys e inicialização idempotente. A CCE nasce com TTL de duas horas. A expiração é verificada ao consultar; sessões expiradas ou resolvidas não são retomáveis. Uma retomada válida renova o TTL.

### Estrutura principal

```text
app.py                 inicialização do FastAPI
config.py              variáveis de ambiente e diretórios
database.py            schema SQLite e seed idempotente
schemas.py             contratos Pydantic
routes/                 páginas e API REST
services/               CCE, transcrição e contexto separados
templates/              interfaces Jinja2
static/css e static/js  visual e comportamento vanilla
tests/                  testes da lógica e da API
data/                   banco SQLite local
uploads/                gravações com nomes internos seguros
```

## Requisitos

- Windows 10/11
- Python 3.11 ou superior (validado também com Python 3.14)
- Ollama instalado e em execução
- Espaço para os modelos Qwen e Whisper

Nenhuma API key é necessária.

## Instalação no Windows

No PowerShell, dentro da pasta do projeto:

```powershell
cd C:\Users\lucas\Desktop\ClaroOne
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instale/inicie o Ollama e baixe o modelo:

```powershell
ollama pull qwen3:4b
ollama serve
```

No Windows, o aplicativo Ollama normalmente já mantém o serviço ativo. Se `ollama serve` indicar porta ocupada, ele provavelmente já está em execução.

## Como iniciar novamente

Depois de fechar o VS Code ou reiniciar o computador:

```powershell
cd C:\Users\lucas\Desktop\ClaroOne
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Abra:

- Aplicação: <http://127.0.0.1:8000>
- API interativa: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/api/health>
- Inspeção da CCE: <http://127.0.0.1:8000/debug>

Pare o servidor com `Ctrl+C`.

## Configuração

Os defaults funcionam sem `.env`. Para personalizar:

```powershell
Copy-Item .env.example .env
```

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:4b
WHISPER_MODEL=small
CCE_TTL_HOURS=2
DEMO_FALLBACK=false
MAX_UPLOAD_MB=25
```

O fallback é `false` por padrão. Se for ativado manualmente, todas as páginas mostram **MODO FALLBACK DE DEMONSTRAÇÃO**; uma falha real nunca é mascarada silenciosamente.

## Roteiro de demonstração

1. Abra a Home e apresente os quatro canais.
2. Entre em **Telefone / URA**.
3. Informe `123.456.789-00` (Lucas de Alencar).
4. Selecione **Fatura e pagamentos**.
5. No quadro **Carregar gravação da ligação**, selecione `.wav`, `.mp3` ou `.m4a`.
6. Clique em **Encerrar ligação**.
7. Acompanhe separadamente IA de Transcrição e IA de Contexto.
8. Veja problema, resumo, destino, protocolo e TTL.
9. Abra o WhatsApp com o mesmo CPF e retome sem repetir o caso.
10. Abra o Minha Claro e veja a navegação adaptada.
11. Abra o Cockpit para ver timeline, snapshot, entidades e transcrição.
12. Use `/debug` para mostrar o JSON persistido.

Áudio sugerido:

> “Olá, estou entrando em contato porque vi na minha fatura uma cobrança de trinta e cinco reais referente a um pacote adicional de internet. Eu não contratei esse pacote e gostaria de contestar essa cobrança.”

O primeiro uso do Whisper baixa o modelo `small` e pode ser mais lento. Faça esse primeiro processamento antes da apresentação.

## Reset

Use **Limpar / reiniciar demonstração** na Home ou **Reiniciar demonstração** em `/debug`. Isso remove CCEs, eventos e uploads, preserva os três clientes fictícios e mantém o schema.

Pela API:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/demo/reset
```

## Testes

```powershell
cd C:\Users\lucas\Desktop\ClaroOne
.\.venv\Scripts\python.exe -m pytest -q
```

Há cobertura para CPF, moeda, criação/eventos da CCE, busca ativa, expiração, renovação, resolução, parsing robusto do JSON, páginas HTTP e upload inválido.

## API interna

- `POST /api/sessions`
- `GET /api/sessions/{id}`
- `GET /api/sessions/active/{cpf}`
- `POST /api/sessions/{id}/audio`
- `POST /api/sessions/{id}/transcribe`
- `POST /api/sessions/{id}/contextualize`
- `POST /api/sessions/{id}/resume`
- `POST /api/sessions/{id}/handoff`
- `POST /api/sessions/{id}/resolve`
- `GET /api/sessions/{id}/events`
- `GET /api/health`

## Solução de problemas

### IA de contextualização indisponível

```powershell
ollama list
ollama pull qwen3:4b
```

Confira `/api/health`. O site continua disponível sem Ollama; somente a contextualização retorna erro legível.

### Primeiro Whisper demora

O primeiro uso baixa o modelo. Mantenha conexão com a internet. Ele fica em cache e é reutilizado no mesmo processo.

### Arquivo não transcreve

Confirme que é áudio real WAV, MP3 ou M4A, contém fala em português, não está vazio e tem até 25 MB. Apenas renomear um arquivo não o torna áudio válido.

### Porta 8000 ocupada

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
```

## Protótipo versus produção conceitual

| Protótipo | Produção conceitual |
|---|---|
| FastAPI local | API Gateway e orquestração |
| SQLite | Bancos corporativos e Redis com TTL |
| Ollama local | IA governada e observável |
| faster-whisper local | Pipeline de voz dimensionado |
| Interfaces simuladas | Canais oficiais, CRM e billing |
| Clientes fictícios | Identidade, consentimento e auditoria |

Produção é apenas referência arquitetural; não foi implementada.

## Limites deliberados

Não há telefonia real, microfone, WhatsApp Business API, CRM, billing, autenticação, Redis, RAG, Docker ou serviços distribuídos. Ações do Cockpit atualizam a CCE e a timeline, mas não acionam sistemas externos.
