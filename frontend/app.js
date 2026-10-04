const isLocal = ["localhost", "127.0.0.1"].includes(location.hostname);
const API_BASE = window.INQUIREX_API_BASE || (isLocal && location.port !== "8000" ? "http://127.0.0.1:8000" : "");

const $ = (id) => document.getElementById(id);
const els = {
  fileInput: $("fileInput"), dropzone: $("dropzone"), uploadStatus: $("uploadStatus"),
  docList: $("docList"), messages: $("messages"), empty: $("empty"),
  form: $("askForm"), question: $("question"), btn: $("askBtn"),
};
let docs = [];
let activeView = "chat";
let lastQuestion = "";
let toastTimer;
let latestEvidence = { sources: [], conflicts: [] };
const HISTORY_KEY = "inquirex.investigations.v1";
const MIGRATION_KEY = "inquirex.legacy-history-migrated.v1";
let investigations = [];
let legacyInvestigations = [];
let legacyMigrationAvailable = localStorage.getItem(MIGRATION_KEY) !== "1";
let currentInvestigationId = "";
let accountUsername = "";
let accountSaveTimer;

function activeInvestigation() { return investigations.find((item) => item.id === currentInvestigationId); }
function persistInvestigations() {
  investigations.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  renderInvestigationHistory();
  if (!accountUsername) return;
  const username = accountUsername;
  const snapshot = JSON.stringify(investigations);
  try { localStorage.setItem(`inquirex.history.${username.toLowerCase()}`, snapshot); }
  catch { showToast("This browser is low on storage. Server history will still be saved."); }
  clearTimeout(accountSaveTimer);
  accountSaveTimer = setTimeout(() => {
    api(`/api/accounts/${encodeURIComponent(username)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ investigations: JSON.parse(snapshot) }),
    }).catch(() => setStatus("Could not sync account history. Check the backend connection.", true));
  }, 350);
}
async function flushAccountHistory() {
  if (!accountUsername) return;
  clearTimeout(accountSaveTimer);
  try {
    await api(`/api/accounts/${encodeURIComponent(accountUsername)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ investigations }),
    });
  } catch { showToast("Could not sync the latest account history. Check the backend connection."); }
}
function createInvestigation() {
  const item = { id: crypto.randomUUID(), title: "New investigation", createdAt: Date.now(), updatedAt: Date.now(), documentIds: [], turns: [] };
  investigations.unshift(item);
  currentInvestigationId = item.id;
  persistInvestigations();
  restoreInvestigation(item.id);
}
function renderInvestigationHistory() {
  const nav = $("investigationHistory");
  if (!nav) return;
  $("investigationCount").textContent = investigations.length;
  nav.innerHTML = investigations.map((item) => `<div class="history-row"><button type="button" class="history-item ${item.id === currentInvestigationId ? "active" : ""}" data-investigation="${esc(item.id)}" title="${esc(item.title)}"><span class="history-item-icon">◉</span><span>${esc(item.title)}</span></button><button type="button" class="history-delete" data-delete-investigation="${esc(item.id)}" aria-label="Delete ${esc(item.title)}" title="Delete investigation">×</button></div>`).join("") || `<p class="history-empty">Your investigations will appear here.</p>`;
}
function deleteInvestigation(id) {
  const target = investigations.find((item) => item.id === id);
  if (!target || !confirm(`Delete “${target.title}” and its saved conversation?`)) return;
  investigations = investigations.filter((item) => item.id !== id);
  if (!investigations.length) {
    investigations = [{ id: crypto.randomUUID(), title: "New investigation", createdAt: Date.now(), updatedAt: Date.now(), documentIds: [], turns: [] }];
  }
  if (currentInvestigationId === id) {
    currentInvestigationId = investigations[0].id;
    restoreInvestigation(currentInvestigationId);
  } else persistInvestigations();
}
function restoreInvestigation(id) {
  const item = investigations.find((entry) => entry.id === id);
  if (!item) return;
  currentInvestigationId = id;
  item.updatedAt = Date.now();
  persistInvestigations();
  $("workspaceTitle").textContent = item.title;
  const crumb = document.querySelector(".crumb strong");
  if (crumb) crumb.textContent = item.title;
  const welcome = $("welcome");
  [...els.messages.children].forEach((node) => { if (node !== welcome) node.remove(); });
  welcome.hidden = item.turns.length > 0;
  els.question.value = "";
  lastQuestion = item.turns.at(-1)?.question || "";
  latestEvidence = { sources: [], conflicts: [] };
  for (const turn of item.turns) {
    addMessage(`<p class="q">${esc(turn.question)}</p>`);
    if (turn.result) {
      addMessage(`<div class="assistant-reply"><span class="assistant-mark"><img src="logo-mark.svg" alt=""></span>${answerHTML(turn.result)}</div>`);
      latestEvidence = turn.result;
    } else if (turn.error) {
      addMessage(`<div class="assistant-reply"><span class="assistant-mark"><img src="logo-mark.svg" alt=""></span><div class="error-msg"><b>I couldn’t finish that just now.</b><p>${esc(turn.error)}</p></div></div>`);
    }
  }
  $("evidenceCount").textContent = latestEvidence.sources?.length || 0;
  if (latestEvidence.sources || latestEvidence.conflicts) renderEvidence(latestEvidence);
  else renderEvidenceTab("passages");
  renderInvestigationHistory();
  loadDocs();
  setView("chat");
  els.messages.scrollTop = els.messages.scrollHeight;
}

