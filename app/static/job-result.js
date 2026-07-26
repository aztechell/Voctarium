import {
  applyStaticI18n,
  applyTheme,
  canRemove,
  createUiContext,
  escapeHtml,
  formatDate,
  formatDuration,
  getStatusLabel,
  playUiNotification,
  setDocumentTitle,
} from "./shared.js";

const root = document.getElementById("result-root");
const resultTitleEl = document.getElementById("result-title");
const backLink = document.getElementById("back-link");
const viewToggleBtn = document.getElementById("view-toggle-btn");
const infoToggleBtn = document.getElementById("info-toggle-btn");
const readerControlsPanelEl = document.getElementById("reader-controls-panel");
const resultInfoPanelEl = document.getElementById("result-info-panel");
const resultMetaEl = document.getElementById("result-meta");
const resultBannerEl = document.getElementById("result-banner");
const resultReaderStageEl = document.getElementById("result-reader-stage");
const resultContentEl = document.getElementById("result-content");
const readerFontSizeInput = document.getElementById("reader-font-size-input");
const readerLineCompactBtn = document.getElementById("reader-line-compact-btn");
const readerLineNormalBtn = document.getElementById("reader-line-normal-btn");
const readerLineRelaxedBtn = document.getElementById("reader-line-relaxed-btn");
const readerWidthInput = document.getElementById("reader-width-input");
const readerWidthValue = document.getElementById("reader-width-value");
const readerJustifyLeftBtn = document.getElementById("reader-justify-left-btn");
const readerJustifyFullBtn = document.getElementById("reader-justify-full-btn");
const readerJustifyHyphenBtn = document.getElementById("reader-justify-hyphen-btn");
const readerParagraphGapInput = document.getElementById("reader-paragraph-gap-input");
const downloadMenuAnchorEl = document.getElementById("download-menu-anchor");
const downloadMenuBtn = document.getElementById("download-menu-btn");
const downloadMenuEl = document.getElementById("download-menu");
const downloadLink = document.getElementById("download-link");
const downloadPdfBtn = document.getElementById("download-pdf-btn");
const playerToggleBtn = document.getElementById("player-toggle-btn");
const toolbarToggleBtn = document.getElementById("toolbar-toggle-btn");
const removeBtn = document.getElementById("remove-btn");
const editorToolbarEl = document.getElementById("editor-toolbar");
const editorFindbarEl = document.getElementById("editor-findbar");
const editorBoldBtn = document.getElementById("editor-bold-btn");
const editorItalicBtn = document.getElementById("editor-italic-btn");
const editorParagraphBtn = document.getElementById("editor-paragraph-btn");
const editorH2Btn = document.getElementById("editor-h2-btn");
const editorH3Btn = document.getElementById("editor-h3-btn");
const editorBulletsBtn = document.getElementById("editor-bullets-btn");
const editorOrderedBtn = document.getElementById("editor-ordered-btn");
const editorUndoBtn = document.getElementById("editor-undo-btn");
const editorRedoBtn = document.getElementById("editor-redo-btn");
const editorFindBtn = document.getElementById("editor-find-btn");
const editorResetBtn = document.getElementById("editor-reset-btn");
const editorSaveBtn = document.getElementById("editor-save-btn");
const editorSaveStatusEl = document.getElementById("editor-save-status");
const editorDirtyIndicatorEl = document.getElementById("editor-dirty-indicator");
const editorWordCountEl = document.getElementById("editor-word-count");
const editorFindInput = document.getElementById("editor-find-input");
const editorFindStatusEl = document.getElementById("editor-find-status");
const editorFindPrevBtn = document.getElementById("editor-find-prev-btn");
const editorFindNextBtn = document.getElementById("editor-find-next-btn");
const editorFindCloseBtn = document.getElementById("editor-find-close-btn");
const viewPopoverAnchorEl = document.getElementById("view-popover-anchor");
const infoPopoverAnchorEl = document.getElementById("info-popover-anchor");
const resultPlayerEl = document.getElementById("result-player");
const resultAudioEl = document.getElementById("result-audio");
const playerRewindBtn = document.getElementById("player-rewind-btn");
const playerPlayBtn = document.getElementById("player-play-btn");
const playerPlayIconEl = document.getElementById("player-play-icon");
const playerForwardBtn = document.getElementById("player-forward-btn");
const playerCurrentTimeEl = document.getElementById("player-current-time");
const playerDurationEl = document.getElementById("player-duration");
const playerWaveformEl = document.getElementById("player-waveform");
const playerRateAnchorEl = document.getElementById("player-rate-anchor");
const playerRatePopoverEl = document.getElementById("player-rate-popover");
const playerRateBtn = document.getElementById("player-rate-btn");
const playerRateOptions = Array.from(document.querySelectorAll(".player-rate-option"));
const playerVolumeAnchorEl = document.getElementById("player-volume-anchor");
const playerVolumePopoverEl = document.getElementById("player-volume-popover");
const playerMuteBtn = document.getElementById("player-mute-btn");
const playerVolumeInput = document.getElementById("player-volume-input");

const TERMINAL_STATUSES = new Set(["done", "failed", "cancelled"]);
const INLINE_BOLD_RE = /\*\*([^*]+)\*\*/g;
const INLINE_ITALIC_RE = /\*([^*]+)\*/g;
const ORDERED_LIST_RE = /^\d+\.\s+(.+)$/;
const TOOLBAR_COLLAPSED_KEY = "voctarium.result.toolbarCollapsed";
const PLAYER_VISIBLE_KEY = "voctarium.result.playerVisible";
const PLAYER_VOLUME_KEY = "voctarium.result.playerVolume";
const PLAYER_MUTED_KEY = "voctarium.result.playerMuted";
const PLAYER_RATE_KEY = "voctarium.result.playerRate";
const PLAYER_RATES = [0.5, 1, 1.2, 1.5, 1.7, 2];
const ICON_PLAY = `
  <svg class="player-control-icon player-control-icon-fill" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M9 6v12l10-6Z" />
  </svg>
`;
const ICON_PAUSE = `
  <svg class="player-control-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M9 6v12" />
    <path d="M15 6v12" />
  </svg>
`;
const ICON_VOLUME = `
  <svg class="player-control-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M4 10v4h4l5 4V6l-5 4Z" />
    <path d="M16 9a4 4 0 0 1 0 6" />
    <path d="M18.5 6.5a8 8 0 0 1 0 11" />
  </svg>
`;
const ICON_VOLUME_MUTED = `
  <svg class="player-control-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
    <path d="M4 10v4h4l5 4V6l-5 4Z" />
    <path d="m18 10 4 4" />
    <path d="m22 10-4 4" />
  </svg>
`;
const FORMATTING_BUTTONS = [
  editorBoldBtn,
  editorItalicBtn,
  editorParagraphBtn,
  editorH2Btn,
  editorH3Btn,
  editorBulletsBtn,
  editorOrderedBtn,
  editorUndoBtn,
  editorRedoBtn,
  editorFindBtn,
  editorResetBtn,
  editorFindPrevBtn,
  editorFindNextBtn,
  editorFindCloseBtn,
];

const { state: prefs, t, savePrefs } = createUiContext();

function createDocumentState(variant) {
  return {
    variant,
    loaded: false,
    loading: false,
    fullMarkdown: "",
    prefixMarkdown: "",
    bodyMarkdown: "",
    editorHtml: "",
    edited: false,
    updatedAt: null,
    baseAvailable: false,
    dirty: false,
    saveState: "idle",
    saveTimer: null,
    savePromise: null,
    pendingSave: false,
    findMatches: [],
    activeMatchIndex: -1,
  };
}

const state = {
  jobId: root.dataset.jobId || "",
  job: null,
  missing: root.dataset.jobExists === "false",
  refreshError: "",
  pollTimer: null,
  metaTimer: null,
  actionError: "",
  actionWarning: "",
  downloadMenuOpen: false,
  infoOpen: false,
  viewOpen: false,
  findOpen: false,
  toolbarCollapsed: window.localStorage.getItem(TOOLBAR_COLLAPSED_KEY) === "true",
  playerVisible: window.localStorage.getItem(PLAYER_VISIBLE_KEY) !== "false",
  player: {
    sourceJobId: null,
    waveformJobId: null,
    waveform: null,
    waveformLoading: false,
    seeking: false,
    volumeOpen: false,
    rateOpen: false,
  },
  sync: {
    jobId: null,
    loaded: false,
    loading: false,
    available: false,
    paragraphs: [],
    items: [],
    byId: new Map(),
    activeId: null,
    seekModifier: false,
    suppressAutoScrollUntil: 0,
  },
  documents: {
    readable: createDocumentState("readable"),
  },
};

function getDocumentState(variant) {
  return state.documents[variant];
}

function getActiveVariant() {
  return "readable";
}

function getActiveDocumentState() {
  return getDocumentState(getActiveVariant());
}

function isReadableAvailable(job) {
  return Boolean(job) && job.status === "done" && job.readable_available;
}

function isVariantAvailable(job, variant = "readable") {
  return variant === "readable" && isReadableAvailable(job);
}

function getDocumentEndpoint(jobId) {
  return `/api/jobs/${encodeURIComponent(jobId)}/documents/readable`;
}

function getPreviewEndpoint(jobId) {
  return `/api/jobs/${encodeURIComponent(jobId)}/readable.preview`;
}

function getMarkdownEndpoint(jobId) {
  return `/api/jobs/${encodeURIComponent(jobId)}/readable.md`;
}

function getPdfEndpoint(jobId) {
  return `/api/jobs/${encodeURIComponent(jobId)}/readable.pdf`;
}

function buildPdfExportOptions() {
  return {
    font_size_px: Math.max(12, Math.min(32, Number(prefs.readerFontSizePx) || 18)),
    line_height_mode: prefs.readerLineHeight,
    align_mode: prefs.readerAlignMode,
    paragraph_gap: Boolean(prefs.readerParagraphGap),
    content_width_percent: Math.max(50, Math.min(100, Number(prefs.readerContentWidthPercent) || 100)),
  };
}

function buildPdfEndpoint(jobId) {
  const options = buildPdfExportOptions();
  const params = new URLSearchParams();
  params.set("font_size_px", String(options.font_size_px));
  params.set("line_height_mode", options.line_height_mode);
  params.set("align_mode", options.align_mode);
  params.set("paragraph_gap", options.paragraph_gap ? "true" : "false");
  params.set("content_width_percent", String(options.content_width_percent));
  return `${getPdfEndpoint(jobId)}?${params.toString()}`;
}

function getSourceEndpoint(jobId) {
  return `/api/jobs/${encodeURIComponent(jobId)}/source-audio`;
}

function getWaveformEndpoint(jobId, points = 900) {
  return `/api/jobs/${encodeURIComponent(jobId)}/waveform?points=${encodeURIComponent(points)}`;
}

