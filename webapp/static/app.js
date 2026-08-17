// Portals Monitor - Mini App logic

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
}

// Ідентифікатор чату/користувача - з Telegram initData (якщо відкрито в
// Telegram) або null, якщо тестуємо у звичайному браузері (портфель тоді
// не працюватиме - потрібен реальний Telegram-контекст).
const CHAT_ID = tg?.initDataUnsafe?.user?.id || null;

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

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function setLastUpdate() {
  const el = document.getElementById("lastUpdate");
  const now = new Date();
  el.textContent = now.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" });
}

async function loadTonPrice() {
  const el = document.getElementById("tonPrice");
  try {
    const data = await getJSON("/api/price");
    if (data.usd) {
      el.textContent = `GRAM (TON) ≈ $${data.usd.toFixed(2)}`;
    } else {
      el.textContent = "курс н/д";
    }
  } catch {
    el.textContent = "курс н/д";
  }
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
  if (tabId === "portfolio") loadPortfolio();
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

// ---------- portfolio tab ----------

function pfNoChatIdWarning() {
  return `<div class="empty-state">Портфель працює тільки всередині Telegram (потрібен твій ідентифікатор користувача) - відкрий Mini App через кнопку в боті, не в звичайному браузері.</div>`;
}

async function loadPortfolio() {
  const summaryEl = document.getElementById("pfSummary");
  const openEl = document.getElementById("pfOpenList");
  const closedEl = document.getElementById("pfClosedList");

  if (!CHAT_ID) {
    openEl.innerHTML = pfNoChatIdWarning();
    closedEl.innerHTML = "";
    summaryEl.innerHTML = "";
    return;
  }

  try {
    const data = await getJSON(`/api/portfolio?chat_id=${CHAT_ID}`);

    summaryEl.innerHTML = `
      <div class="pf-summary-card">
        <div class="pf-summary-label">Реалізовано</div>
        <div class="pf-summary-value" style="color:${data.realized_total >= 0 ? "var(--profit)" : "var(--loss)"}">
          ${data.realized_total >= 0 ? "+" : ""}${data.realized_total.toFixed(2)} TON
        </div>
      </div>
      <div class="pf-summary-card">
        <div class="pf-summary-label">Нереалізовано</div>
        <div class="pf-summary-value" style="color:${data.unrealized_total >= 0 ? "var(--profit)" : "var(--loss)"}">
          ${data.unrealized_total >= 0 ? "+" : ""}${data.unrealized_total.toFixed(2)} TON
        </div>
      </div>`;

    if (!data.open.length) {
      openEl.innerHTML = `<div class="empty-state">Відкритих позицій немає.</div>`;
    } else {
      openEl.innerHTML = data.open
        .map((p) => {
          const hasCurrent = p.unrealized_profit !== null;
          const border = hasCurrent ? signalColor(p.unrealized_profit, "profit") : "var(--neutral)";
          const profitTxt = hasCurrent
            ? `${p.unrealized_profit >= 0 ? "+" : ""}${p.unrealized_profit.toFixed(2)} TON`
            : "floor н/д";
          const subTxt = p.current_floor !== null
            ? ` · floor ${fmtTon(p.current_floor)} (чисто ${fmtTon(p.net_sell_value)})`
            : "";
          return `
            <div class="row" style="border-left-color:${border}">
              <div class="row-main">
                <div class="row-name">${escapeHtml(p.gift_name)}</div>
                <div class="row-sub">купив ${fmtTon(p.buy_price)}${subTxt}</div>
              </div>
              <div class="row-num">
                <div class="row-price">${profitTxt}</div>
              </div>
              <button class="pf-delete" data-delete-id="${p.id}" title="Видалити">\u2715</button>
            </div>`;
        })
        .join("");
    }

    if (!data.closed_by_date.length) {
      closedEl.innerHTML = `<div class="empty-state">Закритих угод ще немає.</div>`;
    } else {
      closedEl.innerHTML = data.closed_by_date
        .map((group) => {
          const groupColor = group.profit_total >= 0 ? "var(--profit)" : "var(--loss)";
          const rows = group.trades
            .map((t) => {
              const border = signalColor(t.profit, "profit");
              return `
                <div class="row" style="border-left-color:${border}">
                  <div class="row-main">
                    <div class="row-name">${escapeHtml(t.gift_name)}</div>
                    <div class="row-sub">${fmtTon(t.buy_price)} \u2192 ${fmtTon(t.sell_price)}</div>
                  </div>
                  <div class="row-num">
                    <div class="row-price">${t.profit >= 0 ? "+" : ""}${fmtTon(t.profit)} TON</div>
                  </div>
                  <button class="pf-delete" data-delete-id="${t.id}" title="Видалити">\u2715</button>
                </div>`;
            })
            .join("");
          return `
            <div class="pf-date-group">
              <div class="pf-date-header">
                <span>${group.date}</span>
                <span style="color:${groupColor}">${group.profit_total >= 0 ? "+" : ""}${group.profit_total.toFixed(2)} TON</span>
              </div>
              ${rows}
            </div>`;
        })
        .join("");
    }
  } catch (err) {
    openEl.innerHTML = `<div class="empty-state">Помилка: ${err.message}</div>`;
  }
}

document.getElementById("pfBuyBtn").addEventListener("click", async () => {
  if (!CHAT_ID) return;
  const name = document.getElementById("pfName").value.trim();
  const price = parseFloat(document.getElementById("pfPrice").value);
  if (!name || !price || price <= 0) {
    tg?.showAlert?.("Вкажи назву і ціну.");
    return;
  }
  try {
    await postJSON("/api/portfolio/buy", { chat_id: CHAT_ID, gift_name: name, price });
    document.getElementById("pfPrice").value = "";
    loadPortfolio();
  } catch (err) {
    tg?.showAlert?.(`Помилка: ${err.message}`);
  }
});

document.getElementById("pfSellBtn").addEventListener("click", async () => {
  if (!CHAT_ID) return;
  const name = document.getElementById("pfName").value.trim();
  const price = parseFloat(document.getElementById("pfPrice").value);
  if (!name || !price || price <= 0) {
    tg?.showAlert?.("Вкажи назву і ціну.");
    return;
  }
  try {
    await postJSON("/api/portfolio/sell", { chat_id: CHAT_ID, gift_name: name, price });
    document.getElementById("pfPrice").value = "";
    loadPortfolio();
  } catch (err) {
    tg?.showAlert?.(`Не знайшов відкриту позицію з такою назвою, або інша помилка: ${err.message}`);
  }
});

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-delete-id]");
  if (!btn || !CHAT_ID) return;
  const tradeId = parseInt(btn.dataset.deleteId, 10);
  try {
    await postJSON("/api/portfolio/delete", { chat_id: CHAT_ID, trade_id: tradeId });
    loadPortfolio();
  } catch (err) {
    tg?.showAlert?.(`Помилка видалення: ${err.message}`);
  }
});

