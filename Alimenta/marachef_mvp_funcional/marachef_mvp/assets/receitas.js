"use strict";

const recipeUrl = id => `/receita?prato=${encodeURIComponent(id)}`;
const recipePhotoUrl = id => `/api/receitas/${encodeURIComponent(id)}/foto`;
const searchKey = value => value.normalize("NFD").replace(/\p{M}/gu, "").toLocaleLowerCase("pt-BR");

async function renderLibrary() {
  const recipes = await api("/api/receitas");
  main.innerHTML = `
    <header class="library-heading">
      <div><p class="eyebrow">Consulta de bancada</p>
        <h1>Biblioteca de Receitas</h1>
        <p>Escolha o prato que você quer aprender a preparar.</p></div>
      <label for="recipe-search">Buscar prato
        <input type="search" id="recipe-search" placeholder="Ex.: Virada Paulista">
      </label>
    </header>
    ${recipes.length ? `<ul class="recipe-grid">${recipes.map((recipe, index) => `
      <li data-recipe-card>
        <a class="recipe-card" href="${recipeUrl(recipe.id)}">
          <div class="recipe-cover" data-cover="${index % 4}" aria-hidden="true">
            <span class="recipe-cover-icon">${icon("dish")}</span>
            ${recipe.has_photo ? `<img src="${recipePhotoUrl(recipe.id)}" alt="" loading="lazy">` : ""}
          </div>
          <div class="recipe-card-body">
            <span class="recipe-tag">${recipe.scope === "demo" ? "Demonstração" : "Receita publicada"}</span>
            <h2>${escapeHtml(recipe.name)}</h2>
            <p>${recipe.kind === "video" ? `${recipe.stage_count} etapas em vídeo` : "Modo de preparo em PDF"}</p>
            <span class="recipe-card-link">Ver modo de preparo ${icon("arrow")}</span>
          </div>
        </a>
      </li>`).join("")}</ul>
      <p id="recipe-empty" class="card muted" role="status" hidden>Nenhum prato encontrado.</p>`
    : '<p class="card muted">As receitas publicadas aparecerão aqui.</p>'}`;
  document.querySelector("#recipe-search").disabled = !recipes.length;
  if (!recipes.length) return;
  const cards = [...main.querySelectorAll("[data-recipe-card]")];
  const keys = recipes.map(item => searchKey([item.name, ...item.aliases].join(" ")));
  document.querySelector("#recipe-search").oninput = event => {
    const query = searchKey(event.target.value).trim();
    cards.forEach((card, index) => { card.hidden = !keys[index].includes(query); });
    document.querySelector("#recipe-empty").hidden = cards.some(card => !card.hidden);
  };
  main.querySelectorAll(".recipe-cover img").forEach(image => {
    image.addEventListener("error", () => image.remove(), {once: true});
    if (image.complete && !image.naturalWidth) image.remove();
  });
}

function recipePdfLink(document, page = document.chunks[0]?.page) {
  const href = `${document.url}${page ? `#page=${page}` : ""}`;
  return `<a class="button secondary" href="${escapeHtml(href)}" target="_blank" rel="noopener">
    ${icon("file")} ${page ? `Abrir PDF · pág. ${page}` : "Abrir PDF"}</a>`;
}

function recipeDocuments(documents, openFirst = false) {
  if (!documents.length) return `<p class="muted">As etapas e orientações deste prato estão no vídeo.</p>`;
  return documents.map((document, index) => `
    <div class="recipe-document">
      <h3>${escapeHtml(sourceTitle(document))}</h3>
      ${recipePdfLink(document)}
      <details ${openFirst && index === 0 ? "open" : ""}><summary>Ler trechos deste prato</summary>
        ${document.chunks.map(chunk => `<p class="recipe-excerpt"><small>Página ${chunk.page}</small>
          <span class="prewrap">${escapeHtml(chunk.body)}</span></p>`).join("")}
      </details>
    </div>`).join("");
}

