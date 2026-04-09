
try {
  localStorage.removeItem("crop_vision_history_v2");
} catch {
  // ignore old storage cleanup
}

const refs = {
  serviceStatus: document.getElementById("serviceStatus"),
  serviceNote: document.getElementById("serviceNote"),
  statusTimeline: document.getElementById("statusTimeline"),
  statusNodes: Array.from(document.querySelectorAll(".status-node")),
  modelName: document.getElementById("modelName"),
  knowledgeCount: document.getElementById("knowledgeCount"),
  sampleCount: document.getElementById("sampleCount"),
  imageSize: document.getElementById("imageSize"),
  deviceName: document.getElementById("deviceName"),
  avgLatency: document.getElementById("avgLatency"),
  sessionCount: document.getElementById("sessionCount"),
  batchDoneCount: document.getElementById("batchDoneCount"),
  modelSelect: document.getElementById("modelSelect"),
  loadModelBtn: document.getElementById("loadModelBtn"),
  imageInput: document.getElementById("imageInput"),
  batchInput: document.getElementById("batchInput"),
  uploadZone: document.getElementById("uploadZone"),
  uploadCopy: document.getElementById("uploadCopy"),
  previewImage: document.getElementById("previewImage"),
  predictBtn: document.getElementById("predictBtn"),
  resetBtn: document.getElementById("resetBtn"),
  runBatchBtn: document.getElementById("runBatchBtn"),
  exportBatchBtn: document.getElementById("exportBatchBtn"),
  actionMessage: document.getElementById("actionMessage"),
  sampleGallery: document.getElementById("sampleGallery"),
  batchQueue: document.getElementById("batchQueue"),
  batchSummary: document.getElementById("batchSummary"),
  latestFile: document.getElementById("latestFile"),
  predictionTimestamp: document.getElementById("predictionTimestamp"),
  candidateHint: document.getElementById("candidateHint"),
  resultOverview: document.getElementById("resultOverview"),
  candidateList: document.getElementById("candidateList"),
  detailSummary: document.getElementById("detailSummary"),
  strategyStatus: document.getElementById("strategyStatus"),
  strategyHint: document.getElementById("strategyHint"),
  strategyPanel: document.getElementById("strategyPanel"),
  strategySources: document.getElementById("strategySources"),
  strategyChat: document.getElementById("strategyChat"),
  strategyQuestion: document.getElementById("strategyQuestion"),
  sendStrategyBtn: document.getElementById("sendStrategyBtn"),
  chatHint: document.getElementById("chatHint"),
  stageImage: document.getElementById("stageImage"),
  visionEmpty: document.getElementById("visionEmpty"),
  stepCards: Array.from(document.querySelectorAll(".step-card")),
  sessionDiagnoses: document.getElementById("sessionDiagnoses"),
  highRiskShare: document.getElementById("highRiskShare"),
  batchProgressText: document.getElementById("batchProgressText"),
  labelChart: document.getElementById("labelChart"),
  riskChart: document.getElementById("riskChart"),
  batchProgress: document.getElementById("batchProgress"),
  modelBackbone: document.getElementById("modelBackbone"),
  modelParams: document.getElementById("modelParams"),
  modelMetric: document.getElementById("modelMetric"),
  modelDropPath: document.getElementById("modelDropPath"),
  runtimeLatency: document.getElementById("runtimeLatency"),
  runtimeStrategy: document.getElementById("runtimeStrategy"),
  runtimeBatch: document.getElementById("runtimeBatch"),
  dashboard: document.getElementById("dashboard"),
  centerColumn: document.getElementById("centerColumn"),
  insightColumn: document.getElementById("insightColumn"),
  scanOverlay: document.getElementById("scanOverlay"),
  scanText: document.getElementById("scanText"),
  pagePanels: Array.from(document.querySelectorAll("[data-page-group]")),
  workspaceButtons: Array.from(document.querySelectorAll(".workspace-btn[data-page]")),
  presentationToggle: document.getElementById("presentationToggle"),
  vizShowcase: document.getElementById("vizShowcase"),
  riskGaugeNeedle: document.getElementById("riskGaugeNeedle"),
  riskGaugeValue: document.getElementById("riskGaugeValue"),
  riskGaugeLabel: document.getElementById("riskGaugeLabel"),
  radarSvg: document.getElementById("radarSvg"),
  radarLegend: document.getElementById("radarLegend"),
};

const state = {
  models: [],
  sampleImages: [],
  currentModel: null,
  strategyAvailable: false,
  strategyStatusReason: "",
  selectedFile: null,
  selectedSampleName: "",
  previewUrl: "",
  latestPrediction: null,
  latestStrategy: null,
  currentStrategyName: "",
  strategyChat: [],
  sessionRecords: [],
  latencySamples: [],
  batchQueue: [],
  batchRunning: false,
  currentPage: "overview",
  presentationMode: false,
  systemStage: "model",
};

const SAMPLE_GALLERY_LIMIT = 4;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatTimestamp(value) {
  try {
    return new Date(value).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return String(value || "-");
  }
}