function getReadableSyncEndpoint(jobId) {
  return `/api/jobs/${encodeURIComponent(jobId)}/sync/readable`;
}

function renderBanner(html = "") {
  resultBannerEl.innerHTML = html;
}

function renderStateCard({ tone = "normal", title, message, progress = null }) {
  const className = tone === "error" ? "error-card" : "state-card";
  const progressHtml = progress == null
    ? ""
    : `
      <div class="result-progress">
        <div class="progress-track"><div class="progress-bar" style="width:${Math.max(0, Math.min(Number(progress) || 0, 100))}%"></div></div>
        <div class="result-progress-value">${escapeHtml(`${Number(progress) || 0}%`)}</div>
      </div>
    `;

  return `
    <div class="${className}">
      <strong>${escapeHtml(title)}</strong>
      <p class="state-copy">${escapeHtml(message)}</p>
      ${progressHtml}
    </div>
  `;
}
function getDesktopApiObject() {
  if (typeof window === "undefined" || window.pywebview == null) {
    return null;
  }
  return window.pywebview?.api || null;
}

function getDesktopSaveApi(api) {
  if (!api || typeof api !== "object") {
    return null;
  }
  if (typeof api.save_markdown === "function") {
    return api.save_markdown.bind(api);
  }
  if (typeof api.saveMarkdown === "function") {
    return api.saveMarkdown.bind(api);
  }
  return null;
}

function getDesktopSavePdfApi(api) {
  if (!api || typeof api !== "object") {
    return null;
  }
  if (typeof api.save_pdf === "function") {
    return api.save_pdf.bind(api);
  }
  if (typeof api.savePdf === "function") {
    return api.savePdf.bind(api);
  }
  return null;
}

function getDesktopBridgeStatusApi(api) {
  if (!api || typeof api !== "object") {
    return null;
  }
  if (typeof api.bridge_status === "function") {
    return api.bridge_status.bind(api);
  }
  if (typeof api.bridgeStatus === "function") {
    return api.bridgeStatus.bind(api);
  }
  return null;
}

function waitForPywebviewApi(timeoutMs = 4000) {
  return new Promise((resolve) => {
    const currentApi = getDesktopApiObject();
    if (currentApi) {
      resolve(currentApi);
      return;
    }

    if (typeof window === "undefined" || window.pywebview == null) {
      resolve(null);
      return;
    }

    let settled = false;
    const finish = (api) => {
      if (settled) {
        return;
      }
      settled = true;
      clearInterval(intervalId);
      clearTimeout(timeoutId);
      window.removeEventListener("pywebviewready", onReady);
      resolve(api || null);
    };

    const onReady = () => finish(getDesktopApiObject());
    const intervalId = window.setInterval(() => {
      const api = getDesktopApiObject();
      if (api) {
        finish(api);
      }
    }, 50);
    const timeoutId = window.setTimeout(() => finish(getDesktopApiObject()), timeoutMs);
    window.addEventListener("pywebviewready", onReady, { once: true });
  });
}

async function resolveDesktopSaveApi(timeoutMs = 4000) {
  const immediateApi = getDesktopApiObject();
  const immediateSaveApi = getDesktopSaveApi(immediateApi);
  if (immediateSaveApi) {
    return { saveApi: immediateSaveApi, bridgeApi: immediateApi };
  }
  const api = await waitForPywebviewApi(timeoutMs);
  return { saveApi: getDesktopSaveApi(api), bridgeApi: api };
}

async function resolveDesktopSavePdfApi(timeoutMs = 4000) {
  const immediateApi = getDesktopApiObject();
  const immediateSaveApi = getDesktopSavePdfApi(immediateApi);
  if (immediateSaveApi) {
    return { saveApi: immediateSaveApi, bridgeApi: immediateApi };
  }
  const api = await waitForPywebviewApi(timeoutMs);
  return { saveApi: getDesktopSavePdfApi(api), bridgeApi: api };
}

async function resolveDesktopSaveApiWithRetry() {
  const firstAttempt = await resolveDesktopSaveApi(4000);
  if (firstAttempt.saveApi) {
    return firstAttempt;
  }
  await new Promise((resolve) => window.setTimeout(resolve, 300));
  return resolveDesktopSaveApi(2000);
}

async function resolveDesktopSavePdfApiWithRetry() {
  const firstAttempt = await resolveDesktopSavePdfApi(4000);
  if (firstAttempt.saveApi) {
    return firstAttempt;
  }
  await new Promise((resolve) => window.setTimeout(resolve, 300));
  return resolveDesktopSavePdfApi(2000);
}

function normalizeSaveResult(payload) {
  if (!payload) {
    return { status: "error", message: "Unknown desktop save response." };
  }
  let resultPayload = payload;
  if (typeof payload === "string") {
    try {
      resultPayload = JSON.parse(payload);
    } catch {
      return { status: "error", message: "Unknown desktop save response." };
    }
  }
  if (!resultPayload || typeof resultPayload !== "object") {
    return { status: "error", message: "Unknown desktop save response." };
  }
  if (resultPayload.ok) {
    return { status: "ok", path: resultPayload.path || "" };
  }
  if (resultPayload.cancelled) {
    return { status: "cancelled" };
  }
  return {
    status: "error",
    message: resultPayload.error || resultPayload.message || "Unknown desktop save error.",
  };
}