try { legacyInvestigations = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); } catch { legacyInvestigations = []; }
if (!Array.isArray(legacyInvestigations)) legacyInvestigations = [];

const esc = (s = "") =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options = {}) {
  let res;
  try {
    res = await fetch(API_BASE + path, options);
  } catch {
    throw new Error("Can't reach the server. Check that the backend is running and API_BASE is correct.");
  }
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail; } catch {}
    throw new Error(detail || `Request failed (${res.status}). Please try again.`);
  }
  return res.json();
}

async function loadDocs() {
  try {
    const allDocs = await api("/api/documents");
    const current = activeInvestigation();
    if (current && !current._initialized) {
      current._initialized = true;
      persistInvestigations();
    }
    const currentIds = current?.documentIds || [];
    docs = allDocs.filter((doc) => currentIds.includes(doc.id));
    renderDocs();
    const count = $("docCount");
    if (count) count.textContent = docs.length;
    const totalPages = docs.reduce((n, d) => n + (d.pages || 0), 0);
    setStatus(docs.length ? `${docs.length} document${docs.length === 1 ? "" : "s"} ready · ${totalPages} page${totalPages === 1 ? "" : "s"}` : "Add a document to start investigating.");
  } catch (e) { setStatus(e.message, true); }
}

function renderDocs() {
  const checked = new Set(selectedIds());
  els.docList.innerHTML = docs.length
    ? docs.map((d) => `
      <li class="doc-row">
        <label title="Include ${esc(d.name)} in your investigation">
          <input type="checkbox" value="${esc(d.id)}" ${checked.size === 0 || checked.has(d.id) ? "checked" : ""}>
          <span class="file-badge">${esc((d.name.split(".").pop() || "DOC").slice(0,3).toUpperCase())}</span><span class="doc-name">${esc(d.name)}<small>${d.pages ?? "?"} pages · ready</small></span>
        </label>
        <button class="doc-del" data-id="${esc(d.id)}" aria-label="Remove ${esc(d.name)}" title="Remove document">×</button>
      </li>`).join("")
    : `<li class="doc-empty">Your library is ready for its first document.</li>`;
  renderDocumentCards(checked);
}

