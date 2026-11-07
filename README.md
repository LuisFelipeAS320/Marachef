# MaraChef

A MaraChef organiza preparos de cozinha em receitas consultáveis. A equipe escolhe um prato na biblioteca, acompanha as etapas por vídeo ou PDF e tira dúvidas com referências ao material aprovado.

## Rodar a demonstração

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

4. Abra a [MaraChef](http://127.0.0.1:8000) e entre como `admin`. Em **Biblioteca de Receitas**, abra **Ovos mexidos com cogumelos e queijo** e clique na quinta etapa. O vídeo abre em **1:03**. Em **Virada Paulista**, abra a aba **Ingredientes** ou pergunte ao assistente quantas porções a receita rende.

O primeiro build baixa as imagens e as dependências. O catálogo local já inclui o PDF, o vídeo aprovado para demonstração e seus embeddings. A carga é repetível e mantém os registros existentes. O chat e novas análises consultam o Gemini pela internet. [Origem dos materiais](Alimenta/marachef_mvp_funcional/marachef_mvp/demo/README.md)

## Durante o hackathon

| Situação | O que fazer |
| --- | --- |
| Voltar à demo em outro dia | Na pasta da aplicação, execute `docker compose up -d --wait`. |
| Parar a aplicação | Execute `docker compose down`. Os volumes guardam banco, mídia e contas. |
| Porta 8000 ocupada | No `.env`, ajuste `APP_PORT` para uma porta livre, execute `docker compose up -d --wait` e abra a nova porta no navegador. |
| Porta 5433 ocupada | No `.env`, ajuste `POSTGRES_PORT`. A aplicação no Docker continua usando a porta interna do banco. |
| Alterar a chave do Gemini | Edite `.env` e execute `docker compose up -d --wait app`. |
| Rede instável | Deixe os contêineres montados antes do evento. Apresente a biblioteca, as fichas e o vídeo já analisado. |

Cada computador tem seu próprio banco, arquivos e contas locais. O estudo de caso institucional pode ser importado à parte com uma cópia autorizada. O [guia de desenvolvimento](Alimenta/marachef_mvp_funcional/marachef_mvp/LEIA_PRIMEIRO.md) explica a execução fora do Docker, os testes e os fluxos de aprovação.