function buildDownloadFilename(job, variant, extension = "md") {
  const baseName = (job?.original_filename || job?.job_id || "voctarium")
    .replace(/[<>:"/\\|?*]+/g, "_")
    .replace(/\.+$/g, "")
    .trim();
  const stem = baseName.replace(/\.[^./\\]+$/u, "") || "voctarium";
  return `${stem}.readable.${extension}`;
}

function isDesktopRuntime() {
  return typeof window !== "undefined" && window.pywebview != null;
}

async function downloadInBrowser(endpoint, filename) {
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

function renderDownloadMenu() {
  const enabled = Boolean(state.job && isReadableAvailable(state.job));
  if (!enabled) {
    state.downloadMenuOpen = false;
  }
  if (downloadMenuBtn) {
    downloadMenuBtn.disabled = !enabled;
    downloadMenuBtn.classList.toggle("disabled", !enabled);
    downloadMenuBtn.classList.toggle("active", enabled && state.downloadMenuOpen);
    downloadMenuBtn.setAttribute("aria-expanded", String(enabled && state.downloadMenuOpen));
    downloadMenuBtn.setAttribute("aria-label", t("actions.downloadMenu"));
    downloadMenuBtn.setAttribute("title", t("actions.downloadMenu"));
  }
  if (downloadMenuEl) {
    downloadMenuEl.hidden = !enabled || !state.downloadMenuOpen;
  }
}

function renderActionLabels() {
  backLink?.setAttribute("aria-label", t("app.backToJobs"));
  backLink?.setAttribute("title", t("app.backToJobs"));
  removeBtn?.setAttribute("aria-label", t("actions.remove"));
  removeBtn?.setAttribute("title", t("actions.remove"));
}

function setDownloadDisabled() {
  state.downloadMenuOpen = false;
  downloadMenuBtn.disabled = true;
  downloadMenuBtn.classList.add("disabled");
  downloadLink.disabled = true;
  downloadLink.classList.add("disabled");
  downloadPdfBtn.disabled = true;
  downloadPdfBtn.classList.add("disabled");
  renderDownloadMenu();
}

function setDownloadEnabled() {
  downloadMenuBtn.disabled = false;
  downloadMenuBtn.classList.remove("disabled");
  downloadLink.disabled = false;
  downloadLink.classList.remove("disabled");
  downloadPdfBtn.disabled = false;
  downloadPdfBtn.classList.remove("disabled");
  renderDownloadMenu();
}

function splitDocumentScaffold(markdown) {
  const normalized = String(markdown || "").replace(/\r\n/g, "\n");
  const marker = normalized.match(/^##\s+.*$/m);
  if (!marker || marker.index == null) {
    return { prefixMarkdown: "", bodyMarkdown: normalized.trimStart() };
  }
  const headingEnd = marker.index + marker[0].length;
  let bodyStart = headingEnd;
  while (bodyStart < normalized.length && normalized[bodyStart] === "\n") {
    bodyStart += 1;
  }
  return {
    prefixMarkdown: normalized.slice(0, bodyStart),
    bodyMarkdown: normalized.slice(bodyStart).trimEnd(),
  };
}

function buildFullMarkdown(prefixMarkdown, bodyMarkdown) {
  const normalizedPrefix = String(prefixMarkdown || "").replace(/\r\n/g, "\n");
  const normalizedBody = String(bodyMarkdown || "").replace(/\r\n/g, "\n").trim();
  let full = normalizedPrefix;
  if (full && !full.endsWith("\n\n")) {
    full = full.replace(/\n*$/u, "\n\n");
  }
  if (normalizedBody) {
    full += normalizedBody;
    if (!full.endsWith("\n")) {
      full += "\n";
    }
    return full;
  }
  return full.trimEnd() ? `${full.trimEnd()}\n` : "";
}

function stripEditorFindHighlightsFrom(rootEl) {
  rootEl.querySelectorAll("mark.editor-find-match").forEach((mark) => {
    const parent = mark.parentNode;
    if (!parent) {
      return;
    }
    while (mark.firstChild) {
      parent.insertBefore(mark.firstChild, mark);
    }
    parent.removeChild(mark);
    parent.normalize();
  });
}

function cleanupEditorArticle(article) {
  const firstHeading = article.querySelector(":scope > h1");
  if (firstHeading && /^(стенограмма|transcript|читабельный текст|readable text)$/i.test(firstHeading.textContent.trim())) {
    firstHeading.remove();
  }

  const firstList = article.querySelector(":scope > ul");
  if (firstList) {
    const listText = firstList.textContent.toLowerCase();
    const metadataMarkers = ["файл:", "движок:", "модель:", "язык:", "создано:", "file:", "engine:", "model:", "language:", "created:"];
    const markerHits = metadataMarkers.filter((marker) => listText.includes(marker)).length;
    if (markerHits >= 2) {
      firstList.remove();
    }
  }

  const firstSubheading = article.querySelector(":scope > h2");
  if (firstSubheading && /^(текст|transcript)$/i.test(firstSubheading.textContent.trim())) {
    firstSubheading.remove();
  }
}

function renderInlineToHtml(text) {
  return escapeHtml(String(text || ""))
    .replace(INLINE_BOLD_RE, "<strong>$1</strong>")
    .replace(INLINE_ITALIC_RE, "<em>$1</em>");
}

function buildFallbackEditorHtml(markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const parts = [];
  let paragraph = [];
  let listType = null;
  let listItems = [];

  function flushParagraph() {
    if (!paragraph.length) {
      return;
    }
    parts.push(`<p>${renderInlineToHtml(paragraph.join(" "))}</p>`);
    paragraph = [];
  }

  function flushList() {
    if (!listType || !listItems.length) {
      listType = null;
      listItems = [];
      return;
    }
    parts.push(`<${listType}>${listItems.map((item) => `<li>${renderInlineToHtml(item)}</li>`).join("")}</${listType}>`);
    listType = null;
    listItems = [];
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    if (line.startsWith("### ")) {
      flushParagraph();
      flushList();
      parts.push(`<h3>${renderInlineToHtml(line.slice(4).trim())}</h3>`);
      continue;
    }
    if (line.startsWith("## ")) {
      flushParagraph();
      flushList();
      parts.push(`<h2>${renderInlineToHtml(line.slice(3).trim())}</h2>`);
      continue;
    }
    if (line.startsWith("- ")) {
      flushParagraph();
      if (listType !== "ul") {
        flushList();
        listType = "ul";
      }
      listItems.push(line.slice(2).trim());
      continue;
    }
    const orderedMatch = line.match(ORDERED_LIST_RE);
    if (orderedMatch) {
      flushParagraph();
      if (listType !== "ol") {
        flushList();
        listType = "ol";
      }
      listItems.push(orderedMatch[1].trim());
      continue;
    }
    flushList();
    paragraph.push(line);
  }

  flushParagraph();
  flushList();
  return parts.join("");
}

function extractEditorBodyHtml(previewHtml) {
  const parser = new DOMParser();
  const documentNode = parser.parseFromString(previewHtml, "text/html");
  const article = documentNode.querySelector(".md-preview");
  if (!article) {
    return "";
  }
  cleanupEditorArticle(article);
  return article.innerHTML.trim();
}

function getEditorSurface() {
  return resultContentEl.querySelector(".editor-surface");
}

function normalizeSyncText(value) {
  return String(value || "")
    .replace(/\u00a0/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleLowerCase();
}

function unwrapElement(element) {
  const parent = element.parentNode;
  if (!parent) {
    return;
  }
  while (element.firstChild) {
    parent.insertBefore(element.firstChild, element);
  }
  parent.removeChild(element);
  parent.normalize();
}

function unwrapSyncSentenceSpans(rootEl) {
  rootEl.querySelectorAll("span.sync-sentence").forEach(unwrapElement);
}

function resetReadableSync() {
  const surface = getEditorSurface();
  if (surface) {
    surface.classList.remove("sync-seek-modifier");
    unwrapSyncSentenceSpans(surface);
    surface.querySelectorAll("[data-sync-id]").forEach((node) => {
      node.classList.remove("sync-paragraph", "sync-sentence", "sync-active");
      delete node.dataset.syncId;
      delete node.dataset.syncStart;
      delete node.dataset.syncEnd;
    });
  }
  state.sync.jobId = null;
  state.sync.loaded = false;
  state.sync.loading = false;
  state.sync.available = false;
  state.sync.paragraphs = [];
  state.sync.items = [];
  state.sync.byId = new Map();
  state.sync.activeId = null;
}

function setReadableSyncPayload(jobId, payload) {
  if (payload?.version !== 2 || payload?.granularity !== "sentence") {
    resetReadableSync();
    return;
  }

  const paragraphs = Array.isArray(payload.paragraphs)
    ? payload.paragraphs.map((paragraph, index) => ({
      id: String(paragraph?.id || `p${index}`),
      index: Number.isInteger(paragraph?.index) ? paragraph.index : index,
      text: String(paragraph?.text || "").trim(),
      normalizedText: normalizeSyncText(paragraph?.text || ""),
    })).filter((paragraph) => paragraph.text)
    : [];

  const items = Array.isArray(payload.items)
    ? payload.items.map((item, index) => {
      const id = String(item?.id || `s${index}`);
      const start = Number(item?.start);
      const end = Number(item?.end);
      const text = String(item?.text || "").trim();
      if (!id || !Number.isFinite(start) || !Number.isFinite(end) || !text) {
        return null;
      }
      const safeStart = Math.max(0, start);
      return {
        id,
        index,
        paragraphId: String(item?.paragraph_id || ""),
        paragraphIndex: Number.isInteger(item?.paragraph_index) ? item.paragraph_index : 0,
        sentenceIndex: Number.isInteger(item?.sentence_index) ? item.sentence_index : index,
        start: safeStart,
        end: Math.max(safeStart, end),
        text,
        normalizedText: normalizeSyncText(text),
      };
    }).filter(Boolean).map((item, index) => ({ ...item, index }))
    : [];

  state.sync.jobId = jobId;
  state.sync.loaded = true;
  state.sync.available = items.length > 0;
  state.sync.paragraphs = paragraphs;
  state.sync.items = items;
  state.sync.byId = new Map(items.map((item) => [item.id, item]));
  state.sync.activeId = null;
}

async function loadReadableSync({ force = false } = {}) {
  const job = state.job;
  if (!job || job.status !== "done" || !job.readable_available || !job.readable_sync_available) {
    resetReadableSync();
    return;
  }
  if (!force && state.sync.loaded && state.sync.jobId === job.job_id) {
    return;
  }
  if (state.sync.loading) {
    return;
  }

  state.sync.loading = true;
  try {
    const response = await fetch(getReadableSyncEndpoint(job.job_id));
    if (!response.ok) {
      resetReadableSync();
      return;
    }
    const payload = await response.json();
    setReadableSyncPayload(job.job_id, payload);
  } catch {
    resetReadableSync();
  } finally {
    state.sync.loading = false;
  }
}

function editorTextBlocks(surface) {
  return Array.from(surface.children)
    .filter((node) => {
      if (!(node instanceof HTMLElement)) {
        return false;
      }
      if (!["P", "DIV"].includes(node.tagName)) {
        return false;
      }
      if (!normalizeSyncText(node.textContent)) {
        return false;
      }
      return !node.querySelector("p, div, li, ul, ol");
    });
}

function buildNormalizedOffsetMap(value) {
  const raw = String(value || "");
  let normalized = "";
  const offsets = [];
  let previousWasSpace = false;
  for (let index = 0; index < raw.length; index += 1) {
    const char = raw[index];
    if (/\s/u.test(char)) {
      if (normalized && !previousWasSpace) {
        normalized += " ";
        offsets.push(index);
        previousWasSpace = true;
      }
      continue;
    }
    normalized += char.toLocaleLowerCase();
    offsets.push(index);
    previousWasSpace = false;
  }
  if (normalized.endsWith(" ")) {
    normalized = normalized.slice(0, -1);
    offsets.pop();
  }
  return { normalized, offsets };
}

function findTextRange(rawText, targetText, fromOffset = 0) {
  const source = String(rawText || "");
  const target = String(targetText || "").trim();
  if (!source || !target) {
    return null;
  }

  const exactIndex = source.toLocaleLowerCase().indexOf(target.toLocaleLowerCase(), Math.max(0, fromOffset));
  if (exactIndex !== -1) {
    return { start: exactIndex, end: exactIndex + target.length };
  }

  const sourceMap = buildNormalizedOffsetMap(source);
  const normalizedTarget = normalizeSyncText(target);
  if (!sourceMap.normalized || !normalizedTarget) {
    return null;
  }

  let searchIndex = 0;
  while (searchIndex < sourceMap.normalized.length) {
    const matchIndex = sourceMap.normalized.indexOf(normalizedTarget, searchIndex);
    if (matchIndex === -1) {
      return null;
    }
    const rawStart = sourceMap.offsets[matchIndex];
    const rawEnd = sourceMap.offsets[matchIndex + normalizedTarget.length - 1] + 1;
    if (rawStart >= Math.max(0, fromOffset - 2)) {
      return { start: rawStart, end: rawEnd };
    }
    searchIndex = matchIndex + Math.max(1, normalizedTarget.length);
  }
  return null;
}

function collectTextNodeRanges(rootEl) {
  const ranges = [];
  let offset = 0;
  const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const length = node.nodeValue.length;
    ranges.push({ node, start: offset, end: offset + length });
    offset += length;
  }
  return ranges;
}

function wrapTextRange(rootEl, start, end, item) {
  if (end <= start) {
    return;
  }
  const ranges = collectTextNodeRanges(rootEl)
    .filter((range) => range.end > start && range.start < end)
    .reverse();

  ranges.forEach((range) => {
    const localStart = Math.max(0, start - range.start);
    const localEnd = Math.min(range.node.nodeValue.length, end - range.start);
    if (localEnd <= localStart) {
      return;
    }
    let targetNode = range.node;
    if (localEnd < targetNode.nodeValue.length) {
      targetNode.splitText(localEnd);
    }
    if (localStart > 0) {
      targetNode = targetNode.splitText(localStart);
    }
    if (!targetNode.nodeValue) {
      return;
    }
    const span = document.createElement("span");
    span.className = "sync-sentence";
    span.dataset.syncId = item.id;
    span.dataset.syncStart = String(item.start);
    span.dataset.syncEnd = String(item.end);
    targetNode.parentNode.insertBefore(span, targetNode);
    span.appendChild(targetNode);
  });
}

function wrapSentenceItemsInBlock(block, items) {
  const ranges = [];
  const rawText = block.textContent || "";
  let cursor = 0;
  items.forEach((item) => {
    const range = findTextRange(rawText, item.text, cursor);
    if (!range) {
      return;
    }
    ranges.push({ ...range, item });
    cursor = range.end;
  });

  ranges.reverse().forEach((range) => {
    wrapTextRange(block, range.start, range.end, range.item);
  });
}

function applyReadableSyncToEditorSurface() {
  const surface = getEditorSurface();
  if (!surface) {
    return;
  }

  unwrapSyncSentenceSpans(surface);
  surface.classList.toggle("sync-seek-modifier", state.sync.seekModifier && state.sync.available);

  if (!state.sync.available || !state.sync.items.length) {
    state.sync.activeId = null;
    return;
  }

  const blocks = editorTextBlocks(surface);
  const usedParagraphIndexes = new Set();
  let paragraphCursor = 0;

  blocks.forEach((block) => {
    const normalized = normalizeSyncText(block.textContent);
    let paragraph = state.sync.paragraphs.find((candidate) => (
      candidate.normalizedText === normalized && !usedParagraphIndexes.has(candidate.index)
    ));

    if (!paragraph) {
      while (
        paragraphCursor < state.sync.paragraphs.length
        && usedParagraphIndexes.has(state.sync.paragraphs[paragraphCursor].index)
      ) {
        paragraphCursor += 1;
      }
      paragraph = state.sync.paragraphs[paragraphCursor] || null;
    }

    if (!paragraph) {
      return;
    }
    usedParagraphIndexes.add(paragraph.index);
    paragraphCursor = Math.max(paragraphCursor, paragraph.index + 1);
    const sentenceItems = state.sync.items.filter((item) => item.paragraphIndex === paragraph.index);
    wrapSentenceItemsInBlock(block, sentenceItems);
  });

  updateActiveSyncFromPlayback({ scroll: false });
}

function setSyncSeekModifier(enabled) {
  state.sync.seekModifier = Boolean(enabled);
  const surface = getEditorSurface();
  if (surface) {
    surface.classList.toggle("sync-seek-modifier", state.sync.seekModifier && state.sync.available);
  }
}

function getSyncElementsById(syncId) {
  const surface = getEditorSurface();
  if (!surface || !syncId) {
    return [];
  }
  return Array.from(surface.querySelectorAll("span.sync-sentence[data-sync-id]"))
    .filter((node) => node.dataset.syncId === syncId);
}

function getFirstSyncElementById(syncId) {
  return getSyncElementsById(syncId)[0] || null;
}

function getSyncItemAtTime(seconds) {
  const current = Number(seconds);
  if (!Number.isFinite(current) || !state.sync.available) {
    return null;
  }

  let lastStarted = null;
  for (const item of state.sync.items) {
    if (current >= item.start && current <= item.end) {
      return item;
    }
    if (current >= item.start) {
      lastStarted = item;
      continue;
    }
    break;
  }
  return lastStarted;
}

function shouldAutoscrollSync() {
  if (!resultAudioEl || resultAudioEl.paused || state.findOpen) {
    return false;
  }
  if (Date.now() < state.sync.suppressAutoScrollUntil) {
    return false;
  }
  const surface = getEditorSurface();
  const active = document.activeElement;
  return !(surface && active && surface.contains(active));
}

function scrollActiveSyncIntoView() {
  if (!shouldAutoscrollSync()) {
    return;
  }
  const activeNode = getFirstSyncElementById(state.sync.activeId);
  if (!activeNode) {
    return;
  }
  const container = resultContentEl;
  const nodeRect = activeNode.getBoundingClientRect();
  const containerRect = container.getBoundingClientRect();
  const topGap = nodeRect.top - containerRect.top;
  const bottomGap = nodeRect.bottom - containerRect.bottom;
  const targetOffset = Math.max(28, containerRect.height * 0.18);

  if (topGap < targetOffset || bottomGap > -targetOffset) {
    container.scrollTo({
      top: Math.max(0, container.scrollTop + topGap - targetOffset),
      behavior: "smooth",
    });
  }
}

function updateActiveSyncFromPlayback({ scroll = true } = {}) {
  if (!state.sync.available || !resultAudioEl) {
    return;
  }
  const item = getSyncItemAtTime(resultAudioEl.currentTime);
  const nextId = item?.id || null;
  if (state.sync.activeId === nextId) {
    if (scroll && nextId) {
      scrollActiveSyncIntoView();
    }
    return;
  }

  getSyncElementsById(state.sync.activeId).forEach((node) => node.classList.remove("sync-active"));
  state.sync.activeId = nextId;
  getSyncElementsById(nextId).forEach((node) => node.classList.add("sync-active"));
  if (scroll && nextId) {
    scrollActiveSyncIntoView();
  }
}

function suppressSyncAutoscroll(ms = 4000) {
  state.sync.suppressAutoScrollUntil = Date.now() + ms;
}

function seekPlayerToSyncItem(item) {
  if (!item || !isSourcePlayable(state.job)) {
    return;
  }
  ensurePlayerSource(state.job);
  const wasPlaying = !resultAudioEl.paused;
  try {
    resultAudioEl.currentTime = Math.max(0, item.start);
  } catch {
    resultAudioEl.addEventListener("loadedmetadata", () => {
      resultAudioEl.currentTime = Math.max(0, item.start);
    }, { once: true });
  }
  updateActiveSyncFromPlayback({ scroll: false });
  renderPlayerControls();
  if (wasPlaying) {
    void resultAudioEl.play().catch((error) => {
      state.actionError = t("result.playerPlayError", { message: error?.message || String(error) });
      renderJobBanner();
    });
  }
}

function getPlainEditorText(surface) {
  if (!surface) {
    return "";
  }
  const clone = surface.cloneNode(true);
  stripEditorFindHighlightsFrom(clone);
  return clone.innerText.replace(/\s+/g, " ").trim();
}

function countWordsAndChars(text) {
  const normalized = String(text || "").trim();
  if (!normalized) {
    return { words: 0, chars: 0 };
  }
  return {
    words: normalized.split(/\s+/u).filter(Boolean).length,
    chars: normalized.replace(/\s/g, "").length,
  };
}
function renderWordCount() {
  const doc = getActiveDocumentState();
  if (!doc.loaded || !isReadableAvailable(state.job)) {
    editorWordCountEl.textContent = "";
    return;
  }
  const surface = getEditorSurface();
  const text = surface ? getPlainEditorText(surface) : doc.bodyMarkdown;
  editorWordCountEl.textContent = t("result.wordsChars", countWordsAndChars(text));
}

function getEditorStatusLabel(saveState) {
  switch (saveState) {
    case "dirty":
      return t("result.editorStatusDirty");
    case "saving":
      return t("result.editorStatusSaving");
    case "saved":
      return t("result.editorStatusSaved");
    case "error":
      return t("result.editorStatusError");
    default:
      return t("result.editorStatusIdle");
  }
}

function renderFindStatus() {
  const doc = getActiveDocumentState();
  if (!state.findOpen) {
    editorFindStatusEl.textContent = t("result.findNoResults");
    return;
  }
  if (!doc.findMatches.length) {
    editorFindStatusEl.textContent = t("result.findNoResults");
    return;
  }
  editorFindStatusEl.textContent = t("result.findResults", {
    current: doc.activeMatchIndex + 1,
    total: doc.findMatches.length,
  });
}

function renderJobBanner() {
  const job = state.job;
  if (state.actionError) {
    renderBanner(renderStateCard({ tone: "error", title: t("result.editorSaveTitle"), message: state.actionError }));
  } else if (state.actionWarning) {
    renderBanner(renderStateCard({ title: t("actions.download"), message: state.actionWarning }));
  } else if (state.refreshError) {
    renderBanner(renderStateCard({ tone: "error", title: t("status.requestError", { message: "" }).replace(/:\s*$/, ""), message: state.refreshError }));
  } else if (!job || state.missing) {
    renderBanner(renderStateCard({ tone: "error", title: t("result.notFoundTitle"), message: t("result.notFound") }));
  } else if (job.status === "queued") {
    renderBanner(renderStateCard({ title: t("result.waitingTitle"), message: t("result.queued"), progress: job.progress_percent || 0 }));
  } else if (job.status === "processing") {
    renderBanner(renderStateCard({ title: t("result.waitingTitle"), message: t("result.processing"), progress: job.progress_percent || 0 }));
  } else if (job.status === "failed") {
    renderBanner(renderStateCard({ tone: "error", title: t("result.failedTitle"), message: job.error || t("result.failed") }));
  } else if (job.status === "cancelled") {
    renderBanner(renderStateCard({ title: t("result.cancelledTitle"), message: job.error || t("result.cancelled") }));
  } else if (!job.readable_available) {
    renderBanner(renderStateCard({ title: t("result.metaTitle"), message: t("result.unavailable") }));
  } else {
    renderBanner("");
  }
}

function renderEditorStatus() {
  const doc = getActiveDocumentState();
  const editorVisible = isReadableAvailable(state.job);
  const toolbarVisible = editorVisible && !state.toolbarCollapsed;
  editorToolbarEl.hidden = !toolbarVisible;
  resultReaderStageEl.classList.toggle("has-search", toolbarVisible && state.findOpen);
  toolbarToggleBtn.disabled = !editorVisible;
  const toolbarToggleLabel = state.toolbarCollapsed ? t("result.toolbarShow") : t("result.toolbarHide");
  toolbarToggleBtn.setAttribute("aria-label", toolbarToggleLabel);
  toolbarToggleBtn.setAttribute("title", toolbarToggleLabel);
  toolbarToggleBtn.setAttribute("aria-expanded", String(toolbarVisible));
  toolbarToggleBtn.classList.toggle("active", toolbarVisible);
  toolbarToggleBtn.classList.toggle("is-collapsed", state.toolbarCollapsed);
  FORMATTING_BUTTONS.forEach((button) => {
    button.disabled = !toolbarVisible;
  });
  editorSaveBtn.disabled = !toolbarVisible || doc.saveState === "saving" || !doc.loaded || !doc.dirty;
  editorFindBtn.classList.toggle("active", toolbarVisible && state.findOpen);
  if (!editorVisible) {
    editorFindbarEl.hidden = true;
    editorSaveStatusEl.textContent = t("result.editorStatusIdle");
    editorDirtyIndicatorEl.hidden = true;
    editorWordCountEl.textContent = "";
    return;
  }
  editorSaveStatusEl.textContent = getEditorStatusLabel(doc.saveState);
  editorDirtyIndicatorEl.hidden = !doc.dirty;
  editorFindbarEl.hidden = !toolbarVisible || !state.findOpen;
  editorFindInput.placeholder = t("result.findPlaceholder");
  renderWordCount();
  renderFindStatus();
}

function isSourcePlayable(job) {
  return Boolean(job) && TERMINAL_STATUSES.has(job.status) && job.source_available;
}

function formatPlayerTime(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const totalSeconds = Math.floor(value);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const rest = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function getPlayerDuration() {
  if (Number.isFinite(resultAudioEl.duration) && resultAudioEl.duration > 0) {
    return resultAudioEl.duration;
  }
  return Number(state.player.waveform?.duration_seconds) || 0;
}

function normalizePlayerRate(value) {
  const rawRate = Number(value);
  if (!Number.isFinite(rawRate)) {
    return 1;
  }
  return PLAYER_RATES.reduce((closest, candidate) => (
    Math.abs(candidate - rawRate) < Math.abs(closest - rawRate) ? candidate : closest
  ), 1);
}

function formatPlayerRate(rate) {
  const normalized = normalizePlayerRate(rate);
  return normalized === 1 ? "1.0x" : `${normalized}x`;
}

function setPlayerRate(rate, { persist = true } = {}) {
  const normalized = normalizePlayerRate(rate);
  resultAudioEl.playbackRate = normalized;
  if (persist) {
    window.localStorage.setItem(PLAYER_RATE_KEY, String(normalized));
  }
  renderPlayerControls();
}

function drawPlayerWaveform() {
  if (!playerWaveformEl) {
    return;
  }
  const canvas = playerWaveformEl;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  const ratio = window.devicePixelRatio || 1;
  const nextWidth = Math.floor(width * ratio);
  const nextHeight = Math.floor(height * ratio);
  if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
    canvas.width = nextWidth;
    canvas.height = nextHeight;
  }

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return;
  }
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const styles = getComputedStyle(document.body);
  const muted = styles.getPropertyValue("--muted").trim() || "#98a7ba";
  const accent = styles.getPropertyValue("--accent").trim() || "#67adff";
  const peaks = Array.isArray(state.player.waveform?.peaks) ? state.player.waveform.peaks : [];
  const duration = getPlayerDuration();
  const progress = duration > 0 ? Math.max(0, Math.min(1, resultAudioEl.currentTime / duration)) : 0;
  const center = height / 2;
  const gap = 2;
  const barWidth = 2;
  const stride = barWidth + gap;
  const barCount = Math.max(1, Math.floor(width / stride));

  for (let index = 0; index < barCount; index += 1) {
    const peakIndex = peaks.length ? Math.min(peaks.length - 1, Math.floor(index * peaks.length / barCount)) : index;
    const fallback = 0.18 + 0.16 * Math.sin(index * 0.47) ** 2;
    const peak = peaks.length ? Math.max(0.04, Number(peaks[peakIndex]) || 0) : fallback;
    const barHeight = Math.max(3, peak * (height - 8));
    const x = index * stride;
    const y = center - barHeight / 2;
    ctx.fillStyle = index / barCount <= progress ? accent : muted;
    ctx.globalAlpha = index / barCount <= progress ? 0.95 : 0.58;
    ctx.fillRect(x, y, barWidth, barHeight);
  }
  ctx.globalAlpha = 1;
}

function renderPlayerControls() {
  const playable = isSourcePlayable(state.job);
  const visible = playable && state.playerVisible;
  resultPlayerEl.hidden = !visible;
  playerToggleBtn.hidden = !playable;
  playerToggleBtn.disabled = !playable;
  const toggleLabel = state.playerVisible ? t("result.playerHide") : t("result.playerShow");
  playerToggleBtn.setAttribute("aria-label", toggleLabel);
  playerToggleBtn.setAttribute("title", toggleLabel);
  playerToggleBtn.classList.toggle("active", visible);

  if (!playable) {
    resultAudioEl.pause();
    resultAudioEl.removeAttribute("src");
    state.player.sourceJobId = null;
    state.player.waveformJobId = null;
    state.player.waveform = null;
    state.player.rateOpen = false;
    state.player.volumeOpen = false;
    playerRatePopoverEl.hidden = true;
    playerVolumePopoverEl.hidden = true;
    return;
  }

  playerRewindBtn.setAttribute("aria-label", t("result.playerRewind"));
  playerRewindBtn.setAttribute("title", t("result.playerRewind"));
  playerForwardBtn.setAttribute("aria-label", t("result.playerForward"));
  playerForwardBtn.setAttribute("title", t("result.playerForward"));
  const playLabel = resultAudioEl.paused ? t("result.playerPlay") : t("result.playerPause");
  playerPlayBtn.setAttribute("aria-label", playLabel);
  playerPlayBtn.setAttribute("title", playLabel);
  playerPlayIconEl.innerHTML = resultAudioEl.paused ? ICON_PLAY : ICON_PAUSE;
  const muteLabel = t("result.playerVolume");
  const rateLabel = t("result.playerRate");
  const rate = normalizePlayerRate(resultAudioEl.playbackRate || 1);
  playerRateBtn.textContent = formatPlayerRate(rate);
  playerRateBtn.setAttribute("aria-label", rateLabel);
  playerRateBtn.setAttribute("title", rateLabel);
  playerRateBtn.setAttribute("aria-expanded", String(state.player.rateOpen));
  playerRatePopoverEl.hidden = !state.player.rateOpen;
  playerRateOptions.forEach((button) => {
    const buttonRate = normalizePlayerRate(button.dataset.rate);
    button.classList.toggle("active", buttonRate === rate);
    button.setAttribute("aria-pressed", String(buttonRate === rate));
  });
  playerMuteBtn.setAttribute("aria-label", muteLabel);
  playerMuteBtn.setAttribute("title", muteLabel);
  playerMuteBtn.setAttribute("aria-expanded", String(state.player.volumeOpen));
  playerMuteBtn.innerHTML = resultAudioEl.muted || resultAudioEl.volume === 0 ? ICON_VOLUME_MUTED : ICON_VOLUME;
  playerVolumePopoverEl.hidden = !state.player.volumeOpen;
  playerVolumeInput.value = String(resultAudioEl.volume);
  playerCurrentTimeEl.textContent = formatPlayerTime(resultAudioEl.currentTime);
  playerDurationEl.textContent = formatPlayerTime(getPlayerDuration());
  drawPlayerWaveform();
}

function ensurePlayerSource(job) {
  if (!isSourcePlayable(job)) {
    renderPlayerControls();
    return;
  }
  if (state.player.sourceJobId === job.job_id) {
    renderPlayerControls();
    return;
  }
  state.player.sourceJobId = job.job_id;
  state.player.waveformJobId = null;
  state.player.waveform = null;
  resultAudioEl.src = getSourceEndpoint(job.job_id);
  const storedVolumeRaw = window.localStorage.getItem(PLAYER_VOLUME_KEY);
  const storedVolume = Number(storedVolumeRaw);
  resultAudioEl.volume = storedVolumeRaw !== null && Number.isFinite(storedVolume) ? Math.max(0, Math.min(1, storedVolume)) : 1;
  resultAudioEl.muted = window.localStorage.getItem(PLAYER_MUTED_KEY) === "true";
  setPlayerRate(window.localStorage.getItem(PLAYER_RATE_KEY), { persist: false });
  playerVolumeInput.value = String(resultAudioEl.volume);
  loadPlayerWaveform(job);
  renderPlayerControls();
}

async function loadPlayerWaveform(job) {
  if (!isSourcePlayable(job) || state.player.waveformLoading || state.player.waveformJobId === job.job_id) {
    return;
  }
  state.player.waveformLoading = true;
  try {
    const response = await fetch(getWaveformEndpoint(job.job_id, 900));
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    state.player.waveform = await response.json();
    state.player.waveformJobId = job.job_id;
  } catch {
    state.player.waveform = null;
    state.player.waveformJobId = job.job_id;
  } finally {
    state.player.waveformLoading = false;
    renderPlayerControls();
  }
}

function setPlayerVisible(visible) {
  state.playerVisible = Boolean(visible);
  window.localStorage.setItem(PLAYER_VISIBLE_KEY, String(state.playerVisible));
  if (!state.playerVisible) {
    resultAudioEl.pause();
  }
  renderPlayerControls();
}

function seekPlayerFromPointer(event) {
  const duration = getPlayerDuration();
  if (duration <= 0) {
    return;
  }
  const rect = playerWaveformEl.getBoundingClientRect();
  const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  resultAudioEl.currentTime = ratio * duration;
  renderPlayerControls();
  updateActiveSyncFromPlayback({ scroll: false });
}

async function togglePlayerPlayback() {
  if (!isSourcePlayable(state.job)) {
    return;
  }
  ensurePlayerSource(state.job);
  if (resultAudioEl.paused) {
    try {
      await resultAudioEl.play();
      state.actionError = "";
      renderJobBanner();
    } catch (error) {
      state.actionError = t("result.playerPlayError", { message: error?.message || String(error) });
      renderJobBanner();
    }
  } else {
    resultAudioEl.pause();
  }
  renderPlayerControls();
}

function setDocumentDirty(variant, dirty) {
  const doc = getDocumentState(variant);
  doc.dirty = dirty;
  if (dirty) {
    state.actionError = "";
  }
  if (dirty && doc.saveState !== "saving") {
    doc.saveState = "dirty";
  }
  if (!dirty && doc.saveState === "dirty") {
    doc.saveState = "idle";
  }
  renderEditorStatus();
}

function scheduleAutosave(variant) {
  const doc = getDocumentState(variant);
  if (doc.saveTimer) {
    window.clearTimeout(doc.saveTimer);
  }
  doc.saveTimer = window.setTimeout(() => {
    void saveDocument(variant);
  }, 800);
}

function serializeInlineNode(node) {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.nodeValue || "";
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return "";
  }
  const element = node;
  if (element.matches("mark.editor-find-match")) {
    return Array.from(element.childNodes).map(serializeInlineNode).join("");
  }
  if (element.tagName === "BR") {
    return " ";
  }
  const content = Array.from(element.childNodes).map(serializeInlineNode).join("");
  if (element.tagName === "STRONG" || element.tagName === "B") {
    return content.trim() ? `**${content}**` : "";
  }
  if (element.tagName === "EM" || element.tagName === "I") {
    return content.trim() ? `*${content}*` : "";
  }
  return content;
}

function serializeParagraphNode(node) {
  return Array.from(node.childNodes)
    .map(serializeInlineNode)
    .join("")
    .replace(/\s+/g, " ")
    .trim();
}

function serializeListNode(node, ordered) {
  return Array.from(node.children)
    .filter((item) => item.tagName === "LI")
    .map((item, index) => {
      const text = serializeParagraphNode(item);
      return ordered ? `${index + 1}. ${text}` : `- ${text}`;
    })
    .filter(Boolean)
    .join("\n");
}

function serializeEditorSurfaceToMarkdown(surface) {
  const clone = surface.cloneNode(true);
  stripEditorFindHighlightsFrom(clone);
  const blocks = [];

  for (const node of Array.from(clone.childNodes)) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = (node.nodeValue || "").trim();
      if (text) {
        blocks.push(text);
      }
      continue;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) {
      continue;
    }
    const element = node;
    if (element.tagName === "H2") {
      const text = serializeParagraphNode(element);
      if (text) {
        blocks.push(`## ${text}`);
      }
      continue;
    }
    if (element.tagName === "H3") {
      const text = serializeParagraphNode(element);
      if (text) {
        blocks.push(`### ${text}`);
      }
      continue;
    }
    if (element.tagName === "UL") {
      const listMarkdown = serializeListNode(element, false);
      if (listMarkdown) {
        blocks.push(listMarkdown);
      }
      continue;
    }
    if (element.tagName === "OL") {
      const listMarkdown = serializeListNode(element, true);
      if (listMarkdown) {
        blocks.push(listMarkdown);
      }
      continue;
    }
    const text = serializeParagraphNode(element);
    if (text) {
      blocks.push(text);
    }
  }
  return blocks.join("\n\n").trim();
}