function renderDocumentCards(checked = new Set()) {
  const target = $("documentCards");
  if (!target) return;
  const upload = `<button class="upload-card" id="workspaceUploadBtn" type="button"><span class="upload-card-icon">⇧</span><strong>Drop files or upload</strong><small>PDF, TXT, Markdown, images</small></button>`;
  target.innerHTML = upload + (docs.length ? docs.map((d) => `
    <button class="document-card ${checked.size === 0 || checked.has(d.id) ? "selected" : ""}" type="button" data-doc-card="${esc(d.id)}" aria-pressed="${checked.size === 0 || checked.has(d.id)}">
      <span class="document-card-icon">${esc((d.name.split(".").pop() || "DOC").slice(0,3).toUpperCase())}</span>
      <strong title="${esc(d.name)}">${esc(d.name)}</strong><small>${d.pages ?? "?"} pages</small><span class="indexed-label"><i></i> Indexed</span>
    </button>`).join("") : `<div class="document-card-empty">Your indexed documents will appear here.</div>`);
  $("workspaceDocCount").textContent = `${docs.length} document${docs.length === 1 ? "" : "s"}`;
  const pageTotal = docs.reduce((sum, d) => sum + (d.pages || 0), 0);
  $("workspacePageCount").textContent = `${pageTotal} page${pageTotal === 1 ? "" : "s"}`;
  $("workspaceIndexLabel").textContent = docs.length ? "Indexed ✓" : "Ready to index";
  $("workspaceIndexLabel").classList.toggle("indexed", docs.length > 0);
  $("docCount").textContent = docs.length;
}

function renderEvidence(result) {
  const conflictSources = (result.conflicts || []).flatMap((c) => c.sources || []);
  const all = [...(result.sources || []), ...conflictSources];
  const seen = new Set();
  latestEvidence = {
    sources: all.filter((s) => { const k = `${s.doc_name}|${s.page}|${s.snippet}`; if (seen.has(k)) return false; seen.add(k); return true; }),
    conflicts: result.conflicts || [],
  };
  $("evidenceCount").textContent = latestEvidence.sources.length;
  renderEvidenceTab($("evidenceContent").dataset.view || "passages");
}

function renderEvidenceTab(view = "passages") {
  const content = $("evidenceContent");
  content.dataset.view = view;
  document.querySelectorAll(".evidence-tab").forEach((b) => b.classList.toggle("active", b.dataset.evidenceView === view));
  if (view === "claims") {
    content.innerHTML = latestEvidence.conflicts.length ? latestEvidence.conflicts.map((c) => `
      <section class="claim-group"><h3>${esc(c.summary)}</h3><span class="claim-relation">Contradictory evidence</span>
      ${(c.sources || []).map((s) => `<article class="claim-source"><strong>${esc(s.doc_name)} · p.${esc(s.page || "?")}</strong><p>${esc(s.snippet)}</p></article>`).join("")}</section>`).join("") : `<div class="evidence-placeholder"><span>◇</span><strong>No conflict was flagged</strong><p>When the answer service identifies conflicting passages, the competing sources will be shown here.</p></div>`;
    return;
  }
  content.innerHTML = latestEvidence.sources.length ? `<div class="evidence-list-heading"><strong>Passages supporting this answer</strong><span>${latestEvidence.sources.length}</span></div>` + latestEvidence.sources.map((s) => `
    <article class="evidence-card"><div class="evidence-card-meta"><span class="evidence-file-icon">▤</span><strong title="${esc(s.doc_name)}">${esc(s.doc_name)}</strong><span>p.${esc(s.page || "?")}</span></div><p>${highlight(s.snippet, s.highlight)}</p><span class="evidence-tag">Cited source</span></article>`).join("") : `<div class="evidence-placeholder"><span>◈</span><strong>Evidence will appear here</strong><p>Ask a question to see the passages that support the answer and any detected conflicts.</p></div>`;
}

const selectedIds = () =>
  [...els.docList.querySelectorAll("input:checked")].map((i) => i.value);

function setStatus(msg, isError = false) {
  els.uploadStatus.textContent = msg;
  els.uploadStatus.classList.toggle("error", isError);
}

async function uploadFiles(files) {
  if (!files.length) return;
  const targetInvestigationId = currentInvestigationId;
  const body = new FormData();
  [...files].forEach((f) => body.append("files", f));
  setStatus(`Indexing ${files.length} file${files.length > 1 ? "s" : ""}… Scanned pages are read locally with OCR.`);
  try {
    const added = await api("/api/documents", { method: "POST", body });
    const current = investigations.find((item) => item.id === targetInvestigationId);
    if (current) {
      current.documentIds = [...new Set([...current.documentIds, ...added.map((doc) => doc.id)])];
      current._initialized = true;
      current.updatedAt = Date.now();
      persistInvestigations();
    }
    await loadDocs();
    showToast(`${files.length} document${files.length === 1 ? " is" : "s are"} ready to explore.`);
  } catch (e) { setStatus(e.message, true); }
  els.fileInput.value = "";
}

