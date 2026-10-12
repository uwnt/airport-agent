// The chat page: sends a question to POST /chat and draws the server-sent events it gets back.
// Tables, score bars and "How I got this" are drawn from tool results only, never from the
// model's text. Model text is Markdown: always rendered with marked, then cleaned by DOMPurify.
"use strict";

const $ = (selector) => document.querySelector(selector);
// The server accepts at most 40 earlier turns of 20,000 characters each (ChatRequest in server.py):
// keep the most recent ones, so a long conversation never starts failing.
const MAX_TURNS = 40;
const MAX_TURN_CHARS = 20000;

// On a site with an access code, the code entered is kept for this browser tab only. Storage can
// be blocked (private windows, strict settings): then it lasts until the page is reloaded.
const CODE_KEY = "airport-agent-access-code";
function storedCode() {
  try { return sessionStorage.getItem(CODE_KEY) || ""; } catch { return ""; }
}
function storeCode(code) {
  try { sessionStorage.setItem(CODE_KEY, code); } catch { /* kept in memory only */ }
}
function forgetCode() {
  state.code = "";
  try { sessionStorage.removeItem(CODE_KEY); } catch { /* nothing stored */ }
}

const state = { info: null, version: "latest", history: [], busy: false, code: storedCode() };

function codeHeaders() {
  return state.code ? { "X-Access-Code": state.code } : {};
}

// Free-form questions (and voice) need the model, and on a site with an access code, the code.
function freeQuestions() {
  const info = state.info;
  return Boolean(info?.model && (!info.access_code_required || info.access_ok));
}

const STEP_LABELS = {
  rank_airports: "Ranking airports",
  compare_airports: "Comparing airports",
  airport_profile: "Reading the airport profile",
  long_haul_share: "Measuring the long-haul share",
  compare_over_time: "Comparing two data versions",
  demand_pressure: "Checking demand pressure",
};
const STRAIN = ["delay", "cancellations", "fare premium"];

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
  return clean;
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

// --- Visuals from tool results ---------------------------------------------------------------

function pointsOf(row, label) {
  const signal = row.signals[label];
  return signal && typeof signal.points === "number" ? signal.points : 0;
}