async function loadDocumentVariant(variant, { force = false } = {}) {
  const doc = getDocumentState(variant);
  if (doc.loaded && !force) {
    return doc;
  }
  if (doc.loading) {
    return doc;
  }

  doc.loading = true;
  try {
    const [documentResponse, previewResponse] = await Promise.all([
      fetch(getDocumentEndpoint(state.jobId)),
      fetch(getPreviewEndpoint(state.jobId)),
    ]);

    if (!documentResponse.ok) {
      throw new Error(`HTTP ${documentResponse.status}`);
    }

    const payload = await documentResponse.json();
    const fullMarkdown = payload.markdown || "";
    const split = splitDocumentScaffold(fullMarkdown);
    let editorHtml = "";
    if (previewResponse.ok) {
      editorHtml = extractEditorBodyHtml(await previewResponse.text());
    }
    if (!editorHtml) {
      editorHtml = buildFallbackEditorHtml(split.bodyMarkdown);
    }

    doc.fullMarkdown = fullMarkdown;
    doc.prefixMarkdown = split.prefixMarkdown;
    doc.bodyMarkdown = split.bodyMarkdown;
    doc.editorHtml = editorHtml;
    doc.edited = Boolean(payload.edited);
    doc.updatedAt = payload.updated_at || null;
    doc.baseAvailable = Boolean(payload.base_available);
    doc.loaded = true;
    doc.dirty = false;
    doc.saveState = "idle";
    doc.findMatches = [];
    doc.activeMatchIndex = -1;
    return doc;
  } finally {
    doc.loading = false;
  }
}

