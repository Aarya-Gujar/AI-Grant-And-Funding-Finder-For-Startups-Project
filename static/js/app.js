/**
 * AI Grant & Funding Finder
 * Main frontend JS — communicates with Flask API
 */

const API = {
  base: window.location.origin,
  grants: () => `${API.base}/api/grants`,
  grant: (id) => `${API.base}/api/grants/${id}`,
  match: () => `${API.base}/api/grants/match`,
  propose: () => `${API.base}/api/grants/propose`,
  summarize: () => `${API.base}/api/grants/summarize`,
  health: () => `${API.base}/api/health`,
};

// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  grants: [],
  matchedGrants: [],
  currentGrant: null,
  currentProposal: null,
  page: 1,
  perPage: 12,
  totalGrants: 0,
  loading: false,
  profile: {},
};

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

// ── Utility ───────────────────────────────────────────────────────────────────
function scoreClass(score) {
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

function truncate(str, n = 160) {
  if (!str) return "";
  return str.length > n ? str.slice(0, n) + "…" : str;
}

function domainTag(domain) {
  const palette = ["tag-blue", "tag-purple", "tag-teal", "tag-green", "tag-yellow"];
  const i = Math.abs([...domain].reduce((a, c) => a + c.charCodeAt(0), 0)) % palette.length;
  return palette[i];
}

async function fetchJSON(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json();
}

function showToast(msg, type = "info") {
  let container = $("#toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    Object.assign(container.style, {
      position: "fixed", bottom: "1.5rem", right: "1.5rem",
      zIndex: 9999, display: "flex", flexDirection: "column", gap: ".5rem",
    });
    document.body.appendChild(container);
  }
  const toast = document.createElement("div");
  toast.className = `alert alert-${type}`;
  toast.style.cssText = "min-width:280px;max-width:380px;box-shadow:0 4px 16px rgba(0,0,0,.2);";
  toast.innerHTML = `<span>${msg}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ── Tab switching ──────────────────────────────────────────────────────────────
function initTabs() {
  $$(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      $$(".tab-btn").forEach(b => b.classList.remove("active"));
      $$(".tab-pane").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const target = $(`#${btn.dataset.tab}`);
      if (target) target.classList.add("active");
    });
  });
}

