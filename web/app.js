const HISTORY_KEY = "crop_vision_history_v2";
const MAX_HISTORY = 6;

const refs = {
  serviceStatus: document.getElementById("serviceStatus"),
  modelName: document.getElementById("modelName"),
  knowledgeCount: document.getElementById("knowledgeCount"),
  sampleCount: document.getElementById("sampleCount"),
  imageSize: document.getElementById("imageSize"),
  deviceName: document.getElementById("deviceName"),
  modelSelect: document.getElementById("modelSelect"),
  loadModelBtn: document.getElementById("loadModelBtn"),
  imageInput: document.getElementById("imageInput"),
  uploadZone: document.getElementById("uploadZone"),
  uploadCopy: document.getElementById("uploadCopy"),
  previewImage: document.getElementById("previewImage"),
  predictBtn: document.getElementById("predictBtn"),
  resetBtn: document.getElementById("resetBtn"),
  actionMessage: document.getElementById("actionMessage"),
  sampleGallery: document.getElementById("sampleGallery"),
  resultOverview: document.getElementById("resultOverview"),
  latestFile: document.getElementById("latestFile"),
  predictionTimestamp: document.getElementById("predictionTimestamp"),
  candidateList: document.getElementById("candidateList"),
  detailSummary: document.getElementById("detailSummary"),
  strategyStatus: document.getElementById("strategyStatus"),
  strategyHint: document.getElementById("strategyHint"),
  strategyPanel: document.getElementById("strategyPanel"),
  strategySources: document.getElementById("strategySources"),
  historyList: document.getElementById("historyList"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  stepCards: Array.from(document.querySelectorAll(".step-card")),
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
  history: loadHistory(),
};

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveHistory() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(state.history));
  } catch {
    // ignore localStorage failures
  }
}

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
    "如需处理建议，再点击候选卡片中的防治策略按钮查询资料。",
  ];
}

function buildCandidateFocus(item) {
  return `建议优先核查“${item.readable_name}”相关的典型症状部位。`;
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
  if (!button.dataset.label) {
    button.dataset.label = button.textContent;
  }

  button.classList.toggle("is-loading", loading);
  if (loading) {
    button.disabled = true;
  } else {
    button.textContent = button.dataset.label;
    button.disabled = false;
  }
}

function syncButtons() {
  refs.loadModelBtn.disabled = state.models.length === 0;
  refs.predictBtn.disabled = !(state.currentModel?.loaded && state.selectedFile);
  refs.resetBtn.disabled = !state.selectedFile;
  refs.clearHistoryBtn.disabled = state.history.length === 0;
}

function renderSteps() {
  const modelLoaded = Boolean(state.currentModel?.loaded);
  const imageReady = Boolean(state.selectedFile);
  const diagnosisReady = Boolean(state.latestPrediction);

  refs.stepCards.forEach((card) => {
    const step = card.dataset.step;
    card.classList.remove("is-current", "is-done");

    if (step === "model") {
      card.classList.add(modelLoaded ? "is-done" : "is-current");
      return;
    }

    if (step === "image") {
      if (modelLoaded) {
        card.classList.add(imageReady ? "is-done" : "is-current");
      }
      return;
    }

    if (imageReady) {
      card.classList.add(diagnosisReady ? "is-done" : "is-current");
    }
  });
}

function updateModelMeta(model, sampleCount = state.sampleImages.length) {
  const loaded = Boolean(model?.loaded);
  refs.modelName.textContent = loaded ? model.model_name || "未知" : "未加载";
  refs.knowledgeCount.textContent = loaded ? model.knowledge_base_count ?? "-" : "-";
  refs.sampleCount.textContent = sampleCount ?? "-";
  refs.imageSize.textContent = loaded ? model.image_size || "-" : "-";
  refs.deviceName.textContent = model?.device || "-";
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
    if (currentPath && currentPath === model.path) {
      option.selected = true;
    }
    refs.modelSelect.appendChild(option);
  });
}

function renderSampleGallery() {
  if (!state.sampleImages.length) {
    refs.sampleGallery.className = "sample-gallery empty-state";
    refs.sampleGallery.textContent = "当前 sample_images 目录下没有可用图片。";
    return;
  }

  refs.sampleGallery.className = "sample-gallery";
  refs.sampleGallery.innerHTML = state.sampleImages
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
      const sample = state.sampleImages.find((item) => item.name === name);
      if (!sample) return;
      await useSample(sample);
    });
  });
}

function resetStrategyView(message) {
  refs.strategySources.innerHTML = "";
  refs.strategyPanel.className = "strategy-panel empty-detail";

  if (!state.strategyAvailable) {
    setInfoPill(refs.strategyStatus, "未启用", "error");
    refs.strategyHint.textContent = "资料整理当前不可用";
    refs.strategyPanel.textContent =
      state.strategyStatusReason || "当前环境未启用 DeepSeek 资料整理。";
    return;
  }

  setInfoPill(refs.strategyStatus, "尚未查询", "muted");
  refs.strategyHint.textContent = "点击候选卡片按钮整理资料";
  refs.strategyPanel.textContent = message || "当前未加载策略内容。";
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
  resetStrategyView();
  renderSteps();
}

