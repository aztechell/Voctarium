import {
  applyStaticI18n,
  applyTheme,
  canCancel,
  canOpen,
  canRemove,
  canRetry,
  createUiContext,
  escapeHtml,
  formatBytes,
  formatDuration,
  getStatusKey,
  getStatusLabel,
  parseJsonSafe,
  playUiNotification,
  setDocumentTitle,
  syncPreferenceButtons,
} from "./shared.js";

const root = document.getElementById("dashboard-root");
const langToggleBtn = document.getElementById("lang-toggle");
const themeToggleBtn = document.getElementById("theme-toggle");
const settingsBtn = document.getElementById("settings-btn");

const uploadForm = document.getElementById("upload-form");
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const pickFilesBtn = document.getElementById("pick-files-btn");
const clearSelectionBtn = document.getElementById("clear-selection-btn");
const showFilesModalBtn = document.getElementById("show-files-modal-btn");
const modelSelect = document.getElementById("model-select");
const openModelsModalBtn = document.getElementById("open-models-modal-btn");
const timestampsInput = document.getElementById("timestamps-input");
const enqueueBtn = document.getElementById("enqueue-btn");
const commandBatchSummaryEl = document.getElementById("command-batch-summary");
const selectionBadge = document.getElementById("selection-badge");
const selectionCard = document.getElementById("selection-card");
const selectionSummary = document.getElementById("selection-summary");
const filesModal = document.getElementById("files-modal");
const closeFilesModalBtn = document.getElementById("close-files-modal-btn");
const filesModalSummary = document.getElementById("files-modal-summary");
const filesModalList = document.getElementById("files-modal-list");
const modelsModal = document.getElementById("models-modal");
const closeModelsModalBtn = document.getElementById("close-models-modal-btn");
const modelsModalSummary = document.getElementById("models-modal-summary");
const modelsModalList = document.getElementById("models-modal-list");
const settingsModal = document.getElementById("settings-modal");
const settingsModalFeedbackEl = document.getElementById("settings-modal-feedback");
const closeSettingsModalBtn = document.getElementById("close-settings-modal-btn");
const saveSettingsBtn = document.getElementById("save-settings-btn");
const cleanupUploadsInput = document.getElementById("cleanup-uploads-input");
const cleanupQueueInput = document.getElementById("cleanup-queue-input");
const uploadFeedbackEl = document.getElementById("upload-feedback");
const uploadCurrentFileEl = document.getElementById("upload-current-file");
const uploadProgressBar = document.getElementById("upload-progress-bar");

const jobsList = document.getElementById("jobs-list");
const jobsEmpty = document.getElementById("jobs-empty");
const jobsCounter = document.getElementById("jobs-counter");
const jobsFeedbackEl = document.getElementById("jobs-feedback");

const TERMINAL_STATUSES = new Set(["done", "failed", "cancelled"]);
const DEFAULT_DESKTOP_SETTINGS = {
  cleanup_uploads_on_close: true,
  cleanup_queue_on_close: false,
};

const { state: prefs, t, savePrefs } = createUiContext();

const state = {
  defaultModel: root.dataset.defaultModel || "",
  jobs: new Map(),
  jobOrder: [],
  selectedFiles: [],
  localQueue: [],
  sending: false,
  uploadProgressTotal: 0,
  uploadProgressDone: 0,
  uploadCurrentName: "",
  uploadNotice: null,
  jobsNotice: null,
  lastUploadSummary: null,
  pollTimer: null,
  elapsedTimer: null,
  filesModalOpen: false,
  modelsModalOpen: false,
  settingsModalOpen: false,
  settingsSaving: false,
  desktopSettingsLoaded: false,
  desktopSettings: { ...DEFAULT_DESKTOP_SETTINGS },
  settingsError: "",
  models: [],
  activeModelId: root.dataset.defaultModel || "",
  knownJobStatus: new Map(),
  trackedBatches: [],
};

function setUploadNotice(message, tone = "normal") {
  state.uploadNotice = message ? { message, tone } : null;
  renderUploadState();
}

function clearUploadNotice() {
  state.uploadNotice = null;
}

function setJobsNotice(message, tone = "normal") {
  state.jobsNotice = message ? { message, tone } : null;
  renderJobsNotice();
}

function clearJobsNotice() {
  state.jobsNotice = null;
  renderJobsNotice();
}