// ── Grants Browser ────────────────────────────────────────────────────────────
async function loadGrants(page = 1) {
  const q        = $("#search-input")?.value.trim() || "";
  const domain   = $("#filter-domain")?.value || "";
  const stage    = $("#filter-stage")?.value || "";
  const location = $("#filter-location")?.value || "";
  const type     = $("#filter-type")?.value || "";

  const params = new URLSearchParams({ page, per_page: state.perPage });
  if (q)        params.set("q", q);
  if (domain)   params.set("domain", domain);
  if (stage)    params.set("stage", stage);
  if (location) params.set("location", location);
  if (type)     params.set("type", type);

  const grid = $("#grants-grid");
  grid.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>Fetching funding opportunities…</p></div>`;

  try {
    const data = await fetchJSON(`${API.grants()}?${params}`);
    state.grants = data.grants || [];
    state.totalGrants = data.total || 0;
    state.page = page;
    renderGrantsGrid(state.grants, grid);
    renderPagination(data.total, page, state.perPage, "#grants-pagination", loadGrants);
    $("#results-count").textContent = `${data.total} funding opportunities found`;
  } catch (err) {
    grid.innerHTML = `<div class="empty-state">
      <div class="icon">⚠️</div>
      <h3>Could not load grants</h3>
      <p>${err.message}</p>
      <p style="margin-top:.5rem;font-size:.8rem">Make sure the Flask server is running on port 5000.</p>
    </div>`;
  }
}

function renderGrantsGrid(grants, container) {
  if (!grants.length) {
    container.innerHTML = `<div class="empty-state">
      <div class="icon">🔍</div>
      <h3>No grants found</h3>
      <p>Try adjusting your search filters or browsing all grants.</p>
    </div>`;
    return;
  }
  container.innerHTML = grants.map(g => grantCardHTML(g)).join("");
  $$(".grant-card", container).forEach((card, i) => {
    card.addEventListener("click", () => openGrantModal(grants[i]));
  });
}

function grantCardHTML(g) {
  const sc = g.relevance_score ?? g.ai_score;
  const cls = sc != null ? scoreClass(sc) : "";
  const tags = (g.tags || []).slice(0, 4).map(t =>
    `<span class="tag ${domainTag(t)}">${t}</span>`
  ).join("");
  const matchTags = (g.match_tags || []).map(t =>
    `<span class="meta-pill">${t}</span>`
  ).join("");

  return `
  <div class="card grant-card ${cls}" data-id="${g.id}">
    <div class="grant-header">
      <div>
        <div class="grant-title">${g.title}</div>
        <div class="grant-source">📌 ${g.source || "Unknown source"}</div>
      </div>
      ${sc != null ? `
        <div class="score-ring ${scoreClass(sc)}">${sc}</div>
      ` : `<span class="grant-badge">${g.type || "Grant"}</span>`}
    </div>
    <div class="grant-meta">
      ${g.funding_amount ? `<span class="meta-pill">💰 ${g.funding_amount}</span>` : ""}
      ${g.location ? `<span class="meta-pill">📍 ${g.location}</span>` : ""}
      ${g.deadline ? `<span class="meta-pill">🗓 ${g.deadline}</span>` : ""}
      ${matchTags}
    </div>
    <div class="grant-desc">${truncate(g.description, 200)}</div>
    <div style="margin-top:.75rem">${tags}</div>
    <div class="grant-actions">
      <button class="btn btn-primary btn-sm" onclick="event.stopPropagation();openGrantModal(window._grants['${g.id}'])">View Details</button>
      <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();quickPropose('${g.id}')">✍️ Draft Proposal</button>
    </div>
  </div>`;
}

// ── Grant Modal ───────────────────────────────────────────────────────────────
function openGrantModal(grant) {
  if (!grant) return;
  state.currentGrant = grant;
  window._grants = window._grants || {};
  window._grants[grant.id] = grant;

  const modal = $("#grant-modal");
  const body  = $(".modal-body", modal);

  $(".modal-title", modal).textContent = grant.title;
  body.innerHTML = `
    <div class="detail-row"><span class="detail-label">Source</span><span class="detail-value">${grant.source || "—"}</span></div>
    <div class="detail-row"><span class="detail-label">Funding Amount</span><span class="detail-value">${grant.funding_amount || "—"}</span></div>
    <div class="detail-row"><span class="detail-label">Type</span><span class="detail-value">${grant.type || "—"}</span></div>
    <div class="detail-row"><span class="detail-label">Deadline</span><span class="detail-value">${grant.deadline || "—"}</span></div>
    <div class="detail-row"><span class="detail-label">Location</span><span class="detail-value">${grant.location || "—"}</span></div>
    <div class="detail-row"><span class="detail-label">Stage</span><span class="detail-value">${(grant.stage || []).join(", ") || "—"}</span></div>
    <div class="detail-row"><span class="detail-label">Domain</span><span class="detail-value">${(grant.domain || []).join(", ") || "—"}</span></div>
    ${grant.match_reason ? `<div class="detail-row"><span class="detail-label">AI Match Reason</span><span class="detail-value">${grant.match_reason}</span></div>` : ""}
    <hr style="margin:1rem 0;border-color:#e0e0e0">
    <h3 style="margin-bottom:.5rem">Description</h3>
    <p style="font-size:.9rem;line-height:1.7;color:#525252">${grant.description || "No description available."}</p>
    <hr style="margin:1rem 0;border-color:#e0e0e0">
    <h3 style="margin-bottom:.5rem">Eligibility</h3>
    <p style="font-size:.9rem;line-height:1.7;color:#525252">${grant.eligibility || "See grant listing for details."}</p>
    ${grant.tags?.length ? `
      <div style="margin-top:1rem">
        ${grant.tags.map(t => `<span class="tag ${domainTag(t)}">${t}</span>`).join("")}
      </div>` : ""}
    ${grant.source_url ? `
      <div style="margin-top:1.2rem">
        <a href="${grant.source_url}" target="_blank" rel="noopener" class="btn btn-secondary btn-sm">
          🔗 Visit Official Page
        </a>
      </div>` : ""}
  `;
  modal.classList.add("open");
}

// ── AI Matching ───────────────────────────────────────────────────────────────
async function runMatching(e) {
  e?.preventDefault();
  const form = $("#matching-form");
  const profile = collectProfile(form);
  if (!profile.name || !profile.domain) {
    showToast("Please fill in at least the startup name and domain.", "warning");
    return;
  }
  state.profile = profile;

  const resultsArea = $("#match-results");
  resultsArea.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>IBM Granite AI is analysing your startup profile…</p></div>`;

  try {
    const data = await fetchJSON(API.match(), {
      method: "POST",
      body: JSON.stringify({ startup_profile: profile, use_ai: true, top_n: 15 }),
    });
    state.matchedGrants = data.grants || [];
    renderMatchResults(data);
    showToast(`✅ Found ${data.total_matched} matching grants for ${profile.name}`, "success");
  } catch (err) {
    resultsArea.innerHTML = `<div class="alert alert-danger">Matching failed: ${err.message}</div>`;
  }
}