function setPreview(file) {
  if (state.previewUrl) {
    URL.revokeObjectURL(state.previewUrl);
  }

  state.previewUrl = URL.createObjectURL(file);
  refs.previewImage.src = state.previewUrl;
  refs.previewImage.hidden = false;
  refs.uploadCopy.hidden = true;
  refs.uploadZone.classList.add("has-preview");
}

function selectFile(file, sampleName = "") {
  state.selectedFile = file;
  state.selectedSampleName = sampleName;
  setPreview(file);
  refs.latestFile.textContent = file.name;
  clearDiagnosisViews();
  renderSampleGallery();
  syncButtons();
  renderSteps();
  setMessage(`已选择样本：${file.name}`);
}

function resetCurrentSample() {
  if (state.previewUrl) {
    URL.revokeObjectURL(state.previewUrl);
  }

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
  syncButtons();
  setMessage("已清空当前样本。请重新选择图片。");
}

function renderOverview(prediction) {
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
        </div>
      </div>

      <div class="overview-grid">
        <div class="overview-metric">
          <span>数据来源</span>
          <strong>${escapeHtml(normalizeDatasetLabel(primary.dataset, primary.original_label))}</strong>
        </div>
        <div class="overview-metric">
          <span>标签编号</span>
          <strong>${escapeHtml(primary.original_label)}</strong>
        </div>
        <div class="overview-metric">
          <span>推荐动作</span>
          <strong>${escapeHtml(riskDescription)}</strong>
        </div>
      </div>

      <ul class="guidance-list">
        ${nextActions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </article>
  `;
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
              <div class="badge-row">
                <span class="badge ${riskClass(item.risk_tone)}">${escapeHtml(localizeRiskLevel(item.risk_tone))}</span>
              </div>
              <h4 class="candidate-name">${escapeHtml(item.readable_name)}</h4>
              <p class="candidate-meta">${escapeHtml(normalizeDatasetLabel(item.dataset, item.original_label))} · ${escapeHtml(item.original_label)}</p>
            </div>
            <div class="candidate-rank">#${item.rank}</div>
          </div>

          <div class="confidence-row">
            <strong>置信度 ${escapeHtml(item.confidence_text)}</strong>
            <div class="progress-track">
              <div class="progress-bar" style="width:${Math.max(item.confidence * 100, 3)}%"></div>
            </div>
          </div>

          <p class="candidate-note">${escapeHtml(buildCandidateFocus(item))}</p>

          <div class="candidate-actions">
            <span class="history-meta">${escapeHtml(localizeRiskDescription(item.risk_tone))}</span>
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
}

function renderDetailSummary(prediction) {
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
    <article class="detail-card">
      <h3>诊断主结论: ${escapeHtml(primary.readable_name)}</h3>
      <p>${escapeHtml(summary)}</p>
    </article>
    <article class="detail-card">
      <h3>建议的人工复核动作</h3>
      <ul>
        ${nextActions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </article>
    <article class="detail-card">
      <h3>使用提示</h3>
      <p>识别结果不能替代农技人员现场诊断或实验室检测。</p>
    </article>
  `;
}

function renderStrategy(data) {
  if (!data.items?.length) {
    refs.strategyPanel.className = "strategy-panel empty-detail";
    refs.strategyPanel.textContent = "暂未查询到明确策略，建议改用学名、别名或人工检索继续确认。";
    refs.strategySources.innerHTML = "";
    return;
  }

  refs.strategyPanel.className = "strategy-panel";
  refs.strategyPanel.innerHTML = data.items
    .map(
      (item) => `
        <article class="strategy-card">
          <h4>${escapeHtml(item.title)}</h4>
          <p>${escapeHtml(item.content)}</p>
          ${item.url ? `<a class="strategy-link" href="${item.url}" target="_blank" rel="noreferrer">打开来源</a>` : ""}
        </article>
      `
    )
    .join("");

  refs.strategySources.innerHTML = (data.sources || [])
    .map(
      (source) => `
        <div class="source-item">
          <span>${escapeHtml(source.title)}</span>
          ${source.url ? `<a href="${source.url}" target="_blank" rel="noreferrer">来源链接</a>` : "<span>无链接</span>"}
        </div>
      `
    )
    .join("");
}

function renderHistory() {
  syncButtons();
  if (!state.history.length) {
    refs.historyList.className = "history-list empty-state";
    refs.historyList.textContent = "暂无历史记录。";
    return;
  }

  refs.historyList.className = "history-list";
  refs.historyList.innerHTML = state.history
    .map(
      (item) => `
        <article class="history-item">
          <strong>${escapeHtml(item.label)}</strong>
          <p class="history-meta">文件: ${escapeHtml(item.fileName)}</p>
          <p class="history-meta">置信度: ${escapeHtml(item.confidenceText)} · 风险等级: ${escapeHtml(item.riskLevel)}</p>
          <p class="history-meta">时间: ${escapeHtml(item.time)}</p>
        </article>
      `
    )
    .join("");
}

function pushHistory(prediction) {
  const primary = prediction.primary_result;
  if (!primary) return;

  state.history.unshift({
    label: primary.readable_name,
    fileName: prediction.filename,
    confidenceText: primary.confidence_text,
    riskLevel: localizeRiskLevel(primary.risk_tone),
    time: formatTimestamp(prediction.generated_at || Date.now()),
  });
  state.history = state.history.slice(0, MAX_HISTORY);
  saveHistory();
  renderHistory();
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
    if (!response.ok) {
      throw new Error("示例图片加载失败");
    }
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
    syncButtons();
    renderSteps();
    setMessage("模型加载成功，可以开始识别。", false);
  } catch (error) {
    setMessage("模型加载失败，请检查后端日志。", true);
  } finally {
    setLoading(refs.loadModelBtn, false);
    syncButtons();
  }
}

