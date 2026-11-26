const API_URL = "http://127.0.0.1:8000";

const CATEGORIES = [
  "Храна и супермаркет",
  "Ресторанти и кафенета",
  "Транспорт и гориво",
  "Битови сметки и наем",
  "Забавление и свободно време",
  "Здраве и аптека",
  "Пазаруване и дрехи",
  "Други",
];

const CATEGORY_STYLE = {
  "Храна и супермаркет":         { icon: "🛒", color: "#22c55e" },
  "Ресторанти и кафенета":       { icon: "☕", color: "#f59e0b" },
  "Транспорт и гориво":          { icon: "⛽", color: "#38bdf8" },
  "Битови сметки и наем":        { icon: "🏠", color: "#a78bfa" },
  "Забавление и свободно време": { icon: "🎉", color: "#f472b6" },
  "Здраве и аптека":             { icon: "💊", color: "#2dd4bf" },
  "Пазаруване и дрехи":          { icon: "🛍️", color: "#fb7185" },
  "Други":                       { icon: "📦", color: "#94a3b8" },
};
const styleFor = (cat) => CATEGORY_STYLE[cat] || CATEGORY_STYLE["Други"];

const $ = (id) => document.getElementById(id);
const money = (n) => `${Number(n || 0).toFixed(2)} лв.`;
const today = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let allExpenses = [];
let categoryChart = null;
let periodChart = null;
let periodGroup = "day";
let selectedFile = null;

/* ---------------- API helper ---------------- */
async function api(path, options = {}) {
  const res = await fetch(API_URL + path, options);
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const detail = data && data.detail;
    throw new Error(typeof detail === "string" ? detail : `Грешка ${res.status}`);
  }
  return data;
}
const postJson = (path, body) =>
  api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/* ---------------- UI helpers ---------------- */
let toastTimer;
function toast(msg, type = "success") {
  const t = $("toast");
  t.textContent = msg;
  t.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), 3500);
}
function setLoading(btn, on) {
  btn.disabled = on;
  btn.classList.toggle("loading", on);
}
const currentMonth = () => $("month-input").value;

/* ---------------- Server status ---------------- */
async function checkServer() {
  const pill = $("server-status");
  try {
    await api("/");
    pill.textContent = "● Онлайн";
    pill.className = "status-pill ok";
    return true;
  } catch {
    pill.textContent = "● Сървърът е офлайн";
    pill.className = "status-pill err";
    toast("Няма връзка със сървъра. Пусни backend-а (uvicorn main:app --reload).", "error");
    return false;
  }
}

/* ---------------- Budget ---------------- */
async function loadBudget() {
  const data = await api(`/budget/${currentMonth()}`);
  renderBudget(data.budget);
  renderCategoryChart(data.categories);
}

function renderBudget(b) {
  $("stat-limit").textContent = money(b.limit_amount);
  $("stat-spent").textContent = money(b.total_spent);
  const rem = $("stat-remaining");
  rem.textContent = b.limit_amount > 0 ? money(b.remaining) : "—";
  rem.className = "stat-value " + (b.limit_amount > 0 ? (b.remaining < 0 ? "negative" : "positive") : "");

  $("budget-alert").classList.toggle("hidden", !b.is_exceeded);
  $("budget-section").classList.toggle("exceeded", !!b.is_exceeded);
  if (b.limit_amount > 0) $("budget-input").placeholder = `Текущ: ${b.limit_amount}`;

  const bar = $("budget-progress");
  const label = $("progress-label");
  if (b.limit_amount > 0) {
    const pct = (b.total_spent / b.limit_amount) * 100;
    bar.style.width = Math.min(pct, 100) + "%";
    bar.className = "progress-bar" + (pct >= 100 ? " over" : pct >= 80 ? " warn" : "");
    label.textContent = `Използвани ${pct.toFixed(0)}% от бюджета.`;
  } else {
    bar.style.width = "0%";
    bar.className = "progress-bar";
    label.textContent = "Задай бюджет, за да следиш прогреса.";
  }
}

