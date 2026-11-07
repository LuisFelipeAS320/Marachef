"use strict";

const main = document.querySelector("#main");
const screen = location.pathname.slice(1);
const selectedSource = new URLSearchParams(location.search).get("fonte");
const VIDEO_LIMIT = 200 * 1024 ** 2;
const labels = {
  oficial: "Base oficial", demo: "Demonstração", institucional: "Estudo de caso",
  documento: "PDF", video: "Vídeo", comentario: "Observação",
  administrador: "Administrador", chef: "Chef", funcionario: "Equipe",
  aprovado: "Aprovado", pendente: "Pendente", rejeitado: "Rejeitado",
};
let user;

const reviewer = () => ["chef", "administrador"].includes(user.role);
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);
const options = (items, placeholder) =>
  `<option value="">${placeholder}</option>` +
  items.map(item => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)}</option>`).join("");
const formatTime = seconds => new Date(Math.floor(seconds * 1000)).toISOString().slice(11, 19);
const formatDate = value => new Date(value).toLocaleString("pt-BR");
const icon = name => `<svg class="icon" aria-hidden="true"><use href="#icon-${name}"/></svg>`;

async function api(path, options) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(typeof data.detail === "string" ? data.detail : "Confira os campos informados.");
    error.status = response.status;
    throw error;
  }
  return data;
}

const post = (path, body) => api(path, body instanceof FormData
  ? {method: "POST", body}
  : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});

function status(element, text, error = false) {
  element.className = error ? "error" : "status";
  element.textContent = text;
}

function bindForm(id, handler, busyText = "Salvando…") {
  const form = document.getElementById(id);
  if (!form) return;
  form.onsubmit = async event => {
    event.preventDefault();
    const report = form.querySelector("[role=status]");
    const controls = form.querySelector("fieldset");
    const fields = new FormData(form, event.submitter);
    controls.disabled = true;
    status(report, busyText);
    try {
      await handler(fields, report);
    } catch (error) {
      status(report, error.message, true);
    } finally {
      controls.disabled = false;
    }
  };
}

function renderLogin() {
  main.innerHTML = `
    <div class="card compact">
      <p class="eyebrow">Cozinha Marambaia</p><h1>Entre na MaraChef</h1>
      <p class="muted">Acesse os preparos e orientações da sua equipe.</p>
      <form id="login"><fieldset>
        <label>Usuário <input name="name" autocomplete="username" required maxlength="150"></label>
        <label>Senha <input name="password" type="password" autocomplete="current-password" required maxlength="256"></label>
        <button>Entrar</button>
      </fieldset><p role="status"></p></form>
    </div>`;
  bindForm("login", async fields => {
    await post("/api/login", Object.fromEntries(fields));
    location.reload();
  }, "Entrando…");
}

async function renderHome() {
  const items = await api("/api/sources");
  const recent = items.filter(item => item.kind === "video").slice(0, 3);
  main.innerHTML = `
    <header class="page-heading">
      <p class="eyebrow">Acervo &amp; memória culinária</p>
      <h1>O conhecimento que preserva nossa cozinha.</h1>
      <p>Registre técnicas, organize preparos e mantenha viva a tradição de cada receita.</p>
    </header>
    <section class="card home-hero">
      <div><h2>Registrar novo preparo</h2>
        <p class="muted">Envie a gravação e as informações do prato para a MaraChef organizar as etapas.</p></div>
      <a class="button" href="/registro">${icon("video")} Registrar novo preparo ${icon("arrow")}</a>
    </section>
    <section class="home-recent">
      <div class="section-heading"><div><p class="nav-caption">Últimos registros</p><h2>Preparos recentes</h2></div>
        <a href="/biblioteca">Ver acervo completo ${icon("arrow")}</a></div>
      <div class="card">${sourceList(recent, "etapas", "Os preparos enviados aparecerão aqui.")}</div>
    </section>
    <section class="home-workflow">
      <h2 class="nav-caption">Metodologia operacional · Como funciona a MaraChef</h2>
      <ol class="workflow-cards">
        <li><span>01</span><div><strong>Grave o preparo</strong><small>Registre a execução na bancada</small></div></li>
        <li><span>02</span><div><strong>IA organiza as etapas</strong><small>Confira técnicas e timestamps</small></div></li>
        <li><span>03</span><div><strong>Valide e preserve</strong><small>Revise antes de publicar no acervo</small></div></li>
      </ol>
    </section>`;
}

async function renderRegister() {
  const dishes = await api("/api/dishes");
  const dishSelect = `<label>Nome do prato ou base <select name="dish_id" required>${options(dishes, "Selecione o prato")}</select></label>`;
  main.innerHTML = `<header class="page-heading register-heading">
      <div><p class="eyebrow">Registro &amp; preservação técnica</p>
        <h1>Registrar um novo preparo</h1>
        <p class="muted">Transforme uma gravação completa em conhecimento organizado para sua equipe.</p></div>
      <ol class="process"><li aria-current="step">01. Enviar gravação</li><li>02. Analisar preparo</li><li>03. Revisar etapas</li></ol>
    </header>
    ${!dishes.length ? "<p>Cadastre um prato antes do envio. Se necessário, peça ajuda ao chef.</p>" : ""}
    <form id="video-upload"><fieldset class="register-grid">
      <section class="card">
        <h2 class="panel-heading">${icon("file")} Identificação da receita</h2>
          ${dishSelect}
          <label>Responsável pelo preparo <input name="cook" maxlength="150" required></label>
          <label>Observações opcionais <textarea name="observations" maxlength="6000"></textarea></label>
          <details><summary>Legendas ou transcrição</summary>
            <label class="sr-only" for="subtitles">Legendas ou transcrição</label>
            <textarea id="subtitles" name="subtitles" maxlength="30000" placeholder="Cole o texto com os timestamps, se disponíveis."></textarea>
          </details>
      </section>
      <div>
        <section class="card"><h2 class="panel-heading">${icon("video")} Gravação técnica do preparo</h2>
          <div class="upload-zone">
            <span class="upload-icon">${icon("upload")}</span>
            <label for="video-file">Selecione a gravação do preparo</label>
            <p class="muted">Envie o vídeo completo da execução. A MaraChef organiza os momentos e as técnicas do preparo em etapas.</p>
            <p id="video-limits" class="muted">MP4, MOV, WebM ou MKV · até 200 MB e 60 minutos</p>
            <input id="video-file" type="file" name="video" accept=".mp4,.mov,.webm,.mkv" aria-describedby="video-limits" required>
          </div>
        </section>
        <section class="card next-step">
          <div><p class="eyebrow">Etapa seguinte</p><h2>Análise do preparo</h2>
            <p class="muted">Depois do envio, você pode analisar o vídeo com a MaraChef.</p></div>
          <button>Enviar vídeo ${icon("arrow")}</button>
        </section>
        <p role="status"></p>
      </div>
    </fieldset></form>
    ${reviewer() ? `<div class="columns register-tools">
        ${user.role === "administrador" ? `<section class="card"><h2>Ficha técnica em PDF</h2>
          <p>Envie um PDF com texto de um prato. A ficha vai para validação.</p>
          <form id="pdf-upload"><fieldset>${dishSelect}
            <label>PDF <input type="file" name="document" accept=".pdf" required></label>
            <button>Enviar PDF</button>
          </fieldset><p role="status"></p></form></section>` : ""}
        ${reviewer() ? `<section class="card"><h2>Cadastrar prato</h2>
          <form id="dish-create"><fieldset>
            <label>Nome <input name="name" maxlength="150" required></label>
            <label>Outros nomes <input name="aliases" placeholder="Separe por vírgulas"></label>
            <button>Cadastrar prato</button>
          </fieldset><p role="status"></p></form></section>` : ""}
    </div>` : ""}`;
  bindForm("dish-create", async fields => {
    await post("/api/dishes", {name: fields.get("name"), aliases: fields.get("aliases").split(",").map(s => s.trim()).filter(Boolean)});
    await renderRegister();
  });
  bindForm("video-upload", async fields => {
    const video = fields.get("video");
    if (!video?.size || !/\.(mp4|mov|webm|mkv)$/i.test(video.name)) {
      throw new Error("Selecione um vídeo MP4, MOV, WebM ou MKV com conteúdo.");
    }
    if (video.size > VIDEO_LIMIT) {
      throw new Error("Selecione um vídeo de até 200 MB.");
    }
    const source = await post("/api/upload", fields);
    location.assign(`/etapas?fonte=${source.id}`);
  }, "Enviando vídeo…");
  bindForm("pdf-upload", async fields => {
    const source = await post("/api/documents", fields);
    location.assign(`/revisao?fonte=${source.id}`);
  }, "Extraindo texto do PDF…");
}

function sourceList(items, route, empty) {
  if (!items.length) return `<p class="muted">${empty}</p>`;
  return `<ul class="records source-records">${items.map(item => {
    const url = `/${route}?fonte=${escapeHtml(item.id)}`;
    const typeIcon = item.kind === "video" ? "video" : item.kind === "comentario" ? "chat" : "file";
    return `<li>
      <span class="source-icon">${icon(typeIcon)}</span>
      <div class="source-description">
        <a class="source-title" href="${url}"><strong>${escapeHtml(item.dish || item.title)}</strong></a>
        <small class="muted">${escapeHtml(item.title)} · ${formatDate(item.created_at)}</small>
      </div>
      <span class="badge ${escapeHtml(item.status || "novo")}">${labels[item.status] ?? "Aguardando análise"}</span>
      <a class="text-link" href="${url}">Ver detalhes ${icon("arrow")}</a>
    </li>`;
  }).join("")}</ul>`;
}

async function renderStages() {
  const items = await api("/api/sources");
  main.innerHTML = `<header class="page-heading"><p class="eyebrow">Mapeamento temporal</p>
    <h1>Etapas Geradas</h1><p class="muted">Abra uma gravação para analisar ou conferir as etapas do preparo.</p></header>
    <section class="card">${sourceList(items.filter(item => item.kind === "video"),
      "etapas", "Nenhum vídeo disponível para análise.")}</section>`;
}

async function renderQueue() {
  if (!reviewer()) {
    main.innerHTML = "<h1>Validações</h1><p>Esta tela é reservada aos chefs e administradores.</p>";
    return;
  }
  const items = await api("/api/sources");
  main.innerHTML = `<header class="page-heading"><p class="eyebrow">Validação do chef</p>
    <h1>Revise o conhecimento antes de preservá-lo.</h1>
    <p class="muted">Confira os registros da equipe antes de publicar no acervo.</p></header>
    <section class="card"><h2>Aguardando revisão</h2>
    ${sourceList(items.filter(item => item.status === "pendente"), "revisao", "Nenhuma fonte pendente.")}</section>
    <section class="card"><h2>Vídeos aguardando análise</h2>
    ${sourceList(items.filter(item => !item.status), "etapas", "Nenhum vídeo aguardando análise.")}</section>
    <section class="card"><h2>Histórico de decisões</h2>
    ${sourceList(items.filter(item => ["rejeitado", "aprovado"].includes(item.status)), "revisao", "Nenhuma decisão registrada.")}</section>`;
}

const stageFields = {
  title: "Nome da etapa", action: "Ação observada", visual: "Características visuais",
  landmark: "Ponto de referência", time: "Tempo e origem", temperature: "Temperatura e origem",
  errors: "Erros e correções demonstrados",
};

function field(label, value, name, editable, singleLine = false) {
  const safe = escapeHtml(value);
  if (!editable) return `<p><strong>${label}</strong><br><span class="prewrap">${safe || "—"}</span></p>`;
  const control = singleLine
    ? `<input name="${name}" value="${safe}" required maxlength="1800">`
    : `<textarea name="${name}" maxlength="1800" required>${safe}</textarea>`;
  return `<label>${label}${control}</label>`;
}

function listField(label, values, name, editable, limit) {
  if (!editable) return field(label, values.join("\n"), name, false);
  return `<label>${label} <span class="muted">(uma por linha)</span>
    <textarea name="${name}" maxlength="${limit * 300}">${escapeHtml(values.join("\n"))}</textarea></label>`;
}

function stageCard(stage, index, media, editable) {
  const commentFields = stage.comments.map((comment, number) => {
    const time = comment.timestamp === null ? "sem timestamp confirmado" : formatTime(comment.timestamp);
    return field(`Declaração do chef · ${escapeHtml(comment.origin)} · ${time}`, comment.text, `stage_${index}_comment_${number}`, editable);
  }).join("");
  return `<details class="stage-card" ${editable && index === 0 ? "open" : ""}><summary>
      <span class="stage-number">${String(index + 1).padStart(2, "0")}</span>
      <strong>${escapeHtml(stage.title)}</strong><small>${formatTime(stage.start)}–${formatTime(stage.end)}</small></summary>
    <p><a data-seek="${stage.start},${stage.end}" href="${media}#t=${stage.start},${stage.end}">Reproduzir este trecho</a></p>
    ${editable ? `<div class="columns">
      <label>Início em segundos <input name="stage_${index}_start" type="number" min="0" step="any" value="${stage.start}" required></label>
      <label>Fim em segundos <input name="stage_${index}_end" type="number" min="0" step="any" value="${stage.end}" required></label>
    </div>` : ""}
    ${Object.entries(stageFields).filter(([key]) => editable || key !== "title")
      .map(([key, label]) => field(label, stage[key], `stage_${index}_${key}`, editable, key === "title")).join("")}
    ${commentFields}
    ${listField("Inferido pela IA · reservado à revisão", stage.inferences, `stage_${index}_inferences`, editable, 12)}
    ${listField("Informações não identificadas", stage.unknowns, `stage_${index}_unknowns`, editable, 12)}
  </details>`;
}

function renderRevision(source, data, media, editable) {
  if (source.kind === "documento") {
    const pages = [...new Set(data.chunks.map(chunk => chunk.page))];
    return `<p><a href="${media}" target="_blank" rel="noopener">Abrir PDF original</a> · ${pages.length} páginas indexáveis</p>
      <details><summary>Conferir texto extraído</summary>
      ${data.chunks.map(chunk => `<p class="prewrap"><strong>Página ${chunk.page}</strong><br>${escapeHtml(chunk.body)}</p>`).join("")}</details>`;
  }
  if (source.kind === "comentario") {
    return `<p class="muted">${escapeHtml(data.step || "Observação geral do vídeo")}</p>${field("Observação", data.text, "comment", editable)}`;
  }
  return `<h3 class="sr-only">Etapas e evidências</h3>
    ${data.stages.map((stage, index) => stageCard(stage, index, media, editable)).join("")}
    <details ${editable ? "open" : ""}><summary>Resumo, ingredientes e utensílios</summary>
    ${field("Resumo", data.summary, "summary", editable)}
    ${listField("Ingredientes identificados", data.ingredients, "ingredients", editable, 60)}
    ${listField("Utensílios identificados", data.utensils, "utensils", editable, 60)}
    ${listField("Dúvidas da análise", data.unknowns, "unknowns", editable, 25)}
    </details>
    <details><summary>Cortes sugeridos para treinamento</summary><ul>${data.cuts.map(cut => `<li>
      <a data-seek="${cut.start},${cut.end}" href="${media}#t=${cut.start},${cut.end}">${formatTime(cut.start)} a ${formatTime(cut.end)}</a>
      · ${escapeHtml(cut.reason)}</li>`).join("")}</ul></details>`;
}

function collectAnalysis(data, fields) {
  const lines = key => fields.get(key).split("\n").map(s => s.trim()).filter(Boolean);
  return {...data, summary: fields.get("summary"), ingredients: lines("ingredients"), utensils: lines("utensils"),
    unknowns: lines("unknowns"), stages: data.stages.map((stage, index) => {
      const prefix = `stage_${index}_`;
      const text = Object.fromEntries(Object.keys(stageFields).map(key => [key, fields.get(prefix + key)]));
      return {...stage, ...text, start: Number(fields.get(prefix + "start")), end: Number(fields.get(prefix + "end")),
        inferences: lines(prefix + "inferences"), unknowns: lines(prefix + "unknowns"),
        comments: stage.comments.map((comment, number) => ({...comment, text: fields.get(prefix + `comment_${number}`)}))};
    })};
}

async function renderSource(id) {
  const detail = await api(`/api/sources/${encodeURIComponent(id)}`);
  const {source, draft, active, history, media, parent} = detail;
  const revision = screen === "biblioteca" ? active ?? draft : draft;
  const editable = reviewer() && screen !== "biblioteca" && revision?.status === "pendente";
  const video = source.kind === "video";
  const heading = video && screen === "etapas" && revision ? "Seu preparo foi organizado." : source.dish || source.title;
  const metadata = [...new Set([source.dish, source.title, source.details.cook, labels[revision?.status]])]
    .filter(item => item && item !== heading);
  main.innerHTML = `<header class="page-heading"><p class="eyebrow">${labels[source.kind]} · ${labels[source.scope]}</p>
    <h1>${escapeHtml(heading)}</h1>
    <p class="muted">${escapeHtml(metadata.join(" · "))}</p></header>
    ${source.scope === "demo" ? "<p>Receita de demonstração aprovada para testes técnicos.</p>" : ""}
    ${parent ? `<p><a href="/biblioteca?fonte=${parent.id}">${escapeHtml(parent.title)}</a> · versão ${parent.version}</p>` : ""}
    <div class="${video ? "detail-grid" : ""}">
    ${video ? `<section class="card video-panel"><h2 class="panel-heading">${icon("video")} Gravação do preparo</h2>
      <video id="player" controls preload="metadata" src="${media}"></video>
      ${revision?.data.stages.length ? `<h3 class="section-label">Mapeamento temporal</h3><ol class="timeline">${revision.data.stages.map((stage, index) => `
        <li><a data-seek="${stage.start},${stage.end}" href="${media}#t=${stage.start},${stage.end}" aria-label="Reproduzir etapa ${index + 1}: ${escapeHtml(stage.title)}">
          <strong>${String(index + 1).padStart(2, "0")}</strong><small>${formatTime(stage.start)}</small></a></li>`).join("")}</ol>` : ""}
      ${source.details.observations ? field("Observações enviadas", source.details.observations, "", false) : ""}
      ${source.details.subtitles ? `<details><summary>Legendas enviadas</summary><p class="prewrap">${escapeHtml(source.details.subtitles)}</p></details>` : ""}
      ${detail.can_analyze && screen !== "biblioteca" ? `<form id="analyze"><fieldset>
        <button>${draft ? "Solicitar nova análise" : "Analisar vídeo com Gemini"}</button>
      </fieldset><p role="status"></p></form>` : ""}</section>` : ""}
    ${revision ? `<section class="card revision-panel"><h2 class="panel-heading">${icon("list")} ${video ? "Etapas sugeridas pela IA" : "Conteúdo da fonte"}</h2>
      <p class="muted">Versão ${revision.version} · ${labels[revision.status]}</p>
      ${active && draft?.id !== active.id && screen !== "biblioteca" ? `<p>Versão ${active.version} disponível para consulta até uma nova aprovação.</p>` : ""}
      <form id="review"><fieldset>
        ${renderRevision(source, revision.data, media, editable)}
        ${editable ? `<label>Nota da revisão <textarea name="note" maxlength="1800"></textarea></label>
        <div class="actions">
          <button name="decision" value="aprovar">Aprovar e publicar</button>
          <button class="secondary" name="decision" value="salvar">Salvar rascunho</button>
          <button class="secondary" name="decision" value="rejeitar" formnovalidate>Rejeitar</button>
        </div>` : ""}
      </fieldset><p role="status"></p></form></section>` : '<section class="card"><h2>Etapas do preparo</h2><p class="muted">O vídeo está pronto para ser analisado.</p></section>'}
    </div>
    ${active && video ? `<section class="card"><h2>Enviar observação</h2><p>A observação será enviada ao chef para validação.</p>
      <form id="comment"><fieldset><label>Etapa <select name="stage">
        ${options(active.data.stages.map((stage, index) => ({name: stage.title, id: index})), "Sobre o vídeo inteiro")}
      </select></label>
      <label>Observação <textarea name="text" maxlength="1800" required></textarea></label>
      <button>Enviar observação</button></fieldset><p role="status"></p></form></section>` : ""}
    ${history.length ? `<section class="card"><h2>Histórico de versões</h2><ul class="records">${history.map(entry => `
      <li><button class="secondary" data-version="${entry.version}">Versão ${entry.version}</button>
        <span class="muted">${labels[entry.status]} · ${escapeHtml(entry.actor)} · ${formatDate(entry.created_at)}</span>
        ${entry.note ? `<p>${escapeHtml(entry.note)}</p>` : ""}</li>`).join("")}</ul>
      <div id="history-detail" aria-live="polite"></div></section>` : ""}`;
  bindForm("analyze", async () => {
    await post("/api/analyze", {id, version: draft?.version ?? 0});
    await renderSource(id);
  }, "O Gemini está processando imagem e áudio. Esta etapa pode levar alguns minutos…");
  if (editable) bindForm("review", async fields => {
    const payload = {version: revision.version, decision: fields.get("decision")};
    if (fields.get("note").trim()) payload.note = fields.get("note");
    if (payload.decision !== "rejeitar") {
      if (video) payload.analysis = collectAnalysis(revision.data, fields);
      if (source.kind === "comentario") payload.comment = fields.get("comment");
    }
    await post(`/api/sources/${id}/review`, payload);
    await renderSource(id);
  }, "Registrando decisão…");
  bindForm("comment", async (fields, report) => {
    await post(`/api/sources/${id}/comments`, {
      version: active.version, text: fields.get("text"), stage: fields.get("stage") === "" ? null : Number(fields.get("stage")),
    });
    document.getElementById("comment").reset();
    status(report, "Observação enviada para revisão.");
  });
  main.onclick = async event => {
    const seek = event.target.closest("[data-seek]");
    const version = event.target.closest("[data-version]");
    if (seek) {
      event.preventDefault();
      const player = document.getElementById("player");
      player.src = `${media}#t=${seek.dataset.seek}`;
      player.scrollIntoView({block: "center"});
      player.play().catch(() => {});
    }
    if (version) {
      const container = document.getElementById("history-detail");
      try {
        const old = await api(`/api/sources/${id}/versions/${version.dataset.version}`);
        container.innerHTML = `<h3>Versão ${old.version}</h3>${renderRevision(source, old.data, media, false)}`;
      } catch (error) {
        status(container, error.message, true);
      }
    }
  };
}

