// The Data panel: who built the data on screen, and the buttons that fetch or build newer data.
// Loaded before app.js (see index.html); app.js calls setUpDataPanel at start.
"use strict";

// Polls /data/status while a job runs; when the server switches to new data, the header (and,
// if "Latest" is picked, the answers) follow it.

const JOB_NAMES = { latest: "Get latest data", local: "Refresh on this machine", github: "Refresh on GitHub Actions" };
const panel = { status: null, timer: null, shownVersion: null };

function showReason(id, option) {
  $(id).textContent = option.enabled ? "" : option.reason;
}

function runningJob(status) {
  return Object.entries(status.jobs).find(([, job]) => job.state === "running");
}

function drawPanel(status) {
  panel.status = status;
  const current = status.current;
  $("#data-version").textContent = current ? `${current.version} (as of ${current.as_of})` : "No data loaded";
  $("#data-built").textContent = current ? current.built_by : "—";
  const sources = state.version === "latest" && state.info ? state.info.sources : [];
  $("#data-asof").replaceChildren(
    ...sources.map((s) => el("li", { class: s.stale ? "stale" : "", text: `${s.source}: ${s.as_of}${s.stale ? " (stale)" : ""}` })),
  );

  const running = runningJob(status);
  const { latest, local, github } = status.options;
  showReason("#data-latest-why", latest);
  showReason("#why-local", local);
  showReason("#why-github", github);
  $("#data-latest").disabled = !latest.enabled || Boolean(running);
  for (const radio of document.querySelectorAll('input[name="refresh-on"]')) {
    radio.disabled = !status.options[radio.value].enabled;
  }
  const picked = document.querySelector('input[name="refresh-on"]:checked');
  if (!picked || picked.disabled) {
    const first = document.querySelector('input[name="refresh-on"]:not(:disabled)')
      || document.querySelector('input[name="refresh-on"]');
    first.checked = true;
  }
  const on = document.querySelector('input[name="refresh-on"]:checked');
  $("#data-refresh").disabled = on.disabled || Boolean(running);

  // The newest job's message: the running one, else the last one that finished.
  const shown = running || Object.entries(status.jobs).find(([, job]) => job.state !== "idle");
  const line = $("#data-status");
  line.classList.toggle("failed", Boolean(shown && shown[1].state === "failed"));
  if (!shown) line.textContent = "";
  else {
    const [name, job] = shown;
    const progress = job.state === "running" && job.progress ? ` (${job.progress})` : "";
    line.replaceChildren(`${JOB_NAMES[name]}: ${job.message}${progress}`);
    if (job.url && job.url.startsWith("https://")) line.append(" ", el("a", { href: job.url, target: "_blank", rel: "noopener", text: "View the run" }));
  }
}

async function refreshPanel() {
  const response = await fetch("/data/status");
  const status = await response.json();
  drawPanel(status);
  const version = status.current && status.current.version;
  if (panel.shownVersion && version && version !== panel.shownVersion && state.version === "latest") {
    await loadInfo("latest");
    drawPanel(status);
    $("#log").append(el("p", { class: "note", text: `Now answering from data version ${version}.` }));
  }
  panel.shownVersion = version;
  clearTimeout(panel.timer);
  if (runningJob(status)) panel.timer = setTimeout(() => refreshPanel().catch(() => {}), 3000);
  return status;
}

async function startDataJob(url, body) {
  const line = $("#data-status");
  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!response.ok) {
      const answer = await response.json().catch(() => ({}));
      line.classList.add("failed");
      line.textContent = answer.detail || `The server answered ${response.status}.`;
      return;
    }
    await refreshPanel();
  } catch (error) {
    line.classList.add("failed");
    line.textContent = error.message;
  }
}

function setUpDataPanel() {
  const dialog = $("#data-panel");
  const opener = $("#data-open");
  opener.addEventListener("click", () => {
    dialog.showModal(); // modal: focus stays inside, Escape closes it
    $("#data-close").focus();
    refreshPanel().catch((error) => { $("#data-status").textContent = error.message; });
  });
  $("#data-close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => opener.focus());
  for (const radio of document.querySelectorAll('input[name="refresh-on"]')) {
    radio.addEventListener("change", () => panel.status && drawPanel(panel.status));
  }
  $("#data-latest").addEventListener("click", () => startDataJob("/data/latest"));
  $("#data-refresh").addEventListener("click", () => {
    const on = document.querySelector('input[name="refresh-on"]:checked').value;
    startDataJob("/data/refresh", { on });
  });
  // The startup release check may still be running: follow it, so the header updates on its own.
  refreshPanel().catch(() => {});
}