els.fileInput.addEventListener("change", (e) => uploadFiles(e.target.files));
["dragenter", "dragover"].forEach((t) =>
  els.dropzone.addEventListener(t, (e) => { e.preventDefault(); els.dropzone.classList.add("over"); }));
["dragleave", "drop"].forEach((t) =>
  els.dropzone.addEventListener(t, (e) => { e.preventDefault(); els.dropzone.classList.remove("over"); }));
els.dropzone.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));

els.docList.addEventListener("click", async (e) => {
  const id = e.target.dataset?.id;
  if (!id) return;
  const current = activeInvestigation();
  if (current) { current.documentIds = current.documentIds.filter((docId) => docId !== id); persistInvestigations(); }
  showToast("Removed from this investigation. Other accounts keep their own access.");
  await loadDocs();
});
els.docList.addEventListener("change", (e) => {
  if (!e.target.matches('input[type="checkbox"]')) return;
  if (!selectedIds().length && docs.length) {
    e.target.checked = true;
    showToast("Keep at least one document selected for this investigation.");
  }
  renderDocumentCards(new Set(selectedIds()));
});

function highlight(snippet, phrase) {
  const safe = esc(snippet);
  if (!phrase) return safe;
  const p = esc(phrase);
  return safe.includes(p) ? safe.replace(p, `<mark>${p}</mark>`) : safe;
}

function sourceHTML(s) {
  const where = s.page ? `page ${esc(s.page)}` : esc(s.section || "");
  return `
    <details class="source">
      <summary>${esc(s.doc_name)} <span>${where}</span></summary>
      <blockquote class="passage">${highlight(s.snippet, s.highlight)}</blockquote>
    </details>`;
}

function answerTextHTML(answer = "") {
  const blocks = [];
  let bullets = [];
  const flushBullets = () => {
    if (!bullets.length) return;
    blocks.push(`<ul class="answer-bullets">${bullets.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`);
    bullets = [];
  };
  for (const line of String(answer).split(/\r?\n/)) {
    const text = line.trim();
    const bullet = text.match(/^(?:[-*•])\s+(.+)$/);
    if (bullet) bullets.push(bullet[1]);
    else {
      flushBullets();
      if (text) blocks.push(`<p>${esc(text)}</p>`);
    }
  }
  flushBullets();
  return blocks.join("");
}

function conflictsHTML(list = []) {
  if (!list.length) return "";
  return `
    <section class="conflicts">
      <h3>These documents disagree</h3>
      ${list.map((c) => `
        <div class="conflict">
          <p>${esc(c.summary)}</p>
          ${(c.sources || []).map(sourceHTML).join("")}
        </div>`).join("")}
    </section>`;
}