function rankingView(name, result) {
  const box = el("section", { class: "ranking" });
  const where = result.region ? ` in ${result.region}` : "";
  box.append(el("h3", { text: `Ranking${where}, ${result.preset} preset` }));
  box.append(
    el("div", { class: "legend" },
      el("span", {}, el("span", { class: "key strain" }), "Strain (delay, cancellations, fares)"),
      el("span", {}, el("span", { class: "key growth" }), "Growth"),
      el("span", {}, el("span", { class: "key friction" }), "Friction penalty"),
    ),
  );
  for (const row of result.rows) {
    const strainParts = STRAIN.map((label) => [label, row.signals[label]]);
    const strain = STRAIN.reduce((sum, label) => sum + pointsOf(row, label), 0);
    const growth = pointsOf(row, "growth");
    const penalty = row.friction.points || 0;
    // Widths only: the bar is drawn from the tool's points; the labels quote the tool's numbers.
    const bar = el("div", { class: "bar", role: "img" });
    const strainSeg = el("span", { class: "seg strain" });
    const growthSeg = el("span", { class: "seg growth" });
    strainSeg.style.width = `${strain}%`;
    growthSeg.style.width = `${growth}%`;
    bar.append(strainSeg, growthSeg);
    if (penalty > 0) {
      const frictionSeg = el("span", { class: "seg friction" });
      // The hatched part covers the points the penalty took: from the score up to the score
      // before friction (shorter than the penalty when the score stopped at 0).
      frictionSeg.style.left = `${Math.max(row.score, 0)}%`;
      frictionSeg.style.width = `${Math.max(row.score_before_friction - row.score, 0)}%`;
      bar.append(frictionSeg);
    }
    const strainText = strainParts
      .map(([label, s]) => `${label} ${s && "points" in s ? s.points : "missing"}`)
      .join(", ");
    const stale = row.friction.stale ? `, ${row.friction.stale_note}` : "";
    const frictionText = penalty ? `−${penalty} (${row.friction.name}${stale})` : "none";
    bar.setAttribute(
      "aria-label",
      `${row.code}: score ${row.score}. Strain points: ${strainText}. ` +
        `Growth points: ${row.signals.growth?.points ?? "missing"}. Friction penalty: ${frictionText}.`,
    );
    const head = el("span", {}, el("b", { text: row.code }), ` ${row.name}`);
    if (row.confidence === "Low") {
      head.append(el("span", { class: "flag", text: "Low confidence", title: (row.confidence_reasons || []).join("; ") }));
    }
    box.append(
      el("div", { class: "airport" },
        el("span", { class: "rank", text: `${row.rank}` }),
        head,
        el("span", { class: "score", text: `${row.score}` }),
        bar,
        el("span", {
          class: "parts",
          text: `Strain ${strainText} · Growth ${row.signals.growth?.points ?? "missing"} · ` +
            `Friction ${frictionText} · National rank ${row.national_rank} of ${result.ranked_count}`,
        }),
      ),
    );
  }
  if (result.not_ranked?.length) {
    const list = result.not_ranked.map((n) => `${n.code} (${n.reason})`).join("; ");
    box.append(el("p", { class: "not-ranked", text: `Not ranked: ${list}` }));
  }
  return box;
}

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
  const stepItems = [];
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
      headers: { "Content-Type": "application/json", ...codeHeaders() },
      body: JSON.stringify({ message, calls, history: state.history, version: state.version }),
    });
    if (!response.ok) {
      if (response.status === 401 && state.info) {
        // The code is no longer accepted (it was changed on the server): ask for it again.
        forgetCode();
        state.info.access_ok = false;
        applyMode();
      }
      const problem = await response.json().catch(() => ({}));
      const detail = typeof problem.detail === "string" ? problem.detail : `The server answered ${response.status}.`;
      fail(detail);
      return;
    }
    for await (const { event, data } of readEvents(response)) {
      if (event === "tool_start") {
        const item = el("li", { text: `${STEP_LABELS[data.name] || data.name} (${describeArgs(data.args)})…` });
        stepItems.push(item);
        view.steps.append(item);
      } else if (event === "tool_result") {
        const item = stepItems.find((i) => !i.classList.contains("done") && !i.classList.contains("failed"));
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
        if (message && !calls.length && freeQuestions()) {
          state.history.push({ role: "user", text: message }, { role: "model", text: data.text.slice(0, MAX_TURN_CHARS) });
          state.history = state.history.slice(-MAX_TURNS);
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
  const free = freeQuestions();
  $("#send").disabled = busy || !free;
  $("#question").disabled = busy || !free;
  for (const button of document.querySelectorAll(".suggestion, #picker-form button")) button.disabled = busy;
}

// --- Header: versions and data freshness -------------------------------------------------------

async function loadInfo(version) {
  const response = await fetch(`/info?version=${encodeURIComponent(version)}`, { headers: codeHeaders() });
  const info = await response.json();
  if (!response.ok) throw new Error(info.detail || `The server answered ${response.status}.`);
  if (info.access_code_required && !info.access_ok && state.code) forgetCode();
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

function setUpChoices(info) {
  $("#suggestions").replaceChildren(
    ...info.questions.map((question) => {
      const button = el("button", { type: "button", class: "suggestion", text: question });
      button.addEventListener("click", () => ask({ message: question }));
      return button;
    }),
  );
  $("#pick-region").replaceChildren(...info.regions.map((r) => el("option", { value: r, text: r })));
  $("#pick-preset").replaceChildren(...info.presets.map((p) => el("option", { value: p, text: p })));

  applyMode();
}

// Free questions on or off: the note, the access code field, the question box and the microphone.
function applyMode() {
  const info = state.info;
  const note = $("#mode-note");
  const free = freeQuestions();
  $("#access").hidden = !(info.model && !free);
  $("#mic").hidden = !(micSupported && free);
  if (free) {
    note.hidden = true;
    hintFollowsWidth = true;
    updateHint();
  } else {
    note.hidden = false;
    note.textContent = info.model
      ? "Free-form questions on this site need an access code. Without it, the suggested " +
        "questions and the picker still run the tools and show their results."
      : "No model is connected (no Gemini API key on the server), so free-form questions are off. " +
        "The suggested questions and the picker still run the tools and show their results.";
    $("#question").placeholder = info.model ? "Needs the access code" : "Needs the model";
    hintFollowsWidth = false;
    // Open on wide screens only: on a phone it would cover the suggested questions.
    $("#picker").open = matchMedia("(min-width: 700px)").matches;
  }
  setBusy(state.busy);
}

// --- Access code (a public site) ---------------------------------------------------------------

function setUpAccess() {
  $("#access-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const input = $("#access-code");
    const code = input.value.trim();
    if (!code) {
      input.focus();
      return;
    }
    state.code = code;
    try {
      await loadInfo(state.version); // the server says whether the code is right
    } catch (error) {
      $("#log").append(el("div", { class: "error", role: "alert", text: error.message }));
      return;
    }
    input.value = "";
    applyMode();
    if (state.info.access_ok) {
      storeCode(code);
      $("#question").focus();
    } else {
      $("#mode-note").textContent = "That access code was not accepted. Check it and try again.";
      input.focus();
    }
  });
}

// --- Picker: rank / compare / profile without the model ---------------------------------------

function setUpPicker() {
  const action = $("#pick-action");
  const update = () => {
    const kind = action.value;
    $("#pick-region-field").hidden = kind !== "rank";
    $("#pick-codes-field").hidden = kind === "rank";
    $("#pick-preset-field").hidden = kind === "profile";
    $("#pick-codes-label").textContent = kind === "profile" ? "Airport code" : "Airport codes";
    $("#pick-codes").placeholder = kind === "profile" ? "SFO" : "LAX, SNA";
  };
  action.addEventListener("change", update);
  update();
  $("#picker-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const kind = action.value;
    const preset = $("#pick-preset").value;
    const codes = $("#pick-codes").value.split(/[\s,]+/).map((c) => c.trim().toUpperCase()).filter(Boolean);
    let call;
    if (kind === "rank") {
      call = { name: "rank_airports", args: { region: $("#pick-region").value, preset } };
    } else if (!codes.length) {
      $("#pick-codes").focus();
      return;
    } else if (kind === "compare") {
      call = { name: "compare_airports", args: { codes, preset } };
    } else {
      call = { name: "airport_profile", args: { code: codes[0] } };
    }
    ask({ calls: [call], label: `${STEP_LABELS[call.name]}: ${describeArgs(call.args)}` });
  });
}

// --- Question box and push-to-talk ------------------------------------------------------------

function setUpQuestionBox() {
  const box = $("#question");
  const submit = () => {
    const message = box.value.trim();
    if (!message) return;
    box.value = "";
    box.style.height = "";
    ask({ message });
  };
  $("#ask").addEventListener("submit", (event) => {
    event.preventDefault();
    submit();
  });
  box.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  });
  box.addEventListener("input", () => {
    box.style.height = "";
    box.style.height = `${box.scrollHeight}px`;
  });
  return submit;
}