function renderJobsNotice() {
  if (!state.jobsNotice) {
    jobsFeedbackEl.textContent = "";
    delete jobsFeedbackEl.dataset.tone;
    return;
  }
  jobsFeedbackEl.textContent = state.jobsNotice.message;
  jobsFeedbackEl.dataset.tone = state.jobsNotice.tone;
}

function applyPageChrome() {
  document.documentElement.lang = prefs.lang;
  applyTheme(prefs.theme);
  applyStaticI18n(t);
  syncPreferenceButtons({ state: prefs, t, langToggleBtn, themeToggleBtn });
  setDocumentTitle(t("appTitle"));
  renderSelectedFiles();
  renderModels();
  renderUploadState();
  renderJobsNotice();
  renderJobs();
}

function updateSelectionBadge() {
  selectionBadge.textContent = String(state.selectedFiles.length);
}

function updateModalBodyState() {
  document.body.classList.toggle("modal-open", state.filesModalOpen || state.modelsModalOpen || state.settingsModalOpen);
}

function closeFilesModal() {
  state.filesModalOpen = false;
  filesModal.hidden = true;
  updateModalBodyState();
}

function closeModelsModal() {
  state.modelsModalOpen = false;
  modelsModal.hidden = true;
  updateModalBodyState();
}

function renderSettingsModal() {
  settingsModal.hidden = !state.settingsModalOpen;
  cleanupUploadsInput.checked = Boolean(state.desktopSettings.cleanup_uploads_on_close);
  cleanupQueueInput.checked = Boolean(state.desktopSettings.cleanup_queue_on_close);
  cleanupUploadsInput.disabled = state.settingsSaving;
  cleanupQueueInput.disabled = state.settingsSaving;
  saveSettingsBtn.disabled = state.settingsSaving;
  if (state.settingsSaving) {
    settingsModalFeedbackEl.textContent = t("settings.saving");
  } else if (state.settingsError) {
    settingsModalFeedbackEl.textContent = state.settingsError;
  } else if (state.desktopSettingsLoaded) {
    settingsModalFeedbackEl.textContent = t("settings.saved");
  } else {
    settingsModalFeedbackEl.textContent = "";
  }
  updateModalBodyState();
}

function openSettingsModal() {
  state.settingsModalOpen = true;
  renderSettingsModal();
  closeSettingsModalBtn.focus();
}

function closeSettingsModal() {
  state.settingsModalOpen = false;
  state.settingsSaving = false;
  state.settingsError = "";
  renderSettingsModal();
}

async function fetchDesktopSettings({ force = false } = {}) {
  if (state.desktopSettingsLoaded && !force) {
    return state.desktopSettings;
  }
  const response = await fetch("/api/settings/desktop");
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  const payload = await response.json();
  state.desktopSettings = {
    cleanup_uploads_on_close: Boolean(payload.cleanup_uploads_on_close),
    cleanup_queue_on_close: Boolean(payload.cleanup_queue_on_close),
  };
  state.desktopSettingsLoaded = true;
  state.settingsError = "";
  return state.desktopSettings;
}

async function saveDesktopSettings() {
  state.settingsSaving = true;
  state.settingsError = "";
  renderSettingsModal();
  try {
    const response = await fetch("/api/settings/desktop", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cleanup_uploads_on_close: cleanupUploadsInput.checked,
        cleanup_queue_on_close: cleanupQueueInput.checked,
      }),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const payload = await response.json();
    state.desktopSettings = {
      cleanup_uploads_on_close: Boolean(payload.cleanup_uploads_on_close),
      cleanup_queue_on_close: Boolean(payload.cleanup_queue_on_close),
    };
    state.desktopSettingsLoaded = true;
  } catch (error) {
    state.settingsError = t("settings.saveError", { message: String(error) });
  } finally {
    state.settingsSaving = false;
    renderSettingsModal();
  }
}

function clearSelectedFiles() {
  closeFilesModal();
  state.selectedFiles = [];
  fileInput.value = "";
  renderSelectedFiles();
  renderUploadState();
}

function fileFingerprint(file) {
  return [file.name || "", Number(file.size) || 0, Number(file.lastModified) || 0].join("::");
}

