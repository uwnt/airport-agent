// The chat page: sends a question to POST /chat and draws the server-sent events it gets back.
// Tables, score bars and "How I got this" are drawn from tool results only, never from the
// model's text. Model text is Markdown: always rendered with marked, then cleaned by DOMPurify.
// The rest of the page lives beside this file, loaded before it (see index.html):
// ranking-view.js, data-panel.js, question-input.js and talk-mode.js. `start` at the end
// runs once all of them are loaded.
"use strict";

const $ = (selector) => document.querySelector(selector);
// The server accepts at most 10 earlier turns and 20,000 characters of them in total (ChatRequest
// in server.py): keep the most recent ones, so a long conversation never starts failing. One
// answer is kept to 8,000 characters, so the latest question and answer (a question is at most
// 2,000) always fit.
const MAX_TURNS = 10;
const MAX_HISTORY_CHARS = 20000;
const MAX_TURN_CHARS = 8000;

// Drop the oldest question-and-answer pairs until the history fits the server's limits.
function trimHistory(history) {
  const size = (turns) => turns.reduce((total, turn) => total + turn.text.length, 0);
  let kept = history.slice(-MAX_TURNS);
  while (kept.length && size(kept) > MAX_HISTORY_CHARS) kept = kept.slice(2);
  return kept;
}

const state = { info: null, version: "latest", history: [], busy: false };

const STEP_LABELS = {
  rank_airports: "Ranking airports",
  compare_airports: "Comparing airports",
  airport_profile: "Reading the airport profile",
  long_haul_share: "Measuring the long-haul share",
  compare_over_time: "Comparing two data versions",
  demand_pressure: "Checking demand pressure",
};

// --- Small helpers ---------------------------------------------------------------------------

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) if (child != null) node.append(child);
  return node;
}

function render(markdown) {
  const clean = DOMPurify.sanitize(marked.parse(markdown || ""), { RETURN_DOM_FRAGMENT: true });
  // Added after sanitising (never allowed through it): each table gets a scrolling wrapper
  // (made focusable by markScrollers once it is known to overflow), and columns of short values (rank, counts) are marked so they do not get the wide text floor.
  for (const table of clean.querySelectorAll("table")) {
    const wrap = document.createElement("div");
    wrap.className = "table-wrap";
    table.replaceWith(wrap);
    wrap.append(table);
    markShortColumns(table);
  }
  return clean;
}

function markShortColumns(table) {
  const rows = [...table.rows];
  const columns = Math.max(0, ...rows.map((r) => r.cells.length));
  for (let c = 0; c < columns; c++) {
    const cells = rows.map((r) => r.cells[c]).filter(Boolean);
    const data = cells.filter((cell) => cell.tagName === "TD");
    if (data.length && data.every((cell) => cell.textContent.trim().length <= 6)) {
      for (const cell of cells) cell.classList.add("short");
    }
  }
}

// Safari does not let a keyboard user focus a scroller on their own, so a table that overflows
// gets a tab stop and a name; one that fits gets neither. Run when an answer is complete (not
// while it streams, which would drop focus on each redraw) and again when the width changes.
function markScrollers(container) {
  const wraps = [...container.querySelectorAll(".table-wrap")];
  wraps.forEach((wrap, index) => {
    if (wrap.scrollWidth > wrap.clientWidth) {
      wrap.tabIndex = 0;
      wrap.setAttribute("role", "region");
      wrap.setAttribute("aria-label", `Table ${index + 1} of ${wraps.length}, scrolls sideways`);
    } else {
      wrap.removeAttribute("tabindex");
      wrap.removeAttribute("role");
      wrap.removeAttribute("aria-label");
    }
  });
}

