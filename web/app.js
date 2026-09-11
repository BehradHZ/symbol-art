const $ = (id) => document.getElementById(id);

const LIMITS = {
  maxUploadBytes: 14 * 1024 * 1024,
  updateDelayMs: 160,
};

const DEFAULTS = {
  width: 40,
  height: 24,
  cell_aspect: 0.5,
  contrast: 1.15,
  gamma: 1,
  mode: "shape",
  font: "default",
  autocontrast: true,
  invert: false,
};

const pairedControls = ["width", "contrast", "gamma", "cell_aspect"];

const state = {
  imageData: null,
  crop: null,
  dimensions: null,
  result: null,
  revision: 0,
  imageRevision: 0,
  shownImageRevision: -1,
  fileRevision: 0,
  loadingFile: false,
  timer: null,
  controller: null,
  cropStart: null,
  previousCrop: null,
};

function readOptions() {
  return {
    width: Number($("widthValue").value),
    height: $("autoHeight").checked ? null : Number($("height").value),
    cell_aspect: Number($("cell_aspectValue").value),
    contrast: Number($("contrastValue").value),
    gamma: Number($("gammaValue").value),
    mode: $("mode").value,
    font: $("font").value,
    autocontrast: $("autocontrast").checked,
    invert: $("invert").checked,
    crop: state.crop,
  };
}

function setStatus(message, kind = "ready") {
  $("status").textContent = message;
  $("statusDot").classList.toggle("busy", kind === "busy");
  $("statusDot").classList.toggle("error", kind === "error");
}

function setExportsEnabled(enabled) {
  ["copy", "saveText", "savePng"].forEach((id) => {
    $(id).disabled = !enabled;
  });
}

function showError(message) {
  $("error").textContent = `error: ${message}`;
  $("error").hidden = false;
  setStatus("failed", "error");
  setExportsEnabled(false);
}

function clearError() {
  $("error").hidden = true;
  $("error").textContent = "";
}

function validateInputs() {
  const ids = [...pairedControls.map((id) => `${id}Value`), "height"];
  return ids.every((id) => $(id).disabled || $(id).checkValidity());
}

function scheduleUpdate() {
  state.revision += 1;
  window.clearTimeout(state.timer);
  state.controller?.abort();
  setExportsEnabled(false);
  $("previewBody").classList.add("stale");
  setStatus("rendering", "busy");
  state.timer = window.setTimeout(() => updatePreview(state.revision), LIMITS.updateDelayMs);
}

async function updatePreview(version) {
  if (state.loadingFile) return;
  if (!validateInputs()) {
    showError("one or more options are outside the allowed range");
    return;
  }

  state.controller = new AbortController();

  try {
    const response = await fetch("/api/convert", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: state.imageData, options: readOptions() }),
      signal: state.controller.signal,
    });

    const data = await response.json();
    if (version !== state.revision) return;
    if (!response.ok) throw new Error(data.error || "conversion failed");

    applyResult(data);
  } catch (error) {
    if (error.name !== "AbortError" && version === state.revision) {
      showError(error.message);
    }
  }
}

function applyResult(data) {
  state.result = data;
  state.dimensions = [data.imageWidth, data.imageHeight];

  if (state.shownImageRevision !== state.imageRevision) {
    $("source").src = data.source;
    state.shownImageRevision = state.imageRevision;
  }

  $("preview").src = data.preview;
  $("textPreview").textContent = data.art;
  configureTextPreview(data.fontFamily);

  $("previewBody").classList.toggle("dark", readOptions().invert);
  $("previewBody").classList.remove("stale");
  $("dimensions").textContent = `${data.imageWidth}×${data.imageHeight}px`;
  $("stats").textContent = `${data.columns} cols × ${data.rows} rows · ${data.elapsed} ms`;

  loadFontOptions(data.fonts);
  drawCrop();
  clearError();
  setExportsEnabled(true);
  setStatus("ready");
}

