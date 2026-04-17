const STORAGE_KEYS = {
  lang: "voctarium.ui.lang",
  theme: "voctarium.ui.theme",
  readerFontScale: "voctarium.ui.readerFontScale",
  readerFontSizePx: "voctarium.ui.readerFontSizePx",
  readerLineHeight: "voctarium.ui.readerLineHeight",
  readerContentWidth: "voctarium.ui.readerContentWidth",
  readerContentWidthPercent: "voctarium.ui.readerContentWidthPercent",
  readerAlignMode: "voctarium.ui.readerAlignMode",
  readerJustify: "voctarium.ui.readerJustify",
  readerParagraphGap: "voctarium.ui.readerParagraphGap",
};

const I18N = {
  ru: {
    appTitle: "Voctarium STT",
    app: {
      backToJobs: "Назад",
      resultTitle: "Результат",
    },
    controls: {
      themeToDark: "Темная",
      themeToLight: "Светлая",
    },
    upload: {
      title: "Загрузка",
      dropTitle: "Перетащи аудио или видео файлы сюда",
      dropHint: "или выбери пакет через кнопку ниже",
      pickFiles: "Выбрать файлы",
      openFileList: "Список файлов",
      fileListTitle: "Файлы в пакете",
      clearSelection: "Очистить",
      selectedBatch: "Выбранный пакет",
      emptySelection: "нет",
      selectedSummary: "{count} файл(ов), {size}",
      localReady: "Пакет готов к отправке.",
      localUploading: "Идет отправка.",
      localDone: "Отправка завершена.",
      localDoneWithErrors: "Отправка завершена с ошибками.",
      model: "Модель faster-whisper",
      manageModels: "Модели",
      timestamps: "Включить таймкоды",
      enqueue: "Добавить в очередь",
      enqueueBusy: "Отправка {done}/{total}",
      noFiles: "Сначала выбери хотя бы один файл.",
      busySelection: "Дождись завершения текущей отправки.",
      currentFile: "Сейчас: {name}",
      uploadProgress: "Отправка {done}/{total}",
      uploadComplete: "Отправлено {done} из {total}. Ошибок: {failed}.",
      queuedBatch: "В очередь добавлено {count} файл(ов).",
      fileMeta: "{size}",
    },
    jobs: {
      title: "Задачи",
      empty: "Пока нет задач.",
      open: "Открыть",
      created: "Создано",
      elapsed: "Время",
      model: "Модель",
      progress: "Прогресс",
      queue: "Очередь",
      error: "Ошибка",
    },
    models: {
      title: "Модели faster-whisper",
      activeSummary: "Активная модель: {model}",
      empty: "Модели не найдены.",
      chooseModel: "Выбери модель",
      chooseOrDownload: "Выбери или скачай модель.",
      installed: "Установлена",
      active: "Активна",
      downloading: "Скачивается",
      unavailable: "Недоступна",
      sizeKnown: "Размер загрузки: {size}",
      sizeUnknown: "Размер загрузки: неизвестен",
      downloadProgress: "{downloaded} / {total} ({percent})",
      download: "Скачать",
      select: "Выбрать",
      delete: "Удалить",
    },
    result: {
      title: "Результат",
      readable: "Читабельный текст",
      view: "Вид",
      editor: "Редактор",
      fontSize: "Размер шрифта",
      lineHeight: "Межстрочие",
      contentWidth: "Ширина текста",
      justify: "Выравнивание",
      lineCompact: "Плотно",
      lineNormal: "Нормально",
      lineRelaxed: "Свободно",
      justifyLeft: "По левому краю",
      justifyOn: "По ширине",
      justifyHyphen: "По ширине + переносы",
      paragraphGap: "Пустая строка между абзацами",
      loading: "Загрузка результата...",
      notReady: "Результат еще не готов.",
      unavailable: "Результат недоступен или уже очищен.",
      notFound: "Задача не найдена.",
      queued: "Задача в очереди. Страница обновится автоматически.",
      processing: "Идет расшифровка. Страница обновится автоматически.",
      cancelled: "Задача была остановлена пользователем.",
      failed: "Задача завершилась с ошибкой.",
      removed: "Задача была удалена.",
      loadError: "Не удалось загрузить результат: {status}",
      pollError: "Не удалось обновить состояние задачи: {message}",
      waitingTitle: "Ожидание результата",
      cancelledTitle: "Обработка остановлена",
      failedTitle: "Ошибка обработки",
      notFoundTitle: "Задача не найдена",
      metaTitle: "Инфо",
      contentTitle: "Текст",
      readableUnavailable: "Читабельный текст для этой задачи недоступен.",
      saveError: "Не удалось сохранить файл: {message}",
      saveFallbackWarning: "Native Save As недоступен, использована обычная загрузка файла.",
      editorToolbar: "Редактор",
      editorStatusDirty: "Не сохранено",
      editorStatusSaving: "Сохраняется…",
      editorStatusSaved: "Сохранено",
      editorStatusError: "Ошибка сохранения",
      editorStatusIdle: "Без изменений",
      editorResetConfirm: "Сбросить правки и вернуть исходный текст?",
      editorResetError: "Не удалось сбросить правки: {message}",
      editorSaveTitle: "Редактор",
      editorUnavailable: "Редактор недоступен для этой задачи.",
      bold: "Жирный",
      italic: "Курсив",
      paragraph: "Параграф",
      heading2: "H2",
      heading3: "H3",
      bulletList: "Маркированный список",
      orderedList: "Нумерованный список",
      undo: "Undo",
      redo: "Redo",
      find: "Поиск",
      reset: "Сбросить",
      findPlaceholder: "Найти в документе",
      findPrev: "Назад",
      findNext: "Вперед",
      findClose: "Закрыть поиск",
      findNoResults: "Ничего не найдено",
      findResults: "{current} из {total}",
      wordsChars: "{words} слов • {chars} символов",
    },
    settings: {
      title: "Настройки",
      cleanupUploadsOnClose: "Очищать загруженные файлы после закрытия",
      cleanupQueueOnClose: "Очищать очередь после закрытия",
      saved: "Настройки готовы",
      saving: "Сохраняется…",
      loadError: "Не удалось загрузить настройки: {message}",
      saveError: "Не удалось сохранить настройки: {message}",
    },
    actions: {
      close: "Закрыть",
      save: "Сохранить",
      settings: "Настройки",
      stop: "Стоп",
      retry: "Повторить",
      remove: "Удалить",
      download: "Скачать .md",
      downloadPdf: "Скачать PDF",
    },
    status: {
      queued: "В очереди",
      processing: "Обработка",
      done: "Готово",
      cancelled: "Остановлено",
      failed: "Ошибка",
      createError: "Ошибка создания задачи: {message}",
      retryError: "Ошибка повтора: {message}",
      modelInstallError: "Ошибка загрузки модели: {message}",
      modelSelectError: "Ошибка выбора модели: {message}",
      modelDeleteError: "Ошибка удаления модели: {message}",
      stopError: "Ошибка остановки: {message}",
      removeError: "Ошибка удаления: {message}",
      requestError: "Сетевой сбой: {message}",
      retrying: "Повторный запуск {name}...",
      stopping: "Остановка {name}...",
      removing: "Удаление {name}...",
    },
    details: {
      filename: "Файл",
      status: "Статус",
      model: "Модель",
      progress: "Прогресс",
      queue: "Позиция в очереди",
      jobId: "Job ID",
      created: "Создано",
      finished: "Завершено",
      elapsed: "Время",
      retryOf: "Повтор задачи",
      timestamps: "Таймкоды",
    },
    common: {
      never: "—",
      unknown: "неизвестно",
      none: "нет",
      enabled: "вкл",
      disabled: "выкл",
      yes: "Да",
      no: "Нет",
    },
  },
  en: {
    appTitle: "Voctarium STT",
    app: {
      backToJobs: "Back",
      resultTitle: "Result",
    },
    controls: {
      themeToDark: "Dark",
      themeToLight: "Light",
    },
    upload: {
      title: "Upload",
      dropTitle: "Drop audio or video files here",
      dropHint: "or choose a batch with the button below",
      pickFiles: "Pick files",
      openFileList: "File list",
      fileListTitle: "Files in batch",
      clearSelection: "Clear",
      selectedBatch: "Selected batch",
      emptySelection: "none",
      selectedSummary: "{count} file(s), {size}",
      localReady: "Batch is ready to queue.",
      localUploading: "Uploading is in progress.",
      localDone: "Upload finished.",
      localDoneWithErrors: "Upload finished with errors.",
      model: "Faster-whisper model",
      manageModels: "Models",
      timestamps: "Include timestamps",
      enqueue: "Add to queue",
      enqueueBusy: "Uploading {done}/{total}",
      noFiles: "Pick at least one file first.",
      busySelection: "Wait until the current upload batch finishes.",
      currentFile: "Now: {name}",
      uploadProgress: "Uploading {done}/{total}",
      uploadComplete: "Uploaded {done} of {total}. Failed: {failed}.",
      queuedBatch: "Queued {count} file(s).",
      fileMeta: "{size}",
    },
    jobs: {
      title: "Jobs",
      empty: "No jobs yet.",
      open: "Open",
      created: "Created",
      elapsed: "Elapsed",
      model: "Model",
      progress: "Progress",
      queue: "Queue",
      error: "Error",
    },
    models: {
      title: "Faster-whisper models",
      activeSummary: "Active model: {model}",
      empty: "No models found.",
      chooseModel: "Choose model",
      chooseOrDownload: "Choose or download a model.",
      installed: "Installed",
      active: "Active",
      downloading: "Downloading",
      unavailable: "Unavailable",
      sizeKnown: "Download size: {size}",
      sizeUnknown: "Download size: unknown",
      downloadProgress: "{downloaded} / {total} ({percent})",
      download: "Download",
      select: "Select",
      delete: "Delete",
    },
    result: {
      title: "Result",
      readable: "Readable text",
      view: "View",
      editor: "Editor",
      fontSize: "Font size",
      lineHeight: "Line spacing",
      contentWidth: "Text width",
      justify: "Alignment",
      lineCompact: "Compact",
      lineNormal: "Normal",
      lineRelaxed: "Relaxed",
      justifyLeft: "Left aligned",
      justifyOn: "Justified",
      justifyHyphen: "Justified + hyphenation",
      paragraphGap: "Blank line between paragraphs",
      loading: "Loading result...",
      notReady: "Result is not ready yet.",
      unavailable: "Result is unavailable or already cleaned.",
      notFound: "Job not found.",
      queued: "The job is still queued. This page will refresh automatically.",
      processing: "Transcription is in progress. This page will refresh automatically.",
      cancelled: "The job was cancelled by the user.",
      failed: "The job finished with an error.",
      removed: "The job was removed.",
      loadError: "Failed to load result: {status}",
      pollError: "Failed to refresh job state: {message}",
      waitingTitle: "Waiting for result",
      cancelledTitle: "Processing cancelled",
      failedTitle: "Processing failed",
      notFoundTitle: "Job not found",
      metaTitle: "Info",
      contentTitle: "Transcript",
      readableUnavailable: "Readable text is unavailable for this job.",
      saveError: "Failed to save file: {message}",
      saveFallbackWarning: "Native Save As is unavailable, browser download fallback was used.",
      editorToolbar: "Editor",
      editorStatusDirty: "Unsaved",
      editorStatusSaving: "Saving…",
      editorStatusSaved: "Saved",
      editorStatusError: "Save error",
      editorStatusIdle: "No changes",
      editorResetConfirm: "Reset edits and restore the original text?",
      editorResetError: "Failed to reset edits: {message}",
      editorSaveTitle: "Editor",
      editorUnavailable: "Editor is unavailable for this job.",
      bold: "Bold",
      italic: "Italic",
      paragraph: "Paragraph",
      heading2: "H2",
      heading3: "H3",
      bulletList: "Bulleted list",
      orderedList: "Numbered list",
      undo: "Undo",
      redo: "Redo",
      find: "Find",
      reset: "Reset",
      findPlaceholder: "Find in document",
      findPrev: "Previous",
      findNext: "Next",
      findClose: "Close search",
      findNoResults: "No matches",
      findResults: "{current} of {total}",
      wordsChars: "{words} words • {chars} chars",
    },
    settings: {
      title: "Settings",
      cleanupUploadsOnClose: "Clean uploaded files on close",
      cleanupQueueOnClose: "Clean queue on close",
      saved: "Settings are ready",
      saving: "Saving…",
      loadError: "Unable to load settings: {message}",
      saveError: "Unable to save settings: {message}",
    },
    actions: {
      close: "Close",
      save: "Save",
      settings: "Settings",
      stop: "Stop",
      retry: "Retry",
      remove: "Remove",
      download: "Download .md",
      downloadPdf: "Download PDF",
    },
    status: {
      queued: "Queued",
      processing: "Processing",
      done: "Done",
      cancelled: "Cancelled",
      failed: "Failed",
      createError: "Create job failed: {message}",
      retryError: "Retry failed: {message}",
      modelInstallError: "Model download failed: {message}",
      modelSelectError: "Model selection failed: {message}",
      modelDeleteError: "Model deletion failed: {message}",
      stopError: "Stop failed: {message}",
      removeError: "Delete failed: {message}",
      requestError: "Network error: {message}",
      retrying: "Retrying {name}...",
      stopping: "Stopping {name}...",
      removing: "Removing {name}...",
    },
    details: {
      filename: "File",
      status: "Status",
      model: "Model",
      progress: "Progress",
      queue: "Queue position",
      jobId: "Job ID",
      created: "Created",
      finished: "Finished",
      elapsed: "Elapsed",
      retryOf: "Retry of",
      timestamps: "Timestamps",
    },
    common: {
      never: "-",
      unknown: "unknown",
      none: "none",
      enabled: "on",
      disabled: "off",
      yes: "Yes",
      no: "No",
    },
  },
};

