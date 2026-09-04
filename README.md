# Claro One

Protótipo acadêmico de continuidade de contexto entre Telefone/URA, WhatsApp, Minha Claro e Cockpit. Os dados e canais são simulados.

## Arquitetura

- FastAPI, Jinja2, HTML/CSS/JavaScript e SQLite.
- CCE com estado estruturado, TTL de duas horas e timeline persistida.
- GroqCloud para duas etapas separadas: áudio → texto com `whisper-large-v3-turbo`; texto → case com `openai/gpt-oss-20b` e JSON Schema estrito validado por Pydantic.
- Não há modelos de IA executados localmente. O uso das IAs exige internet e uma chave da Groq.

## Instalação no Windows

Para clonar o projeto:

```powershell
git clone https://github.com/alencasz/ClaroOne.git
cd ClaroOne
```

Depois:

1. Execute `INSTALAR.bat` uma vez.
2. Crie uma chave em <https://console.groq.com/keys>.
3. No arquivo `.env`, cole a chave após `GROQ_API_KEY=`.
4. Execute `INICIAR_CLARO_ONE.bat` nos usos seguintes.
5. Acesse <http://127.0.0.1:8000>.

O `.env` não é versionado. A chave fica somente no backend.
`DEMO_FALLBACK` permanece `false` por padrão; quando ativado manualmente, o modo simulado fica visível na interface.

## Uso e testes

No Telefone, identifique o cliente, escolha a URA e clique em **Iniciar ligação** para gravar pelo microfone. Ao encerrar, o áudio é enviado automaticamente à Groq. O upload manual de MP3, WAV, M4A, WEBM ou OGG continua disponível como alternativa; há exemplos na pasta `Audios`.

O WhatsApp pode iniciar um contexto por texto ou retomar uma CCE. O Minha Claro transforma o contexto em navegação e também permite navegação manual sem CCE. Cockpit e Debug mostram contexto e eventos reais. A Home ou o Debug reiniciam os dados da demonstração.

Para executar a suíte:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Limites do protótipo

Não há telefonia, WhatsApp, CRM, billing ou autenticação reais. O navegador precisa autorizar o microfone, e o uso da Groq está sujeito à conectividade, aos limites e custos da conta. Em produção, seriam necessários gestão segura de segredos, autenticação, observabilidade, armazenamento apropriado, integrações oficiais e políticas de privacidade e retenção.
