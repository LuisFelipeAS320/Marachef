# MaraChef

Aplicação local para registrar preparos em vídeo, revisar o conhecimento extraído e responder às perguntas da cozinha com referências verificáveis.

## Executar

Para instalar a demonstração completa pelo Docker, siga o [guia na raiz do repositório](../../../README.md). Os passos abaixo mantêm a opção de rodar o servidor diretamente no computador.

Use Python 3.11+, PostgreSQL com pgvector (Docker Compose incluído) e uma chave da Gemini API. Para vídeo, instale FFprobe e FFmpeg. Coloque os executáveis no PATH ou configure `FFMPEG_BIN_DIR` com o caminho da pasta `bin`.

Execute no PowerShell a partir da pasta que contém este arquivo.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe manage.py segredo
```

Se já houver um `.env`, mantenha o arquivo existente. Configure as variáveis abaixo.

| Variável | Configuração |
| --- | --- |
| `GEMINI_API_KEY` | Crie uma chave no [Google AI Studio](https://aistudio.google.com/app/apikey) e guarde-a no `.env`. |
| `GEMINI_MODEL` | Por padrão, `gemini-3.5-flash-lite`. Use um modelo da sua conta com compreensão de vídeo e saída estruturada. |
| `POSTGRES_PASSWORD` | Escolha uma senha longa para o banco do Compose. |
| `DATABASE_URL` | `postgresql://marachef:SENHA@127.0.0.1:5433/marachef`. Codifique a senha para URL se contiver caracteres especiais. |
| `MARACHEF_SESSION_SECRET` | Use a saída de `manage.py segredo`. |
| `MARACHEF_HTTPS_ONLY` | Use `true` ao publicar atrás de HTTPS. |
| `FFMPEG_BIN_DIR` | Caminho opcional para a pasta com `ffmpeg` e `ffprobe`. |

```powershell
docker compose --project-name marachef-alimenta up -d --wait db
.\.venv\Scripts\python.exe manage.py init-db
.\.venv\Scripts\python.exe manage.py criar-usuario admin administrador
.\.venv\Scripts\python.exe manage.py criar-usuario chef chef
.\.venv\Scripts\python.exe manage.py criar-usuario equipe funcionario
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Acesse [MaraChef](http://127.0.0.1:8000) e entre com uma das contas que você criou. As senhas são digitadas no terminal sem aparecer na tela. O comando guarda o hash no `.env`. Reinicie o servidor depois de alterar contas ou variáveis. Em Linux ou macOS, ative o ambiente virtual, instale as dependências, inicie o banco e execute `bash iniciar.sh`.

## Fontes iniciais

Execute `python manage.py carregar-demo` para carregar localmente o pacote com o PDF, os três pratos, o vídeo revisado e seus embeddings. O comando identifica os três pratos e separa os trechos nos títulos das receitas, inclusive quando dois pratos ocupam a mesma página. As tabelas de textura são lidas por coluna para manter cada orientação ligada ao item certo. O carregamento do pacote usa vetores existentes.

```powershell
.\.venv\Scripts\python.exe manage.py carregar-demo
.\.venv\Scripts\python.exe manage.py verificar-demo
```

A base **Demonstração** contém receitas aprovadas para testes técnicos. **Estudo de caso** é uma base separada de contexto institucional. Se tiver uma cópia autorizada do PDF institucional, rode `python manage.py importar-contexto caminho/do/arquivo.pdf`. A importação manual envia o texto extraído ao Gemini para gerar embeddings. A **Base oficial** recebe fichas e registros revisados por um chef ou administrador.

## Fluxo de trabalho

1. Em **Registrar preparo**, cadastre o prato ou escolha um já existente. Chef e administrador podem cadastrar pratos. O administrador pode enviar um PDF de até 25 MB, com texto extraível e referente a um prato.
2. Qualquer perfil autenticado pode registrar um vídeo de até 200 MB e 60 minutos. Informe o cozinheiro e, se houver, acrescente observações e legendas. Envie o vídeo e selecione **Analisar vídeo com Gemini**.
3. A análise separa observações visuais, declarações do chef e inferências. Abra uma etapa para assistir a partir do timestamp e conferir o ponto de referência, o tempo, a temperatura ou a fala associada.
4. Em **Validações**, chef e administrador podem corrigir o rascunho, salvá-lo, aprová-lo ou rejeitá-lo. A análise pode ser solicitada novamente. Cada decisão cria uma versão com autor e data. A aprovação grava os trechos e seus vetores em uma transação.
5. A equipe pode comentar um vídeo aprovado ou uma etapa específica. O chef pode corrigir, aprovar ou rejeitar a observação. Comentários só entram nas consultas quando aprovados e vinculados à versão vigente do vídeo.
6. Em **Biblioteca de Receitas**, escolha um prato publicado. A ficha reúne modo de preparo, ingredientes, documentos e o assistente daquele prato. Quando houver vídeo, clique em uma etapa para assistir ao trecho. As respostas citam a página do PDF ou o timestamp do vídeo.

## Arquitetura

- `app.py` serve a interface, aplica os perfis de acesso e recebe uploads. A biblioteca reúne fontes aprovadas por prato. Quando o mesmo prato tem material de demonstração e material publicado para operação, a ficha usa o material publicado.
- `knowledge.py` valida PDFs e vídeos. O pypdf extrai os trechos com o número de página. O FFprobe valida duração e presença de imagem. O FFmpeg converte MKV para MP4.
- `gemini.py` usa o SDK oficial `google-genai`. Vídeos curtos de até 12 MB e 60 segundos seguem junto à solicitação. A Files API recebe os maiores temporariamente, com exclusão solicitada ao fim da análise. O servidor valida a estrutura e os timestamps retornados.
- `store.py` e `schema.sql` mantêm pratos, fontes, versões e trechos no PostgreSQL. A busca combina distância cosseno no pgvector com relevância lexical em português. Os embeddings textuais usam `gemini-embedding-001` com 768 dimensões.
- `workflow.py` controla a aprovação e o histórico. O RAG fundamenta orientações na versão aprovada vigente. A versão aprovada anterior pode aparecer como referência de uma divergência. Inferências ficam visíveis aos revisores.
- `rag.py` delimita a consulta por base e prato antes de recuperar os trechos. O servidor confere os IDs e os excertos citados pelo Gemini. Quando falta evidência, a MaraChef orienta o funcionário a consultar o chef.
- `data/uploads/` guarda os arquivos com nomes internos aleatórios. A rota de mídia verifica a sessão e o acesso à fonte antes de servir arquivos ou intervalos de vídeo.

Documentação da integração: [Gemini Files API](https://ai.google.dev/api/files), [saída estruturada](https://ai.google.dev/gemini-api/docs/generate-content/structured-output), [embeddings](https://ai.google.dev/gemini-api/docs/embeddings) e [pgvector](https://github.com/pgvector/pgvector).

## Testes

Para rodar as verificações automatizadas, configure `MARACHEF_TEST_DEMO_PDF` com o caminho do PDF e `MARACHEF_TEST_DATABASE_URL` com a conexão de um banco descartável com pgvector. Em seguida, execute:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check assets/marachef.js
```