// Hold the button (or Space / Enter on it) to talk; on release the words are asked.
// The Web Speech API runs in Chrome and Edge, on localhost or HTTPS; elsewhere the button stays hidden.
let micSupported = false;
function setUpMicrophone(submit) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const button = $("#mic");
  if (!Recognition) return;
  micSupported = true;
  button.hidden = !freeQuestions(); // shown later too, once the access code is entered
  const box = $("#question");
  let recognition = null;
  let sendWhenDone = false;

  const start = () => {
    if (recognition || state.busy) return;
    recognition = new Recognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      box.value = Array.from(event.results, (r) => r[0].transcript).join("");
    };
    recognition.onend = () => {
      recognition = null;
      button.classList.remove("listening");
      button.setAttribute("aria-pressed", "false");
      if (sendWhenDone) submit();
    };
    recognition.onerror = (event) => {
      sendWhenDone = false;
      if (event.error === "not-allowed") {
        hintFollowsWidth = false; // keep this message when the screen is rotated
        box.placeholder = "Microphone access was refused";
      }
    };
    sendWhenDone = false;
    button.classList.add("listening");
    button.setAttribute("aria-pressed", "true");
    recognition.start();
  };
  const stop = () => {
    if (!recognition) return;
    sendWhenDone = true;
    recognition.stop();
  };
  button.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    button.setPointerCapture(event.pointerId);
    start();
  });
  button.addEventListener("pointerup", stop);
  button.addEventListener("pointercancel", stop);
  button.addEventListener("keydown", (event) => {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      start();
    }
  });
  button.addEventListener("keyup", (event) => {
    if (event.key === " " || event.key === "Enter") stop();
  });
}

// --- Start ------------------------------------------------------------------------------------

// The full hint is in index.html; a phone gets a shorter one so it never wraps onto a hidden line.
let hintFollowsWidth = true;
let updateHint = () => {};
function setUpHint() {
  const box = $("#question");
  const full = box.placeholder;
  const narrow = matchMedia("(max-width: 700px)");
  updateHint = () => {
    if (hintFollowsWidth) box.placeholder = narrow.matches ? "Ask about airports…" : full;
  };
  narrow.addEventListener("change", () => updateHint());
  updateHint();
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
  setUpAccess();
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
    setUpMicrophone(submit);
  } catch (error) {
    $("#fresh-summary").textContent = "No data";
    $("#log").append(el("div", { class: "error", role: "alert", text: error.message }));
  }
}

start();