let GIFT_NAMES = [];

async function loadGiftNamesAutocomplete() {
  try {
    GIFT_NAMES = await getJSON("/api/gift_names");
  } catch {
    GIFT_NAMES = [];
  }
}

const pfNameInput = document.getElementById("pfName");
const pfSuggestionsEl = document.getElementById("pfSuggestions");

pfNameInput.addEventListener("input", () => {
  const query = pfNameInput.value.trim().toLowerCase();
  if (!query) {
    pfSuggestionsEl.classList.remove("show");
    pfSuggestionsEl.innerHTML = "";
    return;
  }
  const matches = GIFT_NAMES.filter((n) => n.toLowerCase().includes(query)).slice(0, 8);
  if (!matches.length) {
    pfSuggestionsEl.classList.remove("show");
    pfSuggestionsEl.innerHTML = "";
    return;
  }
  pfSuggestionsEl.innerHTML = matches
    .map((n) => `<div class="pf-suggestion-item" data-name="${escapeHtml(n)}">${escapeHtml(n)}</div>`)
    .join("");
  pfSuggestionsEl.classList.add("show");
});

pfSuggestionsEl.addEventListener("click", (e) => {
  const item = e.target.closest(".pf-suggestion-item");
  if (!item) return;
  pfNameInput.value = item.dataset.name;
  pfSuggestionsEl.classList.remove("show");
  pfSuggestionsEl.innerHTML = "";
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".pf-autocomplete-wrap")) {
    pfSuggestionsEl.classList.remove("show");
  }
});

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// ---------- init ----------

loadOverview();
loadTonPrice();
loadGiftNamesAutocomplete();
setInterval(() => {
  const activePanel = document.querySelector(".panel.active").id;
  if (activePanel === "panel-overview") loadOverview();
}, 30000);
setInterval(loadTonPrice, 5 * 60 * 1000);
