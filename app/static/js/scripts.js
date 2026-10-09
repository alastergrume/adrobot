"use strict";

// --- helpers -------------------------------------------------------------------

function toast(message) {
  const box = document.getElementById("toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(box._timer);
  box._timer = setTimeout(() => { box.hidden = true; }, 6000);
}

async function api(method, url, body) {
  const options = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    let detail = data.detail || response.statusText;
    if (Array.isArray(detail)) detail = detail.map((item) => item.msg).join("; ");
    throw new Error(detail);
  }
  return data;
}

// Reload the page but keep the scroll position, so the edited stream stays in view.
function reloadKeepingScroll() {
  try { sessionStorage.setItem("scrollY", String(window.scrollY)); } catch (e) { /* storage unavailable */ }
  window.location.reload();
}

window.addEventListener("load", () => {
  try {
    const y = sessionStorage.getItem("scrollY");
    if (y !== null) {
      window.scrollTo(0, Number(y));
      sessionStorage.removeItem("scrollY");
    }
  } catch (e) { /* storage unavailable */ }
});

async function run(button, action) {
  if (button) button.disabled = true;
  try {
    await action();
  } catch (error) {
    toast(error.message);
    if (button) button.disabled = false;
  }
}

// --- buttons -----------------------------------------------------------------------

const actions = {
  async import(el) {
    const campaign = await api("POST", "/api/campaigns/import", { keitaro_id: Number(el.dataset.keitaroId) });
    window.location.href = `/campaigns/${campaign.id}`;
  },
  async fetch(el) {
    if (el.dataset.dirty === "1" &&
        !confirm("Some streams have unpublished changes. Fetching from Keitaro will discard them. Continue?")) {
      el.disabled = false;
      return;
    }
    await api("POST", `/api/campaigns/${el.dataset.campaignId}/fetch`);
    reloadKeepingScroll();
  },
  async push(el) {
    await api("POST", `/api/streams/${el.dataset.streamId}/push`);
    reloadKeepingScroll();
  },
  async cancel(el) {
    await api("POST", `/api/streams/${el.dataset.streamId}/cancel`);
    reloadKeepingScroll();
  },
  async remove(el) {
    await api("POST", `/api/stream-offers/${el.dataset.id}/remove`);
    reloadKeepingScroll();
  },
  async "bring-back"(el) {
    await api("POST", `/api/stream-offers/${el.dataset.id}/bring-back`);
    reloadKeepingScroll();
  },
  async pin(el) {
    await api("POST", `/api/stream-offers/${el.dataset.id}/pin`, { pinned: el.dataset.pinned !== "1" });
    reloadKeepingScroll();
  },
};

document.addEventListener("click", (event) => {
  const el = event.target.closest("[data-action]");
  if (!el) return;
  const name = el.dataset.action;
  if (name === "edit-share") {
    editShare(el);
    return;
  }
  if (actions[name]) {
    event.preventDefault();
    run(el, () => actions[name](el));
  }
});

// Click on a share turns it into an input; Enter saves (and pins), Escape cancels.
function editShare(button) {
  const input = document.createElement("input");
  input.type = "number";
  input.min = "0";
  input.max = "100";
  input.value = button.dataset.share;
  input.className = "share-input";
  button.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const restore = () => { if (!done) { done = true; input.replaceWith(button); } };

  input.addEventListener("keydown", (event) => {
    if (event.key === "Escape") restore();
    if (event.key !== "Enter") return;
    event.preventDefault();
    const share = Number(input.value);
    if (!Number.isInteger(share) || share < 0 || share > 100) {
      toast("Share must be a whole number from 0 to 100");
      return;
    }
    done = true;
    input.disabled = true;
    api("POST", `/api/stream-offers/${button.dataset.id}/pin`, { pinned: true, share })
      .then(reloadKeepingScroll)
      .catch((error) => { toast(error.message); done = false; restore(); });
  });
  input.addEventListener("blur", restore);
}

// --- forms --------------------------------------------------------------------------

document.addEventListener("submit", (event) => {
  const form = event.target;

  if (form.id === "new-campaign-form") {
    event.preventDefault();
    const data = new FormData(form);
    if (!data.get("offer_id")) { toast("Choose an offer from the list"); return; }
    const button = form.querySelector("button[type=submit]");
    run(button, async () => {
      const campaign = await api("POST", "/api/campaigns", {
        name: data.get("name"),
        geo: data.get("geo"),
        offer_id: Number(data.get("offer_id")),
      });
      window.location.href = `/campaigns/${campaign.id}`;
    });
  }

  if (form.classList.contains("add-offer")) {
    event.preventDefault();
    const offerId = new FormData(form).get("offer_id");
    if (!offerId) { toast("Choose an offer from the list"); return; }
    run(form.querySelector("button[type=submit]"), async () => {
      await api("POST", `/api/streams/${form.dataset.streamId}/offers`, { offer_id: Number(offerId) });
      reloadKeepingScroll();
    });
  }
});

// --- offer autocomplete ---------------------------------------------------------------

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function setupAutocomplete(root) {
  const input = root.querySelector("[data-autocomplete-input]");
  const value = root.querySelector("[data-autocomplete-value]");
  const list = root.querySelector("[data-autocomplete-list]");
  let items = [];
  let active = -1;
  let timer = null;
  let requestId = 0;

  function close() { list.hidden = true; active = -1; }

  function render() {
    if (!items.length) {
      list.innerHTML = '<li class="empty">No offers found</li>';
    } else {
      list.innerHTML = items.map((offer, index) =>
        `<li data-index="${index}" class="${index === active ? "active" : ""}">` +
        `<span class="offer-id">${offer.id}</span> ${escapeHtml(offer.name)}</li>`).join("");
    }
    list.hidden = false;
  }

  async function search() {
    const current = ++requestId;
    const query = input.value.trim();
    try {
      const result = await api("GET", `/api/offers?q=${encodeURIComponent(query)}`);
      // Ignore answers to outdated queries (the user kept typing meanwhile).
      if (current !== requestId || query !== input.value.trim()) return;
      items = result;
      active = items.length ? 0 : -1;
      render();
    } catch (error) {
      toast(error.message);
    }
  }

  function choose(index) {
    const offer = items[index];
    if (!offer) return;
    value.value = offer.id;
    input.value = `${offer.id} ${offer.name}`;
    close();
  }

  input.addEventListener("input", () => {
    // Results of the previous query are stale: never let Enter pick one of them.
    value.value = "";
    items = [];
    active = -1;
    requestId++;
    list.innerHTML = '<li class="empty">Searching…</li>';
    list.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(search, 200);
  });
  input.addEventListener("focus", () => { if (!value.value) search(); });
  input.addEventListener("keydown", (event) => {
    if (list.hidden) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!items.length) return;
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      render();
    } else if (event.key === "Enter") {
      event.preventDefault();
      choose(active);
    } else if (event.key === "Escape") {
      close();
    }
  });
  list.addEventListener("mousedown", (event) => {
    const li = event.target.closest("li[data-index]");
    if (li) {
      event.preventDefault();
      choose(Number(li.dataset.index));
    }
  });
  input.addEventListener("blur", () => setTimeout(close, 100));
}

document.querySelectorAll("[data-autocomplete]").forEach(setupAutocomplete);
