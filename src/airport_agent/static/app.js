// The chat page: sends a question to POST /chat and draws the server-sent events it gets back.
// Tables, score bars and "How I got this" are drawn from tool results only, never from the
// model's text. Model text is Markdown: always rendered with marked, then cleaned by DOMPurify.
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

  if (!info.model) {
    const note = $("#mode-note");
    note.hidden = false;
    note.textContent =
      "No model is connected (no Gemini API key on the server), so free-form questions are off. " +
      "The suggested questions and the picker still run the tools and show their results.";
    $("#question").placeholder = "Needs the model";
    hintFollowsWidth = false;
    // Open on wide screens only: on a phone it would cover the suggested questions.
    $("#picker").open = matchMedia("(min-width: 700px)").matches;
  }
  setBusy(false);
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
function setUpMicrophone(submit) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const button = $("#mic");
  if (!Recognition || !state.info.model) return;
  button.hidden = false;
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

// --- Talk mode: a spoken conversation over the WebSocket /talk ---------------------------------
// The server relays between this page and the model, so no key ever reaches the browser.
// Microphone audio goes up as 16 kHz 16-bit PCM (made by talk-worklet.js); the model's speech
// comes back as 24 kHz 16-bit PCM in binary frames, everything else as JSON events, with the
// typed chat's tool events, so tables are drawn by the same code (showTool).
const SPEECH_RATE = 24000;
const TALK_STATES = {
  connecting: "Connecting…",
  listening: "Listening: ask your question (headphones work best)",
  thinking: "Looking it up…",
  speaking: "Speaking…",
};

function setUpTalk() {
  const button = $("#talk");
  const status = $("#talk-status");
  if (!state.info.talk || !navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) return;
  button.hidden = false;
  let talk = null; // the session in progress

  const say = (node) => { $("#log").append(node); scrollDown(); };
  const show = (key) => {
    status.hidden = false;
    status.textContent = TALK_STATES[key];
    button.dataset.state = key;
  };
  const card = () => {
    if (!talk.view) {
      $("#welcome").hidden = true;
      talk.you = el("div", { class: "you", text: "(spoken question)" });
      talk.heard = "";
      talk.said = "";
      talk.view = answerCard();
      say(talk.you);
      say(talk.view.card);
    }
    return talk.view;
  };
  const endTurn = (t) => {
    if (!t.view) return;
    t.view.body.classList.remove("typing");
    markScrollers(t.view.body);
    if (t.heard && t.said) {
      state.history.push(
        { role: "user", text: t.heard },
        { role: "model", text: t.said.slice(0, MAX_TURN_CHARS) },
      );
      state.history = trimHistory(state.history);
    }
    t.view = null;
  };
  const play = (t, data) => {
    const pcm = new Int16Array(data, 0, data.byteLength >> 1);
    const clip = t.audio.createBuffer(1, pcm.length, SPEECH_RATE);
    const samples = clip.getChannelData(0);
    for (let i = 0; i < pcm.length; i++) samples[i] = pcm[i] / 32768;
    const source = t.audio.createBufferSource();
    source.buffer = clip;
    source.connect(t.audio.destination);
    // Each piece starts where the last one ends, so the speech has no gaps or overlaps.
    t.playAt = Math.max(t.playAt, t.audio.currentTime + 0.05);
    source.start(t.playAt);
    t.playAt += clip.duration;
    t.playing.add(source);
    source.onended = () => t.playing.delete(source);
  };
  const silence = (t) => {
    for (const source of t.playing) source.stop();
    t.playing.clear();
    t.playAt = 0;
  };
  // Close one session's socket, microphone and audio; safe to call more than once.
  const release = (t) => {
    t.socket?.close();
    for (const track of t.mic?.getTracks() || []) track.stop();
    if (t.audio.state !== "closed") t.audio.close();
  };
  const stop = (problem, note) => {
    const t = talk;
    if (!t) return;
    talk = null;
    endTurn(t);
    release(t);
    button.textContent = "Talk";
    button.setAttribute("aria-pressed", "false");
    delete button.dataset.state;
    status.hidden = true;
    if (problem) say(el("div", { class: "error", role: "alert", text: problem }));
    if (note) say(el("p", { class: "note", text: note }));
  };
  const handle = (t, { event, data }) => {
    if (event === "state") {
      show(data.state);
      if (data.state === "listening") endTurn(t);
    } else if (event === "heard") {
      card();
      t.heard += data.text;
      t.you.textContent = t.heard;
    } else if (event === "said") {
      t.said += data.text;
      card().body.replaceChildren(render(t.said));
    } else if (event === "tool_start" || event === "tool_result") {
      showTool(card(), event, data);
    } else if (event === "interrupted") {
      silence(t);
    } else if (event === "error") {
      stop(data.message);
    } else if (event === "closed") {
      stop(null, data.message);
    }
    scrollDown();
  };
  const start = async () => {
    const t = { audio: new AudioContext(), playAt: 0, playing: new Set(), view: null };
    talk = t;
    button.textContent = "Stop";
    button.setAttribute("aria-pressed", "true");
    show("connecting");
    try {
      t.mic = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
    } catch (error) {
      if (talk !== t) return release(t); // stopped meanwhile: a newer session may have started
      stop(error.name === "NotAllowedError"
        ? "Microphone access was refused. Allow it in the browser's site settings, then press Talk."
        : `The microphone could not be opened (${error.message}).`);
      return;
    }
    // After every wait, check this start was not stopped (or replaced) meanwhile; if it was,
    // close what it opened and leave the current session alone.
    if (talk !== t) return release(t);
    try {
      await t.audio.audioWorklet.addModule("/static/talk-worklet.js");
      if (talk !== t) return release(t);
      const scheme = location.protocol === "https:" ? "wss:" : "ws:";
      const version = encodeURIComponent(state.version);
      t.socket = new WebSocket(`${scheme}//${location.host}/talk?version=${version}`);
      t.socket.binaryType = "arraybuffer";
      const mic = new AudioWorkletNode(t.audio, "mic-pcm");
      t.audio.createMediaStreamSource(t.mic).connect(mic);
      mic.connect(t.audio.destination); // it outputs silence; connected so the browser runs it
      mic.port.onmessage = (event) => {
        if (t.socket.readyState === WebSocket.OPEN) t.socket.send(event.data);
      };
      t.socket.onmessage = (event) => {
        if (talk !== t) return;
        if (typeof event.data === "string") handle(t, JSON.parse(event.data));
        else play(t, event.data);
      };
      t.socket.onclose = () => {
        if (talk === t) stop("The voice connection was lost. Press Talk to start again.");
      };
    } catch (error) {
      if (talk !== t) return release(t); // only ever stop this start's own session
      stop(`Talk mode could not start (${error.message}).`);
    }
  };
  button.addEventListener("click", () => (talk ? stop() : start()));
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
    setUpMicrophone(submit);
    setUpTalk();
  } catch (error) {
    $("#fresh-summary").textContent = "No data";
    $("#log").append(el("div", { class: "error", role: "alert", text: error.message }));
  }
}

start();