function collectProfile(form) {
  const get = (name) => form.querySelector(`[name="${name}"]`)?.value?.trim() || "";
  return {
    name: get("startup_name"),
    domain: get("domain"),
    stage: get("stage"),
    location: get("location"),
    problem: get("problem"),
    solution: get("solution"),
    team_size: get("team_size"),
    keywords: get("keywords"),
  };
}

function renderMatchResults(data) {
  const area = $("#match-results");
  if (!data.grants?.length) {
    area.innerHTML = `<div class="empty-state"><div class="icon">🤔</div><h3>No matches found</h3><p>Try broadening your domain or stage.</p></div>`;
    return;
  }

  area.innerHTML = `
    <div class="alert alert-info">
      🤖 IBM Granite AI ranked <strong>${data.total_matched} grants</strong> for
      <strong>${data.startup}</strong>. Scores reflect alignment with your profile.
    </div>
    ${data.grants.map(g => grantCardHTML(g)).join("")}
  `;
  $$(".grant-card", area).forEach((card, i) => {
    card.addEventListener("click", () => openGrantModal(data.grants[i]));
    window._grants = window._grants || {};
    window._grants[data.grants[i].id] = data.grants[i];
  });
}

// ── Proposal Generator ─────────────────────────────────────────────────────────
async function generateProposal(e) {
  e?.preventDefault();
  const grantId = $("#proposal-grant-select")?.value;
  const form = $("#proposal-form");
  const profile = collectProfile(form);

  if (!profile.name || !grantId) {
    showToast("Please select a grant and enter your startup name.", "warning");
    return;
  }

  const output = $("#proposal-output");
  output.innerHTML = `<div class="loading-state"><div class="spinner"></div><p>IBM Granite is drafting your proposal…</p></div>`;

  try {
    const data = await fetchJSON(API.propose(), {
      method: "POST",
      body: JSON.stringify({ startup_profile: profile, grant_id: grantId }),
    });
    state.currentProposal = data.proposal;
    renderProposal(data.proposal);
    showToast("✅ Proposal generated successfully!", "success");
  } catch (err) {
    output.innerHTML = `<div class="alert alert-danger">Proposal generation failed: ${err.message}</div>`;
  }
}

function renderProposal(proposal) {
  const output = $("#proposal-output");
  if (!proposal) { output.innerHTML = ""; return; }

  const sectionsHTML = (proposal.sections || []).map(s => `
    <div class="proposal-section">
      <h3>${s.heading}</h3>
      <p>${s.content.replace(/\n/g, "<br>")}</p>
    </div>
  `).join("");

  output.innerHTML = `
    <div class="card">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:1rem;flex-wrap:wrap;gap:.5rem">
        <div>
          <h2 style="font-size:1.1rem">${proposal.title}</h2>
          <p style="font-size:.8rem;color:var(--text-muted)">Generated ${new Date(proposal.generated_at).toLocaleString()}</p>
        </div>
        <div style="display:flex;gap:.5rem">
          <button class="btn btn-secondary btn-sm" onclick="copyProposal()">📋 Copy</button>
          <button class="btn btn-primary btn-sm" onclick="downloadProposal()">⬇️ Download</button>
        </div>
      </div>
      ${proposal.cover_letter ? `
        <div class="proposal-section">
          <h3>Cover Letter</h3>
          <p>${proposal.cover_letter.replace(/\n/g, "<br>")}</p>
        </div>
        <hr style="margin:1.2rem 0;border-color:#e0e0e0">
      ` : ""}
      ${sectionsHTML}
      <div class="alert alert-warning" style="margin-top:1.5rem;font-size:.8rem">
        ⚠️ ${proposal.disclaimer}
      </div>
    </div>
  `;
}

