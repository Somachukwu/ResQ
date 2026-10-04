/* Civilian mobile triage — conversational first aid, sensing, offline resilience */
import "./resq-theme.js";
import { PROTOCOLS, cacheProtocols, readCachedProtocols, matchProtocols, detectHazards } from "./resq-protocols.js";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const el = {
  hero: $("#hero"),
  session: $("#session"),
  sos: $("#sos"),
  stream: $("#stream"),
  form: $("#composer"),
  field: $("#field"),
  mic: $("#mic"),
  camera: $("#camera"),
  photo: $("#photo"),
  quick: $("#quick"),
  reassure: $("#reassure"),
  eta: $("#eta"),
  gps: $("#gps"),
  gpsBtn: $("#gpsBtn"),
  gpsPulse: $("#gpsPulse"),
  net: $("#net"),
  netPulse: $("#netPulse"),
  netHeaderPulse: $("#netHeaderPulse"),
  netHeaderText: $("#netHeaderText"),
  liveActions: $("#liveActions"),
  drawer: $("#drawer"),
  drawerList: $("#drawerList"),
};

const state = {
  started: false,
  coords: { lat: 6.4520, lng: 7.5100, acc: 10 }, // Default calibrated to Enugu City
  incidentUuid: null,
  hazards: [],
  victims: 1,
  dispatched: false,
  etaSeconds: 0,
  chatHistory: [],
  etaInterval: null,
};

const icons = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
};
const escapeHTML = (value) => String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);

/* ---------------- boot ---------------- */
try {
  cacheProtocols();
  renderOfflineLibrary();
  watchNetwork();
  wireKeyboardAccommodation();
  requestLocation(); // Immediate geolocation acquisition on page load
} catch (err) {
  console.warn("ResQ civilian setup note:", err);
}

/* ---------------- session ---------------- */
export function startSession(e) {
  if (e) {
    if (typeof e.preventDefault === "function") e.preventDefault();
    if (typeof e.stopPropagation === "function") e.stopPropagation();
  }
  if (state.started) return;
  state.started = true;
  if (el.hero) el.hero.classList.add("is-hidden");
  if (el.session) el.session.classList.add("is-active");
  try {
    el.field?.focus({ preventScroll: true });
  } catch (_) {}

  if (!state.incidentUuid) {
    state.incidentUuid = "INC-" + Math.random().toString(36).substring(2, 9).toUpperCase();
    if (window._resqCivSocket) {
      window._resqCivSocket.emit("join", { room: `incident_${state.incidentUuid}` });
    }
    fetch("/api/incidents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        incident_uuid: state.incidentUuid,
        title: "Live Bystander SOS",
        location_name: "Enugu Scene",
        lat: state.coords?.lat || 6.4520,
        lng: state.coords?.lng || 7.5100,
        casualties_count: 1
      })
    }).catch(() => {});
  }

  say(
    "resq",
    "I am right here with you. Describe what you see, or choose one of the quick options below. Your location is being transmitted directly to the Emergency Command Center in Enugu."
  );
  try {
    requestLocation();
  } catch (_) {}
}

window.startSession = startSession;

if (el.sos) {
  el.sos.addEventListener("click", startSession);
  el.sos.addEventListener("pointerup", (e) => {
    if (e.pointerType === "touch" || e.pointerType === "pen") {
      startSession(e);
    }
  });
}
el.gpsBtn?.addEventListener("click", requestLocation);
el.form?.addEventListener("submit", onSubmit);
el.field?.addEventListener("input", autoGrow);
el.field?.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    el.form.requestSubmit();
  }
});
el.camera?.addEventListener("click", () => el.photo.click());
el.photo?.addEventListener("change", onPhoto);
el.mic?.addEventListener("click", toggleVoice);
el.quick?.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  el.field.value = chip.dataset.say;
  el.form.requestSubmit();
});
$$("[data-open-drawer]").forEach((b) => b.addEventListener("click", () => el.drawer.classList.add("is-open")));
$$("[data-close-drawer]").forEach((b) => b.addEventListener("click", () => el.drawer.classList.remove("is-open")));

$("#callResponder")?.addEventListener("click", () => triggerVoiceBridge("civilian_to_command"));

function onSubmit(e) {
  e.preventDefault();
  const text = el.field.value.trim();
  if (!text) return;
  el.field.value = "";
  autoGrow();
  say("me", text);
  respond(text);
}

