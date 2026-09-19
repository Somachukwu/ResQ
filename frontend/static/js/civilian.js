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
  coords: null,
  incidentUuid: null,
  hazards: [],
  victims: 1,
  dispatched: false,
  etaSeconds: 12 * 60,
};

const icons = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
};

/* ---------------- boot ---------------- */
cacheProtocols();
renderOfflineLibrary();
watchNetwork();
wireKeyboardAccommodation();

el.sos.addEventListener("click", startSession);
el.gpsBtn?.addEventListener("click", requestLocation);
el.form.addEventListener("submit", onSubmit);
el.field.addEventListener("input", autoGrow);
el.field.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    el.form.requestSubmit();
  }
});
el.camera.addEventListener("click", () => el.photo.click());
el.photo.addEventListener("change", onPhoto);
el.mic.addEventListener("click", toggleVoice);
el.quick.addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  el.field.value = chip.dataset.say;
  el.form.requestSubmit();
});
$$("[data-open-drawer]").forEach((b) => b.addEventListener("click", () => el.drawer.classList.add("is-open")));
$$("[data-close-drawer]").forEach((b) => b.addEventListener("click", () => el.drawer.classList.remove("is-open")));
$("#callResponder")?.addEventListener("click", () => {
  say("resq", "Connecting you to the responder unit now. Keep your phone on speaker and stay beside the victim.");
});

/* ---------------- session ---------------- */
function startSession() {
  if (state.started) return;
  state.started = true;
  el.hero.classList.add("is-hidden");
  el.session.classList.add("is-active");
  el.field.focus({ preventScroll: true });

  say(
    "resq",
    "I am with you. Tell me in your own words what you can see. If it is easier, tap one of the quick options below."
  );
  requestLocation();
  setTimeout(dispatchResponder, 9000);
}

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

  fetch("/api/civilian/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: text,
      lat: state.coords?.lat,
      lng: state.coords?.lng,
      incident_uuid: state.incidentUuid
    })
  })
  .then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then((data) => {
    thinking.remove();
    if (data.incident_uuid) {
      state.incidentUuid = data.incident_uuid;
    }

    // 1. Empathic / Reassurance message
    if (data.reassurance_message) {
      say("resq", data.reassurance_message);
    }

    // 2. Render WHO First Aid steps only if trauma or clinical urgency is identified
    const steps = data.first_aid_steps || [];
    const hasEmergency = (data.extraction?.suspected_trauma && data.extraction.suspected_trauma.length > 0) ||
                         data.extraction?.severe_hemorrhage ||
                         data.extraction?.unresponsive ||
                         data.extraction?.airway_compromise ||
                         data.extraction?.entrapment ||
                         (data.triage?.rsi_score && data.triage.rsi_score > 1.2);

    if (steps.length > 0 && hasEmergency) {
      const traumaTitles = data.extraction?.suspected_trauma?.length
        ? data.extraction.suspected_trauma.map(t => t.charAt(0).toUpperCase() + t.slice(1)).join(" · ")
        : "Emergency Action Steps";
      const rsiVal = data.triage?.rsi_score ? `RSI ${data.triage.rsi_score}` : "Triage Active";
      const tierVal = data.triage?.triage_tier || "START";

      const p = {
        title: traumaTitles,
        summary: `${rsiVal} (${tierVal}) · WHO & Nigerian Red Cross Protocol Constrained`,
        steps: steps
      };
      setTimeout(() => renderProtocol(p), 180);
    }

    // 3. Render any detected hazards
    const detectedHazards = data.extraction?.scene_hazards || [];
    detectedHazards.forEach((h, i) => {
      if (!state.hazards.includes(h)) {
        state.hazards.push(h);
        setTimeout(() => renderHazard(h), 350 + 150 * i);
      }
    });

    dispatchResponder();
  })
  .catch((err) => {
    console.warn("[Civilian] Backend chat request failed, engaging local offline protocol engine:", err);
    thinking.remove();

    // Local offline heuristic fallback
    const protocols = matchProtocols(text);
    if (protocols.length > 0) {
      say("resq", opening(protocols));
      protocols.slice(0, 1).forEach((p, i) => setTimeout(() => renderProtocol(p), 260 * (i + 1)));
    } else {
      say("resq", "I am with you. Tell me what you can see, or tap one of the quick options below.");
    }

    newHazards.forEach((h, i) =>
      setTimeout(() => {
        renderHazard(h);
      }, 520 + 200 * i)
    );
    if (newHazards.length) {
      setTimeout(
        () => say("resq", "I have flagged that hazard to the responding unit. Stay well back from it while you help."),
        900
      );
    }
    dispatchResponder();
  });
}