function formatDuration(ms) {
  if (!Number.isFinite(ms) || ms <= 0) return "-";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function formatPercent(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`;
}

function formatCount(value) {
  if (!Number.isFinite(value)) return "-";
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)} 亿`;
  if (value >= 10000) return `${(value / 10000).toFixed(2)} 万`;
  return `${value}`;
}


function getBatchStats() {
  const total = state.batchQueue.length;
  const done = state.batchQueue.filter((item) => item.status === "done").length;
  const failed = state.batchQueue.filter((item) => item.status === "失败").length;
  const running = state.batchQueue.filter((item) => item.status === "识别中").length;
  const finished = done + failed;
  const pending = Math.max(total - finished, 0);
  const progress = total ? finished / total : 0;
  return { total, done, failed, running, pending, finished, progress };
}

function estimateBatchEta(stats) {
  if (!state.batchRunning || !stats.pending) return "-";
  const latencies = state.batchQueue
    .filter((item) => item.status === "done" && Number.isFinite(item.latencyMs) && item.latencyMs > 0)
    .map((item) => item.latencyMs);
  if (!latencies.length) return "计算中";
  const avg = latencies.reduce((sum, value) => sum + value, 0) / latencies.length;
  return formatDuration(avg * stats.pending);
}

function getBatchStatusMeta(status) {
  if (status === "done") return { label: "已完成", tone: "done", icon: "✓" };
  if (status === "识别中") return { label: "识别中", tone: "running", icon: "…" };
  if (status === "失败") return { label: "失败", tone: "failed", icon: "!" };
  return { label: "待识别", tone: "pending", icon: "○" };
}

function riskClass(tone) {
  if (tone === "high") return "badge-high";
  if (tone === "medium") return "badge-medium";
  return "badge-low";
}

function localizeRiskLevel(tone) {
  if (tone === "high") return "高可信";
  if (tone === "medium") return "需复核";
  return "低确定性";
}

function localizeRiskDescription(tone) {
  if (tone === "high") return "建议优先按该结果进行人工复核。";
  if (tone === "medium") return "建议结合田间症状与环境信息交叉确认。";
  return "当前结果分散，建议查看更多候选并补充样本。";
}

function buildAnalysisSummary(primary, filename) {
  const name = primary.readable_name;
  const confidence = Number(primary.confidence || 0);
  if (confidence >= 0.88) {
    return `模型高度怀疑该图像表现为“${name}”。当前样本文件为“${filename}”，建议优先围绕该结果做人工复核。`;
  }
  if (confidence >= 0.68) {
    return `模型初步判断该图像更接近“${name}”。当前结果具备参考价值，但仍建议结合田间症状进一步确认。`;
  }
  return `模型暂未形成非常稳定的判断，当前更偏向“${name}”。建议同时查看其他候选结果，谨慎下结论。`;
}

function buildNextActions() {
  return [
    "优先复核图像中最明显的病斑、虫咬痕迹或霉层区域。",
    "对照 Top-5 候选结果，确认是否存在相似病征或虫害混淆。",
    "需要处理建议时，可在右侧策略工作台继续追问。",
  ];
}

function normalizeDatasetLabel(rawLabel, originalLabel) {
  const source = String(originalLabel || "").toLowerCase();
  if (source.startsWith("ip102_")) return "IP102";
  if (source.includes("plantvillage")) return "PlantVillage";
  if (source.includes("plantdoc")) return "PlantDoc";
  const cleaned = String(rawLabel || "").trim();
  if (!cleaned) return "模型标签集";
  if (cleaned.includes("鏄") || cleaned.includes("櫕") || cleaned.includes("锛")) return "模型标签集";
  return cleaned;
}

function setMessage(message, isError = false) {
  refs.actionMessage.textContent = message;
  refs.actionMessage.classList.toggle("error-text", isError);
}

function setStatusBadge(text, isError = false) {
  refs.serviceStatus.textContent = text;
  refs.serviceStatus.classList.toggle("is-error", isError);
}

function setInfoPill(element, text, tone = "muted") {
  element.textContent = text;
  element.classList.remove("info-pill-muted", "info-pill-error", "info-pill-success");
  if (tone === "error") {
    element.classList.add("info-pill-error");
    return;
  }
  if (tone === "success") {
    element.classList.add("info-pill-success");
    return;
  }
  element.classList.add("info-pill-muted");
}

function setLoading(button, loading) {
  if (!button) return;
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.classList.toggle("is-loading", loading);
  if (loading) {
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label;
  }
}

function syncButtons() {
  refs.loadModelBtn.disabled = state.models.length === 0;
  refs.predictBtn.disabled = !(state.currentModel?.loaded && state.selectedFile);
  refs.resetBtn.disabled = !state.selectedFile;
  refs.runBatchBtn.disabled = !(state.currentModel?.loaded && state.batchQueue.length && !state.batchRunning);
  refs.exportBatchBtn.disabled = !state.batchQueue.some((item) => item.status === "done");
  refs.strategyQuestion.disabled = !(state.latestStrategy && state.strategyAvailable);
  refs.sendStrategyBtn.disabled = !(state.latestStrategy && state.strategyAvailable && refs.strategyQuestion.value.trim());
}


function setScanning(active, text = "AI 正在分析图像特征...") {
  if (!refs.scanOverlay || !refs.scanText) return;
  refs.scanText.textContent = text;
  refs.scanOverlay.hidden = !active;
}

function setSystemTimeline(stage) {
  const order = ["model", "inference", "strategy", "batch"];
  const target = order.includes(stage) ? stage : "model";
  state.systemStage = target;
  if (!refs.statusNodes?.length) return;
  const activeIndex = order.indexOf(target);
  refs.statusNodes.forEach((node) => {
    const nodeStage = node.dataset.stage || "";
    const nodeIndex = order.indexOf(nodeStage);
    node.classList.toggle("is-active", nodeIndex === activeIndex);
    node.classList.toggle("is-done", nodeIndex > -1 && nodeIndex < activeIndex);
  });
}

function animateVisiblePanels() {
  const panels = Array.from(document.querySelectorAll(".dashboard .panel:not([hidden])"));
  panels.forEach((panel) => {
    panel.classList.remove("page-enter");
    void panel.offsetWidth;
    panel.classList.add("page-enter");
  });
}

function applyRevealStagger(root, selector) {
  if (!root) return;
  const items = Array.from(root.querySelectorAll(selector));
  items.forEach((item, index) => {
    item.style.setProperty("--reveal-delay", `${Math.min(index * 45, 320)}ms`);
    item.classList.remove("reveal-enter");
    void item.offsetWidth;
    item.classList.add("reveal-enter");
  });
}

function animateNumericText(element, nextValue, formatter) {
  if (!element) return;
  const target = Number(nextValue);
  const formatFn = typeof formatter === "function" ? formatter : (value) => `${Math.round(value)}`;
  if (!Number.isFinite(target)) {
    element.textContent = String(nextValue ?? "-");
    return;
  }

  const current = Number(element.dataset.numericValue || 0);
  if (!Number.isFinite(current) || Math.abs(target - current) < 0.001) {
    element.dataset.numericValue = `${target}`;
    element.textContent = formatFn(target);
    return;
  }

  const startedAt = performance.now();
  const duration = 380;
  const delta = target - current;

  const tick = (now) => {
    const ratio = Math.min((now - startedAt) / duration, 1);
    const eased = 1 - Math.pow(1 - ratio, 3);
    const value = current + (delta * eased);
    element.textContent = formatFn(value);
    if (ratio < 1) {
      requestAnimationFrame(tick);
      return;
    }
    element.dataset.numericValue = `${target}`;
    element.textContent = formatFn(target);
  };

  requestAnimationFrame(tick);
}
function setWorkspacePage(page) {
  const target = ["overview", "diagnosis", "strategy", "analytics", "system"].includes(page) ? page : "overview";
  const showDiagnosis = target === "overview" || target === "diagnosis";
  const showStrategy = target === "overview" || target === "strategy";
  const showAnalytics = target === "overview" || target === "analytics";
  const showSystem = target === "overview" || target === "system";

  refs.pagePanels.forEach((panel) => {
    const group = panel.dataset.pageGroup;
    const shouldShow = (group === "diagnosis" && showDiagnosis)
      || (group === "strategy" && showStrategy)
      || (group === "analytics" && showAnalytics)
      || (group === "system" && showSystem);

    if (shouldShow && panel.hidden) {
      panel.hidden = false;
      panel.classList.remove("page-enter");
      void panel.offsetWidth;
      panel.classList.add("page-enter");
      return;
    }

    panel.hidden = !shouldShow;
  });

  if (refs.centerColumn) refs.centerColumn.hidden = !showDiagnosis;
  if (refs.insightColumn) refs.insightColumn.hidden = !(showStrategy || showAnalytics || showSystem);

  if (refs.dashboard) {
    refs.dashboard.classList.toggle("mode-two", target !== "overview");
  }

  refs.workspaceButtons.forEach((button) => {
    button.classList.toggle("is-active", (button.dataset.page || "overview") === target);
  });

  state.currentPage = target;
  animateVisiblePanels();
}
function toneToGaugeAngle(tone) {
  if (tone === "high") return 70;
  if (tone === "medium") return 0;
  return -70;
}

function clearVisualShowcase() {
  if (refs.riskGaugeNeedle) refs.riskGaugeNeedle.style.transform = "translateX(-50%) rotate(-70deg)";
  if (refs.riskGaugeValue) refs.riskGaugeValue.textContent = "--";
  if (refs.riskGaugeLabel) refs.riskGaugeLabel.textContent = "等待识别结果";
  if (refs.radarSvg) refs.radarSvg.innerHTML = "";
  if (refs.radarLegend) refs.radarLegend.textContent = "等待识别结果...";
}

function polarPoint(cx, cy, radius, angleDeg) {
  const rad = (angleDeg * Math.PI) / 180;
  return {
    x: cx + radius * Math.cos(rad),
    y: cy + radius * Math.sin(rad),
  };
}

function renderRadar(results) {
  if (!refs.radarSvg) return;
  const svg = refs.radarSvg;
  const cx = 160;
  const cy = 136;
  const maxR = 92;
  const axes = 5;
  const data = (results || []).slice(0, axes);

  const rings = [0.25, 0.5, 0.75, 1];
  const axisLines = [];
  const ringPolys = [];
  for (const ring of rings) {
    const points = [];
    for (let i = 0; i < axes; i += 1) {
      const angle = -90 + (360 / axes) * i;
      const p = polarPoint(cx, cy, maxR * ring, angle);
      points.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`);
    }
    ringPolys.push(`<polygon points="${points.join(" ")}" fill="none" stroke="rgba(63,82,44,0.16)" stroke-width="1"/>`);
  }

  for (let i = 0; i < axes; i += 1) {
    const angle = -90 + (360 / axes) * i;
    const p = polarPoint(cx, cy, maxR, angle);
    axisLines.push(`<line x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" stroke="rgba(63,82,44,0.18)" stroke-width="1"/>`);
  }

  const dataPoints = [];
  for (let i = 0; i < axes; i += 1) {
    const angle = -90 + (360 / axes) * i;
    const score = Math.max(0, Math.min(1, Number(data[i]?.confidence || 0)));
    const p = polarPoint(cx, cy, maxR * score, angle);
    dataPoints.push(`${p.x.toFixed(1)},${p.y.toFixed(1)}`);
  }

  const labels = [];
  for (let i = 0; i < axes; i += 1) {
    const angle = -90 + (360 / axes) * i;
    const p = polarPoint(cx, cy, maxR + 16, angle);
    const label = (data[i]?.readable_name || `Top-${i + 1}`).slice(0, 14);
    labels.push(`<text x="${p.x.toFixed(1)}" y="${p.y.toFixed(1)}" font-size="11" fill="rgba(32,48,25,0.76)" text-anchor="middle">${escapeHtml(label)}</text>`);
  }

  svg.innerHTML = [
    `<defs><linearGradient id="radarFill" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="rgba(47,125,81,0.38)"/><stop offset="100%" stop-color="rgba(191,122,42,0.22)"/></linearGradient></defs>`,
    ...ringPolys,
    ...axisLines,
    `<polygon points="${dataPoints.join(" ")}" fill="url(#radarFill)" stroke="rgba(47,125,81,0.86)" stroke-width="2"/>`,
    ...labels,
  ].join("");

  if (refs.radarLegend) {
    refs.radarLegend.innerHTML = data
      .map((item, idx) => `<div class="radar-legend-item"><span>${idx + 1}. ${escapeHtml(item.readable_name)}</span><strong>${escapeHtml(item.confidence_text)}</strong></div>`)
      .join("");
  }
}

function renderVisualShowcase(results) {
  const top = (results || [])[0];
  if (!top) {
    clearVisualShowcase();
    return;
  }
  if (refs.riskGaugeNeedle) {
    const angle = toneToGaugeAngle(top.risk_tone);
    refs.riskGaugeNeedle.style.transform = `translateX(-50%) rotate(${angle}deg)`;
  }
  if (refs.riskGaugeValue) refs.riskGaugeValue.textContent = `${top.confidence_text} - ${localizeRiskLevel(top.risk_tone)}`;
  if (refs.riskGaugeLabel) refs.riskGaugeLabel.textContent = top.readable_name;
  renderRadar(results);
}

function setPresentationMode(enabled) {
  state.presentationMode = Boolean(enabled);
  document.body.classList.toggle("presentation-mode", state.presentationMode);
  if (refs.presentationToggle) {
    refs.presentationToggle.classList.toggle("is-active", state.presentationMode);
    refs.presentationToggle.textContent = state.presentationMode ? "演示模式中" : "演示模式";
  }
}

function renderSteps() {
  const modelLoaded = Boolean(state.currentModel?.loaded);
  const imageReady = Boolean(state.selectedFile || state.batchQueue.length);
  const diagnosisReady = Boolean(state.latestPrediction || state.batchQueue.some((item) => item.status === "done"));
  refs.stepCards.forEach((card) => {
    const step = card.dataset.step;
    card.classList.remove("is-current", "is-done");
    if (step === "model") {
      card.classList.add(modelLoaded ? "is-done" : "is-current");
      return;
    }
    if (step === "image") {
      if (modelLoaded) card.classList.add(imageReady ? "is-done" : "is-current");
      return;
    }
    if (imageReady) card.classList.add(diagnosisReady ? "is-done" : "is-current");
  });
}
function updateModelMeta(model, sampleCount = state.sampleImages.length) {
  const loaded = Boolean(model?.loaded);
  refs.modelName.textContent = loaded ? model.model_name || "未知" : "未加载";
  refs.knowledgeCount.textContent = loaded ? model.knowledge_base_count ?? "-" : "-";
  refs.sampleCount.textContent = sampleCount ?? "-";
  refs.imageSize.textContent = loaded ? model.image_size || "-" : "-";
  refs.deviceName.textContent = model?.device || "-";
  refs.modelBackbone.textContent = loaded ? model.backbone || model.model_name || "未知" : "-";
  refs.modelParams.textContent = loaded ? formatCount(model.parameter_count || 0) : "-";
  refs.modelMetric.textContent = loaded ? model.metric_summary || "未提供评估指标" : "-";
  refs.modelDropPath.textContent = loaded ? `${model.drop_path_rate ?? "-"}` : "-";
}

function updateSessionMeta() {
  const latencyAvg = state.latencySamples.length
    ? state.latencySamples.reduce((sum, value) => sum + value, 0) / state.latencySamples.length
    : 0;
  const doneBatchCount = state.batchQueue.filter((item) => item.status === "done").length;
  const highCount = state.sessionRecords.filter((item) => item.riskTone === "high").length;
  const highShare = state.sessionRecords.length ? highCount / state.sessionRecords.length : 0;

  refs.avgLatency.textContent = formatDuration(latencyAvg);
  animateNumericText(refs.sessionCount, state.sessionRecords.length, (value) => `${Math.round(value)}`);
  animateNumericText(refs.batchDoneCount, doneBatchCount, (value) => `${Math.round(value)}`);
  animateNumericText(refs.sessionDiagnoses, state.sessionRecords.length, (value) => `${Math.round(value)}`);
  animateNumericText(refs.highRiskShare, highShare, (value) => formatPercent(value));
  animateNumericText(refs.batchProgressText, state.batchQueue.length ? (doneBatchCount / state.batchQueue.length) : 0, (value) => formatPercent(value));

  refs.runtimeLatency.textContent = formatDuration(latencyAvg);
  refs.runtimeStrategy.textContent = state.strategyAvailable ? "可用" : "不可用";
  animateNumericText(refs.runtimeBatch, state.batchQueue.length, (value) => `${Math.round(value)}`);
}
function renderModelSelect(models, currentPath = "") {
  refs.modelSelect.innerHTML = "";
  if (!models.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "未发现模型文件";
    refs.modelSelect.appendChild(option);
    return;
  }
  models.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.path;
    option.textContent = model.name;
    if (currentPath && currentPath === model.path) option.selected = true;
    refs.modelSelect.appendChild(option);
  });
}