function respond(text) {
  const hazards = detectHazards(text);
  const newHazards = hazards.filter((h) => !state.hazards.includes(h));
  state.hazards.push(...newHazards);
  const thinking = showTyping();

  const count = text.match(/\b(two|three|four|2|3|4|5)\b/i);
  if (count) state.victims = Math.max(state.victims, parseInt(count[1], 10) || wordToNum(count[1]));

  state.chatHistory.push({ role: "user", text: text });

  const chatEndpoint = window.RESQ_CONFIG?.getApiEndpoint("/api/civilian/chat") || "/api/civilian/chat";
  fetch(chatEndpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: text,
      lat: state.coords?.lat,
      lng: state.coords?.lng,
      incident_uuid: state.incidentUuid,
      history: state.chatHistory.slice(0, -1),
      eta_seconds: state.etaSeconds
    })
  })
  .then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then((data) => {
    thinking.remove();
    if (data.incident_uuid) {
      const isNewIncident = !state.incidentUuid;
      state.incidentUuid = data.incident_uuid;
      if (isNewIncident && window._resqCivSocket) {
        window._resqCivSocket.emit("join", { room: `incident_${state.incidentUuid}` });
      }
    }

    if (data.reassurance_message) {
      state.chatHistory.push({ role: "model", text: data.reassurance_message });
    }

    const replyText = data.reassurance_message || "I am right here with you. Take a slow, gentle breath.";
    say("resq", replyText);

    const steps = (data.first_aid_steps && Array.isArray(data.first_aid_steps) && data.first_aid_steps.length > 0)
      ? data.first_aid_steps
      : null;

    if (steps) {
      renderProtocol({
        title: "Immediate Life-Saving Guidance",
        summary: data.clinical_synthesis || "Follow each action step carefully",
        steps: steps
      });
    }

    if (data.assessment_questions && Array.isArray(data.assessment_questions) && data.assessment_questions.length > 0) {
      renderAssessmentQuestions(data.assessment_questions);
    }
  })
  .catch((err) => {
    thinking.remove();
    console.warn("[Civilian] Backend chat request failed, engaging local offline protocol engine:", err);
    fallbackOfflineEngine(text);
  });
}

function fallbackOfflineEngine(text) {
  const matches = matchProtocols(text);
  if (matches.length > 0) {
    say("resq", opening(matches));
    matches.forEach(renderProtocol);
  } else {
    say("resq", "Keep the person still and warm. I am monitoring your connection.");
  }
}

function renderAssessmentQuestions(questions) {
  if (!questions || !questions.length) return;
  const container = document.createElement("div");
  container.className = "assessment-container";

  questions.forEach(q => {
    const card = document.createElement("div");
    card.className = "assessment-card";
    card.innerHTML = `
      <div class="assessment-q">
        <span class="pulse pulse--teal" aria-hidden="true"></span>
        <p>${escapeHTML(q.question)}</p>
      </div>
      <div class="assessment-chips"></div>
    `;

    const chipsEl = card.querySelector(".assessment-chips");
    (q.options || []).forEach(opt => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip chip--assessment";
      btn.textContent = opt;
      btn.addEventListener("click", () => {
        chipsEl.querySelectorAll(".chip--assessment").forEach(c => {
          c.classList.remove("is-selected");
          c.disabled = true;
          c.style.opacity = "0.5";
        });
        btn.classList.add("is-selected");
        btn.style.opacity = "1";
        say("me", opt);
        respond(opt);
      });
      chipsEl.appendChild(btn);
    });

    container.appendChild(card);
  });

  el.stream.appendChild(container);
  scroll();
}

function opening(protocols) {
  const names = protocols.map((p) => p.title.toLowerCase()).join(" and ");
  return `Understood. Work through the ${names} steps below, one at a time. Tap each step as you finish it.`;
}

function wordToNum(w) {
  return { two: 2, three: 3, four: 4 }[String(w).toLowerCase()] || 1;
}

/* ---------------- rendering ---------------- */
function say(who, text, extraNode) {
  const wrap = document.createElement("div");
  let roleClass = "resq";
  let labelText = "ResQ Clinical Guide";

  if (who === "me") {
    roleClass = "me";
    labelText = "You";
  } else if (who === "commander" || who === "dispatch") {
    roleClass = "dispatch";
    labelText = who === "commander" ? "📡 Emergency Commander" : "🚑 Dispatch Unit";
  }

  wrap.className = `msg msg--${roleClass}`;
  wrap.innerHTML = `<p class="msg__who">${labelText}</p><div class="msg__bubble"></div>`;
  wrap.querySelector(".msg__bubble").textContent = text;
  if (extraNode) wrap.querySelector(".msg__bubble").appendChild(extraNode);
  el.stream.appendChild(wrap);
  scroll();
  return wrap;
}

function showTyping() {
  const wrap = document.createElement("div");
  wrap.className = "msg msg--resq msg--thinking";
  wrap.innerHTML = `
    <p class="msg__who">ResQ Clinical Guide</p>
    <div class="msg__bubble msg__bubble--thinking">
      <div class="typing-dots" aria-label="ResQ is typing">
        <span></span>
        <span></span>
        <span></span>
      </div>
    </div>`;
  el.stream.appendChild(wrap);
  scroll();
  return wrap;
}

