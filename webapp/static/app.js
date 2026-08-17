// Portals Monitor - Mini App logic

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

const state = {
  overviewRange: "all",
  overviewSort: "floor", // "floor" | "volume"
};

// ---------- helpers ----------

function fmtTon(n) {
  if (n === null || n === undefined) return "—";
  return n.toFixed(2);
}

function fmtPct(n) {
  if (n === null || n === undefined) return "н/д";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function changeClass(n) {
  if (n === null || n === undefined) return "flat";
  if (n > 0.05) return "up";
  if (n < -0.05) return "down";
  return "flat";
}

// left border intensity: stronger color the bigger the signal
function signalColor(value, kind) {
  if (value === null || value === undefined) return "var(--neutral)";
  if (kind === "pct") {
    if (value > 0.05) return "var(--profit)";
    if (value < -0.05) return "var(--loss)";
    return "var(--neutral)";
  }
  // profit in TON
  return value > 0 ? "var(--profit)" : "var(--neutral)";
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function setLastUpdate() {
  const el = document.getElementById("lastUpdate");
  const now = new Date();
  el.textContent = now.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
}

// ---------- tabs ----------

document.getElementById("tabs").addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  const tabId = btn.dataset.tab;

  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === btn));
  document.querySelectorAll(".panel").forEach((p) =>
    p.classList.toggle("active", p.id === `panel-${tabId}`)
  );

  if (tabId === "arbitrage") loadArbitrage();
  if (tabId === "orders") loadOrders();
});

// ---------- overview tab ----------

document.getElementById("rangeFilters").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;

  if (chip.dataset.range !== undefined) {
    state.overviewRange = chip.dataset.range;
    document.querySelectorAll("[data-range]").forEach((c) => c.classList.toggle("active", c === chip));
  }
  if (chip.dataset.sort !== undefined) {
    state.overviewSort = state.overviewSort === "volume" ? "floor" : "volume";
    chip.classList.toggle("active", state.overviewSort === "volume");
  }
  loadOverview();
});

async function loadOverview() {
  const listEl = document.getElementById("overviewList");
  try {
    let rows;
    if (state.overviewSort === "volume") {
      rows = await getJSON("/api/volume");
    } else if (state.overviewRange !== "all") {
      rows = await getJSON(`/api/range/${state.overviewRange}`);
    } else {
      rows = await getJSON("/api/floors");
    }

    if (!rows.length) {
      listEl.innerHTML = `<div class="empty-state">Нічого не знайдено.<br>Можливо, бот ще не зробив перше опитування.</div>`;
      return;
    }

    listEl.innerHTML = rows
      .map((r) => {
        const cls = changeClass(r.change_24h_pct);
        const border = signalColor(r.change_24h_pct, "pct");
        const volTxt = r.volume_24h !== null ? `${r.volume_24h.toFixed(0)} TON/24г` : "";
        const salesTxt = r.sales_24h !== null ? ` · ${r.sales_24h} угод` : "";
        return `
          <div class="row" style="border-left-color:${border}">
            <div class="row-main">
              <div class="row-name">${escapeHtml(r.name)}</div>
              <div class="row-sub">${volTxt}${salesTxt}</div>
            </div>
            <div class="row-num">
              <div class="row-price">${fmtTon(r.floor)} TON</div>
              <div class="row-change ${cls}">${fmtPct(r.change_24h_pct)}</div>
            </div>
          </div>`;
      })
      .join("");
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">Помилка завантаження: ${err.message}</div>`;
  }
  setLastUpdate();
}

// ---------- arbitrage tab ----------

async function loadArbitrage() {
  const listEl = document.getElementById("arbitrageList");
  listEl.innerHTML = `<div class="empty-state">Рахую офери на MRKT, це займає ~10-30 сек…</div>`;
  try {
    const rows = await getJSON("/api/arbitrage_top");
    if (!rows.length) {
      listEl.innerHTML = `<div class="empty-state">Дані відсутні. Перевір, чи підключено MRKT (setup_mrkt.py) і чи є ліквідні подарунки.</div>`;
      return;
    }
    listEl.innerHTML = rows
      .map((r) => {
        const border = signalColor(r.profit, "profit");
        const badgeClass = r.buy_on === "Portals" ? "buy-portals" : "buy-mrkt";
        return `
          <div class="row" style="border-left-color:${border}">
            <div class="row-main">
              <div class="row-name">${escapeHtml(r.name)}</div>
              <div class="row-sub">Portals ${fmtTon(r.portals_floor)} · MRKT ${fmtTon(r.mrkt_price)}</div>
            </div>
            <div class="row-num">
              <div class="row-price">${r.profit >= 0 ? "+" : ""}${fmtTon(r.profit)} TON</div>
              <span class="badge ${badgeClass}">купити на ${r.buy_on}</span>
            </div>
          </div>`;
      })
      .join("");
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">Помилка: ${err.message}</div>`;
  }
}

// ---------- orders tab ----------

async function loadOrders() {
  const listEl = document.getElementById("ordersList");
  listEl.innerHTML = `<div class="empty-state">Рахую офери на Portals, це займає ~30-60 сек…</div>`;
  try {
    const rows = await getJSON("/api/orders_top");
    if (!rows.length) {
      listEl.innerHTML = `<div class="empty-state">Немає валідних подарунків з активними оферами.</div>`;
      return;
    }
    listEl.innerHTML = rows
      .map((r) => {
        const border = signalColor(r.profit, "profit");
        return `
          <div class="row" style="border-left-color:${border}">
            <div class="row-main">
              <div class="row-name">${escapeHtml(r.name)}</div>
              <div class="row-sub">офер ${fmtTon(r.offer)} → floor ${fmtTon(r.floor)}</div>
            </div>
            <div class="row-num">
              <div class="row-price">${r.profit >= 0 ? "+" : ""}${fmtTon(r.profit)} TON</div>
            </div>
          </div>`;
      })
      .join("");
  } catch (err) {
    listEl.innerHTML = `<div class="empty-state">Помилка: ${err.message}</div>`;
  }
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// ---------- init ----------

loadOverview();
setInterval(() => {
  const activePanel = document.querySelector(".panel.active").id;
  if (activePanel === "panel-overview") loadOverview();
}, 30000);