Os testes de API usam PostgreSQL e o PDF real. O Gemini é substituído por um dublê nos testes automatizados para verificar permissões, fluxo de aprovação, isolamento por prato e base, citações e ausência de resposta. O comando `verificar-demo` executa as oito perguntas de aceitação e verifica a recusa para a rabada oficial com a integração configurada.

Na instalação local, foram indexados 20 trechos de demonstração e 15 do estudo de caso com embeddings reais. As oito perguntas sobre o PDF, a recusa para a rabada oficial e uma consulta institucional passaram. O teste no Edge verificou login, navegação, chat, logout e abertura do PDF na página citada.

Na instalação Docker a partir de uma cópia limpa, o pacote carregou quatro pratos e 30 trechos. A conta, a ficha em PDF e o vídeo aos 63 segundos continuaram acessíveis após reiniciar a aplicação com a chave vazia. Uma consulta ao Gemini com chave de teste retornou as quatro porções da Virada Paulista com referência à página 2. Os 13 testes automatizados passaram.

O fluxo multimodal foi validado com um vídeo sintético de oito segundos com narração. O Gemini identificou duas etapas. Depois da aprovação no banco descartável, o chat citou a segunda etapa aos 2 segundos e o servidor serviu o intervalo de mídia solicitado. Uma fala saiu transcrita com imprecisão.

## Limites do MVP

- PDFs digitalizados precisam de OCR prévio. O envio de fichas oficiais aceita um prato por arquivo. A importação da demonstração reconhece o PDF fornecido para este projeto.
- A análise é síncrona e depende da disponibilidade e da cota do modelo. Os timestamps são aproximados. O player usa o vídeo original ou convertido e salta para os intervalos sugeridos.
- Citações verificadas apontam para trechos recuperados. A qualidade da síntese e a identificação de divergências dependem da resposta do modelo. O histórico completo permanece disponível para consulta humana.
- As contas e os arquivos são locais. A instalação foi preparada para uso em localhost. A implantação para várias pessoas exige HTTPS, backups do banco e dos uploads e controle de acesso ao servidor.