function renderContentPlaceholder(message) {
  resultContentEl.className = "result-content-card empty";
  resultContentEl.textContent = message;
}

function applyReaderPrefs() {
  const lineHeightMap = { compact: 1.32, normal: 1.42, relaxed: 1.56 };
  resultContentEl.style.setProperty("--reader-font-size-px", `${prefs.readerFontSizePx}px`);
  resultContentEl.style.setProperty("--reader-line-height", String(lineHeightMap[prefs.readerLineHeight] || 1.42));
  resultContentEl.style.setProperty("--reader-content-width-percent", String(Math.max(50, Math.min(100, Number(prefs.readerContentWidthPercent) || 100))));

  const justifyEnabled = isReadableAvailable(state.job);
  resultContentEl.classList.toggle("reader-justify", justifyEnabled && prefs.readerAlignMode === "justify");
  resultContentEl.classList.toggle("reader-justify-hyphen", justifyEnabled && prefs.readerAlignMode === "justify_hyphen");
  resultContentEl.classList.toggle("reader-paragraph-gap", justifyEnabled && Boolean(prefs.readerParagraphGap));
}

function renderReaderControls() {
  const controlsVisible = !state.toolbarCollapsed && state.viewOpen;
  readerControlsPanelEl.hidden = !controlsVisible;
  viewToggleBtn.classList.toggle("active", controlsVisible);
  readerFontSizeInput.value = String(prefs.readerFontSizePx);
  readerLineCompactBtn.classList.toggle("active", prefs.readerLineHeight === "compact");
  readerLineNormalBtn.classList.toggle("active", prefs.readerLineHeight === "normal");
  readerLineRelaxedBtn.classList.toggle("active", prefs.readerLineHeight === "relaxed");
  readerWidthInput.value = String(Math.max(50, Math.min(100, Number(prefs.readerContentWidthPercent) || 100)));
  readerWidthValue.textContent = `${readerWidthInput.value}%`;
  readerJustifyLeftBtn.classList.toggle("active", prefs.readerAlignMode === "left");
  readerJustifyFullBtn.classList.toggle("active", prefs.readerAlignMode === "justify");
  readerJustifyHyphenBtn.classList.toggle("active", prefs.readerAlignMode === "justify_hyphen");
  readerParagraphGapInput.checked = Boolean(prefs.readerParagraphGap);
  applyReaderPrefs();
}