function renderSampleGallery() {
  if (!state.sampleImages.length) {
    refs.sampleGallery.className = "sample-gallery empty-state";
    refs.sampleGallery.textContent = "当前 sample_images 目录下没有可用图片。";
    return;
  }
  const gallerySamples = state.sampleImages.slice(0, SAMPLE_GALLERY_LIMIT);
  refs.sampleGallery.className = "sample-gallery";
  refs.sampleGallery.innerHTML = gallerySamples
    .map((sample) => {
      const activeClass = state.selectedSampleName === sample.name ? " is-active" : "";
      return `
        <button class="sample-card${activeClass}" data-name="${encodeURIComponent(sample.name)}" type="button">
          <img src="${sample.url}" alt="${escapeHtml(sample.name)}" />
          <span>${escapeHtml(sample.name)}</span>
        </button>
      `;
    })
    .join("");
  refs.sampleGallery.querySelectorAll(".sample-card").forEach((button) => {
    button.addEventListener("click", async () => {
      const name = decodeURIComponent(button.dataset.name || "");
      const sample = gallerySamples.find((item) => item.name === name);
      if (sample) await useSample(sample);
    });
  });
}


function renderVisionStage() {
  const hasImage = Boolean(state.previewUrl);
  refs.stageImage.hidden = !hasImage;
  refs.visionEmpty.hidden = hasImage;
  if (refs.scanOverlay) refs.scanOverlay.hidden = true;
  if (!hasImage) {
    refs.visionEmpty.textContent = "上传一张样本图片后，这里会进入诊断舞台。";
    return;
  }
  refs.stageImage.src = state.previewUrl;
}