function renderReferences(sources) {
  if (!sources.length) return "";
  return `<ul>${sources.map(source => {
    const location = source.page ? ` · pág. ${source.page}` : source.start === null ? "" : ` · ${formatTime(source.start)}`;
    const title = escapeHtml(source.title + location);
    const link = source.url ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">${title}</a>` : title;
    return `<li class="ref">${link} · v${source.version}${source.historical ? " · versão substituída" : ""}${source.quote ? `<q>${escapeHtml(source.quote)}</q>` : ""}</li>`;
  }).join("")}</ul>`;
}

async function renderChat() {
  main.innerHTML = `<header class="page-heading"><p class="eyebrow">Ficha técnica · Consulta em bancada</p>
      <h1>Chat MaraChef</h1><p class="muted">Consulte etapas, tempos e referências aprovadas.</p></header>
    <form id="chat"><fieldset class="chat-layout">
      <section class="card">
        <h2 class="panel-heading">${icon("book")} Fonte de consulta</h2>
          <label>Base <select name="scope" id="scope">
            ${Object.entries(labels).filter(([key]) => ["oficial", "demo", "institucional"].includes(key))
              .map(([key, label]) => `<option value="${key}">${label}</option>`).join("")}
          </select></label>
          <label id="dish-label">Prato <select name="dish_id" id="dish"></select></label>
        <a href="/biblioteca">Abrir biblioteca ${icon("arrow")}</a>
      </section>
      <section class="card chat-panel">
        <h2 class="panel-heading">${icon("chat")} Assistente MaraChef</h2>
        <div id="transcript" role="log" aria-label="Conversa"></div>
        <label>Sua pergunta <textarea name="question" maxlength="1800" required placeholder="Como sei que chegou ao ponto?"></textarea></label>
        <button>Perguntar ${icon("arrow")}</button>
        <p role="status"></p>
      </section>
    </fieldset></form>`;
  const scope = document.getElementById("scope");
  const dish = document.getElementById("dish");
  const form = document.getElementById("chat");
  async function updateDishes() {
    const current = scope.value;
    document.getElementById("dish-label").hidden = current === "institucional";
    dish.innerHTML = options([], "Informe o prato na pergunta");
    if (current === "institucional") return;
    try {
      const items = await api(`/api/dishes?scope=${current}`);
      if (scope.value === current) dish.innerHTML = options(items, "Informe o prato na pergunta");
    } catch (error) {
      status(form.querySelector("[role=status]"), error.message, true);
    }
  }
  scope.onchange = updateDishes;
  await updateDishes();
  bindForm("chat", async (fields, report) => {
    const response = await post("/api/chat", {
      question: fields.get("question"), scope: fields.get("scope"), dish_id: fields.get("dish_id") || null,
    });
    if (response.scope === scope.value && response.dish_id) dish.value = response.dish_id;
    const transcript = document.getElementById("transcript");
    transcript.insertAdjacentHTML("afterbegin", `<article class="chat-entry">
      <h2>${escapeHtml(fields.get("question"))}</h2><p class="muted">${escapeHtml(response.scope_label)}</p>
      <p class="prewrap">${escapeHtml(response.answer)}</p>${renderReferences(response.sources)}</article>`);
    form.elements.question.value = "";
    status(report, "");
  }, "Consultando a base…");
}

async function init() {
  try {
    user = await api("/api/me");
    document.body.classList.add("signed-in");
    document.body.dataset.screen = screen;
    document.getElementById("sidebar").hidden = false;
    const panelTitle = document.getElementById("panel-title");
    panelTitle.textContent = ["biblioteca", "receita", "consulta"].includes(screen)
      ? "Consulta de bancada" : reviewer() ? "Painel do chef" : "Painel da equipe";
    panelTitle.hidden = false;
    document.getElementById("nav").hidden = false;
    document.getElementById("account").hidden = false;
    document.querySelector("[data-review]").hidden = !reviewer();
    const activeScreen = screen === "receita" ? "biblioteca" : screen;
    document.querySelector(`nav a[href="/${activeScreen}"]`)?.setAttribute("aria-current", "page");
    document.getElementById("account-name").textContent = user.name;
    document.getElementById("account-role").textContent = labels[user.role];
    document.getElementById("logout").onclick = async () => {
      await post("/api/logout", {});
      location.assign("/inicio");
    };
    if (selectedSource && ["etapas", "biblioteca", "revisao"].includes(screen)) {
      await renderSource(selectedSource);
    } else {
      const render = {
        inicio: renderHome, registro: renderRegister, etapas: renderStages,
        revisao: renderQueue, biblioteca: renderLibrary, consulta: renderChat, receita: renderRecipe,
      };
      await render[screen]();
    }
  } catch (error) {
    if (error.status === 401) renderLogin();
    else main.innerHTML = `<h1>MaraChef</h1><p class="error">${escapeHtml(error.message)}</p>`;
  } finally {
    main.setAttribute("aria-busy", "false");
  }
}

init();