$("budget-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("budget-save-btn");
  const value = parseFloat($("budget-input").value);
  if (isNaN(value) || value < 0) return toast("Въведи валидна сума.", "error");
  setLoading(btn, true);
  try {
    const status = await postJson("/budget", { month: currentMonth(), limit_amount: value });
    renderBudget(status);
    $("budget-input").value = "";
    toast("Бюджетът е запазен ✅");
  } catch (err) {
    toast(err.message, "error");
  } finally {
    setLoading(btn, false);
  }
});

/* ---------------- Charts ---------------- */
Chart.defaults.color = "#a5a8c4";
Chart.defaults.font.family = "Outfit, sans-serif";

function renderCategoryChart(categories) {
  const empty = !categories || categories.length === 0;
  $("chart-empty").classList.toggle("hidden", !empty);
  $("category-chart").parentElement.classList.toggle("hidden", empty);
  if (empty) return;

  const labels = categories.map((c) => c.category);
  const values = categories.map((c) => c.total);
  const colors = labels.map((l) => styleFor(l).color);

  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart($("category-chart"), {
    type: "doughnut",
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, hoverOffset: 10 }] },
    options: {
      maintainAspectRatio: false,
      cutout: "65%",
      plugins: {
        legend: { position: "right", labels: { boxWidth: 12, padding: 12 } },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${money(ctx.raw)}` } },
      },
    },
  });
}

async function loadPeriods() {
  const data = await api(`/analytics/periods?group_by=${periodGroup}&month=${currentMonth()}`);
  const labels = data.periods.map((p) => (periodGroup === "day" ? p.period.slice(8) + "." + p.period.slice(5, 7) : p.period));
  const values = data.periods.map((p) => p.total);

  if (periodChart) periodChart.destroy();
  const ctx = $("period-chart").getContext("2d");
  const gradient = ctx.createLinearGradient(0, 0, 0, 280);
  gradient.addColorStop(0, "rgba(139, 92, 246, 0.9)");
  gradient.addColorStop(1, "rgba(56, 189, 248, 0.4)");

  periodChart = new Chart(ctx, {
    type: "bar",
    data: { labels, datasets: [{ data: values, backgroundColor: gradient, borderRadius: 8, maxBarThickness: 36 }] },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => " " + money(c.raw) } } },
      scales: {
        x: { grid: { display: false } },
        y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.05)" } },
      },
    },
  });
}

$("period-toggle").addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  periodGroup = btn.dataset.group;
  document.querySelectorAll("#period-toggle button").forEach((b) => b.classList.toggle("active", b === btn));
  loadPeriods().catch((err) => toast(err.message, "error"));
});

/* ---------------- Expenses ---------------- */
async function loadExpenses() {
  allExpenses = await api("/expenses");
  renderExpenses();
}

function renderExpenses() {
  const q = $("search-input").value.trim().toLowerCase();
  const list = $("expense-list");
  const items = allExpenses.filter(
    (e) => !q || e.title.toLowerCase().includes(q) || (e.category || "").toLowerCase().includes(q)
  );
  $("list-empty").classList.toggle("hidden", items.length > 0);
  list.innerHTML = items
    .map((e, i) => {
      const s = styleFor(e.category);
      return `
      <li class="expense-item" style="animation-delay:${Math.min(i, 15) * 30}ms">
        <div class="exp-icon" style="background:${s.color}22">${s.icon}</div>
        <div>
          <div class="exp-title">${escapeHtml(e.title)}</div>
          <div class="exp-meta">
            <span>${escapeHtml(e.date)}</span>·<span>${escapeHtml(e.category)}</span>
            ${e.source === "receipt" ? '<span class="badge">🧾 бележка</span>' : ""}
          </div>
        </div>
        <div class="exp-amount">${money(e.amount)}</div>
        <button class="del-btn" data-id="${e.id}" title="Изтрий" aria-label="Изтрий разход">🗑</button>
      </li>`;
    })
    .join("");
}

$("search-input").addEventListener("input", renderExpenses);

$("expense-list").addEventListener("click", async (e) => {
  const btn = e.target.closest(".del-btn");
  if (!btn) return;
  if (!confirm("Сигурен ли си, че искаш да изтриеш този разход?")) return;
  try {
    await api(`/expenses/${btn.dataset.id}`, { method: "DELETE" });
    toast("Разходът е изтрит 🗑");
    refreshAll();
  } catch (err) {
    toast(err.message, "error");
  }
});

$("expense-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("expense-submit-btn");
  const payload = {
    title: $("exp-title").value.trim(),
    amount: parseFloat($("exp-amount").value),
    date: $("exp-date").value,
    category: $("exp-category").value,
  };
  if (!payload.title || !(payload.amount > 0)) return toast("Попълни описание и сума.", "error");
  setLoading(btn, true);
  try {
    const res = await postJson("/expenses", payload);
    toast(`Добавено в „${res.category}“ ${styleFor(res.category).icon}`);
    $("exp-title").value = "";
    $("exp-amount").value = "";
    $("exp-category").value = "";
    refreshAll();
  } catch (err) {
    toast(err.message, "error");
  } finally {
    setLoading(btn, false);
  }
});

/* ---------------- Receipt scan ---------------- */
function selectFile(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) return toast("Моля, избери изображение.", "error");
  if (file.size > 5 * 1024 * 1024) return toast("Файлът е над 5 MB.", "error");
  selectedFile = file;
  const img = $("receipt-preview");
  img.src = URL.createObjectURL(file);
  img.classList.remove("hidden");
  $("dropzone-text").classList.add("hidden");
  $("scan-btn").disabled = false;
  $("scan-result").classList.add("hidden");
}

$("receipt-input").addEventListener("change", (e) => selectFile(e.target.files[0]));

const dz = $("dropzone");
["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
dz.addEventListener("drop", (e) => selectFile(e.dataTransfer.files[0]));

$("scan-btn").addEventListener("click", async () => {
  if (!selectedFile) return;
  const btn = $("scan-btn");
  const out = $("scan-result");
  const form = new FormData();
  form.append("file", selectedFile);
  setLoading(btn, true);
  try {
    const res = await api("/scan-receipt", { method: "POST", body: form });
    const d = res.extracted_data || {};
    out.className = "scan-result";
    out.innerHTML = `
      ✅ <strong>Разходът е записан!</strong><br>
      🏪 ${escapeHtml(d.title)}<br>
      💰 ${money(d.amount)}<br>
      📅 ${escapeHtml(d.date)}<br>
      ${styleFor(d.category).icon} ${escapeHtml(d.category)}`;
    toast("Бележката е разчетена 🧾");
    selectedFile = null;
    $("receipt-input").value = "";
    btn.disabled = true;
    refreshAll();
  } catch (err) {
    out.className = "scan-result error";
    out.textContent = "❌ " + err.message;
  } finally {
    btn.classList.remove("loading");
    btn.disabled = !selectedFile;
  }
});

/* ---------------- AI insights ---------------- */
$("insights-btn").addEventListener("click", async () => {
  const btn = $("insights-btn");
  const body = $("insights-body");
  setLoading(btn, true);
  body.innerHTML = '<p class="muted">AI анализира разходите ти…</p>';
  try {
    const { ai_insights: ai } = await api(`/insights/${currentMonth()}`);
    const tips = (ai.tips || []).map((t, i) => `<li style="animation-delay:${i * 80}ms">${escapeHtml(t)}</li>`).join("");
    body.innerHTML = `
      <p class="insight-summary">${escapeHtml(ai.summary)}</p>
      ${ai.top_habit ? `<div class="insight-habit">🔍 ${escapeHtml(ai.top_habit)}</div>` : ""}
      ${tips ? `<ul class="tips">${tips}</ul>` : ""}`;
  } catch (err) {
    body.innerHTML = `<p class="muted">❌ ${escapeHtml(err.message)}</p>`;
  } finally {
    setLoading(btn, false);
  }
});

/* ---------------- Init ---------------- */
async function refreshAll() {
  try {
    await Promise.all([loadExpenses(), loadBudget(), loadPeriods()]);
  } catch (err) {
    toast(err.message, "error");
  }
}

function init() {
  $("month-input").value = today().slice(0, 7);
  $("exp-date").value = today();
  $("exp-category").insertAdjacentHTML(
    "beforeend",
    CATEGORIES.map((c) => `<option value="${c}">${styleFor(c).icon} ${c}</option>`).join("")
  );
  $("month-input").addEventListener("change", () => {
    $("insights-body").innerHTML = '<p class="muted">Натисни „Анализирай месеца“, за да получиш персонални съвети.</p>';
    refreshAll();
  });
  checkServer().then((ok) => ok && refreshAll());
}

init();