function recipeIngredientLines(text) {
  const groups = text.trim().split(/\n[ \t]*\n+/);
  if (/^Parte do prato[ \t]+Ingredientes$/i.test(groups[0])) {
    const rows = groups.slice(1).map(group => {
      const [line, ...rest] = group.trim().split("\n");
      const [part, ...ingredients] = line.split(/[ \t]{2,}/);
      return {part, ingredients: [...ingredients, ...rest].map(item => item.trim()).join(" ").trim()};
    });
    if (rows.length && rows.every(row => row.ingredients)) {
      return `<dl class="recipe-ingredient-groups">${rows.map(row => `<div>
        <dt>${escapeHtml(row.part)}</dt><dd>${escapeHtml(row.ingredients)}</dd></div>`).join("")}</dl>`;
    }
  }
  return `<ul class="recipe-ingredient-lines">${text.split("\n").map(line => line.trim()).filter(Boolean)
    .map(line => `<li>${escapeHtml(line)}</li>`).join("")}</ul>`;
}

function recipePdfIngredients(documents) {
  for (const document of documents) {
    const text = document.chunks.map(chunk => chunk.body).join("\n");
    const match = text.match(/^\s*(Ingredientes(?:[ \t]+\([^\n]*\))?)[ \t]*:?[ \t]*\n([\s\S]*?)(?=^[ \t]*(?:Passo a passo\b|Modo de preparo\b|\d+\.\s))/im);
    if (match?.[2].trim()) {
      const page = document.chunks.find(chunk => chunk.body.includes(match[1]))?.page;
      return `<div class="recipe-document"><h3>${escapeHtml(match[1])}</h3>
        ${recipeIngredientLines(match[2])}${recipePdfLink(document, page)}</div>`;
    }
  }
  return `<p class="muted">${documents.length ? "Consulte a ficha técnica para conferir os ingredientes documentados." :
    "A lista de ingredientes deste preparo ainda não foi documentada."}</p>`;
}

