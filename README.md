# CLARO ONE

**Continuidade de contexto entre canais**

Protótipo acadêmico que mantém o contexto de um atendimento quando o cliente muda de canal. Todos os dados são fictícios e não existe integração com sistemas reais da Claro.

## Funcionalidades

- Telefone/URA simulado com envio de gravação.
- Transcrição local com faster-whisper.
- Interpretação do atendimento com Ollama e `qwen3:4b`.
- CCE com contexto estruturado, eventos e validade de duas horas.
- Retomada pelo WhatsApp simulado sem repetir o problema.
- Minha Claro adaptado ao tipo de atendimento.
- Cockpit com resumo, entidades, timeline e transcrição.
- Tela de debug e reinicialização da demonstração.

## Como baixar

Instale o [Git](https://git-scm.com/download/win), abra o PowerShell e execute:

```powershell
git clone https://github.com/alencasz/ClaroOne.git
cd ClaroOne
```

## Como instalar e executar

Siga o passo a passo do arquivo [INSTRUCOES_INSTALACAO_E_TESTES.txt](INSTRUCOES_INSTALACAO_E_TESTES.txt).

Depois de iniciar o servidor, abra:

<http://127.0.0.1:8000>

Os áudios prontos para demonstração estão na pasta `Audios`.
