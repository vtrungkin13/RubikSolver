const API_BASE = "http://127.0.0.1:8000";
const $ = (selector) => document.querySelector(selector);

const translations = {
  vi: {
    pageTitle: "RubikSolver — Giải Rubik 3×3",
    heroTitle: "Giải Rubik 3×3",
    heroDescription: "Nhập công thức scramble và chọn phương pháp giải để xem chuỗi nước đi.",
    cubeAlt: "Khối Rubik 3×3 nhiều màu",
    cubeTitle: "Cube 3D", cubeDescription: "Xoay góc nhìn, theo dõi từng nước đi.",
    previous: "Trước", next: "Tiếp", resetCube: "Đặt lại trạng thái scramble",
    setupTitle: "Thiết lập bài giải", setupDescription: "Bắt đầu với trạng thái cube của bạn.",
    scrambleLabel: "Scramble", scrambleHint: "Công thức xáo trộn",
    scrambleHelp: "Dùng ký hiệu chuẩn: R, U, F, L, D, B và dấu ' hoặc 2.",
    charCount: n => `${n} ký tự`, methodLabel: "Phương pháp giải",
    methods: ["CFOP — Cross, F2L, OLL, PLL", "Roux — Giải theo block", "Kociemba — Nhanh, tổng quát"],
    methodHelp: {
      cfop: "Giải theo Cross, F2L, OLL và PLL — phù hợp để học phương pháp CFOP.",
      roux: "Xây dựng hai block, sau đó giải CMLL và các bước LSE.",
      kociemba: "Tìm lời giải nhanh cho nhiều trạng thái cube khác nhau."
    },
    solve: "Tìm lời giải", loadingButton: "Đang tìm lời giải…",
    emptyScramble: "Hãy nhập scramble trước khi tìm lời giải.",
    loading: "Đang phân tích trạng thái cube. Vui lòng đợi một chút.",
    badResponse: "Backend trả về phản hồi không hợp lệ. Hãy kiểm tra API.",
    solveError: "Không thể tìm lời giải.", genericError: "Đã xảy ra lỗi khi gọi API.",
    privacy: "Lời giải được xử lý bởi API cục bộ của bạn.",
    resultTitle: "Lời giải của bạn", resultDescription: "Thực hiện các nước đi theo đúng thứ tự.",
    verified: "✓ Đã xác minh", unverified: "⚠ Chưa xác minh",
    sequenceTitle: "Chuỗi nước đi", sequenceDescription: "Đọc từ trái sang phải",
    copy: "Sao chép", copied: "Đã sao chép", copyFallback: "Chọn văn bản để sao chép",
    phasesTitle: "Các giai đoạn", phaseCount: n => `${n} giai đoạn`,
    statMoves: "Tổng số nước đi", statMetric: "Thước đo", statMethod: "Phương pháp",
    noMoves: "Cube đã ở trạng thái được giải.", noPhaseMoves: "Không cần nước đi",
    moveCount: n => `${n} nước đi`, footer: "Giải từng bước. Hiểu từng nước đi.",
    switchLabel: "Switch language to English"
  },
  en: {
    pageTitle: "RubikSolver — Solve a 3×3 Rubik's Cube",
    heroTitle: "Solve a 3×3 Cube",
    heroDescription: "Enter a scramble and choose a solving method to see the move sequence.",
    cubeAlt: "Colorful 3×3 Rubik's Cube",
    cubeTitle: "3D Cube", cubeDescription: "Rotate the view and follow each move.",
    previous: "Previous", next: "Next", resetCube: "Reset to scramble state",
    setupTitle: "Set up your solve", setupDescription: "Start with your cube's current state.",
    scrambleLabel: "Scramble", scrambleHint: "Scramble sequence",
    scrambleHelp: "Use standard notation: R, U, F, L, D, B and ' or 2.",
    charCount: n => `${n} characters`, methodLabel: "Solving method",
    methods: ["CFOP — Cross, F2L, OLL, PLL", "Roux — Block-building method", "Kociemba — Fast, general-purpose"],
    methodHelp: {
      cfop: "Solve using Cross, F2L, OLL, and PLL — great for learning CFOP.",
      roux: "Build two blocks, then solve CMLL and the LSE steps.",
      kociemba: "Find a fast solution for a wide range of cube states."
    },
    solve: "Find solution", loadingButton: "Finding solution…",
    emptyScramble: "Enter a scramble before finding a solution.",
    loading: "Analyzing your cube state. Please wait a moment.",
    badResponse: "The backend returned an invalid response. Please check the API.",
    solveError: "Unable to find a solution.", genericError: "An error occurred while calling the API.",
    privacy: "Your solution is processed by your local API.",
    resultTitle: "Your solution", resultDescription: "Follow the moves in the order shown.",
    verified: "✓ Verified", unverified: "⚠ Not verified",
    sequenceTitle: "Move sequence", sequenceDescription: "Read from left to right",
    copy: "Copy", copied: "Copied", copyFallback: "Select text to copy",
    phasesTitle: "Solution phases", phaseCount: n => `${n} phases`,
    statMoves: "Total moves", statMetric: "Metric", statMethod: "Method",
    noMoves: "The cube is already solved.", noPhaseMoves: "No moves needed",
    moveCount: n => `${n} moves`, footer: "Solve step by step. Understand every move.",
    switchLabel: "Chuyển ngôn ngữ sang Tiếng Việt"
  }
};