function copyProposal() {
  if (!state.currentProposal) return;
  const text = (state.currentProposal.sections || [])
    .map(s => `${s.heading}\n${"─".repeat(s.heading.length)}\n${s.content}`)
    .join("\n\n");
  navigator.clipboard.writeText(text).then(() => showToast("Copied to clipboard!", "success"));
}

function downloadProposal() {
  if (!state.currentProposal) return;
  const p = state.currentProposal;
  const text = [
    p.title, "=".repeat(p.title.length), "",
    ...(p.sections || []).flatMap(s => [s.heading, "─".repeat(s.heading.length), s.content, ""]),
    p.disclaimer,
  ].join("\n");
  const blob = new Blob([text], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `proposal_${p.grant_id || "grant"}.txt`;
  a.click();
}

// ── Quick propose from grant card ─────────────────────────────────────────────
function quickPropose(grantId) {
  // Switch to proposal tab and pre-select grant
  $$(".tab-btn").forEach(b => b.classList.remove("active"));
  $$(".tab-pane").forEach(p => p.classList.remove("active"));
  $(".tab-btn[data-tab='tab-propose']")?.classList.add("active");
  $("#tab-propose")?.classList.add("active");

  const sel = $("#proposal-grant-select");
  if (sel) {
    // Try to set value; grant might not be in dropdown yet
    sel.value = grantId;
    if (!sel.value) {
      // Add option dynamically
      const grant = state.grants.find(g => g.id === grantId)
        || state.matchedGrants.find(g => g.id === grantId)
        || (window._grants && window._grants[grantId]);
      if (grant) {
        const opt = document.createElement("option");
        opt.value = grant.id;
        opt.textContent = grant.title;
        sel.appendChild(opt);
        sel.value = grantId;
      }
    }
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Populate proposal grant dropdown ─────────────────────────────────────────
async function populateGrantDropdown() {
  const sel = $("#proposal-grant-select");
  if (!sel) return;
  try {
    const data = await fetchJSON(`${API.grants()}?per_page=50`);
    sel.innerHTML = '<option value="">— Select a grant —</option>';
    (data.grants || []).forEach(g => {
      const opt = document.createElement("option");
      opt.value = g.id;
      opt.textContent = `${g.title} (${g.source || ""})`;
      sel.appendChild(opt);
    });
  } catch (_) {}
}

// ── Pagination ────────────────────────────────────────────────────────────────
function renderPagination(total, current, perPage, selector, loadFn) {
  const container = $(selector);
  if (!container) return;
  const pages = Math.ceil(total / perPage);
  if (pages <= 1) { container.innerHTML = ""; return; }

  let html = "";
  for (let i = 1; i <= Math.min(pages, 10); i++) {
    html += `<button class="page-btn ${i === current ? "active" : ""}"
      onclick="(${loadFn.name})(${i})">${i}</button>`;
  }
  container.innerHTML = html;
}

// ── Modal setup ───────────────────────────────────────────────────────────────
function initModals() {
  document.addEventListener("click", (e) => {
    if (e.target.matches(".modal-close") || e.target.matches(".modal-overlay")) {
      $$(".modal-overlay").forEach(m => m.classList.remove("open"));
    }
  });
}

// ── Health check ──────────────────────────────────────────────────────────────
async function checkHealth() {
  const badge = $("#api-status");
  if (!badge) return;
  try {
    const data = await fetchJSON(API.health());
    badge.textContent = "🟢 API Online";
    badge.style.color = "var(--success)";
  } catch (_) {
    badge.textContent = "🔴 API Offline";
    badge.style.color = "var(--danger)";
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initModals();
  checkHealth();
  loadGrants();
  populateGrantDropdown();

  // Search
  $("#search-btn")?.addEventListener("click", () => loadGrants(1));
  $("#search-input")?.addEventListener("keyup", (e) => { if (e.key === "Enter") loadGrants(1); });

  // Filter change
  $$(".filter-select").forEach(sel => sel.addEventListener("change", () => loadGrants(1)));

  // Matching form
  $("#matching-form")?.addEventListener("submit", runMatching);

  // Proposal form
  $("#proposal-form")?.addEventListener("submit", generateProposal);

  // Refresh btn
  $("#refresh-btn")?.addEventListener("click", async () => {
    showToast("Refreshing grant data…", "info");
    await fetchJSON(`${API.grants()}?refresh=true`);
    loadGrants(1);
    showToast("Grant data refreshed!", "success");
  });
});

// expose for inline calls
window.openGrantModal = openGrantModal;
window.quickPropose = quickPropose;
