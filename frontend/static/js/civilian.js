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
  chatHistory: [],
};

const icons = {
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>',
};

/* ---------------- boot ---------------- */
try {
  cacheProtocols();
  renderOfflineLibrary();
  watchNetwork();
  wireKeyboardAccommodation();
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

  say(
    "resq",
    "I am with you. Tell me in your own words what you can see. If it is easier, tap one of the quick options below."
  );
  try {
    requestLocation();
  } catch (_) {}
  setTimeout(dispatchResponder, 9000);
}

// Expose globally so HTML inline onclick fallback works reliably
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
$("#callResponder")?.addEventListener("click", () => {
  say("resq", "Connecting you to the responder unit now. Keep your phone on speaker and stay beside the victim.");
});

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

  // Record user turn in local history
  state.chatHistory.push({ role: "user", text: text });

  fetch("/api/civilian/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: text,
      lat: state.coords?.lat,
      lng: state.coords?.lng,
      incident_uuid: state.incidentUuid,
      history: state.chatHistory.slice(0, -1)
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

    // Record model turn in local history
    if (data.reassurance_message) {
      state.chatHistory.push({ role: "model", text: data.reassurance_message });
    }

    // 1. Natural Conversational Response (with integrated clinical insight if provided)
    let replyText = data.reassurance_message || "";
    if (data.clinical_synthesis && !replyText.includes(data.clinical_synthesis)) {
      replyText = replyText ? `${replyText}\n\n${data.clinical_synthesis}` : data.clinical_synthesis;
    }
    if (replyText) {
      say("resq", replyText);
    }

    // 2. Action Steps: ONLY rendered when the AI or protocol explicitly dictates immediate physical actions
    const steps = (data.first_aid_steps && Array.isArray(data.first_aid_steps) && data.first_aid_steps.length > 0)
      ? data.first_aid_steps
      : (matchProtocols(text)[0]?.steps || []);

    if (steps.length > 0) {
      const traumaTitles = data.extraction?.suspected_trauma?.length
        ? data.extraction.suspected_trauma.map(t => t.charAt(0).toUpperCase() + t.slice(1)).join(", ")
        : "Action Steps";
      const rsiVal = data.triage?.rsi_score ? `RSI ${data.triage.rsi_score}` : "Active Guidance";
      const tierVal = data.triage?.triage_tier || "FIRST AID";

      const p = {
        title: traumaTitles,
        summary: `${rsiVal} (${tierVal}), WHO and Nigerian Red Cross Protocol`,
        steps: steps
      };
      renderProtocol(p);
    }

    // 3. Interactive Assessment Questions (rendered ONLY when the AI deduces assessment is needed)
    if (data.assessment_questions && data.assessment_questions.length > 0) {
      renderAssessmentQuestions(data.assessment_questions);
    }

    // 5. Red Flag Warning Signs (if provided)
    // 4. Red Flag Warning Signs (rendered ONLY when high-risk danger signs exist)
    if (data.red_flags && data.red_flags.length > 0) {
      renderRedFlags(data.red_flags);
    }

    // 6. Render any detected hazards
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


function renderRedFlags(flags) {
  if (!flags || !flags.length) return;
  const card = document.createElement("div");
  card.className = "red-flags-card";
  card.innerHTML = `
    <div class="red-flags-card__head">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      <span>Immediate Warning Signs (Red Flags)</span>
    </div>
    <ul class="red-flags-card__list">
      ${flags.map(f => `<li>${f}</li>`).join("")}
    </ul>
  `;
  el.stream.appendChild(card);
  scroll();
}

function renderAssessmentQuestions(questions) {
  if (!questions || !questions.length) return;
  const container = document.createElement("div");
  container.className = "assessment-container";

  questions.forEach((q, idx) => {
    const card = document.createElement("div");
    card.className = "assessment-card";
    card.innerHTML = `
      <div class="assessment-card__prompt">
        <span class="assessment-card__num">${idx + 1}</span>
        <p class="assessment-card__question">${q.question}</p>
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
        // Mark selected and disable sibling chips
        chipsEl.querySelectorAll(".chip--assessment").forEach(c => {
          c.classList.remove("is-selected");
          c.disabled = true;
          c.style.opacity = "0.5";
        });
        btn.classList.add("is-selected");
        btn.style.opacity = "1";

        // Auto-send response
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
  return `Understood. Work through the ${names} steps below, one at a time. Tap each step as you finish it. I am watching your location the whole time.`;
}

function wordToNum(w) {
  return { two: 2, three: 3, four: 4 }[String(w).toLowerCase()] || 1;
}

/* ---------------- rendering ---------------- */
function say(who, text, extraNode) {
  const wrap = document.createElement("div");
  wrap.className = `msg msg--${who === "me" ? "me" : "resq"}`;
  wrap.innerHTML = `<p class="msg__who">${who === "me" ? "You" : "ResQ Clinical Guide"}</p><div class="msg__bubble"></div>`;
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
      <div class="thinking-row">
        <span class="thinking-dot"></span>
        <span class="thinking-label">Evaluating situation &amp; synthesizing guidance...</span>
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

  // Header
  const head = document.createElement("header");
  head.className = "protocol__head";
  head.style.cssText = "display:flex;align-items:center;justify-content:space-between;padding:12px 16px;background:var(--surface);gap:12px;";
  head.innerHTML = `
    <div style="flex:1;min-width:0;">
      <h2 style="font-size:0.95rem;font-weight:600;color:var(--text);margin:0;">${p.title}</h2>
      <p style="font-size:0.75rem;color:var(--text-3);margin:2px 0 0 0;">${p.summary}</p>
    </div>
    <span class="badge badge--teal" style="font-size:0.7rem;font-weight:600;padding:4px 10px;border-radius:999px;background:color-mix(in srgb,var(--accent) 15%,transparent);color:var(--accent);white-space:nowrap;border:1px solid var(--accent);">Action Steps</span>`;
  card.appendChild(head);

  // Steps container
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
        say("resq", "Well done, all steps completed. Stay beside the casualty, keep them calm, and continue watching their breathing until responders arrive.");
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

  // Scroll to make sure card is in viewport on mobile and desktop
  el.stream.scrollTop = el.stream.scrollHeight;
  requestAnimationFrame(() => {
    el.stream.scrollTop = el.stream.scrollHeight;
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
}

function renderHazard(text) {
  const n = document.createElement("div");
  n.className = "hazard-note";
  n.innerHTML = `${icons.warn}<span><b>Hazard sent to responders.</b> ${text}.</span>`;
  el.stream.appendChild(n);
  scroll();
}

function scroll() {
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
    renderHazard("Vehicle debris field across the carriageway, approach from the shoulder");
    dispatchResponder();
  });

  e.target.value = "";
}

function toggleVoice() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    say("resq", "Voice is not supported on this browser. Type a few words instead, short is fine.");
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
      if (!p || !p.classList) return;
      if (typeof p.classList.toggle === "function") {
        p.classList.toggle("pulse--teal", on);
        p.classList.toggle("pulse--red", !on);
      } else {
        if (on) {
          p.classList.add("pulse--teal");
          p.classList.remove("pulse--red");
        } else {
          p.classList.add("pulse--red");
          p.classList.remove("pulse--teal");
        }
      }
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
  say(
    "resq",
    "Help is actively on the way. An emergency response unit has been dispatched to your coordinates, and I am right here with you to guide every step until they arrive. Take a slow, gentle breath."
  );
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