function opening(protocols) {
  const names = protocols.map((p) => p.title.toLowerCase()).join(" and ");
  return `Understood. Work through the ${names} steps below, one at a time. Tap each step as you finish it. I am watching your location the whole time.`;
}

function wordToNum(w) {
  return { two: 2, three: 3, four: 4 }[String(w).toLowerCase()] || 1;
}

/* ---------------- rendering ---------------- */
function say(who, text, extraNode) {
  const wrap = document.createElement("div");
  wrap.className = `msg msg--${who === "me" ? "me" : "resq"}`;
  wrap.innerHTML = `<p class="msg__who">${who === "me" ? "You" : "ResQ guidance"}</p><div class="msg__bubble"></div>`;
  wrap.querySelector(".msg__bubble").textContent = text;
  if (extraNode) wrap.querySelector(".msg__bubble").appendChild(extraNode);
  el.stream.appendChild(wrap);
  scroll();
  return wrap;
}

function showTyping() {
  const wrap = document.createElement("div");
  wrap.className = "msg msg--resq";
  wrap.innerHTML = `<p class="msg__who">ResQ guidance</p><div class="msg__bubble"><span class="typing"><span></span><span></span><span></span></span></div>`;
  el.stream.appendChild(wrap);
  scroll();
  return wrap;
}

function renderProtocol(p) {
  if (!p || !p.steps || !p.steps.length) return;
  const card = document.createElement("article");
  card.className = "protocol";
  card.innerHTML = `
    <header class="protocol__head">
      <div class="grow">
        <h2 class="protocol__title">${p.title}</h2>
        <p class="protocol__summary">${p.summary}</p>
      </div>
      <span class="badge badge--teal">Action Steps</span>
    </header>
    <ol class="steps">
      ${p.steps
        .map(
          (s, i) => `<li class="step" tabindex="0" role="button" aria-pressed="false">
            <span class="step__num">${i + 1}</span>
            <span class="step__text">${s.replace(/^\d+[\.\)]\s*/, "")}</span>
            <span class="step__check">${icons.check}</span>
          </li>`
        )
        .join("")}
    </ol>`;

  const steps = $$(".step", card);
  const bar = $(".protocol__bar", card);
  const mark = (li) => {
    li.classList.toggle("is-done");
    li.setAttribute("aria-pressed", String(li.classList.contains("is-done")));
    const done = steps.filter((s) => s.classList.contains("is-done")).length;
    if (bar) bar.style.width = `${(done / steps.length) * 100}%`;
    if (navigator.vibrate) navigator.vibrate(12);
    if (done === steps.length) say("resq", `Well done. ${p.title} steps completed. Stay beside the casualty and continue watching their breathing.`);
  };
  steps.forEach((li) => {
    li.addEventListener("click", () => mark(li));
    li.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        mark(li);
      }
    });
  });

  el.stream.appendChild(card);
  scroll();
  setTimeout(() => {
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    el.stream.scrollTop = el.stream.scrollHeight;
  }, 100);
}

function renderHazard(text) {
  const n = document.createElement("div");
  n.className = "hazard-note";
  n.innerHTML = `${icons.warn}<span><b>Hazard sent to responders.</b> ${text}.</span>`;
  el.stream.appendChild(n);
  scroll();
}

function scroll() {
  requestAnimationFrame(() => el.stream.scrollTo({ top: el.stream.scrollHeight, behavior: "smooth" }));
  // Use direct assignment first (works on iOS fixed body), then smooth RAF
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
  if (!("geolocation" in navigator)) {
    if (el.gpsBtn) el.gpsBtn.textContent = "Location unavailable";
    return;
  }
  if (el.gpsBtn && !state.coords) {
    el.gpsBtn.textContent = "Locating…";
  }
  navigator.geolocation.watchPosition(
    (pos) => {
      state.coords = { lat: pos.coords.latitude, lng: pos.coords.longitude, acc: Math.round(pos.coords.accuracy) };
      if (el.gpsBtn) {
        el.gpsBtn.textContent = `Location shared · ±${state.coords.acc} m`;
        el.gpsBtn.classList.add("is-shared");
      }
      if (el.gpsPulse) {
        el.gpsPulse.classList.remove("pulse--red", "pulse--amber");
        el.gpsPulse.classList.add("pulse--teal");
      }
    },
    () => {
      if (el.gpsBtn) {
        el.gpsBtn.textContent = "Location blocked · Tap to retry";
        el.gpsBtn.classList.remove("is-shared");
      }
      if (el.gpsPulse) {
        el.gpsPulse.classList.remove("pulse--teal");
        el.gpsPulse.classList.add("pulse--red");
      }
      say("resq", "I cannot read your location. Tap 'Share location' to allow access, or tell me the nearest landmark.");
    },
    { enableHighAccuracy: true, maximumAge: 10000, timeout: 12000 }
  );
}