function answerHTML(r) {
  const level = r.confidence || "low";
  const thin = r.insufficient_evidence;
  let fallbackCopy = "The answer service is temporarily unavailable. Your cited passages are still available below.";
  const quotaExhausted = /quota.*exhaust|exceed.*quota|plan, billing|billing status/i.test(r.fallback_reason || "");
  if (quotaExhausted) {
    const provider = (r.fallback_reason || "").startsWith("Gemini ") ? "Gemini" : "Your AI provider";
    fallbackCopy = `${provider} says this project has used its available quota. Check usage and model limits in <a href="https://aistudio.google.com/" target="_blank" rel="noopener noreferrer">Google AI Studio</a>. If you reached a daily limit, wait for it to reset; otherwise review the project plan, billing, or model quota. Retrying now will not restore exhausted quota.`;
  }
  else if (/api key|no api key/i.test(r.fallback_reason || "")) fallbackCopy = "Written answers aren’t connected yet, but you can still search and inspect the source passages.";
  else if (/unavailable|503|502|504|temporar|429|rate.limit/i.test(r.fallback_reason || "")) fallbackCopy = "The AI service is having a busy moment. Your source passage is ready; try again in a little while.";
  else if (/model .* unavailable/i.test(r.fallback_reason || "")) fallbackCopy = "The configured AI model needs an update. Search and citations are still working.";
  const excerptFallback = /short excerpts from the closest matching pages/i.test(r.answer || "");
  const fallback = r.answer_mode === "source_only" ? `<div class="model-fallback-notice"><span class="fallback-icon">i</span><span><b>${excerptFallback ? "The answer model is unavailable, so I gathered source excerpts instead." : "I found a useful passage, but couldn’t write a reliable answer just now."}</b><small>${excerptFallback ? "These citations are the original document text, not a synthesized summary." : fallbackCopy}</small></span><details class="fallback-details"><summary>Why did this happen?</summary><small>${esc(r.fallback_reason || "No additional details.")}</small></details></div>` : "";
  const conflictLabel = r.conflicts?.length ? `<p class="conflict-intro">I found details that don’t line up across your documents. Here’s the best-supported answer, with both sides below.</p>` : "";
  const conflictUnavailable = r.conflict_check_available === false ? `<p class="conflict-intro">I couldn’t cross-check the documents this time, so I can’t confirm whether they disagree. You can still open and compare the cited passages.</p>` : "";
  return `
    <article class="answer ${thin ? "thin" : ""}">
      ${fallback}${conflictLabel}
      ${conflictUnavailable}
      <div class="answer-text">${answerTextHTML(r.answer)}</div>
      <p class="confidence">Confidence: <b class="${esc(level)}">${esc(level)}</b>${
        r.confidence_reason ? ` — ${esc(r.confidence_reason)}` : ""}</p>
      ${conflictsHTML(r.conflicts)}
      ${r.sources?.length ? `<section class="sources"><h3>Sources</h3>${r.sources.map(sourceHTML).join("")}</section>` : ""}
      <div class="answer-actions"><button data-action="copy">Copy answer</button><button data-action="retry">Ask again</button></div>
    </article>`;
}

function addMessage(html) {
  els.empty?.remove();
  $("welcome").hidden = true;
  const wrap = document.createElement("div");
  wrap.innerHTML = html;
  els.messages.appendChild(wrap);
  els.messages.scrollTop = els.messages.scrollHeight;
  return wrap;
}

function showToast(message) {
  const node = $("toast"); if (!node) return;
  node.textContent = message; node.classList.add("show");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => node.classList.remove("show"), 2400);
}

function setView(view) {
  activeView = view;
  $("chatView").hidden = view !== "chat";
  $("searchView").hidden = view !== "search";
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  if (view === "search") $("searchQuery").focus(); else els.question.focus();
}

function setProfile(name) {
  const clean = (name || "Investigator").trim().slice(0, 32) || "Investigator";
  $("userLabel").textContent = clean;
  $("userAvatar").textContent = clean.charAt(0).toUpperCase();
}

async function startWorkspace(account) {
  accountUsername = account.username;
  setProfile(accountUsername);
  const legacy = account.created && legacyMigrationAvailable
    ? legacyInvestigations.filter((item) => item.turns?.length || item.documentIds?.length)
    : [];
  investigations = (account.created ? legacy : (Array.isArray(account.investigations) ? account.investigations : [])).filter((item) => item && typeof item === "object");
  legacyInvestigations = [];
  legacyMigrationAvailable = false;
  try { localStorage.setItem(MIGRATION_KEY, "1"); } catch {}
  localStorage.removeItem(HISTORY_KEY);
  if (!investigations.length) {
    investigations = [{ id: crypto.randomUUID(), title: "New investigation", createdAt: Date.now(), updatedAt: Date.now(), documentIds: [], turns: [] }];
  }
  investigations.forEach((item) => {
    if (!Array.isArray(item.documentIds)) item.documentIds = [];
    if (!Array.isArray(item.turns)) item.turns = [];
  });
  currentInvestigationId = investigations.slice().sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))[0].id;
  localStorage.removeItem("inquirex.name");
  $("loginScreen").hidden = true;
  $("appShell").hidden = false;
  renderInvestigationHistory();
  restoreInvestigation(currentInvestigationId);
  if (account.created) persistInvestigations();
  api("/api/health").then((h) => {
    const status = $("indexStatus");
    status.textContent = h.llm_configured ? `AI configured · ${h.model}` : "Add an AI key to enable written answers";
    status.title = h.llm_configured ? `Configured provider: ${h.provider} / ${h.model}` : "Document search works, but generated answers need a provider key in backend/.env";
    status.title += h.ocr_available ? " Local OCR is ready for scanned PDFs." : " Local OCR needs the Tesseract engine for scanned PDFs; see backend/README.md.";
    status.parentElement.classList.toggle("offline", !h.llm_configured);
  }).catch(() => { $("indexStatus").textContent = "Backend unavailable"; });
}