function renderProtocol(p) {
  if (!p || !p.steps || !p.steps.length) return;

  const card = document.createElement("article");
  card.className = "protocol";
  card.style.cssText = "align-self:stretch;border-radius:16px;overflow:hidden;background:var(--surface-2);border:1px solid var(--line);box-shadow:var(--shadow-1);margin:10px 0;flex-shrink:0;";

  const head = document.createElement("header");
  head.className = "protocol__head";
  head.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface);gap:12px;";
  head.innerHTML = `
    <div style="flex:1;min-width:0;">
      <h2 style="font-size:0.95rem;font-weight:600;color:var(--text);margin:0;">${escapeHTML(p.title)}</h2>
      <p style="font-size:0.75rem;color:var(--text-3);margin:2px 0 0 0;">${escapeHTML(p.summary)}</p>
    </div>
    <span class="badge badge--teal" style="font-size:0.7rem;font-weight:600;padding:4px 10px;border-radius:999px;background:color-mix(in srgb,var(--accent) 15%,transparent);color:var(--accent);white-space:nowrap;border:1px solid var(--accent);">Action Steps</span>`;
  card.appendChild(head);

  const list = document.createElement("ol");
  list.className = "steps";
  list.style.cssText = "list-style:none;margin:0;padding:0;";

  p.steps.forEach((s, i) => {
    const text = s.replace(/^\d+[\.\)]\s*/, "");
    const row = document.createElement("li");
    row.className = "step";
    row.setAttribute("tabindex", "0");
    row.setAttribute("role", "button");
    row.setAttribute("aria-pressed", "false");
    row.style.cssText = "display:flex;align-items:center;gap:12px;padding:12px 16px;border-top:1px solid var(--line);cursor:pointer;min-height:52px;-webkit-tap-highlight-color:transparent;transition:background 160ms;";

    const num = document.createElement("span");
    num.className = "step__num";
    num.textContent = i + 1;
    num.style.cssText = "width:28px;height:28px;display:flex;align-items:center;justify-content:center;border-radius:50%;border:1.5px solid var(--line-strong);font-size:12px;font-weight:600;color:var(--text-2);flex-shrink:0;transition:all 200ms;";

    const txt = document.createElement("span");
    txt.className = "step__text";
    txt.textContent = text;
    txt.style.cssText = "flex:1;font-size:0.875rem;line-height:1.5;color:var(--text);";

    const chk = document.createElement("span");
    chk.className = "step__check";
    chk.innerHTML = icons.check;
    chk.style.cssText = "width:20px;height:20px;opacity:0;color:var(--accent);transition:opacity 200ms;flex-shrink:0;";

    row.appendChild(num);
    row.appendChild(txt);
    row.appendChild(chk);
    list.appendChild(row);

    const toggle = () => {
      const isDone = row.classList.toggle("is-done");
      row.setAttribute("aria-pressed", String(isDone));
      if (isDone) {
        num.style.background = "var(--accent)";
        num.style.borderColor = "var(--accent)";
        num.style.color = "var(--accent-ink)";
        txt.style.opacity = "0.45";
        txt.style.textDecoration = "line-through";
        chk.style.opacity = "1";
        row.style.background = "color-mix(in srgb,var(--accent) 6%,transparent)";
        if (navigator.vibrate) navigator.vibrate(14);
      } else {
        num.style.background = "";
        num.style.borderColor = "var(--line-strong)";
        num.style.color = "var(--text-2)";
        txt.style.opacity = "1";
        txt.style.textDecoration = "none";
        chk.style.opacity = "0";
        row.style.background = "";
      }
      const doneCount = list.querySelectorAll(".step.is-done").length;
      if (doneCount === p.steps.length) {
        say("resq", "Well done, all action steps completed. Stay beside the casualty, keep them calm, and monitor breathing.");
      }
    };

    row.addEventListener("click", toggle);
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggle();
      }
    });
  });

  card.appendChild(list);
  el.stream.appendChild(card);
  scroll();
}

function renderHazard(text) {
  const n = document.createElement("div");
  n.className = "hazard-note";
  n.innerHTML = `${icons.warn}<span><b>Hazard reported to dispatch.</b> </span>`;
  n.querySelector("span").append(document.createTextNode(`${text}.`));
  el.stream.appendChild(n);
  scroll();
}

function scroll() {
  el.stream.scrollTop = el.stream.scrollHeight;
  requestAnimationFrame(() => {
    el.stream.scrollTop = el.stream.scrollHeight;
  });
}

function autoGrow() {
  el.field.style.height = "auto";
  el.field.style.height = Math.min(el.field.scrollHeight, 130) + "px";
}

/* ---------------- sensing ---------------- */
function requestLocation() {
  state.coords = state.coords || { lat: 6.4520, lng: 7.5100, acc: 15 };
  if (el.gpsBtn && !state.coords) el.gpsBtn.textContent = "Locating GPS...";
  if (!("geolocation" in navigator)) {
    if (el.gpsBtn) { el.gpsBtn.textContent = "Location calibrated · Enugu"; el.gpsBtn.classList.add("is-shared"); }
    if (el.gpsPulse) { el.gpsPulse.className = "pulse pulse--teal"; }
    return;
  }
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      state.coords = { lat: pos.coords.latitude, lng: pos.coords.longitude, acc: Math.round(pos.coords.accuracy) };
      if (el.gpsBtn) {
        el.gpsBtn.textContent = `Location shared · ±${state.coords.acc} m`;
        el.gpsBtn.classList.add("is-shared");
      }
      if (el.gpsPulse) {
        el.gpsPulse.className = "pulse pulse--teal";
      }
    },
    () => {
      state.coords = { lat: 6.4520, lng: 7.5100, acc: 15 };
      if (el.gpsBtn) {
        el.gpsBtn.textContent = "Location calibrated · Enugu";
        el.gpsBtn.classList.add("is-shared");
      }
      if (el.gpsPulse) {
        el.gpsPulse.className = "pulse pulse--teal";
      }
    },
    { enableHighAccuracy: true, timeout: 5000, maximumAge: 30000 }
  );
  try {
    navigator.geolocation.watchPosition((pos) => {
      state.coords = { lat: pos.coords.latitude, lng: pos.coords.longitude, acc: Math.round(pos.coords.accuracy) };
    }, () => {}, { enableHighAccuracy: true, maximumAge: 10000 });
  } catch (_) {}
}