function configureTextPreview(fontFamily) {
  const family = `${JSON.stringify(fontFamily || "Consolas")}, monospace`;
  $("textPreview").style.fontFamily = family;

  const context = document.createElement("canvas").getContext("2d");
  context.font = `13px ${family}`;
  const lineHeight = context.measureText("M").width / readOptions().cell_aspect;
  $("textPreview").style.lineHeight = `${lineHeight}px`;
}

function loadFontOptions(fonts) {
  if ($("font").options.length > 1) return;
  fonts
    .filter((font) => font !== "default")
    .forEach((font) => $("font").add(new Option(font, font)));
}

function syncPairedControl(id, source) {
  const range = $(id);
  const number = $(`${id}Value`);
  const value = source === "range" ? range.value : number.value;
  range.value = value;
  number.value = value;

  const precision = id === "width" ? 0 : 2;
  $(`${id}Output`).textContent = Number(value).toFixed(precision);
  scheduleUpdate();
}

function drawCrop() {
  const active = Boolean(state.crop && state.dimensions);
  $("cropControls").hidden = !active;
  $("cropBox").style.display = active ? "block" : "none";
  if (!active) return;

  const [left, top, right, bottom] = state.crop;
  const [width, height] = state.dimensions;
  Object.assign($("cropBox").style, {
    left: `${(left / width) * 100}%`,
    top: `${(top / height) * 100}%`,
    width: `${((right - left) / width) * 100}%`,
    height: `${((bottom - top) / height) * 100}%`,
  });

  ["left", "top", "right", "bottom"].forEach((id, index) => {
    $(id).value = state.crop[index];
  });
}

function pointerToImage(event) {
  const rect = $("sourceWrap").getBoundingClientRect();
  const [imageWidth, imageHeight] = state.dimensions;
  const x = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
  const y = Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height));
  return [Math.round(x * imageWidth), Math.round(y * imageHeight)];
}

function startCrop(event) {
  if (!state.dimensions || state.loadingFile) return;
  state.previousCrop = state.crop;
  state.cropStart = pointerToImage(event);
  $("sourceWrap").setPointerCapture(event.pointerId);
}

function moveCrop(event) {
  if (!state.cropStart) return;
  const end = pointerToImage(event);
  state.crop = [
    Math.min(state.cropStart[0], end[0]),
    Math.min(state.cropStart[1], end[1]),
    Math.max(state.cropStart[0], end[0]),
    Math.max(state.cropStart[1], end[1]),
  ];
  drawCrop();
}

function finishCrop() {
  if (!state.cropStart) return;
  state.cropStart = null;

  if (!state.crop || state.crop[2] - state.crop[0] < 3 || state.crop[3] - state.crop[1] < 3) {
    state.crop = state.previousCrop;
  }

  drawCrop();
  scheduleUpdate();
}

function cancelCrop() {
  state.cropStart = null;
  state.crop = state.previousCrop;
  drawCrop();
}

async function loadFile(file) {
  if (!file) return;

  state.revision += 1;
  const ticket = ++state.fileRevision;
  window.clearTimeout(state.timer);
  state.controller?.abort();
  setExportsEnabled(false);
  $("previewBody").classList.add("stale");

  if (file.size > LIMITS.maxUploadBytes) {
    showError("image must be smaller than 14 MB");
    return;
  }

  state.loadingFile = true;
  setStatus("reading file", "busy");

  try {
    const data = await readAsDataUrl(file);
    if (ticket !== state.fileRevision) return;

    state.imageData = data;
    state.crop = null;
    state.dimensions = null;
    state.imageRevision += 1;
    $("filename").textContent = file.name;
    drawCrop();
  } catch (error) {
    if (ticket === state.fileRevision) showError(error.message);
  } finally {
    if (ticket === state.fileRevision) state.loadingFile = false;
  }

  if (ticket === state.fileRevision) scheduleUpdate();
}

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error("file could not be read"));
    reader.readAsDataURL(file);
  });
}

function loadDemo() {
  state.fileRevision += 1;
  state.loadingFile = false;
  state.imageData = null;
  state.imageRevision += 1;
  state.crop = null;
  state.dimensions = null;
  $("filename").textContent = "behrad-input.jpg";
  drawCrop();
  scheduleUpdate();
}