$("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.currentTarget;
  const input = $("username");
  const username = input.value.trim();
  const status = $("accountStatus");
  const button = form.querySelector('button[type="submit"]');
  if (!form.reportValidity()) return;
  button.disabled = true;
  status.textContent = "Checking username…";
  status.classList.remove("error");
  try {
    const account = await api("/api/accounts/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username }) });
    status.textContent = account.created ? `Username available. Creating ${account.username}…` : `Welcome back, ${account.username}. Restoring your investigations…`;
    await startWorkspace(account);
    status.textContent = "";
  } catch (err) {
    status.textContent = err.message;
    status.classList.add("error");
  } finally { button.disabled = false; }
});
$("addFiles").addEventListener("click", () => els.fileInput.click());
$("documentCards").addEventListener("click", (e) => {
  if (e.target.closest("#workspaceUploadBtn")) { els.fileInput.click(); return; }
  const card = e.target.closest("[data-doc-card]");
  if (!card) return;
  const checkbox = [...els.docList.querySelectorAll("input[type=checkbox]")].find((i) => i.value === card.dataset.docCard);
  if (checkbox) {
    checkbox.checked = !checkbox.checked;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
  }
});
document.querySelectorAll(".evidence-tab").forEach((b) => b.addEventListener("click", () => renderEvidenceTab(b.dataset.evidenceView)));
$("newChat").addEventListener("click", createInvestigation);
$("investigationHistory").addEventListener("click", (e) => {
  const deleteButton = e.target.closest("[data-delete-investigation]");
  if (deleteButton) { deleteInvestigation(deleteButton.dataset.deleteInvestigation); return; }
  const button = e.target.closest("[data-investigation]");
  if (button) restoreInvestigation(button.dataset.investigation);
});
document.querySelectorAll(".nav-item").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
document.querySelectorAll("[data-prompt]").forEach((b) => b.addEventListener("click", () => { els.question.value = b.dataset.prompt; els.form.requestSubmit(); }));
$("profileButton").addEventListener("click", () => {
  const menu = $("profileMenu");
  menu.hidden = !menu.hidden;
  $("profileButton").setAttribute("aria-expanded", String(!menu.hidden));
});
async function signOut() {
  await flushAccountHistory();
  accountUsername = "";
  clearTimeout(accountSaveTimer);
  $("profileMenu").hidden = true;
  $("profileButton").setAttribute("aria-expanded", "false");
  $("appShell").hidden = true;
  $("loginScreen").hidden = false;
  $("username").value = "";
  $("accountStatus").textContent = "";
  $("username").focus();
}
$("changeName").addEventListener("click", signOut);
$("logoutButton").addEventListener("click", signOut);
$("helpButton").addEventListener("click", () => showToast("Choose documents, ask a question, then open a citation to check the exact passage."));
document.addEventListener("click", (e) => { if (!e.target.closest(".profile-button, .profile-menu")) $("profileMenu").hidden = true; });

els.messages.addEventListener("click", async (e) => {
  const action = e.target.dataset.action;
  const card = e.target.closest(".answer");
  if (!card) return;
  if (action === "copy") {
    try {
      const answer = card.querySelector(".answer-text");
      const text = answer ? [...answer.children].map((block) =>
        block.matches(".answer-bullets")
          ? [...block.querySelectorAll("li")].map((item) => `• ${item.innerText}`).join("\n")
          : block.innerText,
      ).join("\n\n") : "";
      await navigator.clipboard.writeText(text);
      showToast("Answer copied.");
    } catch {
      showToast("Could not copy answer to clipboard.");
    }
  }
  if (action === "retry" && lastQuestion) { els.question.value = lastQuestion; els.form.requestSubmit(); }
});