function renderMeta() {
  const job = state.job;
  const rows = [
    { key: "details.status", value: job ? getStatusLabel(job, t) : t("common.unknown") },
    { key: "details.model", value: job?.model_id || t("common.unknown") },
    { key: "details.progress", value: job ? `${job.progress_percent || 0}%` : t("common.never") },
    { key: "details.created", value: job ? formatDate(job.created_at, prefs.lang, t) : t("common.never") },
    { key: "details.finished", value: job?.finished_at ? formatDate(job.finished_at, prefs.lang, t) : t("common.never") },
    { key: "details.elapsed", value: job ? formatDuration(job.started_at, job.finished_at, t) : t("common.never") },
    { key: "details.retryOf", value: job?.retry_of_job_id || t("common.none") },
    { key: "details.timestamps", value: job ? (job.include_timestamps ? t("common.enabled") : t("common.disabled")) : t("common.never") },
    { key: "details.jobId", value: state.jobId || t("common.unknown") },
  ];

  resultMetaEl.innerHTML = rows.map((row) => `
    <div class="result-meta-item">
      <div class="result-meta-label">${escapeHtml(t(row.key))}</div>
      <div class="result-meta-value">${escapeHtml(row.value)}</div>
    </div>
  `).join("");
}

function renderHeader() {
  const job = state.job;
  const title = job?.original_filename || state.jobId || t("result.title");
  resultTitleEl.textContent = title;
  setDocumentTitle(`${title} - ${t("appTitle")}`);
  renderActionLabels();
}

function renderInfoPanel() {
  const hasJob = Boolean(state.job) && !state.missing;
  const infoVisible = hasJob && !state.toolbarCollapsed && state.infoOpen;
  resultInfoPanelEl.hidden = !infoVisible;
  infoToggleBtn.disabled = !hasJob;
  infoToggleBtn.classList.toggle("active", infoVisible);
}

function renderEditorSurface(doc) {
  resultContentEl.className = "result-content-card reader-editor";
  resultContentEl.classList.toggle("variant-readable", doc.variant === "readable");
  resultContentEl.innerHTML = `
    <div class="editor-shell">
      <div id="editor-surface" class="editor-surface md-preview" contenteditable="true" spellcheck="true">${doc.editorHtml || "<p></p>"}</div>
    </div>
  `;
  applyReaderPrefs();
  bindEditorSurface();
  applyReadableSyncToEditorSurface();
  if (state.findOpen) {
    refreshFindMatches();
  }
  renderEditorStatus();
}
function clearFindHighlights() {
  const surface = getEditorSurface();
  if (!surface) {
    return;
  }
  stripEditorFindHighlightsFrom(surface);
  const doc = getActiveDocumentState();
  doc.findMatches = [];
  doc.activeMatchIndex = -1;
}

function setActiveFindMatch(index) {
  const doc = getActiveDocumentState();
  doc.findMatches.forEach((node, matchIndex) => {
    node.classList.toggle("active", matchIndex === index);
  });
  doc.activeMatchIndex = index;
  const activeNode = doc.findMatches[index];
  if (activeNode) {
    const container = resultContentEl;
    const nodeRect = activeNode.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const topGap = nodeRect.top - containerRect.top;
    const bottomGap = nodeRect.bottom - containerRect.bottom;
    const offsetTop = 48;
    if (topGap < offsetTop) {
      container.scrollTo({
        top: Math.max(0, container.scrollTop + topGap - offsetTop),
        behavior: "smooth",
      });
    } else if (bottomGap > -24) {
      container.scrollTo({
        top: Math.max(0, container.scrollTop + bottomGap + 32),
        behavior: "smooth",
      });
    }
  }
  renderFindStatus();
}

function refreshFindMatches() {
  const surface = getEditorSurface();
  const doc = getActiveDocumentState();
  if (!surface || !state.findOpen) {
    doc.findMatches = [];
    doc.activeMatchIndex = -1;
    renderFindStatus();
    return;
  }

  clearFindHighlights();
  const query = editorFindInput.value.trim();
  if (!query) {
    renderFindStatus();
    return;
  }

  const walker = document.createTreeWalker(surface, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });

  const lowerQuery = query.toLowerCase();
  const matches = [];
  const textNodes = [];
  while (walker.nextNode()) {
    textNodes.push(walker.currentNode);
  }

  for (const sourceNode of textNodes) {
    let textNode = sourceNode;
    const text = textNode.nodeValue || "";
    const lowerText = text.toLowerCase();
    const positions = [];
    let startIndex = 0;
    while (startIndex < lowerText.length) {
      const matchIndex = lowerText.indexOf(lowerQuery, startIndex);
      if (matchIndex === -1) {
        break;
      }
      positions.push(matchIndex);
      startIndex = matchIndex + lowerQuery.length;
    }

    const nodeMatches = [];
    for (let index = positions.length - 1; index >= 0; index -= 1) {
      const matchStart = positions[index];
      const matched = textNode.splitText(matchStart);
      textNode = matched.splitText(lowerQuery.length);
      const mark = document.createElement("mark");
      mark.className = "editor-find-match";
      matched.parentNode.insertBefore(mark, matched);
      mark.appendChild(matched);
      nodeMatches.unshift(mark);
    }
    matches.push(...nodeMatches);
  }

  doc.findMatches = matches;
  doc.activeMatchIndex = matches.length ? 0 : -1;
  setActiveFindMatch(doc.activeMatchIndex);
}

function stepFindMatch(direction) {
  const doc = getActiveDocumentState();
  if (!doc.findMatches.length) {
    renderFindStatus();
    return;
  }
  const nextIndex = (doc.activeMatchIndex + direction + doc.findMatches.length) % doc.findMatches.length;
  setActiveFindMatch(nextIndex);
}

function closeFindBar() {
  state.findOpen = false;
  editorFindbarEl.hidden = true;
  clearFindHighlights();
  renderFindStatus();
  renderEditorStatus();
}

function setToolbarCollapsed(collapsed) {
  state.toolbarCollapsed = Boolean(collapsed);
  window.localStorage.setItem(TOOLBAR_COLLAPSED_KEY, String(state.toolbarCollapsed));
  if (state.toolbarCollapsed) {
    state.viewOpen = false;
    state.infoOpen = false;
    if (state.findOpen) {
      state.findOpen = false;
      editorFindbarEl.hidden = true;
      clearFindHighlights();
    }
  }
  renderReaderControls();
  renderInfoPanel();
  renderEditorStatus();
}

function openFindBar() {
  if (state.toolbarCollapsed) {
    setToolbarCollapsed(false);
  }
  if (state.findOpen) {
    closeFindBar();
    return;
  }
  state.findOpen = true;
  editorFindbarEl.hidden = false;
  renderEditorStatus();
  editorFindInput.focus();
  editorFindInput.select();
  refreshFindMatches();
}

function bindEditorSurface() {
  const surface = getEditorSurface();
  if (!surface) {
    return;
  }
  try {
    document.execCommand("defaultParagraphSeparator", false, "p");
  } catch {
    // Ignore unsupported command.
  }

  surface.addEventListener("input", () => {
    const doc = getActiveDocumentState();
    doc.bodyMarkdown = serializeEditorSurfaceToMarkdown(surface);
    doc.fullMarkdown = buildFullMarkdown(doc.prefixMarkdown, doc.bodyMarkdown);
    setDocumentDirty(doc.variant, true);
    scheduleAutosave(doc.variant);
    renderWordCount();
    if (state.findOpen) {
      refreshFindMatches();
    }
  });

  surface.addEventListener("paste", (event) => {
    event.preventDefault();
    const text = event.clipboardData?.getData("text/plain") || "";
    document.execCommand("insertText", false, text);
  });

  surface.addEventListener("click", (event) => {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const block = target.closest("span.sync-sentence[data-sync-id]");
    if (!block || !surface.contains(block)) {
      return;
    }
    const item = state.sync.byId.get(block.dataset.syncId);
    if (!item) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    seekPlayerToSyncItem(item);
  });

  surface.addEventListener("keydown", (event) => {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }
    const key = event.key.toLowerCase();
    if (key === "b") {
      event.preventDefault();
      runEditorCommand("bold");
      return;
    }
    if (key === "i") {
      event.preventDefault();
      runEditorCommand("italic");
      return;
    }
    if (key === "f") {
      event.preventDefault();
      openFindBar();
      return;
    }
    if (key === "s") {
      event.preventDefault();
      void saveCurrentDocument();
    }
  });
}