function onPhoto(e) {
  const file = e.target.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const preview = document.createElement("div");
    preview.className = "photo-preview";
    preview.innerHTML = `<img src="${reader.result}" alt="Scene photo" style="max-height:180px;border-radius:12px;margin:8px 0;" />`;
    say("me", "Photo of emergency scene uploaded", preview);
    uploadPhoto(reader.result);
  };
  reader.readAsDataURL(file);
}

function uploadPhoto(dataUrl) {
  const thinking = showTyping();
  const b64 = dataUrl.split(",")[1];
  const endpoint = window.RESQ_CONFIG?.getApiEndpoint("/api/civilian/upload-photo") || "/api/civilian/upload-photo";

  fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ photo_b64: b64, mime_type: "image/jpeg", incident_uuid: state.incidentUuid })
  })
  .then(res => res.json())
  .then(data => {
    thinking.remove();
    if (data.vision_result) {
      const v = data.vision_result;
      if (v.hazards_detected?.length) {
        v.hazards_detected.forEach(h => renderHazard(h));
      }
      if (v.responder_safety_advisory) {
        say("resq", `Scene analysis note: ${v.responder_safety_advisory}`);
      }
    }
  })
  .catch(() => thinking.remove());
}

let mediaRec = null;
let isRec = false;
function toggleVoice() {
  if (isRec) {
    mediaRec?.stop();
    isRec = false;
    el.mic?.classList.remove("is-active");
  } else {
    if (!navigator.mediaDevices?.getUserMedia) {
      alert("Voice transcription requires microphone access.");
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
      mediaRec = new MediaRecorder(stream);
      isRec = true;
      el.mic?.classList.add("is-active");
      mediaRec.start();
      setTimeout(() => { if (isRec) toggleVoice(); }, 7000);
    }).catch(() => {
      alert("Microphone access unavailable.");
    });
  }
}

function watchNetwork() {
  const paint = () => {
    const on = navigator.onLine;
    if (el.net) el.net.textContent = on ? "Online" : "Offline (Local Protocols)";
    if (el.netHeaderText) el.netHeaderText.textContent = on ? "Online" : "Offline";
    if (el.netPulse) {
      el.netPulse.className = on ? "pulse pulse--teal" : "pulse pulse--orange";
    }
    if (el.netHeaderPulse) {
      el.netHeaderPulse.className = on ? "pulse pulse--teal" : "pulse pulse--orange";
    }
  };
  window.addEventListener("online", paint);
  window.addEventListener("offline", paint);
  paint();
}

function renderOfflineLibrary() {
  const data = readCachedProtocols() || PROTOCOLS;
  el.drawerList.innerHTML = Object.values(data)
    .map(
      (p) => `<details class="proto-item">
        <summary class="proto-summary">
          <span class="proto-title">${p.title}</span>
          <span class="proto-cue" aria-hidden="true">
            <svg class="proto-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>
          </span>
        </summary>
        <ol class="proto-steps">${p.steps.map((s) => `<li>${s}</li>`).join("")}</ol>
      </details>`
    )
    .join("");
}

function wireKeyboardAccommodation() {
  const updateViewport = () => {
    if (!window.visualViewport) return;
    const h = window.visualViewport.height;
    document.documentElement.style.setProperty("--visual-viewport-h", `${h}px`);
    if (el.stream && state.started) {
      el.stream.scrollTop = el.stream.scrollHeight;
    }
  };
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", updateViewport);
    window.visualViewport.addEventListener("scroll", updateViewport);
    updateViewport();
  }
  el.field.addEventListener("focus", () => {
    setTimeout(() => {
      updateViewport();
      el.field.scrollIntoView({ block: "nearest", behavior: "smooth" });
      if (el.stream) el.stream.scrollTop = el.stream.scrollHeight;
    }, 250);
  });
}

/* ---------------- Synchronized ETA Ticker ---------------- */
function startSynchronizedEtaTicker() {
  if (state.etaInterval) clearInterval(state.etaInterval);
  const updateDisplay = () => {
    if (!el.eta) return;
    if (state.etaSeconds <= 0) {
      el.eta.textContent = "Arrived on Scene";
      return;
    }
    const m = Math.floor(state.etaSeconds / 60);
    const s = String(state.etaSeconds % 60).padStart(2, "0");
    el.eta.textContent = `${m}:${s}`;
  };
  updateDisplay();
  state.etaInterval = setInterval(() => {
    if (state.etaSeconds > 0) {
      state.etaSeconds -= 1;
      updateDisplay();
    }
  }, 1000);
}