async function renderRecipe() {
  const id = new URLSearchParams(location.search).get("prato");
  if (!id) {
    location.replace("/biblioteca");
    return;
  }
  const endpoint = `/api/receitas/${encodeURIComponent(id)}`;
  const {recipe, videos, documents} = await api(endpoint);
  const name = escapeHtml(recipe.name);
  main.innerHTML = `
    <header class="recipe-hero">
      <a href="/biblioteca">← Voltar à biblioteca</a>
      <div class="recipe-hero-title">
        <div><p>Consulta de bancada</p><h1>${name}</h1></div>
        <span class="recipe-tag">${recipe.scope === "demo" ? "Receita de demonstração" : "Receita publicada"}</span>
      </div>
    </header>
    ${reviewer() ? `<details class="card recipe-photo-edit">
      <summary id="recipe-photo-label">${recipe.has_photo ? "Trocar foto do prato" : "Adicionar foto do prato"}</summary>
      <p class="muted">A foto aparece no cartão da biblioteca. Use JPG, PNG ou WebP de até 5 MB.</p>
      <form id="recipe-photo"><fieldset>
        <label>Foto do prato <input name="photo" type="file" accept="image/jpeg,image/png,image/webp" required></label>
        <button>Salvar foto</button>
      </fieldset><p role="status"></p></form>
    </details>` : ""}
    <div class="recipe-toolbar">
      <div class="recipe-tabs" role="group" aria-label="Seções da receita">
        <button data-recipe-tab="preparo" aria-pressed="true">${icon("play")} Modo de preparo</button>
        <button data-recipe-tab="ingredientes" aria-pressed="false">${icon("list")} Ingredientes</button>
        <button data-recipe-tab="ficha" aria-pressed="false">${icon("file")} Ficha técnica</button>
      </div>
      <p id="recipe-meta" class="muted"></p>
    </div>
    <div class="recipe-workspace">
      <div>
        <div id="recipe-preparo" data-recipe-panel>
          ${videos.length ? `<section class="card recipe-player">
            ${videos.length > 1 ? `<label>Vídeo do preparo <select id="recipe-recording">
              ${videos.map((video, index) => `<option value="${index}">Gravação ${index + 1} · ${formatTime(video.duration)}${video.cook ? ` · ${escapeHtml(video.cook)}` : ""}</option>`).join("")}
            </select></label>` : ""}
            <h2 class="section-label" id="recipe-player-title">Vídeo da etapa selecionada</h2>
            <video id="recipe-player" controls playsinline preload="metadata"></video>
          </section>
          <section class="card" id="recipe-ingredients-preview" hidden>
            <h2 class="section-label">${icon("list")} Ingredientes documentados</h2>
            <div id="recipe-ingredients-preview-list"></div>
          </section>
          <section class="card recipe-observation" id="recipe-observation"></section>` :
          `<section class="card"><h2>Modo de preparo em PDF</h2>
            <p class="muted">Abra a ficha na página deste prato ou leia os trechos aqui.</p>
            ${recipeDocuments(documents, true)}</section>`}
        </div>
        <section class="card" id="recipe-ingredientes" data-recipe-panel hidden>
          <h2>Ingredientes</h2><div id="recipe-ingredient-list">${recipePdfIngredients(documents)}</div>
        </section>
        <section class="card" id="recipe-ficha" data-recipe-panel hidden>
          <h2>Ficha técnica</h2>
          ${recipe.summary ? `<p>${escapeHtml(recipe.summary)}</p>` : ""}
          ${videos.length ? '<dl class="recipe-facts" id="recipe-facts"></dl>' : ""}
          ${recipeDocuments(documents)}
        </section>
      </div>
      <div class="recipe-side">
        <section class="card recipe-assistant">
          <header class="recipe-panel-header"><span class="recipe-assistant-icon">${icon("chat")}</span>
            <div><h2>Assistente MaraChef</h2><p class="muted">Dúvidas sobre ${name}</p></div></header>
          <div id="recipe-conversation" class="recipe-conversation" role="log" aria-label="Conversa sobre o prato">
            <p class="recipe-answer">O que você quer saber sobre este preparo?</p>
          </div>
          <div class="recipe-suggestions" aria-label="Perguntas sugeridas">
            <button type="button" class="secondary" data-question="Quais são os ingredientes?">Ingredientes</button>
            <button type="button" class="secondary" data-question="Como sei que chegou ao ponto?">Ponto do preparo</button>
            ${videos.length ? '<button type="button" class="secondary" data-question="O que observar nesta etapa?">O que observar?</button>' : ""}
          </div>
          <form id="recipe-chat"><fieldset>
            <div class="recipe-message">
              <label for="recipe-question" class="sr-only">Pergunte sobre este prato</label>
              <input id="recipe-question" name="question" maxlength="1400" required placeholder="Pergunte sobre este prato…">
              <button aria-label="Enviar pergunta">${icon("arrow")}</button>
            </div>
          </fieldset><p role="status"></p></form>
          <small class="muted">Respostas com referências do prato selecionado.</small>
        </section>
        ${videos.length ? `<section class="card recipe-steps">
          <h2 class="section-label">Etapas de preparo</h2>
          <p class="muted">Escolha uma etapa para assistir ao trecho.</p>
          <ol id="recipe-steps"></ol>
        </section>` : ""}
      </div>
    </div>`;
  bindForm("recipe-photo", async (fields, report) => {
    if (fields.get("photo").size > 5 * 1024 ** 2) throw new Error("Envie uma foto de até 5 MB.");
    await post(recipePhotoUrl(id), fields);
    document.getElementById("recipe-photo").reset();
    document.getElementById("recipe-photo-label").textContent = "Trocar foto do prato";
    status(report, "Foto salva na biblioteca.");
  }, "Salvando foto…");
  const sections = [...main.querySelectorAll("[data-recipe-panel]")];
  const tabs = [...main.querySelectorAll("[data-recipe-tab]")];
  const show = tab => {
    sections.forEach(section => { section.hidden = section.id !== `recipe-${tab}`; });
    tabs.forEach(button => button.setAttribute("aria-pressed", button.dataset.recipeTab === tab));
  };
  tabs.forEach(button => { button.onclick = () => show(button.dataset.recipeTab); });

  let videoIndex = 0;
  let stageIndex = 0;
  const player = document.querySelector("#recipe-player");
  function selectStage(index, play = false) {
    stageIndex = index;
    const video = videos[videoIndex];
    const stage = video.stages[stageIndex];
    document.querySelector("#recipe-player-title").textContent = stage.title;
    player.src = `${video.url}#t=${stage.start},${stage.end}`;
    document.querySelector("#recipe-steps").querySelectorAll("button").forEach((button, position) => {
      button.setAttribute("aria-pressed", position === stageIndex);
    });
    document.querySelector("#recipe-observation").innerHTML = `
      <h2 class="section-label">${icon("list")} O que observar nesta etapa</h2>
      <p>${escapeHtml(stage.action)}</p>
      ${[stage.visual, stage.landmark].filter(value => value && !/^não identificad[ao]/i.test(value))
        .map(value => `<p class="muted">${escapeHtml(value)}</p>`).join("")}`;
    if (play) {
      show("preparo");
      player.play().catch(() => {});
      if (window.matchMedia("(max-width: 50rem)").matches) player.scrollIntoView({block:"center"});
    }
  }
  function selectRecording(index) {
    videoIndex = index;
    const video = videos[videoIndex];
    document.querySelector("#recipe-meta").textContent =
      `${formatTime(video.duration)} de vídeo · ${video.stages.length} etapas${video.cook ? ` · ${video.cook}` : ""}`;
    document.querySelector("#recipe-steps").innerHTML = video.stages.map((stage, position) => `
      <li><button type="button" data-recipe-stage="${position}" aria-pressed="false">
        <span>${position + 1}</span><strong>${escapeHtml(stage.title)}</strong>
        <small>${icon("play")} ${formatTime(stage.start)}</small>
      </button></li>`).join("");
    const ingredients = `<ul class="recipe-ingredients">${video.ingredients
      .map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
    document.querySelector("#recipe-ingredient-list").innerHTML = video.ingredients.length
      ? `<p class="muted">Ingredientes identificados no vídeo.</p>${ingredients}` : recipePdfIngredients(documents);
    document.querySelector("#recipe-ingredients-preview").hidden = !video.ingredients.length;
    document.querySelector("#recipe-ingredients-preview-list").innerHTML = ingredients;
    document.querySelector("#recipe-facts").innerHTML = `
      <div><dt>Duração da gravação</dt><dd>${formatTime(video.duration)}</dd></div>
      <div><dt>Etapas documentadas</dt><dd>${video.stages.length}</dd></div>
      ${video.cook ? `<div><dt>Responsável pelo preparo</dt><dd>${escapeHtml(video.cook)}</dd></div>` : ""}`;
    selectStage(0);
  }
  if (videos.length) {
    selectRecording(0);
    const recording = document.querySelector("#recipe-recording");
    if (recording) recording.onchange = () => selectRecording(Number(recording.value));
    document.querySelector("#recipe-steps").onclick = event => {
      const button = event.target.closest("[data-recipe-stage]");
      if (button) selectStage(Number(button.dataset.recipeStage), true);
    };
  } else {
    document.querySelector("#recipe-meta").textContent = "Preparo documentado em PDF";
  }

  const form = document.querySelector("#recipe-chat");
  const input = document.querySelector("#recipe-question");
  const conversation = document.querySelector("#recipe-conversation");
  main.querySelectorAll("[data-question]").forEach(button => {
    button.onclick = () => {
      input.value = button.dataset.question;
      input.focus();
    };
  });
  bindForm("recipe-chat", async (fields, report) => {
    const question = fields.get("question").trim();
    if (!question) throw new Error("Digite sua pergunta.");
    const stage = videos[videoIndex]?.stages[stageIndex];
    const contextual = stage && /\b(nesta|nessa|desta|dessa|esta|essa) etapa\b/i.test(question)
      ? `${question}\nEtapa selecionada: ${stage.title.slice(0, 220)}.` : question;
    const response = await post(`${endpoint}/perguntar`, {question: contextual});
    conversation.insertAdjacentHTML("beforeend", `
      <p class="recipe-question">${escapeHtml(question)}</p>
      <div class="recipe-answer"><p class="prewrap">${escapeHtml(response.answer)}</p>
        ${renderReferences(response.sources)}</div>`);
    conversation.scrollTop = conversation.scrollHeight;
    form.reset();
    status(report, "");
  }, "Consultando as orientações deste prato…");
  conversation.onclick = event => {
    const link = event.target.closest("a[href*='#t=']");
    if (!link || !player) return;
    const media = new URL(link.href);
    const index = videos.findIndex(video => video.url === media.pathname);
    if (index < 0) return;
    event.preventDefault();
    const recording = document.querySelector("#recipe-recording");
    if (recording) recording.value = index;
    selectRecording(index);
    const [start] = media.hash.slice(3).split(",").map(Number);
    const match = videos[index].stages.findIndex(stage => stage.start <= start && start < stage.end);
    if (match >= 0) selectStage(match);
    show("preparo");
    player.src = `${media.pathname}${media.hash}`;
    player.scrollIntoView({block:"center"});
    player.play().catch(() => {});
  };
}