function describeArgs(args) {
  const parts = Object.entries(args || {})
    .filter(([, value]) => value != null)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`);
  return parts.join("; ");
}

function shown(value) {
  if (value == null) return "–";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function scrollDown() {
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

// --- Server-sent events over fetch (EventSource can only GET) ---------------------------------

async function* readEvents(response) {
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += value;
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      let event = "message";
      let data = "";
      for (const line of chunk.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      yield { event, data: data ? JSON.parse(data) : null };
    }
  }
}

// --- "How I got this": the sourced numbers behind an answer ----------------------------------

// Every value in a result that carries its source and as-of date, with where it was found.
function sourcedNumbers(result) {
  const found = [];
  const walk = (node, path) => {
    if (Array.isArray(node)) {
      node.forEach((item, i) => walk(item, item && item.code ? [...path, item.code] : [...path, `${i + 1}`]));
    } else if (node && typeof node === "object") {
      if ("source" in node && "as_of" in node && ("value" in node || "value_pct" in node)) {
        const value = "value_pct" in node ? `${node.value_pct}%` : shown(node.value);
        found.push({ item: path.join(" › "), value, unit: node.unit || "", source: node.source, asOf: node.as_of });
      }
      for (const [key, value] of Object.entries(node)) {
        if (value && typeof value === "object" && key !== "sources") walk(value, [...path, key]);
      }
    }
  };
  walk(result, []);
  return found;
}

function howItem(name, args, result) {
  const item = el("li", {},
    el("code", { text: name }),
    ` with ${describeArgs(args) || "no inputs"}`,
  );
  if (result.error) {
    item.append(el("div", { class: "error", text: `Tool error: ${result.error}` }));
    return item;
  }
  if (typeof result.score === "number") item.append(el("div", { text: `Score: ${result.score}` }));
  const rows = sourcedNumbers(result);
  if (rows.length) {
    const table = el("table", {},
      el("thead", {}, el("tr", {}, ...["Item", "Value", "Unit", "Source", "As of"].map((h) => el("th", { text: h })))),
    );
    const body = el("tbody");
    for (const r of rows) {
      body.append(el("tr", {}, ...[r.item, r.value, r.unit, r.source, r.asOf].map((t) => el("td", { text: t }))));
    }
    table.append(body);
    item.append(el("div", { class: "table-wrap" }, table));
  }
  item.append(
    el("details", {},
      el("summary", { text: "Everything the tool returned (JSON)" }),
      el("pre", { text: JSON.stringify(result, null, 2) }),
    ),
  );
  return item;
}

// --- One question and its answer --------------------------------------------------------------

function answerCard() {
  const card = el("article", { class: "answer" });
  const steps = el("ol", { class: "steps", "aria-label": "Steps" });
  const visuals = el("div", { class: "visuals" });
  const body = el("div", { class: "body typing" });
  const howList = el("ol");
  const how = el("details", { class: "how", hidden: "" },
    el("summary", { text: "How I got this" }),
    el("p", { class: "muted", text: "The tools that ran, their inputs, and the numbers they returned with source and date." }),
    howList,
  );
  // A closed panel has no width, so its tables are marked when it opens (and again on resize).
  how.addEventListener("toggle", () => { if (how.open) markScrollers(how); });
  card.append(steps, visuals, body, how);
  return { card, steps, visuals, body, how, howList };
}

// A tool step in an answer card: a step line on "tool_start"; on "tool_result" the step is ticked
// and its table, score bars and "How I got this" entry are drawn.
// Typed and spoken answers share it.
function showTool(view, event, data) {
  if (event === "tool_start") {
    const label = STEP_LABELS[data.name] || data.name;
    view.steps.append(el("li", { text: `${label} (${describeArgs(data.args)})…` }));
    return;
  }
  const item = Array.from(view.steps.children).find(
    (i) => !i.classList.contains("done") && !i.classList.contains("failed"),
  );
  if (item) {
    item.textContent = item.textContent.replace(/…$/, "");
    item.classList.add(data.result.error ? "failed" : "done");
  }
  if (!data.result.error && Array.isArray(data.result.rows) && data.result.rows.length) {
    view.visuals.append(rankingView(data.name, data.result));
  }
  view.howList.append(howItem(data.name, data.args, data.result));
  view.how.hidden = false;
  if (view.how.open) markScrollers(view.how); // an open panel: mark the new table and renumber all
}

async function ask({ message = "", calls = [], label }) {
  if (state.busy) return;
  state.busy = true;
  setBusy(true);
  $("#welcome").hidden = true;
  const log = $("#log");
  log.append(el("div", { class: "you", text: label || message }));
  const view = answerCard();
  log.append(view.card);
  scrollDown();

  let text = "";
  let pending = false;
  let finished = false;
  const draw = () => {
    pending = false;
    view.body.replaceChildren(render(text));
  };
  const fail = (messageText) => {
    // Draw what arrived once, and stop any frame already queued, so it cannot replace the marked tables.
    finished = true;
    draw();
    view.body.classList.remove("typing");
    markScrollers(view.body);
    view.card.append(el("div", { class: "error", role: "alert", text: messageText }));
  };

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, calls, history: state.history, version: state.version }),
    });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({}));
      // A refused request (422) sends a list of {msg, ...}; show the messages, minus pydantic's prefix.
      const messages = Array.isArray(problem.detail)
        ? problem.detail.map((d) => String((d && d.msg) || "").replace(/^Value error, /, "")).filter(Boolean)
        : [];
      const detail =
        typeof problem.detail === "string"
          ? problem.detail
          : messages.length
            ? messages.join(" ")
            : `The server answered ${response.status}.`;
      fail(detail);
      return;
    }
    for await (const { event, data } of readEvents(response)) {
      if (event === "tool_start" || event === "tool_result") {
        showTool(view, event, data);
      } else if (event === "text") {
        text += data.text;
        if (!pending) {
          pending = true;
          // A frame queued before "done" must not redraw over the finished, marked-up answer.
          requestAnimationFrame(() => { if (!finished) draw(); });
        }
      } else if (event === "done") {
        text = data.text;
        finished = true;
        draw();
        view.body.classList.remove("typing");
        markScrollers(view.body);
        if (message && !calls.length && state.info?.model) {
          state.history.push({ role: "user", text: message }, { role: "model", text: data.text.slice(0, MAX_TURN_CHARS) });
          state.history = trimHistory(state.history);
        }
      } else if (event === "error") {
        fail(data.message);
      }
      scrollDown();
    }
  } catch (error) {
    fail(`The connection failed (${error.message}). Try again.`);
  } finally {
    view.body.classList.remove("typing");
    state.busy = false;
    setBusy(false);
  }
}

function setBusy(busy) {
  const model = state.info?.model;
  $("#send").disabled = busy || !model;
  $("#question").disabled = busy || !model;
  for (const button of document.querySelectorAll(".suggestion, #picker-form button")) button.disabled = busy;
}

// --- Header: versions and data freshness -------------------------------------------------------

async function loadInfo(version) {
  const response = await fetch(`/info?version=${encodeURIComponent(version)}`);
  const info = await response.json();
  if (!response.ok) throw new Error(info.detail || `The server answered ${response.status}.`);
  state.info = info;
  state.version = version;

  const select = $("#version");
  select.replaceChildren(
    ...info.versions.map((v) => el("option", { value: v, text: v === "latest" ? `Latest (${info.version})` : v })),
  );
  select.value = version;

  const stale = info.sources.filter((s) => s.stale);
  $("#fresh").classList.toggle("stale", stale.length > 0);
  $("#fresh-summary").textContent = stale.length
    ? `Data as of ${info.as_of}: ${stale.length} source${stale.length > 1 ? "s" : ""} stale`
    : `Data as of ${info.as_of}`;
  $("#fresh-list").replaceChildren(
    ...info.sources.map((s) =>
      el("li", { class: s.stale ? "stale" : "", text: `${s.source}: as of ${s.as_of}${s.stale ? " (stale)" : ""}` }),
    ),
  );
  $("#fresh-rule").textContent =
    `Stale (amber) means a source's newest data ends more than ${info.stale_after_months} months ` +
    `before ${info.stale_reference}. Set in config/sources.yaml (freshness.stale_after_months).`;
  return info;
}