$("searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = $("searchQuery").value.trim(); if (!query) return;
  const area = $("searchResults"); area.innerHTML = `<div class="search-loading">Looking through your documents…</div>`;
  const ids = $("searchSelectedOnly").checked ? selectedIds() : (activeInvestigation()?.documentIds || []);
  if (!ids.length) { area.innerHTML = `<div class="search-empty"><strong>No documents in this investigation yet.</strong><p>Add a document to search its evidence.</p></div>`; return; }
  try {
    const result = await api("/api/search", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({query,document_ids:ids})});
    $("searchSummary").textContent = `${result.results.length} passage${result.results.length === 1 ? "" : "s"} found for “${query}”`;
    area.innerHTML = result.results.length ? result.results.map((p,i)=>`<article class="result-card"><div class="result-meta"><span class="result-index">${String(i+1).padStart(2,"0")}</span><strong>${esc(p.doc_name)}</strong><span>PAGE ${esc(p.page)}</span></div><p class="result-snippet">${esc(p.snippet)}</p><div class="result-footer"><button class="result-ask" data-ask="${esc(query)}">Ask about this ↗</button></div></article>`).join("") : `<div class="search-empty"><span>⌕</span><strong>No close matches yet.</strong><p>Try a shorter phrase or a different wording.</p></div>`;
  } catch (err) { area.innerHTML = `<div class="search-empty"><strong>Search didn’t finish.</strong><p>${esc(err.message)}</p></div>`; }
});
$("searchResults").addEventListener("click", (e) => { const q=e.target.dataset.ask; if(q){setView("chat");els.question.value=q;els.form.requestSubmit();} });

els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = els.question.value.trim();
  if (!question) return;
  if (!docs.length) { setStatus("Add at least one document first.", true); return; }
  lastQuestion = question;

  const investigation = activeInvestigation();
  if (!investigation) return;
  const turn = { question, result: null, error: null };
  investigation.turns.push(turn);
  investigation.title = investigation.title === "New investigation" ? question.slice(0, 36) + (question.length > 36 ? "…" : "") : investigation.title;
  $("workspaceTitle").textContent = investigation.title;
  const crumb = document.querySelector(".crumb strong");
  if (crumb) crumb.textContent = investigation.title;
  investigation.updatedAt = Date.now();
  persistInvestigations();

  addMessage(`<p class="q">${esc(question)}</p>`);
  const pending = addMessage(`<div class="thinking"><span class="assistant-mark"><img src="logo-mark.svg" alt=""></span><div><b>Let me look through the sources</b><small>Matching passages and checking for disagreements…</small></div></div>`);
  els.question.value = "";
  els.btn.disabled = true;

  try {
    const result = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, document_ids: selectedIds() }),
    });
    turn.result = result;
    investigation.updatedAt = Date.now();
    persistInvestigations();
    if (currentInvestigationId === investigation.id) renderEvidence(result);
    pending.innerHTML = `<div class="assistant-reply"><span class="assistant-mark"><img src="logo-mark.svg" alt=""></span>${answerHTML(result)}</div>`;
  } catch (err) {
    turn.error = err.message;
    turn.result = null;
    persistInvestigations();
    pending.innerHTML = `<div class="assistant-reply"><span class="assistant-mark"><img src="logo-mark.svg" alt=""></span><div class="error-msg"><b>I couldn’t finish that just now.</b><p>${esc(err.message)}</p><button data-action="retry" class="retry-action">Try again</button></div></div>`;
  } finally {
    els.btn.disabled = false;
    els.messages.scrollTop = els.messages.scrollHeight;
    els.question.focus();
  }
});

els.question.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); els.form.requestSubmit(); }
});

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (!$("appShell").hidden) {
      createInvestigation();
    }
  }
});