async function predictImage() {
  if (!(state.currentModel?.loaded && state.selectedFile)) {
    setMessage("请先加载模型并选择图片。", true);
    return;
  }

  setLoading(refs.predictBtn, true);
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
    const fileBuffer = await state.selectedFile.arrayBuffer();
    const data = await requestJson("/api/predict", {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "x-filename": encodeURIComponent(state.selectedFile.name),
      },
      body: fileBuffer,
    });

    state.latestPrediction = data;
    refs.latestFile.textContent = data.filename;
    refs.predictionTimestamp.textContent = `更新于 ${formatTimestamp(data.generated_at)}`;
    renderOverview(data);
    renderCandidates(data.results || []);
    renderDetailSummary(data);
    resetStrategyView();
    pushHistory(data);
    renderSteps();
    setMessage("识别完成。可继续点击候选结果查询防治策略。", false);
  } catch (error) {
    clearDiagnosisViews("识别失败，请更换图片或检查后端日志。");
    refs.resultOverview.className = "result-overview empty-overview";
    refs.resultOverview.textContent = "识别失败，请更换图片或检查后端日志。";
    refs.detailSummary.className = "detail-summary empty-detail";
    refs.detailSummary.textContent = "识别失败，请更换图片或检查后端日志。";
    setMessage("识别失败，请检查后端日志。", true);
  } finally {
    setLoading(refs.predictBtn, false);
    syncButtons();
    renderSteps();
  }
}

async function fetchStrategy(name, button) {
  if (!state.strategyAvailable) {
    setMessage("当前环境未启用 DeepSeek 资料整理。", true);
    return;
  }

  setLoading(button, true);
  setInfoPill(refs.strategyStatus, "查询中", "success");
  refs.strategyHint.textContent = `正在整理 ${name} 的资料`;
  refs.strategyPanel.className = "strategy-panel empty-detail";
  refs.strategyPanel.textContent = `正在为“${name}”整理防治资料...`;
  refs.strategySources.innerHTML = "";

  try {
    const data = await requestJson("/api/strategy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });

    renderStrategy(data);
    setInfoPill(refs.strategyStatus, "已加载", "success");
    refs.strategyHint.textContent = `已整理 ${data.items?.length || 0} 条关于 ${name} 的资料`;
    setMessage(`已加载“${name}”的资料摘要。`);
  } catch (error) {
    setInfoPill(refs.strategyStatus, "查询失败", "error");
    refs.strategyHint.textContent = "请检查 DeepSeek 配置或网络后重试";
    refs.strategyPanel.className = "strategy-panel empty-detail";
    refs.strategyPanel.textContent = error.message || "资料整理失败，请检查 DeepSeek 配置或网络连接。";
    refs.strategySources.innerHTML = "";
    setMessage(error.message || "资料整理失败，请检查 DeepSeek 配置或网络连接。", true);
  } finally {
    setLoading(button, false);
  }
}

function clearHistory() {
  state.history = [];
  saveHistory();
  renderHistory();
}

async function initPage() {
  renderHistory();
  clearDiagnosisViews();

  try {
    const [health, samples] = await Promise.all([
      requestJson("/api/health"),
      requestJson("/api/samples"),
    ]);

    state.models = health.available_models || [];
    state.currentModel = health.current_model || null;
    state.strategyAvailable = Boolean(health.strategy_available);
    state.strategyStatusReason = health.strategy_status_reason || "";
    state.sampleImages = samples.images || [];

    setStatusBadge("服务已连接", false);
    updateModelMeta(state.currentModel, health.sample_count);
    renderModelSelect(state.models, state.currentModel?.model_path || "");
    renderSampleGallery();
    resetStrategyView();
    syncButtons();
    renderSteps();

    if (state.currentModel?.loaded) {
      setMessage("模型已就绪，请选择图片开始识别。", false);
    } else if (state.models.length) {
      setMessage("已发现模型文件，请先点击“加载模型”。", false);
    } else {
      setMessage("未发现模型文件，请检查 trained_models 目录。", true);
    }
  } catch (error) {
    setStatusBadge("服务连接失败", true);
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
refs.clearHistoryBtn.addEventListener("click", clearHistory);
refs.imageInput.addEventListener("change", (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  selectFile(file, "");
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
  const file = event.dataTransfer?.files?.[0];
  if (!file) return;
  selectFile(file, "");
});

initPage();