// --- Start ------------------------------------------------------------------------------------

// The full hint is in index.html; a phone gets a shorter one so it never wraps onto a hidden line.
let hintFollowsWidth = true;
function setUpHint() {
  const box = $("#question");
  const full = box.placeholder;
  const narrow = matchMedia("(max-width: 700px)");
  const update = () => {
    if (hintFollowsWidth) box.placeholder = narrow.matches ? "Ask about airports…" : full;
  };
  narrow.addEventListener("change", update);
  update();
  // Tables may start or stop overflowing when the width changes (rotating a phone).
  addEventListener("resize", () => {
    for (const body of document.querySelectorAll(".answer .body:not(.typing)")) markScrollers(body);
    for (const panel of document.querySelectorAll(".answer details.how[open]")) markScrollers(panel);
  });
}

async function start() {
  setUpHint();
  const submit = setUpQuestionBox();
  setUpPicker();
  $("#version").addEventListener("change", async (event) => {
    const before = state.version;
    try {
      await loadInfo(event.target.value);
      $("#log").append(el("p", { class: "note", text: `Now answering from data version ${event.target.value}.` }));
    } catch (error) {
      event.target.value = before; // keep showing the version the answers still come from
      $("#log").append(el("div", { class: "error", role: "alert", text: error.message }));
    }
  });
  try {
    setUpChoices(await loadInfo("latest"));
    setUpDataPanel();
    setUpMicrophone(submit);
    setUpTalk();
  } catch (error) {
    $("#fresh-summary").textContent = "No data";
    $("#log").append(el("div", { class: "error", role: "alert", text: error.message }));
  }
}

start();
