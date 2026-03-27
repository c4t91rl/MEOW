/* ================================
   CONFIG
   ================================ */
const API_URL = "http://localhost:8000/analyze";
// zmienicie na prod URL, np. "https://meow.railway.app/analyze"

/* ================================
   DOM REFS
   ================================ */
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const stateWelcome = $("#state-welcome");
const stateLoading = $("#state-loading");
const stateError = $("#state-error");
const stateResults = $("#state-results");
const analyzeBtn = $("#analyzeBtn");
const retryBtn = $("#retryBtn");
const loadingStep = $("#loading-step");
const errorMessage = $("#error-message");

/* ================================
   STATE MANAGEMENT
   ================================ */
function showState(state) {
  [stateWelcome, stateLoading, stateError, stateResults].forEach(
    (el) => (el.style.display = "none")
  );
  state.style.display = "";
}

function setLoading(step) {
  loadingStep.textContent = step;
}

function showError(msg) {
  errorMessage.textContent = msg;
  showState(stateError);
  analyzeBtn.disabled = false;
}

/* ================================
   EXTRACT PAGE DATA
   ================================ */
async function extractPageData() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (!tab) return reject(new Error("No active tab found"));

      const url = tab.url || "";

      // chrome://, edge://, about:, etc.
      if (
        url.startsWith("chrome") ||
        url.startsWith("edge") ||
        url.startsWith("about") ||
        url.startsWith("chrome-extension")
      ) {
        return reject(
          new Error("Cannot analyze browser internal pages")
        );
      }

      chrome.tabs.sendMessage(
        tab.id,
        { action: "extract" },
        (response) => {
          if (chrome.runtime.lastError) {
            // Content script might not be injected; try programmatic injection
            chrome.scripting.executeScript(
              {
                target: { tabId: tab.id },
                files: ["content.js"],
              },
              () => {
                if (chrome.runtime.lastError) {
                  return reject(
                    new Error(
                      "Cannot access this page. Try refreshing first."
                    )
                  );
                }
                // Retry message
                setTimeout(() => {
                  chrome.tabs.sendMessage(
                    tab.id,
                    { action: "extract" },
                    (resp2) => {
                      if (chrome.runtime.lastError || !resp2) {
                        return reject(
                          new Error("Failed to extract page data")
                        );
                      }
                      if (!resp2.success) {
                        return reject(
                          new Error(resp2.error || "Extraction error")
                        );
                      }
                      resolve(resp2.data);
                    }
                  );
                }, 300);
              }
            );
            return;
          }

          if (!response) {
            return reject(new Error("No response from content script"));
          }
          if (!response.success) {
            return reject(
              new Error(response.error || "Extraction error")
            );
          }
          resolve(response.data);
        }
      );
    });
  });
}

/* ================================
   CALL BACKEND
   ================================ */
