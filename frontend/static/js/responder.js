/* Responder tactical cockpit brief — telemetry, stage control, navigation, multi-pane & mobile view */
import "./resq-theme.js";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const INCIDENT = {
  id: "RQ-2417",
  coords: { lat: 6.3894, lng: 7.2295 },
  place: "Enugu–Onitsha Expressway, km 42 eastbound (near Ugwuoba)",
};

const el = {
  telemetry: $("#telemetry"),
  beat: $("#beat"),
  log: $("#statuslog"),
  navigate: $("#navigate"),
  call: $("#callCivilian"),
  mobileNavBtn: $("#mobileNavBtn"),
  mobileCallBtn: $("#mobileCallBtn"),
  arrivalCountdown: $("#arrivalCountdown"),
  mobileEta: $("#mobileEta"),
  ackBtn: $("#ackBriefBtn"),
  ackText: $("#ackBtnText"),
  lastRadioUpdate: $("#lastRadioUpdate"),
  fullscreenBtn: $("#fullscreenBtn"),
  workspace: $("#responderWorkspace"),
};

/* ---------------- arrival countdown ticker ---------------- */
let arrivalSeconds = 12 * 60 + 4; // 12:04
function tickArrival() {
  if (arrivalSeconds > 0) {
    arrivalSeconds -= 1;
    const m = Math.floor(arrivalSeconds / 60);
    const s = arrivalSeconds % 60;
    const timeStr = `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    if (el.arrivalCountdown) el.arrivalCountdown.textContent = timeStr;
    if (el.mobileEta) el.mobileEta.textContent = timeStr;
  }
}
setInterval(tickArrival, 1000);

/* ---------------- radio sync ticker ---------------- */
let radioElapsed = 0;
function tickRadio() {
  radioElapsed += 1;
  if (el.lastRadioUpdate) {
    if (radioElapsed < 60) {
      el.lastRadioUpdate.textContent = `Updated ${radioElapsed}s ago`;
    } else {
      el.lastRadioUpdate.textContent = `Updated ${Math.floor(radioElapsed / 60)}m ago`;
    }
  }
}
setInterval(tickRadio, 1000);

/* ---------------- acknowledge brief toggle ---------------- */
let isAcked = false;
if (el.ackBtn) {
  el.ackBtn.addEventListener("click", () => {
    isAcked = !isAcked;
    if (isAcked) {
      el.ackBtn.classList.add("is-acked");
      if (el.ackText) el.ackText.textContent = "Brief acknowledged";
      logLine("Brief acknowledged by Unit 14", "Dispatch notified via telemetry");
      radioElapsed = 0;
      if (navigator.vibrate) navigator.vibrate([30, 50, 30]);
    } else {
      el.ackBtn.classList.remove("is-acked");
      if (el.ackText) el.ackText.textContent = "Acknowledge brief";
      logLine("Brief status reset to pending", "Dispatch telemetry updated");
    }
  });
}

/* ---------------- telemetry heartbeat: broadcast GPS every 15 s ---------------- */
let beats = 0;
if (el.telemetry) el.telemetry.classList.add("is-live");

function broadcast() {
  beats += 1;
  radioElapsed = 0;
  const t = new Date();
  if (el.beat) {
    el.beat.textContent = `${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}:${String(
      t.getSeconds()
    ).padStart(2, "0")}`;
  }
  if (el.telemetry) {
    el.telemetry.animate(
      [{ opacity: 1 }, { opacity: 0.45 }, { opacity: 1 }],
      { duration: 600, easing: "ease-out" }
    );
  }
  if (beats % 4 === 0) logLine("Position broadcast to dispatch", "GPS lock held");
}

if ("geolocation" in navigator) {
  navigator.geolocation.watchPosition(
    () => {},
    () => logLine("GPS signal weak", "Using last known position"),
    { enableHighAccuracy: true, maximumAge: 15000 }
  );
}
broadcast();
setInterval(broadcast, 15000);

/* ---------------- stage control ---------------- */
$$(".stage-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".stage-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    logLine(`Status set to ${btn.dataset.stage}`, "Dispatch notified");
    radioElapsed = 0;
    if (navigator.vibrate) navigator.vibrate(20);
  });
});

/* ---------------- actions: navigate & call ---------------- */
function openNavigation() {
  const { lat, lng } = INCIDENT.coords;
  logLine("Turn-by-turn navigation opened", `${lat.toFixed(4)}, ${lng.toFixed(4)}`);
  window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, "_blank", "noopener");
}

function openCallScene() {
  logLine("Voice channel opened to bystander", "Scene line live");
  radioElapsed = 0;
  alert("Connecting voice radio channel to bystander at scene (RQ-2417)...");
}

el.navigate?.addEventListener("click", openNavigation);
el.mobileNavBtn?.addEventListener("click", openNavigation);

el.call?.addEventListener("click", openCallScene);
el.mobileCallBtn?.addEventListener("click", openCallScene);

/* ---------------- status log ---------------- */
function logLine(label, detail) {
  if (!el.log) return;
  const row = document.createElement("p");
  row.className = "statuslog__row";
  const t = new Date();
  row.innerHTML = `<span>${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}</span><b>${label}</b><span>${detail}</span>`;
  el.log.prepend(row);
  while (el.log.children.length > 8) el.log.lastElementChild.remove();
}

logLine(`Mission ${INCIDENT.id} accepted`, INCIDENT.place);

/* ---------------- fullscreen view toggle (Requirement 3) ---------------- */
function wireFullscreen() {
  const btn = el.fullscreenBtn;
  if (!btn) return;
  const maxIcon = btn.querySelector(".fs-icon-max");
  const minIcon = btn.querySelector(".fs-icon-min");

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  };

  btn.addEventListener("click", toggleFullscreen);

  document.addEventListener("fullscreenchange", () => {
    const isFs = !!document.fullscreenElement;
    if (maxIcon) maxIcon.classList.toggle("hidden", isFs);
    if (minIcon) minIcon.classList.toggle("hidden", !isFs);
    btn.title = isFs ? "Exit Fullscreen" : "Toggle Fullscreen Mode";
  });
}
wireFullscreen();

/* ---------------- mobile segmented switcher (Requirement 4) ---------------- */
function wireMobileNav() {
  const tabs = $$(".m-nav-tab");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => {
        const isActive = t === tab;
        t.classList.toggle("is-active", isActive);
        t.setAttribute("aria-selected", String(isActive));
      });
      if (el.workspace) {
        el.workspace.dataset.activeTab = tab.dataset.tab;
      }
    });
  });
}
wireMobileNav();