function mergeSelectedFiles(files) {
  const nextFiles = Array.from(files || []);
  if (nextFiles.length === 0) {
    return;
  }

  state.lastUploadSummary = null;
  clearUploadNotice();

  const merged = new Map(state.selectedFiles.map((file) => [fileFingerprint(file), file]));
  nextFiles.forEach((file) => {
    const key = fileFingerprint(file);
    if (!merged.has(key)) {
      merged.set(key, file);
    }
  });

  state.selectedFiles = Array.from(merged.values());
  renderSelectedFiles();
  renderUploadState();
}

function openFilesModal() {
  if (state.selectedFiles.length === 0) {
    return;
  }
  state.filesModalOpen = true;
  filesModal.hidden = false;
  updateModalBodyState();
  closeFilesModalBtn.focus();
}

function openModelsModal() {
  state.modelsModalOpen = true;
  modelsModal.hidden = false;
  updateModalBodyState();
  closeModelsModalBtn.focus();
}

function removeSelectedFileAt(index) {
  if (!Number.isInteger(index) || index < 0 || index >= state.selectedFiles.length) {
    return;
  }

  state.selectedFiles.splice(index, 1);
  renderSelectedFiles();
  renderUploadState();

  if (state.selectedFiles.length === 0) {
    closeFilesModal();
  }
}

function renderSelectedFiles() {
  const hasFiles = state.selectedFiles.length > 0;
  selectionCard.classList.toggle("empty", !hasFiles);
  dropZone.classList.toggle("has-files", hasFiles);
  updateSelectionBadge();
  clearSelectionBtn.disabled = !hasFiles || state.sending;
  showFilesModalBtn.disabled = !hasFiles;

  if (!hasFiles) {
    selectionSummary.textContent = t("common.none");
    filesModalSummary.textContent = t("common.none");
    filesModalList.innerHTML = "";
    closeFilesModal();
    return;
  }

  const totalBytes = state.selectedFiles.reduce((sum, file) => sum + (Number(file.size) || 0), 0);
  const summaryText = t("upload.selectedSummary", {
    count: state.selectedFiles.length,
    size: formatBytes(totalBytes),
  });

  selectionSummary.textContent = summaryText;
  filesModalSummary.textContent = summaryText;

  filesModalList.innerHTML = state.selectedFiles
    .map(
      (file, index) => `
        <li class="files-modal-item">
          <span class="files-modal-name">${escapeHtml(file.name)}</span>
          <span class="files-modal-size">${escapeHtml(formatBytes(file.size))}</span>
          <button class="mini-btn files-modal-remove" type="button" data-remove-selected-index="${index}">
            ${escapeHtml(t("actions.remove"))}
          </button>
        </li>
      `,
    )
    .join("");
}

