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
const downloadLink = document.getElementById("download-link");
const downloadPdfBtn = document.getElementById("download-pdf-btn");
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

const TERMINAL_STATUSES = new Set(["done", "failed", "cancelled"]);
const INLINE_BOLD_RE = /\*\*([^*]+)\*\*/g;
const INLINE_ITALIC_RE = /\*([^*]+)\*/g;
const ORDERED_LIST_RE = /^\d+\.\s+(.+)$/;
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
  infoOpen: false,
  viewOpen: false,
  findOpen: false,
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

function setDownloadDisabled() {
  downloadLink.disabled = true;
  downloadLink.classList.add("disabled");
  downloadPdfBtn.disabled = true;
  downloadPdfBtn.classList.add("disabled");
}

function setDownloadEnabled() {
  downloadLink.disabled = false;
  downloadLink.classList.remove("disabled");
  downloadPdfBtn.disabled = false;
  downloadPdfBtn.classList.remove("disabled");
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
  editorToolbarEl.hidden = !editorVisible;
  resultReaderStageEl.classList.toggle("has-search", editorVisible && state.findOpen);
  editorSaveBtn.disabled = !editorVisible || doc.saveState === "saving" || !doc.loaded || !doc.dirty;
  editorFindBtn.classList.toggle("active", editorVisible && state.findOpen);
  if (!editorVisible) {
    editorFindbarEl.hidden = true;
    editorSaveStatusEl.textContent = t("result.editorStatusIdle");
    editorDirtyIndicatorEl.hidden = true;
    editorWordCountEl.textContent = "";
    return;
  }
  editorSaveStatusEl.textContent = getEditorStatusLabel(doc.saveState);
  editorDirtyIndicatorEl.hidden = !doc.dirty;
  editorFindbarEl.hidden = !state.findOpen;
  editorFindInput.placeholder = t("result.findPlaceholder");
  renderWordCount();
  renderFindStatus();
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
  readerControlsPanelEl.hidden = !state.viewOpen;
  viewToggleBtn.classList.toggle("active", state.viewOpen);
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
}

function renderInfoPanel() {
  const hasJob = Boolean(state.job) && !state.missing;
  resultInfoPanelEl.hidden = !hasJob || !state.infoOpen;
  infoToggleBtn.disabled = !hasJob;
  infoToggleBtn.classList.toggle("active", hasJob && state.infoOpen);
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

function openFindBar() {
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

  surface.addEventListener("keydown", (event) => {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }
    const key = event.key.toLowerCase();
    if (key === "b") {
      event.preventDefault();
      document.execCommand("bold");
      return;
    }
    if (key === "i") {
      event.preventDefault();
      document.execCommand("italic");
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

    if (!currentJob || currentJob.status !== nextJob.status || currentJob.readable_available !== nextJob.readable_available) {
      state.documents.readable.loaded = false;
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

  downloadLink?.addEventListener("click", () => {
    void handleDownload();
  });
  downloadPdfBtn?.addEventListener("click", () => {
    void handlePdfDownload();
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

  FORMATTING_BUTTONS.forEach(bindToolbarMouseDown);

  document.addEventListener("mousedown", (event) => {
    const target = event.target;
    if (!(target instanceof Node)) {
      return;
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
    if (event.key === "Escape") {
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