/* ---------------- Phone sound synthesizer (Web Audio API) ---------------- */
const phoneSound = (() => {
  let ctx = null;
  let osc1 = null;
  let osc2 = null;
  let gain = null;
  let interval = null;

  function getCtx() {
    if (!ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) ctx = new AudioCtx();
    }
    if (ctx && ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }
    return ctx;
  }

  function stop() {
    if (interval) {
      clearInterval(interval);
      interval = null;
    }
    try {
      if (osc1) { osc1.stop(); osc1.disconnect(); osc1 = null; }
      if (osc2) { osc2.stop(); osc2.disconnect(); osc2 = null; }
      if (gain) { gain.disconnect(); gain = null; }
    } catch (_) {}
  }

  function playBeep() {
    stop();
    const ac = getCtx();
    if (!ac) return;

    function burst() {
      try {
        const now = ac.currentTime;
        const g = ac.createGain();
        g.gain.setValueAtTime(0, now);
        g.gain.linearRampToValueAtTime(0.12, now + 0.05);
        g.gain.setValueAtTime(0.12, now + 1.2);
        g.gain.linearRampToValueAtTime(0, now + 1.25);
        g.connect(ac.destination);

        const o1 = ac.createOscillator();
        const o2 = ac.createOscillator();
        o1.type = "sine";
        o2.type = "sine";
        o1.frequency.setValueAtTime(440, now);
        o2.frequency.setValueAtTime(480, now);
        o1.connect(g);
        o2.connect(g);
        o1.start(now);
        o2.start(now);
        o1.stop(now + 1.25);
        o2.stop(now + 1.25);
      } catch (_) {}
    }

    burst();
    interval = setInterval(burst, 3000);
  }

  function playIncomingRing() {
    stop();
    const ac = getCtx();
    if (!ac) return;

    function doubleRing() {
      try {
        const now = ac.currentTime;
        [0, 0.45].forEach((delay) => {
          const t = now + delay;
          const g = ac.createGain();
          g.gain.setValueAtTime(0, t);
          g.gain.linearRampToValueAtTime(0.15, t + 0.04);
          g.gain.setValueAtTime(0.15, t + 0.35);
          g.gain.linearRampToValueAtTime(0, t + 0.4);
          g.connect(ac.destination);

          const o1 = ac.createOscillator();
          const o2 = ac.createOscillator();
          o1.type = "sine";
          o2.type = "sine";
          o1.frequency.setValueAtTime(440, t);
          o2.frequency.setValueAtTime(480, t);
          o1.connect(g);
          o2.connect(g);
          o1.start(t);
          o2.start(t);
          o1.stop(t + 0.4);
          o2.stop(t + 0.4);
        });
      } catch (_) {}
    }

    doubleRing();
    interval = setInterval(doubleRing, 2600);
  }

  return { playBeep, playIncomingRing, stop };
})();

/* ---------------- WebRTC Voice Call ---------------- */
let civPeerConnection = null;
let civLocalStream = null;
let civPendingOffer = null;
let civPendingIceCandidates = [];
let civCallTimerInterval = null;
let civCallSeconds = 0;

function handleCivIceCandidate(candidate) {
  if (civPeerConnection && civPeerConnection.remoteDescription && civPeerConnection.remoteDescription.type) {
    civPeerConnection.addIceCandidate(new RTCIceCandidate(candidate)).catch((err) => {
      console.warn("[WebRTC] addIceCandidate error:", err);
    });
  } else {
    civPendingIceCandidates.push(candidate);
  }
}

async function drainCivIceCandidates() {
  if (!civPeerConnection || !civPeerConnection.remoteDescription) return;
  while (civPendingIceCandidates.length > 0) {
    const cand = civPendingIceCandidates.shift();
    try {
      await civPeerConnection.addIceCandidate(new RTCIceCandidate(cand));
    } catch (err) {
      console.warn("[WebRTC] Error adding buffered ICE candidate:", err);
    }
  }
}

function startCivCallTimer() {
  civCallSeconds = 0;
  const timerEl = document.getElementById("civVoiceModalTimer");
  if (timerEl) timerEl.textContent = "00:00";
  if (civCallTimerInterval) clearInterval(civCallTimerInterval);
  civCallTimerInterval = setInterval(() => {
    civCallSeconds += 1;
    const m = Math.floor(civCallSeconds / 60);
    const s = civCallSeconds % 60;
    const tEl = document.getElementById("civVoiceModalTimer");
    if (tEl) tEl.textContent = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }, 1000);
}

function stopCivCallTimer() {
  if (civCallTimerInterval) {
    clearInterval(civCallTimerInterval);
    civCallTimerInterval = null;
  }
}

function updateVoiceBridgeStatus(text) {
  const statusEl = document.getElementById("civVoiceModalStatus");
  if (statusEl) statusEl.textContent = text;
}

function initCivVoiceModalListeners() {
  const ansBtn = document.getElementById("civAnswerCallBtn");
  if (ansBtn && !ansBtn._resqBound) {
    ansBtn._resqBound = true;
    ansBtn.addEventListener("click", () => answerIncomingCall());
  }
  const endBtn = document.getElementById("civEndCallBtn");
  if (endBtn && !endBtn._resqBound) {
    endBtn._resqBound = true;
    endBtn.addEventListener("click", () => {
      phoneSound.stop();
      endCivVoiceModalUI();
    });
  }
}

function showCivVoiceModalUI(title, statusText, timerText, showAnswerBtn = false, endLabel = "End Call") {
  initCivVoiceModalListeners();
  const modal = document.getElementById("civVoiceModal");
  const target = document.getElementById("civVoiceModalTitle");
  const status = document.getElementById("civVoiceModalStatus");
  const timer = document.getElementById("civVoiceModalTimer");
  const ansBtn = document.getElementById("civAnswerCallBtn");
  const endLabelEl = document.getElementById("civEndCallLabel");

  if (modal) {
    modal.style.display = "flex";
    modal.classList.remove("hidden");
  }
  if (target) target.textContent = title || "Emergency Operator";
  if (status) status.textContent = statusText || "Connecting live audio link...";
  if (timer) timer.textContent = timerText || "00:00";
  if (ansBtn) {
    ansBtn.style.display = showAnswerBtn ? "inline-flex" : "none";
    ansBtn.classList.toggle("hidden", !showAnswerBtn);
  }
  if (endLabelEl) endLabelEl.textContent = endLabel;
}