function resetStrategyView(message) {
  refs.strategySources.innerHTML = "";
  refs.strategyPanel.className = "strategy-panel empty-detail";
  state.latestStrategy = null;
  state.currentStrategyName = "";
  state.strategyChat = [];
  refs.strategyQuestion.value = "";
  if (!state.strategyAvailable) {
    setInfoPill(refs.strategyStatus, "未启用", "error");
    refs.strategyHint.textContent = "资料整理当前不可用";
    refs.strategyPanel.textContent = state.strategyStatusReason || "当前环境未启用策略资料服务。";
    refs.strategyChat.className = "chat-thread empty-detail";
    refs.strategyChat.textContent = "当前无法开启策略追问。";
    refs.chatHint.textContent = "等待策略服务可用";
    syncButtons();
    return;
  }
  setInfoPill(refs.strategyStatus, "尚未查询", "muted");
  refs.strategyHint.textContent = "点击候选卡片按钮整理资料";
  refs.strategyPanel.textContent = message || "当前未加载策略内容。";
  refs.strategyChat.className = "chat-thread empty-detail";
  refs.strategyChat.textContent = "先完成一次策略查询，再继续追问。";
  refs.chatHint.textContent = "可继续追问剂量、安全性或雨后调整";
  syncButtons();
}

function clearDiagnosisViews(message = "上传样本后，这里会展示诊断主结论、风险等级和下一步建议。") {
  state.latestPrediction = null;
  refs.resultOverview.className = "result-overview empty-overview";
  refs.resultOverview.textContent = message;
  refs.candidateList.className = "candidate-list empty-state";
  refs.candidateList.textContent = "完成识别后，这里会出现候选结果卡片。";
  refs.detailSummary.className = "detail-summary empty-detail";
  refs.detailSummary.textContent = "等待识别结果。";
  refs.predictionTimestamp.textContent = "等待推理";
  refs.candidateHint.textContent = "识别完成后可点击候选卡片整理资料";
  resetStrategyView();
  clearVisualShowcase();
  renderSteps();
  syncButtons();
}
function setPreview(file) {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = URL.createObjectURL(file);
  refs.previewImage.src = state.previewUrl;
  refs.previewImage.hidden = false;
  refs.uploadCopy.hidden = true;
  refs.uploadZone.classList.add("has-preview");
  renderVisionStage();
}

function selectFile(file, sampleName = "") {
  state.selectedFile = file;
  state.selectedSampleName = sampleName;
  setPreview(file);
  refs.latestFile.textContent = file.name;
  clearDiagnosisViews();
  renderSampleGallery();
  renderSteps();
  syncButtons();
  setMessage(`已选择样本：${file.name}`);
}

function resetCurrentSample() {
  if (state.previewUrl) URL.revokeObjectURL(state.previewUrl);
  state.previewUrl = "";
  state.selectedFile = null;
  state.selectedSampleName = "";
  refs.previewImage.hidden = true;
  refs.previewImage.removeAttribute("src");
  refs.uploadCopy.hidden = false;
  refs.uploadZone.classList.remove("has-preview");
  refs.latestFile.textContent = "未选择图片";
  refs.imageInput.value = "";
  clearDiagnosisViews();
  renderSampleGallery();
  renderVisionStage();
  syncButtons();
  setMessage("已清空当前样本。请重新选择图片。");
}