function resolveText(lang, path) {
  const parts = path.split(".");
  let value = I18N[lang];
  for (const part of parts) {
    if (value == null || typeof value !== "object" || !(part in value)) {
      return path;
    }
    value = value[part];
  }
  return typeof value === "string" ? value : path;
}

export function parseJsonSafe(value, fallback) {
  try {
    return JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function loadString(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value === null ? fallback : value;
  } catch {
    return fallback;
  }
}

export function saveString(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Ignore storage failures.
  }
}

export function createUiContext() {
  const legacyWidth = loadString(STORAGE_KEYS.readerContentWidth, "wide");
  const legacyWidthPercentMap = {
    narrow: 75,
    wide: 90,
    full: 100,
  };

  const state = {
    lang: loadString(STORAGE_KEYS.lang, "ru"),
    theme: loadString(STORAGE_KEYS.theme, "dark"),
    readerFontScale: Number.parseFloat(loadString(STORAGE_KEYS.readerFontScale, "1")),
    readerFontSizePx: Number.parseInt(loadString(STORAGE_KEYS.readerFontSizePx, "0"), 10),
    readerLineHeight: loadString(STORAGE_KEYS.readerLineHeight, "normal"),
    readerContentWidthPercent: Number.parseInt(
      loadString(
        STORAGE_KEYS.readerContentWidthPercent,
        String(legacyWidthPercentMap[legacyWidth] || 100),
      ),
      10,
    ),
    readerAlignMode: loadString(STORAGE_KEYS.readerAlignMode, loadString(STORAGE_KEYS.readerJustify, "justify")),
    readerParagraphGap: loadString(STORAGE_KEYS.readerParagraphGap, "false") === "true",
  };

  if (!["ru", "en"].includes(state.lang)) {
    state.lang = "ru";
  }
  if (!["light", "dark"].includes(state.theme)) {
    state.theme = "dark";
  }
  if (!Number.isFinite(state.readerFontScale)) {
    state.readerFontScale = 1;
  }
  state.readerFontScale = Math.min(1.4, Math.max(0.85, state.readerFontScale));
  if (!Number.isFinite(state.readerFontSizePx) || state.readerFontSizePx <= 0) {
    state.readerFontSizePx = Math.round(18 * state.readerFontScale);
  }
  state.readerFontSizePx = Math.min(32, Math.max(12, state.readerFontSizePx));
  if (!["compact", "normal", "relaxed"].includes(state.readerLineHeight)) {
    state.readerLineHeight = "normal";
  }
  if (!Number.isFinite(state.readerContentWidthPercent)) {
    state.readerContentWidthPercent = 100;
  }
  state.readerContentWidthPercent = Math.max(50, Math.min(100, state.readerContentWidthPercent));
  if (!["left", "justify", "justify_hyphen"].includes(state.readerAlignMode)) {
    state.readerAlignMode = "justify";
  }

  function t(path, vars = {}) {
    let text = resolveText(state.lang, path);
    Object.entries(vars).forEach(([key, value]) => {
      text = text.replaceAll(`{${key}}`, String(value));
    });
    return text;
  }

  function savePrefs() {
    saveString(STORAGE_KEYS.lang, state.lang);
    saveString(STORAGE_KEYS.theme, state.theme);
    saveString(STORAGE_KEYS.readerFontSizePx, String(state.readerFontSizePx));
    saveString(STORAGE_KEYS.readerLineHeight, state.readerLineHeight);
    saveString(STORAGE_KEYS.readerContentWidthPercent, String(state.readerContentWidthPercent));
    saveString(STORAGE_KEYS.readerAlignMode, state.readerAlignMode);
    saveString(STORAGE_KEYS.readerParagraphGap, state.readerParagraphGap ? "true" : "false");
  }

  return { state, t, savePrefs };
}

