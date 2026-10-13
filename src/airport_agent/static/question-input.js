// The ways to ask without Talk mode: suggested questions, the picker (no model needed), the
// question box and push-to-talk. Loaded before app.js (see index.html); app.js sets them up at
// start and each one asks through its `ask`.
"use strict";

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