const methodSelect = $("#method");
const scrambleInput = $("#scramble");
const solveButton = $("#solve");
const solveLabel = $("#solve-label");
const statusMessage = $("#status");
const resultPanel = $("#result");
const languageToggle = $("#language-toggle");
let language = "vi";
let lastSolution = null;
let lastCopied = false;
let scrambleDebounce = null;
let solveRequestVersion = 0;

function t(key, ...args) {
  const value = translations[language][key];
  return typeof value === "function" ? value(...args) : value;
}

function updateLanguage(nextLanguage) {
  language = nextLanguage;
  document.documentElement.lang = language;
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    const key = element.dataset.i18n;
    if (key in translations[language]) element.innerHTML = t(key);
  });
  document.querySelectorAll("[data-i18n-alt]").forEach((element) => {
    element.alt = t(element.dataset.i18nAlt);
  });
  languageToggle.innerHTML = language === "vi"
    ? 'EN <span class="language-divider">/</span> <strong>VI</strong>'
    : '<strong>EN</strong> <span class="language-divider">/</span> VI';
  languageToggle.setAttribute("aria-label", t("switchLabel"));
  languageToggle.title = t("switchLabel");
  [...methodSelect.options].forEach((option, index) => {
    option.textContent = t("methods")[index];
  });
  $("#char-count").textContent = t("charCount", scrambleInput.value.length);
  $("#method-help").textContent = t("methodHelp")[methodSelect.value] ?? "";
  if (solveButton.disabled) solveLabel.textContent = t("loadingButton");
  else solveLabel.textContent = t("solve");
  if (statusMessage.dataset.statusKey) {
    showStatus(t(statusMessage.dataset.statusKey), statusMessage.dataset.statusKind || "error");
  }
  if (lastSolution) renderSolution(lastSolution);
  if (lastCopied) $("#copy-solution").innerHTML = `✓ <span>${t("copied")}</span>`;
}

languageToggle.addEventListener("click", () => updateLanguage(language === "vi" ? "en" : "vi"));

scrambleInput.addEventListener("input", () => {
  solveRequestVersion += 1;
  $("#char-count").textContent = t("charCount", scrambleInput.value.length);
  lastSolution = null;
  resultPanel.classList.add("hidden");
  window.clearTimeout(scrambleDebounce);
  scrambleDebounce = window.setTimeout(() => {
    document.dispatchEvent(new CustomEvent("rubik:scramble", { detail: scrambleInput.value.trim() }));
  }, 300);
});

methodSelect.addEventListener("change", () => {
  solveRequestVersion += 1;
  lastSolution = null;
  resultPanel.classList.add("hidden");
  $("#method-help").textContent = t("methodHelp")[methodSelect.value] ?? "";
  window.clearTimeout(scrambleDebounce);
  document.dispatchEvent(new CustomEvent("rubik:scramble", { detail: scrambleInput.value.trim() }));
});

function showStatus(message, kind = "error", key = null) {
  statusMessage.textContent = message;
  statusMessage.className = "status-message";
  statusMessage.dataset.statusKey = key || "";
  statusMessage.dataset.statusKind = kind;
  if (kind === "loading") statusMessage.classList.add("loading");
}