function resetOptions() {
  pairedControls.forEach((id) => {
    const value = DEFAULTS[id];
    $(id).value = value;
    $(`${id}Value`).value = value;
    $(`${id}Output`).textContent = Number(value).toFixed(id === "width" ? 0 : 2);
  });

  $("height").value = DEFAULTS.height;
  $("autoHeight").checked = true;
  $("height").disabled = true;
  $("mode").value = DEFAULTS.mode;
  $("font").value = DEFAULTS.font;
  $("autocontrast").checked = DEFAULTS.autocontrast;
  $("invert").checked = DEFAULTS.invert;
  state.crop = null;
  drawCrop();
  scheduleUpdate();
}

function download(url, filename) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
}

function saveText() {
  if (!state.result) return;
  const url = URL.createObjectURL(new Blob([`${state.result.art}\n`], { type: "text/plain;charset=utf-8" }));
  download(url, `symbol-art-${state.result.columns}.txt`);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function savePng() {
  if (state.result) download(state.result.preview, `symbol-art-${state.result.columns}.png`);
}

async function copyText() {
  if (!state.result) return;
  try {
    await navigator.clipboard.writeText(state.result.art);
    setStatus("copied");
  } catch {
    showError("browser denied clipboard access; use .txt export instead");
  }
}

function setOutputMode(mode) {
  const textMode = mode === "text";
  $("preview").hidden = textMode;
  $("textPreview").hidden = !textMode;
  $("imageTab").classList.toggle("active", !textMode);
  $("textTab").classList.toggle("active", textMode);
  $("imageTab").setAttribute("aria-selected", String(!textMode));
  $("textTab").setAttribute("aria-selected", String(textMode));
}

function bindEvents() {
  pairedControls.forEach((id) => {
    $(id).addEventListener("input", () => syncPairedControl(id, "range"));
    $(`${id}Value`).addEventListener("input", () => syncPairedControl(id, "number"));
  });

  ["mode", "font", "autocontrast", "invert", "height"].forEach((id) => {
    $(id).addEventListener("input", scheduleUpdate);
  });

  $("autoHeight").addEventListener("change", () => {
    $("height").disabled = $("autoHeight").checked;
    scheduleUpdate();
  });

  ["left", "top", "right", "bottom"].forEach((id) => {
    $(id).addEventListener("input", () => {
      state.crop = ["left", "top", "right", "bottom"].map((field) => Number($(field).value));
      drawCrop();
      scheduleUpdate();
    });
  });

  $("clearCrop").addEventListener("click", () => {
    state.crop = null;
    drawCrop();
    scheduleUpdate();
  });

  $("sourceWrap").addEventListener("pointerdown", startCrop);
  $("sourceWrap").addEventListener("pointermove", moveCrop);
  $("sourceWrap").addEventListener("pointerup", finishCrop);
  $("sourceWrap").addEventListener("pointercancel", cancelCrop);

  $("upload").addEventListener("click", () => $("file").click());
  $("file").addEventListener("change", () => {
    loadFile($("file").files[0]);
    $("file").value = "";
  });
  $("demo").addEventListener("click", loadDemo);
  $("reset").addEventListener("click", resetOptions);

  $("imageTab").addEventListener("click", () => setOutputMode("image"));
  $("textTab").addEventListener("click", () => setOutputMode("text"));
  $("copy").addEventListener("click", copyText);
  $("saveText").addEventListener("click", saveText);
  $("savePng").addEventListener("click", savePng);

  document.addEventListener("dragover", (event) => {
    event.preventDefault();
    $("dropzone").classList.add("drop-active");
  });

  document.addEventListener("dragleave", (event) => {
    if (!event.relatedTarget) $("dropzone").classList.remove("drop-active");
  });

  document.addEventListener("drop", (event) => {
    event.preventDefault();
    $("dropzone").classList.remove("drop-active");
    loadFile(event.dataTransfer.files[0]);
  });
}

bindEvents();
scheduleUpdate();