function renderModels() {
  const installedModels = state.models.filter((item) => item.installed);
  const activeModel = state.activeModelId
    ? (state.models.find((item) => item.id === state.activeModelId) || null)
    : null;

  const activeInstalled = Boolean(activeModel && activeModel.installed);
  const selectedValue = activeInstalled ? state.activeModelId : "";

  modelSelect.innerHTML = [
    `<option value="">${escapeHtml(t("models.chooseModel"))}</option>`,
    ...installedModels.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`),
  ].join("");
  modelSelect.value = selectedValue;

  modelSelect.disabled = installedModels.length === 0 || state.sending;
  openModelsModalBtn.disabled = false;

  modelsModalSummary.textContent = t("models.activeSummary", {
    model: activeModel?.label || state.activeModelId || t("common.none"),
  });

  if (state.models.length === 0) {
    modelsModalList.innerHTML = `<li class="jobs-empty state-copy">${escapeHtml(t("models.empty"))}</li>`;
    return;
  }

  modelsModalList.innerHTML = state.models
    .map((item) => {
      const isActive = Boolean(state.activeModelId) && item.id === state.activeModelId;
      const badges = [];
      if (isActive) badges.push(`<span class="job-metric-chip"><span>${escapeHtml(t("models.active"))}</span></span>`);
      if (item.installed) badges.push(`<span class="job-metric-chip"><span>${escapeHtml(t("models.installed"))}</span></span>`);
      if (item.downloading) badges.push(`<span class="job-metric-chip"><span>${escapeHtml(t("models.downloading"))}</span></span>`);
      if (!item.installed && !item.downloading) badges.push(`<span class="job-metric-chip"><span>${escapeHtml(t("models.unavailable"))}</span></span>`);

      const actions = [];
      if (!item.installed && !item.downloading) {
        actions.push(`<button class="mini-btn" type="button" data-model-action="download" data-model-id="${escapeHtml(item.id)}">${escapeHtml(t("models.download"))}</button>`);
      }
      if (item.installed && !isActive && !item.downloading) {
        actions.push(`<button class="mini-btn" type="button" data-model-action="select" data-model-id="${escapeHtml(item.id)}">${escapeHtml(t("models.select"))}</button>`);
      }
      if (item.deletable) {
        actions.push(`<button class="mini-btn" type="button" data-model-action="delete" data-model-id="${escapeHtml(item.id)}">${escapeHtml(t("models.delete"))}</button>`);
      }
      const errorHtml = item.error ? `<div class="job-error">${escapeHtml(item.error)}</div>` : "";
      const totalBytes = Number(item.download_size_bytes);
      const downloadedBytes = Number(item.downloaded_bytes) || 0;
      const progressPercent = Math.max(0, Math.min(100, Number(item.progress_percent) || 0));
      const sizeText = Number.isFinite(totalBytes) && totalBytes > 0
        ? t("models.sizeKnown", { size: formatBytes(totalBytes) })
        : t("models.sizeUnknown");
      const progressHtml = item.downloading
        ? `
          <div class="model-download-progress">
            <div class="progress-track">
              <div class="progress-bar" style="width:${progressPercent}%"></div>
            </div>
            <span class="model-progress-value">${escapeHtml(t("models.downloadProgress", {
              downloaded: formatBytes(downloadedBytes),
              total: Number.isFinite(totalBytes) && totalBytes > 0 ? formatBytes(totalBytes) : "?",
              percent: `${progressPercent}%`,
            }))}</span>
          </div>
        `
        : "";

      return `
        <li class="model-item">
          <div class="model-item-main">
            <div class="model-item-title-row">
              <strong class="model-item-title">${escapeHtml(item.label)}</strong>
              <span class="files-modal-size">${escapeHtml(item.repo_id)}</span>
            </div>
            <div class="model-item-meta">${escapeHtml(sizeText)}</div>
            <div class="job-meta-row">${badges.join("")}</div>
            ${progressHtml}
            ${errorHtml}
          </div>
          <div class="model-item-actions">${actions.join("")}</div>
        </li>
      `;
    })
    .join("");
}

function hasActiveInstalledModel() {
  if (!state.activeModelId) {
    return false;
  }
  if (state.models.length === 0) {
    return Boolean(state.activeModelId);
  }
  return state.models.some((item) => item.id === state.activeModelId && item.installed);
}

function renderUploadState() {
  const hasSelection = state.selectedFiles.length > 0;
  const hasModel = hasActiveInstalledModel();
  const selectedSummaryText = hasSelection
    ? t("upload.selectedSummary", {
      count: state.selectedFiles.length,
      size: formatBytes(state.selectedFiles.reduce((sum, file) => sum + (Number(file.size) || 0), 0)),
    })
    : t("upload.emptySelection");
  const progressRatio = state.uploadProgressTotal > 0 ? state.uploadProgressDone / state.uploadProgressTotal : 0;
  uploadProgressBar.style.width = `${Math.max(0, Math.min(progressRatio, 1)) * 100}%`;

  pickFilesBtn.disabled = state.sending;
  clearSelectionBtn.disabled = !hasSelection || state.sending;
  showFilesModalBtn.disabled = !hasSelection;
  enqueueBtn.disabled = state.sending || !hasSelection || !hasModel;
  enqueueBtn.textContent = state.sending
    ? t("upload.enqueueBusy", { done: state.uploadProgressDone, total: state.uploadProgressTotal })
    : t("upload.enqueue");

  if (state.sending) {
    uploadFeedbackEl.dataset.tone = "normal";
    uploadFeedbackEl.textContent = t("upload.localUploading");
    commandBatchSummaryEl.textContent = t("upload.uploadProgress", {
      done: state.uploadProgressDone,
      total: state.uploadProgressTotal,
    });
    uploadCurrentFileEl.textContent = t("upload.currentFile", {
      name: state.uploadCurrentName || t("common.unknown"),
    });
    return;
  }

  uploadCurrentFileEl.textContent = "";

  if (state.uploadNotice) {
    uploadFeedbackEl.dataset.tone = state.uploadNotice.tone;
    uploadFeedbackEl.textContent = state.uploadNotice.message;
    commandBatchSummaryEl.textContent = hasSelection ? selectedSummaryText : t("common.none");
    return;
  }

  if (state.lastUploadSummary) {
    const summary = state.lastUploadSummary;
    uploadFeedbackEl.dataset.tone = summary.failed > 0 ? "error" : "success";
    uploadFeedbackEl.textContent = summary.failed > 0 ? t("upload.localDoneWithErrors") : t("upload.localDone");
    commandBatchSummaryEl.textContent = t("upload.uploadComplete", {
      done: summary.done,
      total: summary.total,
      failed: summary.failed,
    });
    return;
  }

  if (hasSelection) {
    uploadFeedbackEl.dataset.tone = hasModel ? "normal" : "error";
    uploadFeedbackEl.textContent = hasModel ? t("upload.localReady") : t("models.chooseOrDownload");
    commandBatchSummaryEl.textContent = selectedSummaryText;
    return;
  }

  if (!hasModel) {
    uploadFeedbackEl.dataset.tone = "error";
    uploadFeedbackEl.textContent = t("models.chooseOrDownload");
    commandBatchSummaryEl.textContent = t("common.none");
    return;
  }

  delete uploadFeedbackEl.dataset.tone;
  uploadFeedbackEl.textContent = "";
  commandBatchSummaryEl.textContent = t("common.none");
}

function renderJobs() {
  jobsCounter.textContent = String(state.jobOrder.length);

  if (state.jobOrder.length === 0) {
    jobsList.innerHTML = "";
    jobsEmpty.style.display = "block";
    return;
  }

  jobsEmpty.style.display = "none";
  jobsList.innerHTML = state.jobOrder
    .map((jobId) => {
      const job = state.jobs.get(jobId);
      if (!job) {
        return "";
      }
      const statusKey = getStatusKey(job);
      const errorHtml = job.error ? `<div class="job-error">${escapeHtml(job.error)}</div>` : "";
      const openAction = canOpen(job)
        ? `<a class="mini-btn as-link" href="/jobs/${encodeURIComponent(jobId)}">${escapeHtml(t("jobs.open"))}</a>`
        : "";
      const metrics = [
        { label: t("jobs.model"), value: job.model_id || t("common.unknown") },
      ];

      if (job.status === "queued") {
        metrics.push({ label: t("jobs.queue"), value: String(job.queue_position || 0) });
      } else {
        metrics.push({ label: t("jobs.elapsed"), value: formatDuration(job.started_at, job.finished_at, t) });
      }

      const metricsHtml = metrics
        .map(
          (item) => `
            <span class="job-metric-chip">
              <span class="job-metric-label">${escapeHtml(item.label)}</span>
              <span>${escapeHtml(item.value)}</span>
            </span>
          `,
        )
        .join("");

      const actionParts = [];
      if (openAction) {
        actionParts.push(openAction);
      }
      if (canCancel(job)) {
        actionParts.push(
          `<button class="mini-btn" data-action="stop" data-job-id="${escapeHtml(jobId)}">${escapeHtml(t("actions.stop"))}</button>`,
        );
      } else {
        if (canRetry(job)) {
          actionParts.push(
            `<button class="mini-btn" data-action="retry" data-job-id="${escapeHtml(jobId)}">${escapeHtml(t("actions.retry"))}</button>`,
          );
        }
        if (canRemove(job)) {
          actionParts.push(
            `<button class="mini-btn" data-action="remove" data-job-id="${escapeHtml(jobId)}">${escapeHtml(t("actions.remove"))}</button>`,
          );
        }
      }

      return `
        <article class="job-card ${statusKey === "failed" ? "failed" : ""}">
          <div class="job-head">
            <div class="job-name">${escapeHtml(job.original_filename || jobId)}</div>
            <span class="job-status status-${escapeHtml(statusKey)}">${escapeHtml(getStatusLabel(job, t))}</span>
          </div>

          <div class="job-meta-row">${metricsHtml}</div>

          <div class="job-progress-row">
            <div class="progress-track">
              <div class="progress-bar" style="width:${Number(job.progress_percent) || 0}%"></div>
            </div>
            <span class="job-progress-value">${escapeHtml(`${job.progress_percent || 0}%`)}</span>
          </div>

          ${errorHtml}

          <div class="job-actions">
            ${actionParts.join("")}
          </div>
        </article>
      `;
    })
    .join("");
}

async function syncJobsFromServer() {
  const response = await fetch("/api/jobs?limit=200");
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  const items = Array.isArray(payload.items) ? payload.items : [];
  state.jobs = new Map(items.map((item) => [item.job_id, item]));
  state.jobOrder = items.map((item) => item.job_id);
}

async function syncModelsFromServer() {
  const response = await fetch("/api/models/faster-whisper");
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const payload = await response.json();
  state.models = Array.isArray(payload.items) ? payload.items : [];
  state.activeModelId = payload.active_model_id || "";
}

function registerJobStatusTransitions() {
  for (const [jobId, job] of state.jobs.entries()) {
    const previousStatus = state.knownJobStatus.get(jobId);
    if (previousStatus && previousStatus !== job.status && !TERMINAL_STATUSES.has(previousStatus) && TERMINAL_STATUSES.has(job.status)) {
      const kind = job.status === "done" ? "job_done" : "job_attention";
      void playUiNotification(kind);
    }
    state.knownJobStatus.set(jobId, job.status);
  }
}

function evaluateBatchNotifications() {
  const remainingBatches = [];
  state.trackedBatches.forEach((batch) => {
    if (!batch.uploadDone || batch.notified || batch.jobIds.length === 0) {
      remainingBatches.push(batch);
      return;
    }
    const allFinished = batch.jobIds.every((jobId) => TERMINAL_STATUSES.has(state.knownJobStatus.get(jobId)));
    if (!allFinished) {
      remainingBatches.push(batch);
      return;
    }
    batch.notified = true;
    void playUiNotification("queue_complete");
  });
  state.trackedBatches = remainingBatches.filter((batch) => !batch.notified);
}

async function pollAndRender() {
  try {
    await Promise.all([syncJobsFromServer(), syncModelsFromServer()]);
    registerJobStatusTransitions();
    evaluateBatchNotifications();
    renderModels();
    renderJobs();
    clearJobsNotice();
  } catch (error) {
    setJobsNotice(t("status.requestError", { message: String(error) }), "error");
  }
}

async function createJobFromQueueItem(item) {
  const data = new FormData();
  data.append("file", item.file);
  data.append("model_id", item.model_id);
  data.append("include_timestamps", item.include_timestamps ? "true" : "false");

  const response = await fetch("/api/jobs", {
    method: "POST",
    body: data,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

async function processLocalQueue() {
  if (state.sending || state.localQueue.length === 0) {
    renderUploadState();
    return;
  }

  state.sending = true;
  state.uploadProgressTotal = state.localQueue.length;
  state.uploadProgressDone = 0;
  state.uploadCurrentName = "";
  state.lastUploadSummary = null;
  clearUploadNotice();
  const batch = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    jobIds: [],
    notified: false,
    uploadDone: false,
  };
  renderUploadState();

  let failed = 0;
  while (state.localQueue.length > 0) {
    const item = state.localQueue[0];
    state.uploadCurrentName = item.file.name;
    renderUploadState();

    try {
      const payload = await createJobFromQueueItem(item);
      batch.jobIds.push(payload.job_id);
      state.knownJobStatus.set(payload.job_id, payload.status || "queued");
      state.localQueue.shift();
      state.uploadProgressDone += 1;
      await pollAndRender();
    } catch (error) {
      failed += 1;
      state.localQueue.shift();
      state.uploadProgressDone += 1;
      setUploadNotice(t("status.createError", { message: String(error) }), "error");
    }
  }

  state.sending = false;
  state.uploadCurrentName = "";
  clearUploadNotice();
  state.lastUploadSummary = {
    done: state.uploadProgressTotal - failed,
    total: state.uploadProgressTotal,
    failed,
  };
  if (batch.jobIds.length > 0) {
    batch.uploadDone = true;
    state.trackedBatches.push(batch);
  }
  state.uploadProgressTotal = 0;
  state.uploadProgressDone = 0;
  renderUploadState();
}

function queueSelectedFiles() {
  if (state.sending) {
    setUploadNotice(t("upload.busySelection"), "error");
    return;
  }
  if (state.selectedFiles.length === 0) {
    setUploadNotice(t("upload.noFiles"), "error");
    return;
  }
  if (!hasActiveInstalledModel()) {
    setUploadNotice(t("models.chooseOrDownload"), "error");
    return;
  }

  const files = state.selectedFiles.slice();
  const modelId = state.activeModelId;
  const includeTimestamps = Boolean(timestampsInput.checked);
  files.forEach((file) => {
    state.localQueue.push({
      file,
      model_id: modelId,
      include_timestamps: includeTimestamps,
    });
  });

  state.lastUploadSummary = null;
  clearUploadNotice();
  state.uploadNotice = {
    message: t("upload.queuedBatch", { count: files.length }),
    tone: "normal",
  };
  clearSelectedFiles();
  processLocalQueue();
}

async function handleRetry(jobId) {
  const job = state.jobs.get(jobId);
  if (!job || !canRetry(job)) {
    return;
  }

  setJobsNotice(t("status.retrying", { name: job.original_filename || jobId }));
  try {
    const response = await fetch(`/api/jobs/${jobId}/retry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const payload = await response.json();
    if (payload.job_id) {
      state.knownJobStatus.set(payload.job_id, payload.status || "queued");
    }
    clearJobsNotice();
    window.location.assign(`/jobs/${encodeURIComponent(payload.job_id)}`);
  } catch (error) {
    setJobsNotice(t("status.retryError", { message: String(error) }), "error");
  }
}