function endCivVoiceModalUI() {
  const modal = document.getElementById("civVoiceModal");
  if (modal) {
    modal.style.display = "none";
    modal.classList.add("hidden");
  }
  const ansBtn = document.getElementById("civAnswerCallBtn");
  if (ansBtn) {
    ansBtn.style.display = "none";
    ansBtn.classList.add("hidden");
  }
  stopCivCallTimer();
  endWebRtcCall();
}

function showVoiceBridgeModal(statusText, mode = "active") {
  if (mode === "calling") {
    showCivVoiceModalUI("Calling Emergency Command...", statusText || "Connecting audio link to operator station...", "--:--", false, "Cancel Call");
  } else if (mode === "incoming") {
    showCivVoiceModalUI("Incoming Call from Command", statusText || "Emergency Operator calling scene...", "Ringing...", true, "Decline");
  } else {
    showCivVoiceModalUI("Connected to Emergency Command", statusText || "Audio channel connected · Encrypted", "00:00", false, "End Call");
  }
}

async function getSafeAudioStream() {
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    try {
      return await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      console.warn("[WebRTC-CIV] Microphone capture unavailable, using fallback audio stream:", err);
    }
  }
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const dst = ctx.createMediaStreamDestination();
    const gain = ctx.createGain();
    gain.gain.value = 0;
    osc.connect(gain);
    gain.connect(dst);
    osc.start();
    return dst.stream;
  } catch (synthErr) {
    console.warn("[WebRTC-CIV] Fallback audio creation error:", synthErr);
    return new MediaStream();
  }
}

async function answerIncomingCall() {
  phoneSound.stop();
  if (!civPendingOffer || !civPendingOffer.sdp) {
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 100));
      if (civPendingOffer && civPendingOffer.sdp) break;
    }
  }
  if (!civPendingOffer || !civPendingOffer.sdp) {
    console.warn("[WebRTC-CIV] No pending offer available to answer.");
    return;
  }

  const ansBtn = document.getElementById("civAnswerCallBtn");
  if (ansBtn) {
    ansBtn.style.display = "none";
    ansBtn.classList.add("hidden");
  }
  const endLabel = document.getElementById("civEndCallLabel");
  if (endLabel) endLabel.textContent = "End Call";
  updateVoiceBridgeStatus("Audio channel connected · Encrypted");

  // Pre-unlock remote audio in direct user click gesture
  let remoteAudio = document.getElementById("civRemoteAudio");
  if (!remoteAudio) {
    remoteAudio = document.createElement("audio");
    remoteAudio.id = "civRemoteAudio";
    remoteAudio.autoplay = true;
    remoteAudio.playsInline = true;
    remoteAudio.muted = false;
    document.body.appendChild(remoteAudio);
  }
  remoteAudio.play().catch(() => {});

  civLocalStream = await getSafeAudioStream();

  const config = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
  civPeerConnection = new RTCPeerConnection(config);
  civLocalStream.getTracks().forEach((track) => civPeerConnection.addTrack(track, civLocalStream));

  civPeerConnection.ontrack = (event) => {
    let audio = document.getElementById("civRemoteAudio");
    if (!audio) {
      audio = document.createElement("audio");
      audio.id = "civRemoteAudio";
      audio.autoplay = true;
      audio.playsInline = true;
      audio.muted = false;
      document.body.appendChild(audio);
    }
    if (event.streams && event.streams[0]) {
      audio.srcObject = event.streams[0];
    } else {
      const inboundStream = new MediaStream();
      inboundStream.addTrack(event.track);
      audio.srcObject = inboundStream;
    }
    audio.play().catch((e) => console.warn("[WebRTC] Audio play error:", e));
  };

  civPeerConnection.onicecandidate = (event) => {
    if (event.candidate && window._resqCivSocket) {
      window._resqCivSocket.emit("webrtc:signal", {
        incident_uuid: civPendingOffer.incident_uuid || state.incidentUuid,
        from: "civilian",
        type: "ice-candidate",
        candidate: event.candidate
      });
    }
  };

  try {
    await civPeerConnection.setRemoteDescription(new RTCSessionDescription(civPendingOffer.sdp));
    await drainCivIceCandidates();
    const answer = await civPeerConnection.createAnswer();
    await civPeerConnection.setLocalDescription(answer);
    if (window._resqCivSocket) {
      window._resqCivSocket.emit("webrtc:signal", {
        incident_uuid: civPendingOffer.incident_uuid || state.incidentUuid,
        from: "civilian",
        type: "answer",
        sdp: answer
      });
    }
    showCivVoiceModalUI("Connected to Emergency Command", "Audio channel connected · Encrypted", "00:00", false, "End Call");
    startCivCallTimer();
  } catch (err) {
    console.error("[WebRTC] Answer creation failed:", err);
    updateVoiceBridgeStatus("Call connection failed.");
  }
}