function renderOverview(prediction, latencyMs = 0) {
  const primary = prediction.primary_result;
  if (!primary) {
    refs.resultOverview.className = "result-overview empty-overview";
    refs.resultOverview.textContent = "未生成诊断总览。";
    return;
  }
  const nextActions = buildNextActions();
  const summary = buildAnalysisSummary(primary, prediction.filename);
  const riskLevel = localizeRiskLevel(primary.risk_tone);
  const riskDescription = localizeRiskDescription(primary.risk_tone);
  refs.resultOverview.className = "result-overview";
  refs.resultOverview.innerHTML = `
    <article class="overview-card">
      <div class="overview-top">
        <div>
          <div class="badge-row">
            <span class="badge ${riskClass(primary.risk_tone)}">${escapeHtml(riskLevel)}</span>
            <span class="info-pill">主结果置信度 ${escapeHtml(primary.confidence_text)}</span>
          </div>
          <h3 class="overview-title">${escapeHtml(primary.readable_name)}</h3>
          <p class="overview-summary">${escapeHtml(summary)}</p>
        </div>
        <div class="meta-row">
          <span class="info-pill">Top-1</span>
          <span class="info-pill">耗时 ${escapeHtml(formatDuration(latencyMs))}</span>
        </div>
      </div>
      <div class="overview-grid">
        <div class="overview-metric"><span>数据来源</span><strong>${escapeHtml(normalizeDatasetLabel(primary.dataset, primary.original_label))}</strong></div>
        <div class="overview-metric"><span>标签编号</span><strong>${escapeHtml(primary.original_label)}</strong></div>
        <div class="overview-metric"><span>复核建议</span><strong>${escapeHtml(riskDescription)}</strong></div>
      </div>
      <ul class="guidance-list">${nextActions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    </article>
  `;
  applyRevealStagger(refs.resultOverview, ".overview-card, .overview-metric, .guidance-list li");
}
function renderCandidates(results) {
  if (!results.length) {
    refs.candidateList.className = "candidate-list empty-state";
    refs.candidateList.textContent = "暂无候选结果。";
    return;
  }
  refs.candidateList.className = "candidate-list";
  refs.candidateList.innerHTML = results
    .map((item) => {
      const disabled = state.strategyAvailable ? "" : "disabled";
      const buttonText = state.strategyAvailable ? "获取防治策略" : "未启用资料整理";
      const topClass = item.rank === 1 ? " is-top" : "";
      return `
        <article class="candidate-card${topClass}">
          <div class="candidate-head">
            <div>
              <div class="badge-row"><span class="badge ${riskClass(item.risk_tone)}">${escapeHtml(localizeRiskLevel(item.risk_tone))}</span></div>
              <h4 class="candidate-name">${escapeHtml(item.readable_name)}</h4>
              <p class="candidate-meta">${escapeHtml(normalizeDatasetLabel(item.dataset, item.original_label))} · ${escapeHtml(item.original_label)}</p>
            </div>
            <div class="candidate-rank">#${item.rank}</div>
          </div>
          <div class="confidence-row">
            <strong>置信度 ${escapeHtml(item.confidence_text)}</strong>
            <div class="progress-track"><div class="progress-bar" style="width:${Math.max(item.confidence * 100, 3)}%"></div></div>
          </div>
          <p class="candidate-note">建议优先核查“${escapeHtml(item.readable_name)}”相关的典型症状部位。</p>
          <div class="candidate-actions">
            <span class="candidate-hint">${escapeHtml(localizeRiskDescription(item.risk_tone))}</span>
            <button class="strategy-btn" type="button" data-name="${encodeURIComponent(item.readable_name)}" ${disabled}>${buttonText}</button>
          </div>
        </article>
      `;
    })
    .join("");
  refs.candidateList.querySelectorAll(".strategy-btn").forEach((button) => {
    button.addEventListener("click", async (event) => {
      const name = decodeURIComponent(event.currentTarget.dataset.name || "");
      await fetchStrategy(name, event.currentTarget);
    });
  });
  applyRevealStagger(refs.candidateList, ".candidate-card");
}
function renderDetailSummary(prediction, latencyMs = 0) {
  const primary = prediction.primary_result;
  if (!primary) {
    refs.detailSummary.className = "detail-summary empty-detail";
    refs.detailSummary.textContent = "暂无诊断细节。";
    return;
  }
  const nextActions = buildNextActions();
  const summary = buildAnalysisSummary(primary, prediction.filename);
  refs.detailSummary.className = "detail-summary";
  refs.detailSummary.innerHTML = `
    <article class="detail-card"><h3>诊断主结论: ${escapeHtml(primary.readable_name)}</h3><p>${escapeHtml(summary)}</p></article>
    <article class="detail-card"><h3>工程指标</h3><p>本次推理耗时 ${escapeHtml(formatDuration(latencyMs))}，当前设备 ${escapeHtml(state.currentModel?.device || "-")}，策略服务 ${escapeHtml(state.strategyAvailable ? "可用" : "不可用")}。</p></article>
    <article class="detail-card"><h3>建议的人工复核动作</h3><ul>${nextActions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></article>
  `;
  applyRevealStagger(refs.detailSummary, ".detail-card");
}
function renderStrategy(data) {
  const items = data.items || [];
  if (!items.length) {
    refs.strategyPanel.className = "strategy-panel empty-detail";
    refs.strategyPanel.textContent = "暂未查询到明确策略，建议改用学名、别名或人工检索继续确认。";
    refs.strategySources.innerHTML = "";
    return;
  }
  refs.strategyPanel.className = "strategy-panel";
  refs.strategyPanel.innerHTML = items
    .map((item, index) => `
      <details class="accordion-card" ${index === 0 ? "open" : ""}>
        <summary>
          <div class="accordion-title-row">
            <h4 class="accordion-title">${escapeHtml(item.title || `资料重点 ${index + 1}`)}</h4>
            <span class="accordion-meta">点击展开</span>
          </div>
        </summary>
        <p>${escapeHtml(item.content || "暂无摘要内容。")}</p>
        ${item.url ? `<a class="strategy-link" href="${item.url}" target="_blank" rel="noreferrer">打开来源</a>` : ""}
      </details>
    `)
    .join("");
  refs.strategySources.innerHTML = (data.sources || [])
    .map((source) => `
      <div class="source-item">
        <span>${escapeHtml(source.title)}</span>
        ${source.url ? `<a href="${source.url}" target="_blank" rel="noreferrer">来源链接</a>` : "<span>无链接</span>"}
      </div>
    `)
    .join("");

  applyRevealStagger(refs.strategyPanel, ".accordion-card");
  applyRevealStagger(refs.strategySources, ".source-item");
}
function renderChatThread() {
  if (!state.strategyChat.length) {
    refs.strategyChat.className = "chat-thread empty-detail";
    refs.strategyChat.textContent = "先完成一次策略查询，再继续追问。";
    return;
  }
  refs.strategyChat.className = "chat-thread";
  refs.strategyChat.innerHTML = state.strategyChat
    .map((item) => `
      <article class="chat-bubble ${escapeHtml(item.role)}">
        <span class="chat-role">${item.role === "user" ? "用户追问" : "农技助手"}</span>
        <p>${escapeHtml(item.content)}</p>
      </article>
    `)
    .join("");
  refs.strategyChat.scrollTop = refs.strategyChat.scrollHeight;
}

function buildChartRows(entries, formatter) {
  return entries
    .map(({ label, value, ratio }) => `
      <article class="chart-row">
        <div class="chart-label-row"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(formatter(value, ratio))}</span></div>
        <div class="chart-bar-track"><div class="chart-bar-fill" style="width:${Math.max(Math.round(ratio * 100), value ? 4 : 0)}%"></div></div>
      </article>
    `)
    .join("");
}