export function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function formatBytes(bytes) {
  const size = Number(bytes) || 0;
  if (size <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = size;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const digits = value >= 100 || unitIndex === 0 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[unitIndex]}`;
}

export function formatDate(value, lang, t) {
  if (!value) {
    return t("common.never");
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return t("common.unknown");
  }
  return date.toLocaleString(lang === "ru" ? "ru-RU" : "en-US");
}

export function formatDuration(startIso, endIso, t) {
  if (!startIso) {
    return t("common.never");
  }
  const start = new Date(startIso);
  if (Number.isNaN(start.getTime())) {
    return t("common.unknown");
  }
  const end = endIso ? new Date(endIso) : new Date();
  const diffMs = Math.max(0, end.getTime() - start.getTime());
  const totalSeconds = Math.floor(diffMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((item) => String(item).padStart(2, "0")).join(":");
}

export function getStatusKey(job) {
  return job?.status || "queued";
}

export function getStatusLabel(job, t) {
  return t(`status.${getStatusKey(job)}`);
}

export function canRetry(job) {
  return Boolean(job) && ["done", "failed", "cancelled"].includes(job.status) && job.source_available;
}

export function canDownload(job) {
  return Boolean(job) && job.status === "done" && job.readable_available;
}

export function canOpen(job) {
  return canDownload(job);
}

export function canRemove(job) {
  return Boolean(job) && job.status !== "processing";
}

export function canCancel(job) {
  return Boolean(job) && job.status === "processing";
}

export function applyTheme(theme) {
  document.body.dataset.theme = theme;
}

export function applyStaticI18n(t) {
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    const key = node.getAttribute("data-i18n");
    node.textContent = t(key);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
    const key = node.getAttribute("data-i18n-placeholder");
    node.setAttribute("placeholder", t(key));
  });
}

export function syncPreferenceButtons({ state, t, langToggleBtn, themeToggleBtn }) {
  if (langToggleBtn) {
    langToggleBtn.textContent = state.lang === "ru" ? "EN" : "RU";
  }
  if (themeToggleBtn) {
    themeToggleBtn.textContent = state.theme === "dark" ? t("controls.themeToLight") : t("controls.themeToDark");
  }
}

export function setDocumentTitle(title) {
  document.title = title;
}

let webAudioContext = null;

function webToneSequence(kind) {
  if (typeof window === "undefined") {
    return Promise.resolve();
  }
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextCtor) {
    return Promise.resolve();
  }
  if (!webAudioContext) {
    webAudioContext = new AudioContextCtor();
  }
  const context = webAudioContext;
  const now = context.currentTime;
  const tones = kind === "job_attention"
    ? [420, 320]
    : kind === "queue_complete"
      ? [660, 880]
      : [740];

  tones.forEach((frequency, index) => {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    oscillator.connect(gain);
    gain.connect(context.destination);
    const startAt = now + index * 0.16;
    gain.gain.setValueAtTime(0.0001, startAt);
    gain.gain.exponentialRampToValueAtTime(0.04, startAt + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, startAt + 0.12);
    oscillator.start(startAt);
    oscillator.stop(startAt + 0.13);
  });
  return Promise.resolve();
}

export async function playUiNotification(kind) {
  const desktopApi = typeof window !== "undefined" ? window.pywebview?.api?.play_notification : null;
  if (desktopApi) {
    try {
      await desktopApi(kind);
      return;
    } catch {
      // Fall through to browser beep.
    }
  }
  await webToneSequence(kind);
}

export function renderMarkdownContent(container, mode, content) {
  container.classList.remove("empty");
  if (mode === "raw") {
    container.innerHTML = `<pre class="raw-block">${escapeHtml(content)}</pre>`;
    return;
  }
  container.innerHTML = content;
}

export { I18N, STORAGE_KEYS };