async function saveDocument(variant, { immediate = false, keepalive = false } = {}) {
  const doc = getDocumentState(variant);
  if (doc.saveTimer && immediate) {
    window.clearTimeout(doc.saveTimer);
    doc.saveTimer = null;
  }
  if (doc.savePromise) {
    doc.pendingSave = true;
    return doc.savePromise;
  }
  if (!doc.loaded) {
    return true;
  }

  const surface = variant === "readable" ? getEditorSurface() : null;
  if (surface) {
    doc.bodyMarkdown = serializeEditorSurfaceToMarkdown(surface);
    doc.fullMarkdown = buildFullMarkdown(doc.prefixMarkdown, doc.bodyMarkdown);
  }

  if (!doc.dirty && !immediate) {
    return true;
  }

  doc.saveState = "saving";
  state.actionError = "";
  renderEditorStatus();
  renderJobBanner();

  const promise = fetch(getDocumentEndpoint(state.jobId), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ markdown: doc.fullMarkdown }),
    keepalive,
  })
    .then(async (response) => {
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
      }
      return response.json();
    })
    .then((payload) => {
      doc.fullMarkdown = payload.markdown || doc.fullMarkdown;
      const split = splitDocumentScaffold(doc.fullMarkdown);
      doc.prefixMarkdown = split.prefixMarkdown;
      doc.bodyMarkdown = split.bodyMarkdown;
      doc.edited = Boolean(payload.edited);
      doc.updatedAt = payload.updated_at || null;
      doc.baseAvailable = Boolean(payload.base_available);
      doc.dirty = false;
      doc.saveState = "saved";
      state.actionError = "";
      if (state.job) {
        state.job.readable_edited = doc.edited;
        state.job.readable_editor_updated_at = doc.updatedAt;
      }
      renderEditorStatus();
      renderJobBanner();
      return true;
    })
    .catch((error) => {
      doc.saveState = "error";
      state.actionError = t("result.saveError", { message: String(error) });
      renderEditorStatus();
      renderJobBanner();
      return false;
    })
    .finally(() => {
      doc.savePromise = null;
      if (doc.pendingSave) {
        doc.pendingSave = false;
        if (doc.dirty) {
          scheduleAutosave(variant);
        }
      }
    });

  doc.savePromise = promise;
  return promise;
}

async function saveCurrentDocument({ keepalive = false } = {}) {
  const variant = "readable";
  const doc = getDocumentState(variant);
  if (!doc.loaded) {
    return true;
  }
  return saveDocument(variant, { immediate: true, keepalive });
}

async function flushCurrentEditor() {
  const variant = "readable";
  const doc = getDocumentState(variant);
  if (!doc.loaded || !doc.dirty) {
    return true;
  }
  return saveDocument(variant, { immediate: true });
}

async function resetCurrentDocument() {
  const variant = "readable";
  const doc = getDocumentState(variant);
  if (!doc.loaded) {
    return;
  }
  if (!window.confirm(t("result.editorResetConfirm"))) {
    return;
  }

  try {
    const response = await fetch(getDocumentEndpoint(state.jobId), { method: "DELETE" });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const payload = await response.json();
    const split = splitDocumentScaffold(payload.markdown || "");
    doc.fullMarkdown = payload.markdown || "";
    doc.prefixMarkdown = split.prefixMarkdown;
    doc.bodyMarkdown = split.bodyMarkdown;
    doc.edited = Boolean(payload.edited);
    doc.updatedAt = payload.updated_at || null;
    doc.baseAvailable = Boolean(payload.base_available);
    doc.dirty = false;
    doc.saveState = "saved";
    doc.editorHtml = buildFallbackEditorHtml(doc.bodyMarkdown);
    state.actionError = "";
    state.actionWarning = "";
    renderJobState();
  } catch (error) {
    state.actionError = t("result.editorResetError", { message: String(error) });
    renderJobState();
  }
}

async function renderDocumentContent() {
  const job = state.job;
  if (!job) {
    renderContentPlaceholder(t("result.notFound"));
    return;
  }
  if (job.status === "cancelled") {
    renderContentPlaceholder(t("result.cancelled"));
    return;
  }
  if (job.status === "failed") {
    renderContentPlaceholder(job.error || t("result.failed"));
    return;
  }
  if (job.status !== "done") {
    renderContentPlaceholder(t("result.notReady"));
    return;
  }

  if (!isReadableAvailable(job)) {
    renderContentPlaceholder(t("result.readableUnavailable"));
    return;
  }

  try {
    const doc = await loadDocumentVariant("readable");
    await loadReadableSync();
    renderEditorSurface(doc);
  } catch (error) {
    renderContentPlaceholder(t("status.requestError", { message: String(error) }));
  }
}

function renderJobState() {
  const job = state.job;
  renderHeader();
  renderMeta();
  renderInfoPanel();
  renderReaderControls();
  renderEditorStatus();
  ensurePlayerSource(job);

  removeBtn.disabled = !canRemove(job);
  if (isReadableAvailable(job)) {
    setDownloadEnabled();
  } else {
    setDownloadDisabled();
  }
  renderJobBanner();
  void renderDocumentContent();
}