function renderAnalytics() {
  updateSessionMeta();

  if (!state.sessionRecords.length) {
    refs.labelChart.className = "chart-list empty-state compact-empty";
    refs.labelChart.textContent = "会话内暂无诊断数据。";
    refs.riskChart.className = "chart-list empty-state compact-empty";
    refs.riskChart.textContent = "等待识别结果。";
  } else {
    const labelMap = new Map();
    const riskMap = new Map([["高可信", 0], ["需复核", 0], ["低确定性", 0]]);
    state.sessionRecords.forEach((item) => {
      labelMap.set(item.label, (labelMap.get(item.label) || 0) + 1);
      riskMap.set(item.riskLevel, (riskMap.get(item.riskLevel) || 0) + 1);
    });
    const total = state.sessionRecords.length;
    const labelEntries = Array.from(labelMap.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 6)
      .map(([label, value]) => ({ label, value, ratio: value / total }));
    const riskEntries = Array.from(riskMap.entries()).map(([label, value]) => ({ label, value, ratio: total ? value / total : 0 }));
    refs.labelChart.className = "chart-list";
    refs.labelChart.innerHTML = buildChartRows(labelEntries, (value, ratio) => `${value} 次 · ${formatPercent(ratio)}`);
    refs.riskChart.className = "chart-list";
    refs.riskChart.innerHTML = buildChartRows(riskEntries, (value, ratio) => `${value} 次 · ${formatPercent(ratio)}`);
    applyRevealStagger(refs.labelChart, ".chart-row");
    applyRevealStagger(refs.riskChart, ".chart-row");
  }

  if (!state.batchQueue.length) {
    refs.batchProgress.className = "progress-stack empty-state compact-empty";
    refs.batchProgress.textContent = "尚未建立批量任务。";
  } else {
    refs.batchProgress.className = "progress-stack";
    refs.batchProgress.innerHTML = state.batchQueue.slice(0, 6).map((item) => {
      const resultText = item.result?.primary_result?.readable_name || item.error || "等待识别";
      const statusMeta = getBatchStatusMeta(item.status);
      return `<article class="batch-result-card"><div class="batch-row"><strong>${escapeHtml(item.file.name)}</strong><span class="batch-status">${escapeHtml(statusMeta.label)}</span></div><p class="batch-meta">${escapeHtml(resultText)}</p></article>`;
    }).join("");
    applyRevealStagger(refs.batchProgress, ".batch-result-card");
  }
}
function renderBatchSummary() {
  if (!refs.batchSummary && refs.batchQueue?.parentElement) {
    const summary = document.createElement("div");
    summary.id = "batchSummary";
    summary.className = "batch-summary empty-state compact-empty";
    summary.textContent = "添加批量图片后，这里会显示总进度与预计剩余时间。";
    refs.batchQueue.parentElement.insertBefore(summary, refs.batchQueue);
    refs.batchSummary = summary;
  }
  if (!refs.batchSummary) return;
  if (!state.batchQueue.length) {
    refs.batchSummary.className = "batch-summary empty-state compact-empty";
    refs.batchSummary.textContent = "添加批量图片后，这里会显示总进度与预计剩余时间。";
    return;
  }

  const stats = getBatchStats();
  const progressValue = Math.round(stats.progress * 100);
  const eta = estimateBatchEta(stats);
  const progressWidth = Math.max(progressValue, stats.finished ? 4 : 0);
  const note = state.batchRunning
    ? `正在执行中：已完成 ${stats.finished}/${stats.total}，预计剩余 ${eta}`
    : `队列就绪：共 ${stats.total} 项，成功 ${stats.done}，失败 ${stats.failed}`;

  refs.batchSummary.className = "batch-summary";
  refs.batchSummary.innerHTML = `
    <div class="batch-summary-grid">
      <article class="batch-summary-cell"><span>总任务</span><strong>${stats.total}</strong></article>
      <article class="batch-summary-cell"><span>已完成</span><strong>${stats.done}</strong></article>
      <article class="batch-summary-cell"><span>失败</span><strong>${stats.failed}</strong></article>
      <article class="batch-summary-cell"><span>预计剩余</span><strong>${eta}</strong></article>
    </div>
    <div class="batch-summary-progress-track"><div class="batch-summary-progress-fill" style="width:${progressWidth}%"></div></div>
    <p class="batch-summary-note">进度 ${progressValue}% · ${escapeHtml(note)}</p>
  `;
}

async function retryBatchItem(itemId) {
  if (state.batchRunning) return;
  const item = state.batchQueue.find((entry) => entry.id === itemId);
  if (!item || item.status !== "失败") return;

  setSystemTimeline("batch");
  state.batchRunning = true;
  syncButtons();
  setMessage(`正在重试：${item.file.name}`);

  await runSingleBatchTask(item);

  state.batchRunning = false;
  renderBatchQueue();
  renderAnalytics();
  syncButtons();
  renderSteps();

  if (item.status === "done") {
    setMessage(`重试成功：${item.file.name}`);
  } else {
    setMessage(`重试失败：${item.file.name}，请检查样本或网络。`, true);
  }
  setSystemTimeline("model");
}
function renderBatchQueue() {
  renderBatchSummary();
  if (!state.batchQueue.length) {
    refs.batchQueue.className = "batch-queue empty-state";
    refs.batchQueue.textContent = "批量任务为空。可拖入多张图片建立巡检队列。";
    return;
  }

  refs.batchQueue.className = "batch-queue batch-queue-rich";
  refs.batchQueue.innerHTML = state.batchQueue.map((item) => {
    const primary = item.result?.primary_result;
    const statusMeta = getBatchStatusMeta(item.status);
    const latencyText = Number.isFinite(item.latencyMs) && item.latencyMs > 0 ? formatDuration(item.latencyMs) : "-";
    const topLabel = primary ? primary.readable_name : "-";
    const confidence = primary ? primary.confidence_text : "-";
    const confidenceValue = primary ? Math.max(Math.round(Number(primary.confidence || 0) * 100), 3) : 0;
    const detail = item.status === "失败"
      ? (item.error || "识别失败")
      : (primary ? `来源 ${normalizeDatasetLabel(primary.dataset, primary.original_label)} · 耗时 ${latencyText}` : "等待模型处理");
    const retryButton = item.status === "失败"
      ? `<button type="button" class="ghost-btn batch-retry-btn" data-id="${escapeHtml(item.id)}" ${state.batchRunning ? "disabled" : ""}>重试该条</button>`
      : "";

    return `
      <article class="batch-task-card batch-task-${statusMeta.tone}">
        <div class="batch-task-thumb-wrap">
          <img class="batch-task-thumb" src="${escapeHtml(item.previewUrl || "")}" alt="${escapeHtml(item.file.name)}" />
        </div>
        <div class="batch-task-body">
          <div class="batch-task-head">
            <strong class="batch-file-name">${escapeHtml(item.file.name)}</strong>
            <span class="batch-state-chip state-${statusMeta.tone}">${statusMeta.icon} ${statusMeta.label}</span>
          </div>
          <div class="batch-task-meta">
            <span>Top-1：${escapeHtml(topLabel)}</span>
            <span>置信度：${escapeHtml(confidence)}</span>
            <span>耗时：${escapeHtml(latencyText)}</span>
          </div>
          ${primary ? `<div class="batch-card-confidence"><div class="batch-card-track"><div class="batch-card-fill" style="width:${confidenceValue}%"></div></div></div>` : ""}
          <p class="batch-task-note">${escapeHtml(detail)}</p>
          ${retryButton ? `<div class="batch-task-actions">${retryButton}</div>` : ""}
        </div>
      </article>
    `;
  }).join("");

  refs.batchQueue.querySelectorAll(".batch-retry-btn").forEach((button) => {
    button.addEventListener("click", async (event) => {
      const itemId = event.currentTarget.dataset.id || "";
      await retryBatchItem(itemId);
    });
  });

  applyRevealStagger(refs.batchQueue, ".batch-task-card");
}
function pushSessionRecord(prediction, latencyMs, source = "single") {
  const primary = prediction.primary_result;
  if (!primary) return;
  state.sessionRecords.push({
    label: primary.readable_name,
    riskTone: primary.risk_tone,
    riskLevel: localizeRiskLevel(primary.risk_tone),
    confidence: Number(primary.confidence || 0),
    confidenceText: primary.confidence_text,
    fileName: prediction.filename,
    generatedAt: prediction.generated_at,
    latencyMs,
    source,
  });
  if (Number.isFinite(latencyMs) && latencyMs > 0) state.latencySamples.push(latencyMs);
  renderAnalytics();
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const raw = await response.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { detail: raw || "请求失败" };
  }
  if (!response.ok) {
    throw new Error(data.detail || data.message || `请求失败: HTTP ${response.status}`);
  }
  return data;
}