async function handleRemove(jobId) {
  const job = state.jobs.get(jobId);
  if (!job || !canRemove(job)) {
    return;
  }

  setJobsNotice(t("status.removing", { name: job.original_filename || jobId }));
  try {
    const response = await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    state.jobs.delete(jobId);
    state.jobOrder = state.jobOrder.filter((id) => id !== jobId);
    renderJobs();
    clearJobsNotice();
  } catch (error) {
    setJobsNotice(t("status.removeError", { message: String(error) }), "error");
  }
}

async function handleStop(jobId) {
  const job = state.jobs.get(jobId);
  if (!job || !canCancel(job)) {
    return;
  }

  setJobsNotice(t("status.stopping", { name: job.original_filename || jobId }));
  try {
    const response = await fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    const payload = await response.json();
    state.jobs.set(jobId, payload);
    renderJobs();
    clearJobsNotice();
  } catch (error) {
    setJobsNotice(t("status.stopError", { message: String(error) }), "error");
  }
}

async function handleModelInstall(modelId) {
  setJobsNotice(t("models.downloading"));
  try {
    const response = await fetch("/api/models/faster-whisper/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: modelId }),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    await pollAndRender();
    clearJobsNotice();
  } catch (error) {
    setJobsNotice(t("status.modelInstallError", { message: String(error) }), "error");
  }
}

async function handleModelSelect(modelId) {
  try {
    const response = await fetch("/api/models/faster-whisper/select", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model_id: modelId }),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    await pollAndRender();
  } catch (error) {
    setJobsNotice(t("status.modelSelectError", { message: String(error) }), "error");
  }
}

