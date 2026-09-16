/* Offline-resilient first-aid protocol library.
   Constrained to WHO Basic Emergency Care + Nigerian Red Cross first-aid guidance.
   Cached into localStorage on first load so the guidance survives signal loss. */

export const PROTOCOL_VERSION = "2026.02";

export const PROTOCOLS = {
  bleeding: {
    id: "bleeding",
    title: "Severe bleeding control",
    summary: "Stop the loss of blood before anything else.",
    steps: [
      "Protect yourself. Use gloves, a clean plastic bag or thick cloth over your hands.",
      "Press hard directly on the wound with a clean cloth. Do not lift to check.",
      "Keep pressing without stopping for 10 minutes. Add cloth on top if it soaks through.",
      "If an arm or leg is bleeding badly, raise it above the level of the heart.",
      "If bleeding does not slow, tie a firm band 5 cm above the wound and note the time.",
      "Keep the person warm and lying down. Watch their breathing.",
    ],
  },
  unresponsive: {
    id: "unresponsive",
    title: "Unresponsive but breathing",
    summary: "Protect the airway with the recovery position.",
    steps: [
      "Tap the shoulder and shout. If there is no answer, they are unresponsive.",
      "Check the mouth and remove anything loose you can see.",
      "Tilt the head back gently and lift the chin to open the airway.",
      "Look and feel for breathing for 10 seconds.",
      "If breathing, roll them onto their side, head resting on their hand, top knee bent.",
      "Stay with them. Re-check breathing every minute until help arrives.",
    ],
  },
  cpr: {
    id: "cpr",
    title: "Not breathing — CPR",
    summary: "Push hard, push fast, do not stop.",
    steps: [
      "Lay the person flat on their back on a hard surface.",
      "Place the heel of one hand in the centre of the chest, the other hand on top.",
      "Push straight down about 5 cm, then let the chest come all the way back up.",
      "Keep a fast rhythm — about 2 pushes every second.",
      "Do not stop to check unless they wake, move or breathe normally.",
      "If someone else is present, swap every 2 minutes so you do not tire.",
    ],
  },
  shock: {
    id: "shock",
    title: "Shock management",
    summary: "Cold, pale, shaking, confused — act now.",
    steps: [
      "Lay the person down and raise their legs about 30 cm if no leg injury.",
      "Loosen tight clothing at the neck, chest and waist.",
      "Cover them with a cloth or wrapper to keep body heat in.",
      "Do not give food or water, even if they ask.",
      "Reassure them calmly and keep checking breathing.",
    ],
  },
  burns: {
    id: "burns",
    title: "Burns and scalds",
    summary: "Cool water, nothing else.",
    steps: [
      "Move the person away from the heat source safely.",
      "Cool the burn under clean running water for 20 minutes.",
      "Remove rings, watches and tight clothing near the burn before swelling starts.",
      "Cover loosely with clean plastic wrap or a clean cloth.",
      "Never apply oil, toothpaste, butter, ice or ash.",
    ],
  },
  fracture: {
    id: "fracture",
    title: "Suspected fracture or spine injury",
    summary: "Do not move them unless there is danger.",
    steps: [
      "Keep the person still. Do not straighten a bent limb.",
      "If you suspect a neck or back injury, hold the head steady in line with the body.",
      "Support the injured limb with rolled cloth on both sides.",
      "Control any bleeding around the injury with gentle pressure.",
      "Only move them if there is fire, fuel or traffic danger.",
    ],
  },
  choking: {
    id: "choking",
    title: "Choking",
    summary: "Clear the airway fast.",
    steps: [
      "Ask: are you choking? If they cannot speak or cough, act immediately.",
      "Lean them forward and give 5 firm blows between the shoulder blades.",
      "If still blocked, stand behind, hands above the navel, and give 5 inward-upward thrusts.",
      "Alternate 5 back blows and 5 thrusts.",
      "If they collapse and stop breathing, start CPR.",
    ],
  },
};

const CACHE_KEY = "resq-protocols";

export function cacheProtocols() {
  try {
    localStorage.setItem(
      CACHE_KEY,
      JSON.stringify({ version: PROTOCOL_VERSION, data: PROTOCOLS, at: Date.now() })
    );
  } catch (_) {
    /* storage full or blocked — protocols remain in memory */
  }
}

export function readCachedProtocols() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return PROTOCOLS;
    return JSON.parse(raw).data || PROTOCOLS;
  } catch (_) {
    return PROTOCOLS;
  }
}

/* Very small keyword router — chooses which protocol a plain-language
   description maps to. Runs offline; the server AI refines it when online. */
export function matchProtocols(text) {
  const t = (text || "").toLowerCase();
  const hits = [];
  const add = (k) => {
    if (!hits.includes(k)) hits.push(k);
  };
  if (/(blood|bleed|cut|gash|wound|deep|hemorr|haemorr)/.test(t)) add("bleeding");
  if (/(not respond|unrespons|unconscious|passed out|fainted|no answer)/.test(t)) add("unresponsive");
  if (/(not breath|no breath|stopped breathing|no pulse|heart stop|cardiac)/.test(t)) add("cpr");
  if (/(cold|pale|shaking|shiver|confus|weak pulse|shock)/.test(t)) add("shock");
  if (/(burn|scald|fire|hot oil|petrol fire)/.test(t)) add("burns");
  if (/(broken|fracture|bone|neck|spine|back injury|leg twisted)/.test(t)) add("fracture");
  if (/(chok|swallow|blocked airway|food stuck)/.test(t)) add("choking");
  if (!hits.length) add("unresponsive");
  return hits.map((k) => PROTOCOLS[k]);
}

/* Hazards detected from the bystander's own words — relayed to responders. */
export function detectHazards(text) {
  const t = (text || "").toLowerCase();
  const found = [];
  if (/(fuel|petrol|diesel|spill|leak)/.test(t)) found.push("Fuel spill at collision site — do not deploy flares");
  if (/(fire|burning|smoke|flames)/.test(t)) found.push("Active fire or smoke on scene");
  if (/(power line|electric|cable|transformer|wire)/.test(t)) found.push("Downed power lines — treat as live");
  if (/(tanker|gas|cylinder|chemical)/.test(t)) found.push("Possible hazardous cargo — establish 100 m cordon");
  if (/(flood|water|river|submerged)/.test(t)) found.push("Water hazard — flooded carriageway");
  if (/(traffic|highway|expressway|road|trailer|truck)/.test(t)) found.push("Live traffic exposure — approach lane closure required");
  if (/(crowd|mob|fight|angry)/.test(t)) found.push("Crowd control risk on scene");
  return found;
}