function makeStat(value, label) {
  const card = document.createElement("div");
  card.className = "stat-card";
  const number = document.createElement("div");
  number.className = "stat-value";
  number.textContent = value;
  const caption = document.createElement("div");
  caption.className = "stat-label";
  caption.textContent = label;
  card.append(number, caption);
  return card;
}

function renderPhases(phases = []) {
  const container = $("#phases");
  container.replaceChildren();
  $("#phase-count").textContent = t("phaseCount", phases.length);

  phases.forEach((phase, index) => {
    const section = document.createElement("section");
    section.className = "phase";
    const titleRow = document.createElement("div");
    titleRow.className = "phase-title-row";
    const number = document.createElement("span");
    number.className = "phase-index";
    number.textContent = String(index + 1).padStart(2, "0");
    const title = document.createElement("h4");
    title.textContent = phase.name;
    const count = document.createElement("span");
    count.className = "phase-count";
    count.textContent = t("moveCount", phase.move_count ?? 0);
    titleRow.append(number, title, count);
    section.append(titleRow);
    if (phase.description) {
      const description = document.createElement("p");
      description.className = "phase-description";
      description.textContent = phase.description;
      section.append(description);
    }
    const moves = document.createElement("pre");
    moves.textContent = phase.moves || t("noPhaseMoves");
    section.append(moves);
    container.append(section);
  });
}

function renderSolution(data) {
  $("#summary").replaceChildren(
    makeStat(data.move_count ?? 0, t("statMoves")),
    makeStat(data.metric ?? "—", t("statMetric")),
    makeStat(data.method ?? methodSelect.value, t("statMethod"))
  );
  const sequence = $("#solution");
  sequence.replaceChildren();
  if (data.moves?.trim()) {
    data.moves.trim().split(/\s+/).forEach((move, index) => {
      if (index) sequence.append(document.createTextNode(" "));
      const token = document.createElement("span");
      token.className = "solution-token";
      token.textContent = move;
      sequence.append(token);
    });
  } else {
    sequence.textContent = t("noMoves");
  }
  const verifiedBadge = $("#verified-badge");
  verifiedBadge.textContent = data.verified ? t("verified") : t("unverified");
  verifiedBadge.classList.toggle("unverified", !data.verified);
  renderPhases(data.phases);
}

solveButton.addEventListener("click", async () => {
  const requestVersion = ++solveRequestVersion;
  const scramble = scrambleInput.value.trim();
  if (!scramble) {
    showStatus(t("emptyScramble"), "error", "emptyScramble");
    scrambleInput.focus();
    return;
  }

  solveButton.disabled = true;
  solveLabel.textContent = t("loadingButton");
  showStatus(t("loading"), "loading", "loading");
  resultPanel.classList.add("hidden");

  try {
    const response = await fetch(API_BASE + "/api/solve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scramble, method: methodSelect.value })
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error(t("badResponse"));
    }
    if (requestVersion !== solveRequestVersion) return;
    if (!response.ok) {
      const message = data.detail?.message ?? data.detail ?? t("solveError");
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    lastSolution = data;
    renderSolution(data);
    document.dispatchEvent(new CustomEvent("rubik:solution", { detail: data }));
    resultPanel.classList.remove("hidden");
    showStatus("");
  } catch (error) {
    showStatus(error.message || t("genericError"));
  } finally {
    solveButton.disabled = false;
    solveLabel.textContent = t("solve");
  }
});

$("#copy-solution").addEventListener("click", async () => {
  const solution = $("#solution").textContent.trim();
  if (!solution) return;
  const copyButton = $("#copy-solution");
  try {
    await navigator.clipboard.writeText(solution);
    copyButton.innerHTML = `✓ <span>${t("copied")}</span>`;
    lastCopied = true;
  } catch {
    const range = document.createRange();
    range.selectNodeContents($("#solution"));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    copyButton.innerHTML = t("copyFallback");
    lastCopied = false;
  }
  window.setTimeout(() => {
    copyButton.innerHTML = `▢ <span>${t("copy")}</span>`;
    lastCopied = false;
  }, 1800);
});

updateLanguage("vi");