async function triggerVoiceBridge(type = "civilian_to_command") {
  showCivVoiceModalUI("Calling Emergency Command...", "Connecting audio link to operator station...", "--:--", false, "Cancel Call");
  phoneSound.playBeep();
  civPendingIceCandidates = [];

  // Pre-unlock remote audio in direct user click gesture
  let remoteAudio = document.getElementById("civRemoteAudio");
  if (!remoteAudio) {
    remoteAudio = document.createElement("audio");
    remoteAudio.id = "civRemoteAudio";
    remoteAudio.autoplay = true;
    remoteAudio.playsInline = true;
    remoteAudio.muted = false;
    document.body.appendChild(remoteAudio);
  }
  remoteAudio.play().catch(() => {});

  if (!state.incidentUuid) {
    state.incidentUuid = "INC-" + Math.random().toString(36).substring(2, 9).toUpperCase();
    if (window._resqCivSocket) {
      window._resqCivSocket.emit("join", { room: `incident_${state.incidentUuid}` });
    }
    fetch("/api/incidents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        incident_uuid: state.incidentUuid,
        title: "Live Scene Bystander Call",
        location_name: "Enugu Scene",
        lat: state.coords?.lat || 6.4520,
        lng: state.coords?.lng || 7.5100,
        casualties_count: 1
      })
    }).catch(() => {});
  }

  civLocalStream = await getSafeAudioStream();

  const config = { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
  civPeerConnection = new RTCPeerConnection(config);
  civLocalStream.getTracks().forEach((track) => civPeerConnection.addTrack(track, civLocalStream));

  civPeerConnection.ontrack = (event) => {
    let remoteAudio = document.getElementById("civRemoteAudio");
    if (!remoteAudio) {
      remoteAudio = document.createElement("audio");
      remoteAudio.id = "civRemoteAudio";
      remoteAudio.autoplay = true;
      remoteAudio.playsInline = true;
      remoteAudio.muted = false;
      document.body.appendChild(remoteAudio);
    }
    if (event.streams && event.streams[0]) {
      remoteAudio.srcObject = event.streams[0];
    } else {
      const inboundStream = new MediaStream();
      inboundStream.addTrack(event.track);
      remoteAudio.srcObject = inboundStream;
    }
    remoteAudio.play().catch((e) => console.warn("[WebRTC] Audio play error:", e));
  };

  civPeerConnection.onicecandidate = (event) => {
    if (event.candidate && window._resqCivSocket) {
      window._resqCivSocket.emit("webrtc:signal", {
        incident_uuid: state.incidentUuid,
        from: "civilian",
        type: "ice-candidate",
        candidate: event.candidate
      });
    }
  };

  civPeerConnection.onconnectionstatechange = () => {
    if (civPeerConnection.connectionState === "connected") {
      updateVoiceBridgeStatus("Audio link active with Emergency Command.");
    } else if (civPeerConnection.connectionState === "failed" || civPeerConnection.connectionState === "disconnected") {
      updateVoiceBridgeStatus("Connection lost. Reconnecting...");
    }
  };

  try {
    const offer = await civPeerConnection.createOffer();
    await civPeerConnection.setLocalDescription(offer);
    if (window._resqCivSocket) {
      window._resqCivSocket.emit("call_bridge:event", {
        incident_uuid: state.incidentUuid,
        caller: "civilian",
        active: true,
        action: "call"
      });
      window._resqCivSocket.emit("webrtc:signal", {
        incident_uuid: state.incidentUuid,
        from: "civilian",
        type: "offer",
        sdp: offer
      });
    }
  } catch (err) {
    console.error("[WebRTC] Offer creation failed:", err);
    phoneSound.stop();
    updateVoiceBridgeStatus("Call setup failed. Try again.");
  }

  if (state.incidentUuid) {
    fetch(`/api/incidents/${state.incidentUuid}/call-bridge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "start", type: type, caller: "civilian", title: "Direct Scene Caller" })
    }).catch(() => {});
  }
}

function endWebRtcCall() {
  phoneSound.stop();
  stopCivCallTimer();
  if (civPeerConnection) {
    try { civPeerConnection.close(); } catch (_) {}
    civPeerConnection = null;
  }
  if (civLocalStream) {
    civLocalStream.getTracks().forEach((t) => t.stop());
    civLocalStream = null;
  }
  civPendingOffer = null;
  civPendingIceCandidates = [];
  const remoteAudio = document.getElementById("civRemoteAudio");
  if (remoteAudio) remoteAudio.remove();

  if (state.incidentUuid) {
    fetch(`/api/incidents/${state.incidentUuid}/call-bridge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "end" })
    }).catch(() => {});
    if (window._resqCivSocket) {
      window._resqCivSocket.emit("call_bridge:event", {
        incident_uuid: state.incidentUuid,
        caller: "civilian",
        active: false,
        action: "hangup"
      });
      window._resqCivSocket.emit("webrtc:signal", {
        incident_uuid: state.incidentUuid,
        from: "civilian",
        type: "hangup"
      });
    }
  }
}

