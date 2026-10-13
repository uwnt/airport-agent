// Talk mode: a spoken conversation over the WebSocket /talk.
// The server relays between this page and the model, so no key ever reaches the browser.
// Microphone audio goes up as 16 kHz 16-bit PCM (made by talk-worklet.js); the model's speech
// comes back as 24 kHz 16-bit PCM in binary frames, everything else as JSON events, with the
// typed chat's tool events, so tables are drawn by the same code (showTool).
// Loaded before app.js (see index.html); app.js calls setUpTalk at start.
"use strict";

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
