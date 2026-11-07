# MaraChef

Como saber se a carne chegou ao ponto? Qual é a textura certa antes de seguir para a próxima etapa? Esses detalhes costumam aparecer quando alguém demonstra o preparo. A MaraChef transforma essas demonstrações e as fichas técnicas da cozinha em receitas que a equipe consegue consultar na hora de preparar um prato.

## Como funciona

1. **Registrar o preparo.** A equipe escolhe um prato e envia o vídeo. O Gemini organiza a gravação em etapas com marcações de tempo. O administrador também pode enviar uma ficha técnica em PDF.
2. **Revisar e publicar.** Em **Validações**, o chef confere o conteúdo, corrige o que for preciso e aprova a versão que vai para a biblioteca.
3. **Aprender na bancada.** Na **Biblioteca de Receitas**, a equipe escolhe o prato, consulta os ingredientes e abre o trecho de vídeo da etapa que quer aprender. O assistente responde com base no material aprovado e aponta para o trecho do vídeo ou para a página do PDF usada como referência.

## O que mostrar no hackathon

- **Aprender uma etapa.** Abra **Ovos mexidos com cogumelos e queijo** e clique na quinta etapa. O vídeo vai direto a **1:03**.
- **Conferir uma orientação.** Abra **Virada Paulista**, consulte os ingredientes e pergunte ao assistente quantas porções a receita rende. A resposta indica a página da ficha.
- **Registrar um preparo.** Envie um vídeo em **Registrar Preparo**, acompanhe a análise automática e abra o rascunho em **Validações** para mostrar como o chef decide o que vai para a biblioteca.

O catálogo da demonstração já inclui fichas em PDF e um vídeo com etapas revisadas. Esse material funciona com a chave do Gemini vazia. O assistente e a análise de novos vídeos usam a API pela internet. [Origem dos materiais](Alimenta/marachef_mvp_funcional/marachef_mvp/demo/README.md)

## Como rodar a demonstração

Instale e abra o Docker Desktop no Windows ou macOS. No Linux, use Docker Engine com o plugin Docker Compose. Os contêineres incluem Python, PostgreSQL com pgvector, FFmpeg e FFprobe. [Instalação do Docker Compose](https://docs.docker.com/compose/install/)

1. Clone o repositório e abra um terminal na raiz. Gere a configuração local com o comando do seu sistema.

   **Windows · PowerShell**

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\scripts\configurar-demo.ps1
   ```

   **macOS ou Linux**

   ```sh
   sh scripts/configurar-demo.sh
   ```

2. Para usar o chat ou analisar novos vídeos, preencha `GEMINI_API_KEY` no arquivo `Alimenta/marachef_mvp_funcional/marachef_mvp/.env`. A reprodução do vídeo e a leitura das fichas do pacote funcionam com o campo vazio. [Criar chave no Google AI Studio](https://aistudio.google.com/app/apikey)

3. Suba os serviços e crie sua conta. Escolha uma senha de pelo menos 12 caracteres quando o terminal pedir.

   ```sh
   cd Alimenta/marachef_mvp_funcional/marachef_mvp
   docker compose up --build -d --wait
   docker compose exec app python manage.py criar-usuario admin administrador
   ```

4. Abra a [MaraChef](http://127.0.0.1:8000) e entre como `admin`.

O primeiro build baixa as imagens e as dependências. A carga do catálogo é repetível e mantém os registros existentes.

<details>
<summary>Operação local e solução de problemas</summary>

| Situação | O que fazer |
| --- | --- |
| Voltar à demo em outro dia | Na pasta da aplicação, execute `docker compose up -d --wait`. |
| Parar a aplicação | Execute `docker compose down`. Os volumes guardam banco, mídia e contas. |
| Porta 8000 ocupada | No `.env`, ajuste `APP_PORT` para uma porta livre, execute `docker compose up -d --wait` e abra a nova porta no navegador. |
| Porta 5433 ocupada | No `.env`, ajuste `POSTGRES_PORT`. A aplicação no Docker continua usando a porta interna do banco. |
| Alterar a chave do Gemini | Edite `.env` e execute `docker compose up -d --wait app`. |
| Rede instável | Deixe os contêineres montados antes do evento. Apresente a biblioteca, as fichas e o vídeo já analisado. |

Cada computador tem seu próprio banco, arquivos e contas locais. O estudo de caso institucional pode ser importado à parte com uma cópia autorizada.

</details>

## Desenvolvimento

A aplicação usa FastAPI, PostgreSQL com pgvector para buscar trechos do acervo, Gemini para análise e respostas, e FFmpeg para processar os vídeos. O guia técnico reúne a execução fora do Docker, os testes e os detalhes da arquitetura. [Guia de desenvolvimento](Alimenta/marachef_mvp_funcional/marachef_mvp/LEIA_PRIMEIRO.md)