async function handleModelDelete(modelId) {
  try {
    const response = await fetch(`/api/models/faster-whisper/${encodeURIComponent(modelId)}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }
    await pollAndRender();
  } catch (error) {
    setJobsNotice(t("status.modelDeleteError", { message: String(error) }), "error");
  }
}

function setupDragAndDrop() {
  function indicate(active) {
    dropZone.classList.toggle("dragover", active);
  }

  ["dragenter", "dragover"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      if (state.sending) {
        return;
      }
      indicate(true);
    });
  });

  ["dragleave", "dragend"].forEach((eventName) => {
    dropZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      indicate(false);
    });
  });

  dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    indicate(false);
    if (state.sending) {
      setUploadNotice(t("upload.busySelection"), "error");
      return;
    }
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length > 0) {
      mergeSelectedFiles(files);
    }
  });
}

function bindEvents() {
  langToggleBtn.addEventListener("click", () => {
    prefs.lang = prefs.lang === "ru" ? "en" : "ru";
    savePrefs();
    applyPageChrome();
  });

  themeToggleBtn.addEventListener("click", () => {
    prefs.theme = prefs.theme === "dark" ? "light" : "dark";
    savePrefs();
    applyPageChrome();
  });

  settingsBtn.addEventListener("click", async () => {
    try {
      await fetchDesktopSettings();
      openSettingsModal();
    } catch (error) {
      state.settingsError = t("settings.loadError", { message: String(error) });
      openSettingsModal();
    }
  });

  dropZone.addEventListener("click", (event) => {
    if (state.sending) {
      return;
    }
    if (event.target.closest("button")) {
      return;
    }
    fileInput.click();
  });

  dropZone.addEventListener("keydown", (event) => {
    if (state.sending) {
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      fileInput.click();
    }
  });

  pickFilesBtn.addEventListener("click", () => {
    if (!state.sending) {
      fileInput.click();
    }
  });

  fileInput.addEventListener("change", () => {
    mergeSelectedFiles(Array.from(fileInput.files || []));
    fileInput.value = "";
  });

  clearSelectionBtn.addEventListener("click", () => {
    clearSelectedFiles();
  });

  showFilesModalBtn.addEventListener("click", () => {
    openFilesModal();
  });

  openModelsModalBtn.addEventListener("click", () => {
    openModelsModal();
  });

  closeFilesModalBtn.addEventListener("click", () => {
    closeFilesModal();
  });

  closeModelsModalBtn.addEventListener("click", () => {
    closeModelsModal();
  });

  closeSettingsModalBtn.addEventListener("click", () => {
    closeSettingsModal();
  });

  saveSettingsBtn.addEventListener("click", () => {
    void saveDesktopSettings();
  });

  modelSelect.addEventListener("change", () => {
    if (!modelSelect.value) {
      modelSelect.value = state.activeModelId || "";
      return;
    }
    handleModelSelect(modelSelect.value);
  });

  filesModal.addEventListener("click", (event) => {
    if (event.target === filesModal || event.target.closest("[data-modal-dismiss]")) {
      closeFilesModal();
    }
  });

  modelsModal.addEventListener("click", (event) => {
    if (event.target === modelsModal || event.target.closest("[data-model-modal-dismiss]")) {
      closeModelsModal();
    }
  });

  settingsModal.addEventListener("click", (event) => {
    if (event.target === settingsModal || event.target.closest("[data-settings-modal-dismiss]")) {
      closeSettingsModal();
    }
  });

  filesModalList.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-selected-index]");
    if (!removeButton) {
      return;
    }
    removeSelectedFileAt(Number(removeButton.dataset.removeSelectedIndex));
  });

  modelsModalList.addEventListener("click", (event) => {
    const actionButton = event.target.closest("[data-model-action]");
    if (!actionButton) {
      return;
    }
    const modelId = actionButton.dataset.modelId;
    const action = actionButton.dataset.modelAction;
    if (!modelId) {
      return;
    }
    if (action === "download") {
      handleModelInstall(modelId);
      return;
    }
    if (action === "select") {
      handleModelSelect(modelId);
      return;
    }
    if (action === "delete") {
      handleModelDelete(modelId);
    }
  });

  uploadForm.addEventListener("submit", (event) => {
    event.preventDefault();
    queueSelectedFiles();
  });

  jobsList.addEventListener("click", (event) => {
    const actionButton = event.target.closest("button[data-action]");
    if (!actionButton) {
      return;
    }
    const jobId = actionButton.dataset.jobId;
    const action = actionButton.dataset.action;
    if (!jobId) {
      return;
    }
    if (action === "retry") {
      handleRetry(jobId);
      return;
    }
    if (action === "stop") {
      handleStop(jobId);
      return;
    }
    if (action === "remove") {
      handleRemove(jobId);
    }
  });

  setupDragAndDrop();

  window.addEventListener("unhandledrejection", (event) => {
    setJobsNotice(t("status.requestError", { message: String(event.reason) }), "error");
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && state.filesModalOpen) {
      closeFilesModal();
    }
    if (event.key === "Escape" && state.modelsModalOpen) {
      closeModelsModal();
    }
    if (event.key === "Escape" && state.settingsModalOpen) {
      closeSettingsModal();
    }
  });
}

async function boot() {
  applyPageChrome();
  bindEvents();
  renderSettingsModal();
  try {
    await fetchDesktopSettings();
  } catch {
    state.desktopSettingsLoaded = false;
  }
  renderSettingsModal();
  await pollAndRender();

  state.pollTimer = setInterval(() => {
    pollAndRender();
  }, 2500);

  state.elapsedTimer = setInterval(() => {
    renderJobs();
  }, 1000);
}

boot();