async function analyzeWithBackend(pageData) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(pageData),
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Server error ${res.status}: ${errText}`);
    }

    return await res.json();
  } catch (err) {
    clearTimeout(timeout);
    if (err.name === "AbortError") {
      throw new Error("Analysis timed out. Try again.");
    }
    throw err;
  }
}

/* ================================
   RENDER RESULTS
   ================================ */
function getRiskColor(score) {
  if (score <= 25) return "var(--risk-low)";
  if (score <= 50) return "var(--risk-medium)";
  if (score <= 75) return "var(--risk-high)";
  return "var(--risk-critical)";
}

function getRiskClass(score) {
  if (score <= 25) return "risk-low";
  if (score <= 50) return "risk-medium";
  if (score <= 75) return "risk-high";
  return "risk-critical";
}

function getBarColor(value, inverted = false) {
  const effective = inverted ? value : 100 - value;
  if (effective >= 70) return "var(--risk-low)";
  if (effective >= 45) return "var(--risk-medium)";
  if (effective >= 25) return "var(--risk-high)";
  return "var(--risk-critical)";
}

function animateNumber(el, target, duration = 1000) {
  const start = 0;
  const startTime = performance.now();

  function update(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    // ease out quad
    const eased = 1 - (1 - progress) * (1 - progress);
    const current = Math.round(start + (target - start) * eased);
    el.textContent = current;
    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

function renderResults(data) {
  showState(stateResults);

  // ---- Risk Score Ring ----
  const score = data.overall_risk ?? 0;
  const circumference = 2 * Math.PI * 52; // r=52
  const offset = circumference - (score / 100) * circumference;
  const ringEl = $("#ring-progress");
  const color = getRiskColor(score);

  // Delay to trigger CSS transition
  requestAnimationFrame(() => {
    ringEl.style.strokeDashoffset = offset;
    ringEl.style.stroke = color;
  });

  animateNumber($("#risk-score-value"), score);

  // Risk label
  const riskLabel = $("#risk-label");
  const label =
    data.risk_label ||
    (score <= 25
      ? "Low Risk"
      : score <= 50
      ? "Medium Risk"
      : score <= 75
      ? "High Risk"
      : "Critical Risk");

  riskLabel.textContent = label;
  riskLabel.className = "risk-label " + getRiskClass(score);

  // Confidence
  const conf = data.confidence;
  $("#risk-confidence").textContent =
    conf != null ? `Confidence: ${Math.round(conf * 100)}%` : "";

  // ---- Page Type ----
  const pt = data.page_type || {};
  const pageTypeTag = $("#page-type-tag");
  pageTypeTag.textContent = formatLabel(pt.label || "unknown");

  const ptConf = pt.confidence;
  $("#page-type-confidence").textContent =
    ptConf != null ? `${Math.round(ptConf * 100)}% confidence` : "";

  // ---- Score Breakdown ----
  const scores = data.scores || {};

  renderBar("lang", scores.language_trust ?? 0, true);
  renderBar("source", scores.source_trust ?? 50, true);
  renderBar("domain", scores.domain_trust ?? 50, true);
  renderBar("trans", scores.transparency ?? 50, true);

  // ---- Patterns ----
  const patternsContainer = $("#patterns-container");
  const patternsCard = $("#patterns-card");
  const patterns = data.misinfo_patterns || [];

  patternsContainer.innerHTML = "";

  if (patterns.length === 0 || patterns.includes("none_detected")) {
    patternsContainer.innerHTML =
      '<span class="tag tag-pattern safe">✓ None detected</span>';
  } else {
    patterns.forEach((p) => {
      const tag = document.createElement("span");
      const severity = getPatternSeverity(p);
      tag.className = `tag tag-pattern ${severity}`;
      tag.textContent = formatLabel(p);
      patternsContainer.appendChild(tag);
    });
  }

  // ---- Security ----
  const sec = data.security || {};
  const secGrid = $("#security-grid");
  secGrid.innerHTML = "";

  const secItems = [
    {
      icon: sec.https ? "🔒" : "🔓",
      label: "HTTPS",
      value: sec.https ? "Secure" : "Not secure",
      cls: sec.https ? "good" : "bad",
    },
    {
      icon: "📅",
      label: "Domain Age",
      value:
        sec.domain_age_days != null
          ? formatDomainAge(sec.domain_age_days)
          : "Unknown",
      cls:
        sec.domain_age_days == null
          ? ""
          : sec.domain_age_days < 90
          ? "bad"
          : sec.domain_age_days < 365
          ? "warn"
          : "good",
    },
    {
      icon: sec.suspicious_hostname ? "🚩" : "✅",
      label: "Hostname",
      value: sec.suspicious_hostname ? "Suspicious" : "Normal",
      cls: sec.suspicious_hostname ? "bad" : "good",
    },
  ];

  secItems.forEach((item) => {
    const div = document.createElement("div");
    div.className = "security-item";
    div.innerHTML = `
      <span class="security-icon">${item.icon}</span>
      <div class="security-info">
        <span class="security-label">${item.label}</span>
        <span class="security-value ${item.cls}">${item.value}</span>
      </div>
    `;
    secGrid.appendChild(div);
  });

  // ---- Explanations ----
  const expList = $("#explanations-list");
  const explanations = data.explanations || [];
  expList.innerHTML = "";

  if (explanations.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No specific concerns identified.";
    expList.appendChild(li);
  } else {
    explanations.forEach((exp) => {
      const li = document.createElement("li");
      li.textContent = exp;
      expList.appendChild(li);
    });
  }
}

function renderBar(key, value, inverted) {
  const valEl = $(`#score-${key}-val`);
  const barEl = $(`#bar-${key}`);

  animateNumber(valEl, value, 800);

  const color = getBarColor(value, inverted);

  setTimeout(() => {
    barEl.style.width = value + "%";
    barEl.style.background = color;
  }, 100);
}

/* ================================
   HELPERS
   ================================ */
function formatLabel(str) {
  return str
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDomainAge(days) {
  if (days < 30) return `${days} days`;
  if (days < 365) return `${Math.round(days / 30)} months`;
  const years = (days / 365).toFixed(1);
  return `${years} years`;
}

function getPatternSeverity(pattern) {
  const high = [
    "conspiracy_cues",
    "authority_mimicry",
    "manipulative_framing",
  ];
  const medium = [
    "sensationalism",
    "unverified_claims",
    "missing_sourcing",
  ];
  const low = ["satire_parody"];

  if (high.includes(pattern)) return "";
  if (medium.includes(pattern)) return "warn";
  if (low.includes(pattern)) return "safe";
  return "warn";
}

/* ================================
   MAIN ANALYZE FLOW
   ================================ */
async function runAnalysis() {
  analyzeBtn.disabled = true;
  showState(stateLoading);

  try {
    // Step 1: Extract
    setLoading("Extracting page content…");
    const pageData = await extractPageData();

    // Step 2: Analyze
    setLoading("Running risk analysis…");
    const result = await analyzeWithBackend(pageData);

    // Step 3: Render
    setLoading("Building report…");

    // Small delay for UX feel
    await new Promise((r) => setTimeout(r, 300));

    renderResults(result);
  } catch (err) {
    console.error("MEOW error:", err);
    showError(err.message || "An unexpected error occurred.");
  } finally {
    analyzeBtn.disabled = false;
  }
}

/* ================================
   EVENT LISTENERS
   ================================ */
analyzeBtn.addEventListener("click", runAnalysis);
retryBtn.addEventListener("click", runAnalysis);

/* ================================
   KEYBOARD
   ================================ */
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !analyzeBtn.disabled) {
    runAnalysis();
  }
});