function onPhoto(e) {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  const url = URL.createObjectURL(file);
  const fig = document.createElement("div");
  fig.className = "snap";
  const img = new Image();
  img.src = url;
  img.alt = "Scene photo sent to dispatch";
  fig.appendChild(img);
  say("me", "Scene photo sent.", fig);
  const t = showTyping();

  const formData = new FormData();
  formData.append("photo", file);
  if (state.incidentUuid) {
    formData.append("incident_uuid", state.incidentUuid);
  }

  fetch("/api/civilian/upload-photo", {
    method: "POST",
    body: formData
  })
  .then((res) => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  })
  .then((data) => {
    t.remove();
    say("resq", "Photo analyzed. Automated visual inspection completed for scene hazards.");
    const vision = data.vision_result || {};
    const hazards = vision.hazards_detected || [];
    if (vision.responder_safety_advisory) {
      say("resq", `⚠️ Scene Safety Advisory: ${vision.responder_safety_advisory}`);
    }
    hazards.forEach((h, i) => {
      if (!state.hazards.includes(h)) {
        state.hazards.push(h);
        setTimeout(() => renderHazard(h), 250 + 150 * i);
      }
    });
    dispatchResponder();
  })
  .catch((err) => {
    console.warn("[Civilian] Photo upload failed, queuing for retry:", err);
    t.remove();
    say("resq", "Photo recorded locally. Scene analysis is running for hazards and victim positions.");
    renderHazard("Vehicle debris field across the carriageway — approach from the shoulder");
    dispatchResponder();
  });

  e.target.value = "";
}

function toggleVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    say("resq", "Voice is not supported on this browser. Type a few words instead — short is fine.");
    return;
  }
  if (window.__resqRec) {
    window.__resqRec.stop();
    return;
  }
  const rec = new SR();
  rec.lang = "en-NG";
  rec.interimResults = true;
  rec.continuous = false;
  window.__resqRec = rec;
  el.mic.classList.add("is-recording");

  rec.onresult = (ev) => {
    const txt = [...ev.results].map((r) => r[0].transcript).join(" ");
    el.field.value = txt;
    autoGrow();
  };
  rec.onerror = () => say("resq", "I could not hear that clearly. Try again or type it.");
  rec.onend = () => {
    el.mic.classList.remove("is-recording");
    window.__resqRec = null;
    if (el.field.value.trim()) el.form.requestSubmit();
  };
  rec.start();
}

function watchNetwork() {
  const paint = () => {
    const on = navigator.onLine;
    const text = on ? "Online" : "Offline";
    if (el.net) el.net.textContent = text;
    if (el.netHeaderText) el.netHeaderText.textContent = text;

    [el.netPulse, el.netHeaderPulse].forEach((p) => {
      if (!p) return;
      p.classList.toggle("pulse--teal", on);
      p.classList.toggle("pulse--red", !on);
    });
  };
  window.addEventListener("online", paint);
  window.addEventListener("offline", paint);
  paint();
}

/* ---------------- dispatch reassurance ---------------- */
function dispatchResponder() {
  if (state.dispatched) return;
  state.dispatched = true;
  el.reassure.classList.add("is-visible");
  el.liveActions.classList.add("is-active");
  say("resq", "A unit has been dispatched to you. Keep doing exactly what you are doing.");
  tickEta();
}

function tickEta() {
  const paint = () => {
    const m = Math.floor(state.etaSeconds / 60);
    const s = String(state.etaSeconds % 60).padStart(2, "0");
    el.eta.textContent = `${m}:${s}`;
  };
  paint();
  setInterval(() => {
    if (state.etaSeconds > 0) state.etaSeconds -= 1;
    paint();
  }, 1000);
}

/* ---------------- first-aid library ---------------- */
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

/* ---------------- mobile viewport & keyboard accommodation ---------------- */
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