async function useSample(sample) {
  try {
    setMessage(`正在载入示例样本：${sample.name}`);
    const response = await fetch(sample.url);
    if (!response.ok) throw new Error("示例图片加载失败");
    const blob = await response.blob();
    const file = new File([blob], sample.name, { type: blob.type || "image/jpeg" });
    selectFile(file, sample.name);
    setMessage(`已载入示例样本：${sample.name}`);
  } catch (error) {
    setMessage(error.message || "示例图片加载失败", true);
  }
}

async function loadModel() {
  const path = refs.modelSelect.value;
  if (!path) {
    setMessage("没有可加载的模型。", true);
    return;
  }
  setSystemTimeline("model");
  setLoading(refs.loadModelBtn, true);
  setMessage("正在加载模型...");
  try {
    const data = await requestJson("/api/models/load", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    state.currentModel = data.current_model;
    updateModelMeta(state.currentModel);
    renderAnalytics();
    renderSteps();
    syncButtons();
    setMessage("模型加载成功，可以开始识别。", false);
  } catch (error) {
    setMessage(error.message || "模型加载失败，请检查后端日志。", true);
  } finally {
    setLoading(refs.loadModelBtn, false);
    syncButtons();
  }
}

async function runPrediction(file) {
  const startedAt = performance.now();
  const fileBuffer = await file.arrayBuffer();
  const data = await requestJson("/api/predict", {
    method: "POST",
    headers: {
      "Content-Type": "application/octet-stream",
      "x-filename": encodeURIComponent(file.name),
    },
    body: fileBuffer,
  });
  return { data, latencyMs: performance.now() - startedAt };
}

async function predictImage() {
  setWorkspacePage("diagnosis");
  if (!(state.currentModel?.loaded && state.selectedFile)) {
    setMessage("请先加载模型并选择图片。", true);
    return;
  }
  const minScanDurationMs = 2500;
  const scanDelay = new Promise((resolve) => setTimeout(resolve, minScanDurationMs));
  setSystemTimeline("inference");
  setLoading(refs.predictBtn, true);
  setScanning(true, "AI 正在扫描叶片纹理...");
  setMessage("正在执行模型推理...");
  refs.resultOverview.className = "result-overview empty-overview";
  refs.resultOverview.textContent = "模型正在分析当前图片，请稍候...";
  refs.candidateList.className = "candidate-list empty-state";
  refs.candidateList.textContent = "正在生成候选结果...";
  refs.detailSummary.className = "detail-summary empty-detail";
  refs.detailSummary.textContent = "正在整理诊断摘要...";
  refs.predictionTimestamp.textContent = "正在推理";
  resetStrategyView();
  try {
    const prediction = await runPrediction(state.selectedFile);
    await scanDelay;
    const { data, latencyMs } = prediction;
    state.latestPrediction = data;
    refs.latestFile.textContent = data.filename;
    refs.predictionTimestamp.textContent = `更新于 ${formatTimestamp(data.generated_at)}`;
    refs.candidateHint.textContent = `共生成 ${(data.results || []).length} 个候选结果，可进一步查询策略。`;
    renderOverview(data, latencyMs);
    renderVisualShowcase(data.results || []);
    renderCandidates(data.results || []);
    renderDetailSummary(data, latencyMs);
    pushSessionRecord(data, latencyMs, "single");
    renderVisionStage();
    renderSteps();
    syncButtons();
    setMessage("识别完成。可继续点击候选结果查询防治策略。", false);
  } catch (error) {
    await scanDelay;
    clearDiagnosisViews("识别失败，请更换图片或检查后端日志。");
    refs.resultOverview.className = "result-overview empty-overview";
    refs.resultOverview.textContent = "识别失败，请更换图片或检查后端日志。";
    refs.detailSummary.className = "detail-summary empty-detail";
    refs.detailSummary.textContent = "识别失败，请更换图片或检查后端日志。";
    setMessage(error.message || "识别失败，请检查后端日志。", true);
  } finally {
    setScanning(false);
    setSystemTimeline("model");
    setLoading(refs.predictBtn, false);
    syncButtons();
    renderSteps();
  }
}

async function fetchStrategy(name, button) {
  setWorkspacePage("strategy");
  if (!state.strategyAvailable) {
    setMessage("当前环境未启用策略资料服务。", true);
    return;
  }
  setSystemTimeline("strategy");
  setLoading(button, true);
  setInfoPill(refs.strategyStatus, "整理中", "success");
  refs.strategyHint.textContent = `正在整理 ${name} 的资料`;
  state.latestStrategy = null;
  state.currentStrategyName = "";
  state.strategyChat = [];
  refs.strategyChat.className = "chat-thread empty-detail";
  refs.strategyChat.textContent = "正在初始化策略工作台...";
  refs.strategyPanel.className = "strategy-panel empty-detail";
  refs.strategyPanel.textContent = `正在为“${name}”整理防治资料...`;
  refs.strategySources.innerHTML = "";
  try {
    const data = await requestJson("/api/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    state.latestStrategy = data;
    state.currentStrategyName = name;
    state.strategyChat = [
      { role: "user", content: `请整理“${name}”的防治资料。` },
      { role: "assistant", content: data.summary || `已整理 ${name} 的相关资料。` },
    ];
    renderStrategy(data);
    renderChatThread();
    refs.strategyQuestion.value = "";
    refs.chatHint.textContent = `可继续围绕“${name}”追问施药、安全性或环境条件`;
    setInfoPill(refs.strategyStatus, "已加载", "success");
    refs.strategyHint.textContent = `已整理 ${data.items?.length || 0} 条关于 ${name} 的资料`;
    setMessage(`已加载“${name}”的资料摘要。`, false);
  } catch (error) {
    setInfoPill(refs.strategyStatus, "查询失败", "error");
    refs.strategyHint.textContent = "请检查 API Key、Base URL 或网络后重试";
    refs.strategyPanel.className = "strategy-panel empty-detail";
    refs.strategyPanel.textContent = error.message || "资料整理失败，请检查 API Key、Base URL 或网络连接。";
    refs.strategySources.innerHTML = "";
    refs.strategyChat.className = "chat-thread empty-detail";
    refs.strategyChat.textContent = "首轮策略整理失败，暂时无法继续追问。";
    setMessage(error.message || "资料整理失败，请检查 API Key、Base URL 或网络连接。", true);
  } finally {
    setSystemTimeline("model");
    setLoading(button, false);
    syncButtons();
  }
}

async function sendStrategyQuestion() {
  setWorkspacePage("strategy");
  const question = refs.strategyQuestion.value.trim();
  if (!(question && state.latestStrategy && state.currentStrategyName)) return;
  setSystemTimeline("strategy");
  setLoading(refs.sendStrategyBtn, true);
  state.strategyChat.push({ role: "user", content: question });
  renderChatThread();
  try {
    const data = await requestJson("/api/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: state.currentStrategyName,
        question,
        context: state.latestStrategy.summary || "",
        history: state.strategyChat,
      }),
    });
    state.latestStrategy = data;
    state.strategyChat.push({ role: "assistant", content: data.summary || "已完成追问回答。" });
    renderStrategy(data);
    renderChatThread();
    refs.strategyQuestion.value = "";
    setInfoPill(refs.strategyStatus, "已更新", "success");
    refs.strategyHint.textContent = `已完成关于 ${state.currentStrategyName} 的追问整理`;
    setMessage("已生成追问回答。", false);
  } catch (error) {
    state.strategyChat.push({ role: "assistant", content: error.message || "追问失败，请稍后重试。" });
    renderChatThread();
    setInfoPill(refs.strategyStatus, "追问失败", "error");
    setMessage(error.message || "追问失败，请检查 API Key、Base URL 或网络。", true);
  } finally {
    setSystemTimeline("model");
    setLoading(refs.sendStrategyBtn, false);
    syncButtons();
  }
}