/* ---------------- WebSocket: Synchronous Multi-Role Integration ---------------- */
function initCivilianSocket() {
  if (typeof io === "undefined") {
    setTimeout(initCivilianSocket, 200);
    return;
  }
  if (window._resqCivSocket) return;
  const serverUrl = window.RESQ_CONFIG?.backendUrl || undefined;
  const sock = io(serverUrl, { transports: ["websocket", "polling"], reconnection: true });
  window._resqCivSocket = sock;

  const onCivConnected = () => {
    sock.emit("join", { room: "civilians" });
    if (state.incidentUuid) {
      sock.emit("join", { room: `incident_${state.incidentUuid}` });
    }
  };
  sock.on("connect", onCivConnected);
  if (sock.connected) onCivConnected();

  // Responder Acknowledged & Rolling -> Official Confirmation
  sock.on("civilian:dispatch_confirmed", (data) => {
    if (data.incident_uuid && data.incident_uuid !== state.incidentUuid) return;
    state.dispatched = true;
    const reassureTitle = document.getElementById("reassureTitle");
    const reassureBody = document.getElementById("reassureBody");
    const unit = data.unit_code || "AMB-01";

    if (reassureTitle) reassureTitle.textContent = `Unit ${unit} Dispatched & En Route`;
    if (el.reassure) el.reassure.classList.add("is-visible");
    if (el.liveActions) el.liveActions.classList.add("is-active");

    const etaSec = parseInt(data.eta_seconds, 10) || (parseInt(data.eta_minutes, 10) * 60) || 480;
    state.etaSeconds = etaSec;
    startSynchronizedEtaTicker();

    const mins = data.eta_minutes || Math.round(etaSec / 60);
    say("dispatch", `Unit ${unit} has confirmed dispatch and is rolling to your location. Estimated arrival: ${mins} minutes. Responders are on the road.`);
    if (navigator.vibrate) navigator.vibrate([100, 60, 100]);
  });

  // Dynamic ETA update as ambulance moves
  sock.on("civilian:eta_update", (data) => {
    if (data.incident_uuid && data.incident_uuid !== state.incidentUuid) return;
    const secs = parseInt(data.eta_seconds, 10);
    if (!isNaN(secs)) {
      state.etaSeconds = secs;
      if (el.eta) {
        const m = Math.floor(secs / 60);
        const s = String(secs % 60).padStart(2, "0");
        el.eta.textContent = `${m}:${s}`;
      }
    }
  });

  // Unit arrived on scene
  sock.on("responder:on_scene", (data) => {
    if (data.incident_uuid && data.incident_uuid !== state.incidentUuid) return;
    state.etaSeconds = 0;
    if (el.eta) el.eta.textContent = "Arrived on Scene";
    say("dispatch", `Ambulance unit ${data.unit_code || "AMB-01"} has arrived on scene. Look out for the flashing beacon and direct the crew.`);
    if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
  });

  // Direct message from Commander
  sock.on("dispatcher:message", (data) => {
    if (data.incident_uuid && state.incidentUuid && data.incident_uuid !== state.incidentUuid) return;
    if (data.incident_uuid && !state.incidentUuid) {
      state.incidentUuid = data.incident_uuid;
      sock.emit("join", { room: `incident_${state.incidentUuid}` });
    }
    say("commander", data.message || "Commander is monitoring your scene.");
    if (navigator.vibrate) navigator.vibrate(50);
  });

  // Voice Link Bridge Event
  sock.on("call_bridge:event", (data) => {
    if (data.caller === "civilian") return; // ignore own signals
    if (data.incident_uuid) {
      state.incidentUuid = data.incident_uuid;
      sock.emit("join", { room: `incident_${state.incidentUuid}` });
    }
    if (!data.active) {
      phoneSound.stop();
      endCivVoiceModalUI();
      return;
    }
    if (data.caller === "command" || data.caller === "dispatcher") {
      if (data.incident_uuid && !civPendingOffer) {
        civPendingOffer = { incident_uuid: data.incident_uuid };
      }
      phoneSound.playIncomingRing();
      showCivVoiceModalUI(
        "Incoming Call from Command",
        `Emergency Operator calling scene · Incident: ${data.incident_uuid || "Live Scene"}`,
        "Ringing...",
        true,
        "Decline"
      );
    }
  });

  // WebRTC signaling via dedicated civilian socket
  sock.on("webrtc:signal", async (data) => {
    if (data.from === "civilian") return; // ignore own signals
    try {
      if (data.type === "offer" && data.sdp) {
        // Requirement 6: If command initiates call, it should pop up immediately on civilian end
        if (data.incident_uuid) {
          state.incidentUuid = data.incident_uuid;
          sock.emit("join", { room: `incident_${state.incidentUuid}` });
        }
        civPendingOffer = data;
        civPendingIceCandidates = [];
        phoneSound.playIncomingRing();
        showCivVoiceModalUI(
          "Incoming Call from Command",
          `Emergency Operator calling scene · Incident: ${data.incident_uuid || "Live Scene"}`,
          "Ringing...",
          true,
          "Decline"
        );

      } else if (data.type === "answer" && data.sdp && civPeerConnection) {
        // Command answered civilian call
        phoneSound.stop();
        await civPeerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
        await drainCivIceCandidates();
        showCivVoiceModalUI("Emergency Command Connected", "Audio channel connected · Encrypted", "00:00", false, "End Call");
        startCivCallTimer();

      } else if (data.type === "ice-candidate" && data.candidate) {
        handleCivIceCandidate(data.candidate);

      } else if (data.type === "hangup") {
        phoneSound.stop();
        endCivVoiceModalUI();
      }
    } catch (err) {
      console.warn("[WebRTC] Signal handling error:", err);
    }
  });
}

initCivilianSocket();