async function syncJob() {
  try {
    const response = await fetch(`/api/jobs/${state.jobId}`);
    if (response.status === 404) {
      state.job = null;
      state.missing = true;
      state.refreshError = "";
      renderJobState();
      return;
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const nextJob = await response.json();
    const currentJob = state.job;
    state.job = nextJob;
    state.missing = false;
    state.refreshError = "";

    if (
      !currentJob
      || currentJob.status !== nextJob.status
      || currentJob.readable_available !== nextJob.readable_available
      || currentJob.readable_sync_available !== nextJob.readable_sync_available
    ) {
      state.documents.readable.loaded = false;
      resetReadableSync();
    }

    if (currentJob && currentJob.status !== nextJob.status && !TERMINAL_STATUSES.has(currentJob.status) && TERMINAL_STATUSES.has(nextJob.status)) {
      const kind = nextJob.status === "done" ? "job_done" : "job_attention";
      void playUiNotification(kind);
    }

    renderJobState();
  } catch (error) {
    state.refreshError = t("result.pollError", { message: String(error) });
    renderJobState();
  }
}
function schedulePolling(delayMs = 1500) {
  if (state.pollTimer) {
    window.clearTimeout(state.pollTimer);
  }
  state.pollTimer = window.setTimeout(async () => {
    await syncJob();
    if (state.job && !TERMINAL_STATUSES.has(state.job.status)) {
      schedulePolling(delayMs);
    }
  }, delayMs);
}

async function handleRemove() {
  if (!state.job || !canRemove(state.job)) {
    return;
  }
  try {
    if (state.job.status === "done") {
      const saved = await flushCurrentEditor();
      if (!saved) {
        return;
      }
    }
    const response = await fetch(`/api/jobs/${state.job.job_id}`, { method: "DELETE" });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    window.location.href = "/";
  } catch (error) {
    state.actionError = t("status.removeError", { message: String(error) });
    renderJobState();
  }
}

function setReaderAlignMode(mode) {
  prefs.readerAlignMode = mode;
  savePrefs();
  renderReaderControls();
}

function setReaderLineHeight(mode) {
  prefs.readerLineHeight = mode;
  savePrefs();
  renderReaderControls();
}

function setReaderContentWidth(value) {
  const normalized = Math.max(50, Math.min(100, Number(value) || 100));
  prefs.readerContentWidthPercent = normalized;
  savePrefs();
  renderReaderControls();
}

function setReaderParagraphGap(enabled) {
  prefs.readerParagraphGap = Boolean(enabled);
  savePrefs();
  renderReaderControls();
}

function setReaderFontSize(value) {
  const normalized = Math.max(12, Math.min(32, Number(value) || 18));
  prefs.readerFontSizePx = normalized;
  savePrefs();
  renderReaderControls();
}

function ensureEditorReadyForAction() {
  const surface = getEditorSurface();
  if (!surface) {
    return null;
  }
  surface.focus();
  return surface;
}

function runEditorCommand(command, value = null) {
  const surface = ensureEditorReadyForAction();
  if (!surface) {
    return;
  }
  try {
    document.execCommand(command, false, value);
  } catch {
    return;
  }
  const doc = getActiveDocumentState();
  doc.bodyMarkdown = serializeEditorSurfaceToMarkdown(surface);
  doc.fullMarkdown = buildFullMarkdown(doc.prefixMarkdown, doc.bodyMarkdown);
  setDocumentDirty(doc.variant, true);
  scheduleAutosave(doc.variant);
  renderWordCount();
  if (state.findOpen) {
    refreshFindMatches();
  }
}

function bindToolbarMouseDown(button) {
  button?.addEventListener("mousedown", (event) => {
    event.preventDefault();
  });
}

async function downloadActiveArtifact(kind = "markdown") {
  const job = state.job;
  if (!job || !isReadableAvailable(job)) {
    return;
  }

  if (job.status === "done") {
    const saved = await flushCurrentEditor();
    if (!saved) {
      return;
    }
  }

  state.actionError = "";
  state.actionWarning = "";
  renderJobBanner();
  renderEditorStatus();

  const endpoint = kind === "pdf"
    ? buildPdfEndpoint(job.job_id)
    : getMarkdownEndpoint(job.job_id);
  const filename = buildDownloadFilename(job, "readable", kind === "pdf" ? "pdf" : "md");

  if (!isDesktopRuntime()) {
    await downloadInBrowser(endpoint, filename);
    return;
  }

  const resolvedSave = kind === "pdf"
    ? await resolveDesktopSavePdfApiWithRetry()
    : await resolveDesktopSaveApiWithRetry();

  if (!resolvedSave.saveApi) {
    await downloadInBrowser(endpoint, filename);
    state.actionWarning = t("result.saveFallbackWarning");
    renderJobBanner();
    return;
  }

  const payload = kind === "pdf"
    ? await resolvedSave.saveApi(job.job_id, "readable", filename, buildPdfExportOptions())
    : await resolvedSave.saveApi(job.job_id, "readable", filename);
  const result = normalizeSaveResult(payload);

  if (result.status === "ok" || result.status === "cancelled") {
    return;
  }

  state.actionError = t("result.saveError", { message: result.message || "Unknown desktop save error." });
  renderJobBanner();
  renderEditorStatus();
}

async function handleDownload() {
  try {
    await downloadActiveArtifact("markdown");
  } catch (error) {
    state.actionError = t("result.saveError", { message: String(error) });
    renderJobBanner();
    renderEditorStatus();
  }
}

async function handlePdfDownload() {
  try {
    await downloadActiveArtifact("pdf");
  } catch (error) {
    state.actionError = t("result.saveError", { message: String(error) });
    renderJobBanner();
    renderEditorStatus();
  }
}

function applyPageChrome() {
  applyTheme(prefs.theme);
  document.documentElement.lang = prefs.lang === "ru" ? "ru" : "en";
  applyStaticI18n(t);
  const job = state.job;
  const title = job?.original_filename
    ? `${job.original_filename} - ${t("app.resultTitle")}`
    : t("app.resultTitle");
  setDocumentTitle(title);
}

function bindEvents() {
  viewToggleBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    state.viewOpen = !state.viewOpen;
    if (state.viewOpen) {
      state.infoOpen = false;
    }
    renderReaderControls();
    renderInfoPanel();
  });

  infoToggleBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    state.infoOpen = !state.infoOpen;
    if (state.infoOpen) {
      state.viewOpen = false;
    }
    renderInfoPanel();
    renderReaderControls();
  });

  readerFontSizeInput?.addEventListener("input", () => {
    setReaderFontSize(readerFontSizeInput.value);
  });
  readerLineCompactBtn?.addEventListener("click", () => setReaderLineHeight("compact"));
  readerLineNormalBtn?.addEventListener("click", () => setReaderLineHeight("normal"));
  readerLineRelaxedBtn?.addEventListener("click", () => setReaderLineHeight("relaxed"));
  readerWidthInput?.addEventListener("input", () => setReaderContentWidth(readerWidthInput.value));
  readerJustifyLeftBtn?.addEventListener("click", () => setReaderAlignMode("left"));
  readerJustifyFullBtn?.addEventListener("click", () => setReaderAlignMode("justify"));
  readerJustifyHyphenBtn?.addEventListener("click", () => setReaderAlignMode("justify_hyphen"));
  readerParagraphGapInput?.addEventListener("change", () => setReaderParagraphGap(readerParagraphGapInput.checked));

  downloadMenuBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    if (downloadMenuBtn.disabled) {
      return;
    }
    state.downloadMenuOpen = !state.downloadMenuOpen;
    renderDownloadMenu();
  });
  downloadLink?.addEventListener("click", () => {
    state.downloadMenuOpen = false;
    renderDownloadMenu();
    void handleDownload();
  });
  downloadPdfBtn?.addEventListener("click", () => {
    state.downloadMenuOpen = false;
    renderDownloadMenu();
    void handlePdfDownload();
  });
  playerToggleBtn?.addEventListener("click", () => {
    setPlayerVisible(!state.playerVisible);
  });
  toolbarToggleBtn?.addEventListener("click", () => {
    setToolbarCollapsed(!state.toolbarCollapsed);
  });
  removeBtn?.addEventListener("click", () => {
    void handleRemove();
  });

  editorBoldBtn?.addEventListener("click", () => runEditorCommand("bold"));
  editorItalicBtn?.addEventListener("click", () => runEditorCommand("italic"));
  editorParagraphBtn?.addEventListener("click", () => runEditorCommand("formatBlock", "P"));
  editorH2Btn?.addEventListener("click", () => runEditorCommand("formatBlock", "H2"));
  editorH3Btn?.addEventListener("click", () => runEditorCommand("formatBlock", "H3"));
  editorBulletsBtn?.addEventListener("click", () => runEditorCommand("insertUnorderedList"));
  editorOrderedBtn?.addEventListener("click", () => runEditorCommand("insertOrderedList"));
  editorUndoBtn?.addEventListener("click", () => runEditorCommand("undo"));
  editorRedoBtn?.addEventListener("click", () => runEditorCommand("redo"));
  editorSaveBtn?.addEventListener("click", () => {
    void saveCurrentDocument();
  });
  editorFindBtn?.addEventListener("click", () => openFindBar());
  editorResetBtn?.addEventListener("click", () => {
    void resetCurrentDocument();
  });
  editorFindPrevBtn?.addEventListener("click", () => stepFindMatch(-1));
  editorFindNextBtn?.addEventListener("click", () => stepFindMatch(1));
  editorFindCloseBtn?.addEventListener("click", () => closeFindBar());
  editorFindInput?.addEventListener("input", () => refreshFindMatches());
  editorFindInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      stepFindMatch(event.shiftKey ? -1 : 1);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeFindBar();
    }
  });

  playerPlayBtn?.addEventListener("click", () => {
    void togglePlayerPlayback();
  });
  playerRewindBtn?.addEventListener("click", () => {
    resultAudioEl.currentTime = Math.max(0, resultAudioEl.currentTime - 5);
    renderPlayerControls();
    updateActiveSyncFromPlayback({ scroll: false });
  });
  playerForwardBtn?.addEventListener("click", () => {
    const duration = getPlayerDuration();
    resultAudioEl.currentTime = duration > 0
      ? Math.min(duration, resultAudioEl.currentTime + 5)
      : resultAudioEl.currentTime + 5;
    renderPlayerControls();
    updateActiveSyncFromPlayback({ scroll: false });
  });
  playerMuteBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    state.player.volumeOpen = !state.player.volumeOpen;
    state.player.rateOpen = false;
    renderPlayerControls();
  });
  playerRateBtn?.addEventListener("click", (event) => {
    event.stopPropagation();
    state.player.rateOpen = !state.player.rateOpen;
    state.player.volumeOpen = false;
    renderPlayerControls();
  });
  playerRateOptions.forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      setPlayerRate(button.dataset.rate);
      state.player.rateOpen = false;
      renderPlayerControls();
    });
  });
  playerVolumeInput?.addEventListener("input", () => {
    const volume = Math.max(0, Math.min(1, Number(playerVolumeInput.value) || 0));
    resultAudioEl.volume = volume;
    if (volume > 0) {
      resultAudioEl.muted = false;
    }
    window.localStorage.setItem(PLAYER_VOLUME_KEY, String(volume));
    window.localStorage.setItem(PLAYER_MUTED_KEY, String(resultAudioEl.muted));
    renderPlayerControls();
  });
  resultAudioEl?.addEventListener("play", () => {
    renderPlayerControls();
    updateActiveSyncFromPlayback({ scroll: false });
  });
  resultAudioEl?.addEventListener("pause", () => renderPlayerControls());
  resultAudioEl?.addEventListener("loadedmetadata", () => {
    renderPlayerControls();
    updateActiveSyncFromPlayback({ scroll: false });
  });
  resultAudioEl?.addEventListener("durationchange", () => renderPlayerControls());
  resultAudioEl?.addEventListener("timeupdate", () => {
    drawPlayerWaveform();
    updateActiveSyncFromPlayback();
  });
  resultAudioEl?.addEventListener("volumechange", () => {
    playerVolumeInput.value = String(resultAudioEl.volume);
    renderPlayerControls();
  });
  resultAudioEl?.addEventListener("ratechange", () => renderPlayerControls());
  resultAudioEl?.addEventListener("error", () => {
    const error = resultAudioEl.error;
    const message = error?.message || (error?.code ? `Media error ${error.code}` : "Unsupported source");
    state.actionError = t("result.playerPlayError", { message });
    renderJobBanner();
    renderPlayerControls();
  });
  resultAudioEl?.addEventListener("ended", () => renderPlayerControls());
  playerWaveformEl?.addEventListener("pointerdown", (event) => {
    state.player.seeking = true;
    playerWaveformEl.setPointerCapture?.(event.pointerId);
    seekPlayerFromPointer(event);
  });
  playerWaveformEl?.addEventListener("pointermove", (event) => {
    if (state.player.seeking) {
      seekPlayerFromPointer(event);
    }
  });
  playerWaveformEl?.addEventListener("pointerup", (event) => {
    state.player.seeking = false;
    playerWaveformEl.releasePointerCapture?.(event.pointerId);
  });
  playerWaveformEl?.addEventListener("pointercancel", () => {
    state.player.seeking = false;
  });
  resultContentEl?.addEventListener("wheel", () => suppressSyncAutoscroll(), { passive: true });
  resultContentEl?.addEventListener("touchstart", () => suppressSyncAutoscroll(), { passive: true });
  resultContentEl?.addEventListener("pointerdown", () => suppressSyncAutoscroll(1800));

  FORMATTING_BUTTONS.forEach(bindToolbarMouseDown);

  document.addEventListener("mousedown", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
    }
    if (state.downloadMenuOpen && downloadMenuAnchorEl && !downloadMenuAnchorEl.contains(target)) {
      state.downloadMenuOpen = false;
      renderDownloadMenu();
    }
    if (state.player.volumeOpen && playerVolumeAnchorEl && !playerVolumeAnchorEl.contains(target)) {
      state.player.volumeOpen = false;
      renderPlayerControls();
    }
    if (state.player.rateOpen && playerRateAnchorEl && !playerRateAnchorEl.contains(target)) {
      state.player.rateOpen = false;
      renderPlayerControls();
    }
    if (state.viewOpen && viewPopoverAnchorEl && !viewPopoverAnchorEl.contains(target)) {
      state.viewOpen = false;
      renderReaderControls();
    }
    if (state.infoOpen && infoPopoverAnchorEl && !infoPopoverAnchorEl.contains(target)) {
      state.infoOpen = false;
      renderInfoPanel();
    }
  });

  window.addEventListener("beforeunload", () => {
    if (state.pollTimer) {
      window.clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    const doc = getDocumentState("readable");
    if (doc.loaded && doc.dirty) {
      void saveDocument("readable", { immediate: true, keepalive: true });
    }
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Control" || event.key === "Meta") {
      setSyncSeekModifier(true);
    }
    if (event.key === "Escape") {
      if (state.downloadMenuOpen) {
        state.downloadMenuOpen = false;
        renderDownloadMenu();
      }
      if (state.player.volumeOpen) {
        state.player.volumeOpen = false;
        renderPlayerControls();
      }
      if (state.player.rateOpen) {
        state.player.rateOpen = false;
        renderPlayerControls();
      }
      if (state.findOpen) {
        closeFindBar();
      }
      if (state.viewOpen) {
        state.viewOpen = false;
        renderReaderControls();
      }
      if (state.infoOpen) {
        state.infoOpen = false;
        renderInfoPanel();
      }
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      void saveCurrentDocument();
    }
  });
  window.addEventListener("keyup", (event) => {
    if (event.key === "Control" || event.key === "Meta") {
      setSyncSeekModifier(false);
    }
  });
  window.addEventListener("blur", () => setSyncSeekModifier(false));
  window.addEventListener("resize", () => drawPlayerWaveform());
}

async function boot() {
  bindEvents();
  applyPageChrome();
  renderJobState();
  await syncJob();
  if (state.job && !TERMINAL_STATUSES.has(state.job.status)) {
    schedulePolling();
  }
}

void boot();