function addBatchFiles(files) {
  const incoming = Array.from(files || []);
  if (!incoming.length) return;

  let addedCount = 0;
  incoming.forEach((file) => {
    const duplicate = state.batchQueue.some((item) => item.file.name === file.name && item.file.size === file.size && item.file.lastModified === file.lastModified);
    if (!duplicate) {
      state.batchQueue.push({
        id: `${file.name}-${file.size}-${file.lastModified}`,
        file,
        previewUrl: URL.createObjectURL(file),
        status: "待识别",
        result: null,
        error: "",
        latencyMs: 0,
      });
      addedCount += 1;
    }
  });

  renderBatchQueue();
  renderAnalytics();
  renderSteps();
  syncButtons();

  if (addedCount) {
    setMessage(`批量队列已新增 ${addedCount} 张图片。`, false);
  } else {
    setMessage("所选图片已存在于队列中。", true);
  }
}

async function runSingleBatchTask(item) {
  item.status = "识别中";
  item.error = "";
  renderBatchQueue();
  renderAnalytics();
  syncButtons();

  try {
    const { data, latencyMs } = await runPrediction(item.file);
    item.status = "done";
    item.result = data;
    item.latencyMs = latencyMs;
    pushSessionRecord(data, latencyMs, "batch");
  } catch (error) {
    item.status = "失败";
    item.error = error.message || "识别失败";
    item.latencyMs = 0;
  }

  renderBatchQueue();
  renderAnalytics();
  syncButtons();
}
async function runBatchProcessing() {
  setWorkspacePage("analytics");
  if (!(state.currentModel?.loaded && state.batchQueue.length)) {
    setMessage("请先加载模型并添加批量图片。", true);
    return;
  }

  setSystemTimeline("batch");
  state.batchRunning = true;
  renderBatchQueue();
  renderAnalytics();
  syncButtons();
  setLoading(refs.runBatchBtn, true);
  setMessage("正在执行批量识别...");

  for (const item of state.batchQueue) {
    if (item.status === "done") continue;
    await runSingleBatchTask(item);
  }

  state.batchRunning = false;
  setSystemTimeline("model");
  setLoading(refs.runBatchBtn, false);
  syncButtons();
  renderBatchQueue();
  renderAnalytics();
  renderSteps();

  const stats = getBatchStats();
  const finishedMessage = `批量识别完成：成功 ${stats.done}，失败 ${stats.failed}。`;
  setMessage(finishedMessage, false);
}
function exportBatchCsv() {
  const rows = state.batchQueue.filter((item) => item.status === "done" && item.result?.primary_result);
  if (!rows.length) {
    setMessage("没有可导出的批量结果。", true);
    return;
  }
  const escapeCsv = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const lines = [["文件名", "Top1", "置信度", "风险等级", "数据来源", "生成时间", "耗时(ms)"].map(escapeCsv).join(",")];
  rows.forEach((item) => {
    const primary = item.result.primary_result;
    lines.push([
      item.result.filename,
      primary.readable_name,
      primary.confidence_text,
      localizeRiskLevel(primary.risk_tone),
      normalizeDatasetLabel(primary.dataset, primary.original_label),
      item.result.generated_at,
      Math.round(item.latencyMs || 0),
    ].map(escapeCsv).join(","));
  });
  const blob = new Blob([`\uFEFF${lines.join("\n")}`], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `batch_results_${Date.now()}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  setMessage("批量结果已导出为 CSV。", false);
}


async function initPage() {
  clearDiagnosisViews();
  clearVisualShowcase();
  setSystemTimeline("model");
  renderVisionStage();
  renderBatchQueue();
  renderAnalytics();
  try {
    const [health, samples] = await Promise.all([requestJson("/api/health"), requestJson("/api/samples")]);
    state.models = health.available_models || [];
    state.currentModel = health.current_model || null;
    state.strategyAvailable = Boolean(health.strategy_available);
    state.strategyStatusReason = health.strategy_status_reason || "";
    state.sampleImages = samples.images || [];
    setStatusBadge("服务已连接", false);
    refs.serviceNote.textContent = state.strategyAvailable ? "策略服务可尝试调用" : "策略服务未启用";
    updateModelMeta(state.currentModel, health.sample_count);
    renderModelSelect(state.models, state.currentModel?.model_path || "");
    renderSampleGallery();
    resetStrategyView();
    renderAnalytics();
    renderSteps();
    syncButtons();
    setWorkspacePage(state.currentPage || "overview");
    if (state.currentModel?.loaded) {
      setMessage("模型已就绪，请选择图片开始识别。", false);
    } else if (state.models.length) {
      setMessage("已发现模型文件，请先点击“加载模型”。", false);
    } else {
      setMessage("未发现模型文件，请检查 trained_models 目录。", true);
    }
  } catch (error) {
    setStatusBadge("服务连接失败", true);
    refs.serviceNote.textContent = "后端尚未启动";
    setMessage("无法连接后端服务，请先启动 python src/web_service.py。", true);
    refs.sampleGallery.className = "sample-gallery empty-state";
    refs.sampleGallery.textContent = "无法读取示例图库。";
    refs.resultOverview.className = "result-overview empty-overview";
    refs.resultOverview.textContent = "无法连接后端服务，请先启动 python src/web_service.py。";
    refs.detailSummary.className = "detail-summary empty-detail";
    refs.detailSummary.textContent = "后端未启动，当前无法获取诊断结果。";
  }
}

refs.loadModelBtn.addEventListener("click", loadModel);
refs.predictBtn.addEventListener("click", predictImage);
refs.resetBtn.addEventListener("click", resetCurrentSample);
refs.runBatchBtn.addEventListener("click", runBatchProcessing);
refs.exportBatchBtn.addEventListener("click", exportBatchCsv);
refs.sendStrategyBtn.addEventListener("click", sendStrategyQuestion);
refs.strategyQuestion.addEventListener("input", syncButtons);
refs.imageInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (file) selectFile(file, "");
});
refs.batchInput.addEventListener("change", (event) => {
  addBatchFiles(event.target.files);
  refs.batchInput.value = "";
});
refs.workspaceButtons.forEach((button) => {
  button.addEventListener("click", () => setWorkspacePage(button.dataset.page || "overview"));
});
refs.presentationToggle?.addEventListener("click", () => {
  setPresentationMode(!state.presentationMode);
});
["dragenter", "dragover"].forEach((eventName) => {
  refs.uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    refs.uploadZone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((eventName) => {
  refs.uploadZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    refs.uploadZone.classList.remove("dragover");
  });
});
refs.uploadZone.addEventListener("drop", (event) => {
  const files = Array.from(event.dataTransfer?.files || []);
  if (!files.length) return;
  const imageFiles = files.filter((file) => file.type.startsWith("image/"));
  if (!imageFiles.length) return;
  selectFile(imageFiles[0], "");
  if (imageFiles.length > 1) addBatchFiles(imageFiles.slice(1));
});

initPage();





































