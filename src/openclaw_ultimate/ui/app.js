"use strict";

const state = {
  meta: null,
  diagnostics: [],
  plans: [],
  selectedPlan: null,
  memories: [],
  confirmations: [],
  audit: [],
  knowledge: null,
  mcp: null,
  lastFailedMessage: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function api(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeout ?? 20000);
  try {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
      signal: options.signal || controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data?.error?.message || `请求失败：${response.status}`);
      error.status = response.status;
      error.payload = data;
      throw error;
    }
    return data.data ?? data;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("本地服务响应超时，请检查模型或组件状态。");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatTime(value) {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    }).format(new Date(value));
  } catch { return value; }
}

let toastTimer;
function toast(message, type = "ok") {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast show ${type === "error" ? "error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.className = "toast"; }, 3400);
}

function setBusy(button, busy, label) {
  if (!button) return;
  if (busy) {
    button.dataset.original = button.textContent;
    button.textContent = label || "处理中…";
    button.disabled = true;
  } else {
    button.textContent = button.dataset.original || button.textContent;
    button.disabled = false;
  }
}

const titles = {
  overview: "系统总览", tasks: "任务编排", chat: "本地对话",
  knowledge: "知识库", memory: "长期记忆", safety: "安全中心",
  integrations: "模型与集成",
};

function showView(name) {
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
  $("#view-title").textContent = titles[name] || "VELA";
  if (window.innerWidth < 780) window.scrollTo({ top: 0, behavior: "smooth" });
}

async function loadMeta() {
  state.meta = await api("/v1/meta");
  $("#version-label").textContent = `${state.meta.legacy_name} compatibility · v${state.meta.version}`;
  $("#system-pill").innerHTML = "<i></i>本地服务在线";
}

async function loadStatus() {
  const report = await api("/health", { timeout: 60000 });
  state.diagnostics = report.components || [];
  const pill = $("#system-pill");
  pill.classList.toggle("offline", !report.ok);
  pill.innerHTML = `<i></i>${report.ok ? "系统就绪" : "需要检查"}`;
  $("#status-time").textContent = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  renderStatus();
}

function renderStatus() {
  const component = (name) => state.diagnostics.find((item) => item.name === name);
  const ready = state.diagnostics.filter((item) => item.state === "ready").length;
  const planDone = state.plans.filter((item) => item.status === "completed").length;
  const metrics = [
    [
      "可用组件",
      state.diagnostics.length ? `${ready}/${state.diagnostics.length}` : "检查中",
      "实时健康检查",
    ],
    ["任务计划", state.plans.length, `${planDone} 个已完成`],
    [
      "知识文档",
      state.knowledge?.document_count ?? "—",
      `${state.knowledge?.chunk_count ?? 0} 个检索块`,
    ],
    ["待确认", state.confirmations.length, "高风险操作由你决定"],
  ];
  $("#metric-grid").innerHTML = metrics.map(([label, value, note]) => `
    <article class="metric"><span>${label}</span><strong>${value}</strong><small>${note}</small></article>
  `).join("");
  $("#component-list").innerHTML = state.diagnostics.map((item) => `
    <div class="component">
      <div><strong>${escapeHtml(item.name)}</strong><p title="${escapeHtml(item.detail)}">${escapeHtml(item.detail)}</p></div>
      <span class="state ${item.state}">${escapeHtml(item.state)}</span>
    </div>
  `).join("") || `<div class="empty-state small"><p>正在检查本地组件…</p></div>`;
  const integrations = [
    ["OC", "OpenClaw", component("openclaw")],
    ["OL", "Ollama", component("ollama")],
    ["CU", "ComfyUI", component("comfyui")],
    ["MC", "MCP", component("mcp")],
  ];
  $("#integration-grid").innerHTML = integrations.map(([symbol, label, item]) => `
    <article class="integration-card">
      <span class="symbol">${symbol}</span>
      <h3>${label} <span class="state ${item?.state || "unavailable"}">${item?.state || "unknown"}</span></h3>
      <p>${escapeHtml(item?.detail || "未发现")}</p>
      ${label === "MCP" && state.mcp?.enabled ? `<button class="mini-button" data-mcp-test="${escapeHtml(state.mcp.servers[0]?.name || "")}">测试链路</button>` : ""}
    </article>
  `).join("");
}

function unwrapBridge(value) {
  return value?.data?.data ?? value?.data ?? value;
}

async function loadPlans() {
  const result = await api("/v1/plans");
  state.plans = result.plans || [];
  renderPlans();
}

function renderPlans() {
  $("#plan-count").textContent = state.plans.length;
  const markup = state.plans.map((plan) => `
    <button class="plan-card ${state.selectedPlan?.id === plan.id ? "active" : ""}" data-plan-id="${plan.id}">
      <div class="row"><strong>${escapeHtml(plan.goal)}</strong><span class="state ${plan.status}">${plan.status}</span></div>
      <small>${plan.steps.length} 个步骤 · ${formatTime(plan.updated_at)}</small>
    </button>
  `).join("");
  $("#plan-list").innerHTML = markup || `<div class="empty-state small"><p>还没有任务计划</p></div>`;
  $("#recent-plans").innerHTML = state.plans.slice(0, 5).map((plan) => `
    <button class="plan-card" data-plan-id="${plan.id}" data-jump="tasks">
      <div class="row"><strong>${escapeHtml(plan.goal)}</strong><span class="state ${plan.status}">${plan.status}</span></div>
      <small>${formatTime(plan.updated_at)}</small>
    </button>
  `).join("") || `<div class="empty-state small"><p>新计划会出现在这里</p></div>`;
  renderStatus();
}

async function selectPlan(planId) {
  const bridge = await api(`/v1/plans/${planId}`);
  const bundle = unwrapBridge(bridge);
  state.selectedPlan = bundle.plan;
  state.selectedPlan.reflections = bundle.reflections || [];
  state.selectedPlan.retry_attempts = bundle.retry_attempts || [];
  state.selectedPlan.revisions = bundle.revisions || [];
  state.selectedPlan.verifications = bundle.verifications || [];
  renderPlans();
  renderPlanDetail();
}

function renderPlanDetail() {
  const plan = state.selectedPlan;
  if (!plan) return;
  const canRun = ["ready", "running"].includes(plan.status);
  const canPause = ["ready", "running"].includes(plan.status);
  const canResume = plan.status === "paused";
  const canCancel = !["completed", "cancelled"].includes(plan.status);
  $("#plan-detail").innerHTML = `
    <div class="detail-title">
      <p class="eyebrow">PLAN ${escapeHtml(plan.id.slice(0, 10).toUpperCase())}</p>
      <h2>${escapeHtml(plan.goal)}</h2>
      <p>创建于 ${formatTime(plan.created_at)} · 更新于 ${formatTime(plan.updated_at)}</p>
    </div>
    <div class="action-row">
      <button class="primary" data-plan-action="run" ${canRun ? "" : "disabled"}>执行</button>
      <button class="secondary" data-plan-action="pause" ${canPause ? "" : "disabled"}>暂停</button>
      <button class="secondary" data-plan-action="resume" ${canResume ? "" : "disabled"}>恢复</button>
      <button class="secondary" data-plan-action="reflect">反思失败</button>
      <button class="danger" data-plan-action="cancel" ${canCancel ? "" : "disabled"}>取消</button>
      <span class="state ${plan.status}">${plan.status}</span>
    </div>
    <div class="step-list">
      ${plan.steps.map((step, index) => `
        <article class="step ${step.status}">
          <div class="step-head"><h4>${index + 1}. ${escapeHtml(step.title)}</h4><span class="state ${step.status}">${step.status}</span></div>
          <p>${escapeHtml(step.description)}</p>
          ${step.tool_hint ? `<small>建议工具：${escapeHtml(step.tool_hint)}</small>` : ""}
          ${step.result ? `<pre>${escapeHtml(step.result)}</pre>` : ""}
          ${step.error ? `<pre>${escapeHtml(step.error)}</pre>` : ""}
        </article>
      `).join("")}
    </div>
    ${plan.reflections?.length ? `<div class="result-card"><header><strong>失败反思</strong><span>${plan.reflections.length} 条</span></header><p>${escapeHtml(plan.reflections.map((item) => `${item.failure_type}: ${item.root_cause} → ${item.suggested_action}`).join("\n"))}</p></div>` : ""}
    ${plan.verifications?.length ? `<div class="result-card"><header><strong>执行验证</strong><span>${plan.verifications.length} 条</span></header><p>${escapeHtml(plan.verifications.map((item) => `${item.step_id}: ${item.status} · ${item.summary}`).join("\n"))}</p></div>` : ""}
  `;
}

async function createPlan(goal, button) {
  if (!goal.trim()) return;
  setBusy(button, true, "正在规划…");
  try {
    const response = await api("/v1/plans", { method: "POST", body: JSON.stringify({ goal }) });
    const plan = unwrapBridge(response);
    toast("新计划已生成");
    await loadPlans();
    showView("tasks");
    await selectPlan(plan.id);
  } catch (error) { toast(error.message, "error"); }
  finally { setBusy(button, false); }
}

async function planAction(action, button) {
  const plan = state.selectedPlan;
  if (!plan) return;
  setBusy(button, true);
  try {
    await api(`/v1/plans/${plan.id}/${action}`, { method: "POST", body: "{}" });
    toast({ run: "执行完成", pause: "暂停请求已记录", resume: "计划已恢复", cancel: "计划已取消", reflect: "失败反思已更新" }[action] || "操作完成");
    await loadPlans();
    await selectPlan(plan.id);
  } catch (error) { toast(error.message, "error"); }
  finally { setBusy(button, false); }
}

async function sendChat(message, button) {
  const cleanMessage = message.trim();
  if (!cleanMessage) return;
  const log = $("#chat-log");
  log.insertAdjacentHTML("beforeend", `
    <div class="message user">
      <div class="message-avatar">YOU</div>
      <div class="message-body"><span>YOU · LOCAL</span><p>${escapeHtml(cleanMessage)}</p></div>
    </div>
  `);
  $("#chat-message").value = "";
  setBusy(button, true, "思考中…");
  const pendingId = `pending-${Date.now()}`;
  log.insertAdjacentHTML("beforeend", `
    <div class="message assistant pending" id="${pendingId}">
      <img class="message-avatar" src="/assets/vela-avatar.png" alt="">
      <div class="message-body">
        <span>VELA · PROCESSING</span>
        <p><i class="thinking-dot"></i><i class="thinking-dot"></i><i class="thinking-dot"></i>正在通过本地模型处理</p>
      </div>
    </div>
  `);
  log.scrollTop = log.scrollHeight;
  try {
    const result = await api("/v1/chat", {
      method: "POST",
      body: JSON.stringify({ message: cleanMessage }),
      timeout: 180000,
    });
    $(`#${pendingId}`)?.remove();
    state.lastFailedMessage = null;
    log.insertAdjacentHTML("beforeend", `
      <div class="message assistant">
        <img class="message-avatar" src="/assets/vela-avatar.png" alt="">
        <div class="message-body">
          <span>VELA · ${Number(result.steps || 1)} LOCAL STEP${Number(result.steps || 1) === 1 ? "" : "S"}</span>
          <p>${escapeHtml(result.output)}</p>
        </div>
      </div>
    `);
  } catch (error) {
    $(`#${pendingId}`)?.remove();
    state.lastFailedMessage = cleanMessage;
    const errorType = error.payload?.error?.type || "LocalConnectionError";
    log.insertAdjacentHTML("beforeend", `
      <div class="message assistant error">
        <img class="message-avatar" src="/assets/vela-avatar.png" alt="">
        <div class="message-body">
          <span>VELA · ${escapeHtml(errorType)}</span>
          <p>这次本地处理没有完成：${escapeHtml(error.message)}</p>
          <button class="secondary retry-chat" type="button" data-retry-chat>重试这条消息</button>
        </div>
      </div>
    `);
  } finally {
    setBusy(button, false);
    log.scrollTop = log.scrollHeight;
  }
}

async function loadKnowledge() {
  state.knowledge = await api("/v1/knowledge/status");
  $("#knowledge-stats").innerHTML = `
    <span>${state.knowledge.document_count} 个文档</span>
    <span>${state.knowledge.chunk_count} 个分块</span>
    <span>${(state.knowledge.database_size_bytes / 1024 / 1024).toFixed(1)} MB</span>
    <span>更新 ${formatTime(state.knowledge.last_indexed_at)}</span>`;
  renderStatus();
}

async function searchKnowledge(query, button) {
  setBusy(button, true);
  try {
    const result = await api("/v1/knowledge/search", { method: "POST", body: JSON.stringify({ query, limit: 8 }) });
    $("#knowledge-results").innerHTML = result.results.map((item) => `
      <article class="result-card">
        <header><code>${escapeHtml(item.citation)}</code><span>${Number(item.score).toFixed(3)}</span></header>
        <p>${escapeHtml(item.content)}</p>
      </article>
    `).join("") || `<div class="empty-state small"><p>没有找到足够相关的内容</p></div>`;
  } catch (error) { toast(error.message, "error"); }
  finally { setBusy(button, false); }
}

async function loadMemories() {
  const result = await api("/v1/memories");
  state.memories = result.memories || [];
  $("#memory-count").textContent = state.memories.length;
  $("#memory-list").innerHTML = state.memories.map((item) => `
    <article class="memory-item">
      <header><strong>${escapeHtml(item.memory_type)}</strong><button class="mini-button" data-delete-memory="${item.id}">删除</button></header>
      <p>${escapeHtml(item.content)}</p>
      <div class="memory-meta"><span>重要度 ${item.importance}</span><span>${escapeHtml(item.sensitivity)}</span><span>${formatTime(item.updated_at)}</span></div>
    </article>
  `).join("") || `<div class="empty-state small"><p>暂时没有长期记忆</p></div>`;
}

async function remember(content, button) {
  setBusy(button, true);
  try {
    await api("/v1/memories", {
      method: "POST",
      body: JSON.stringify({
        content,
        memory_type: $("#memory-type").value,
        importance: Number($("#memory-importance").value),
        sensitivity: $("#memory-sensitivity").value,
      }),
    });
    $("#memory-content").value = "";
    toast("记忆已保存在本地");
    await loadMemories();
  } catch (error) { toast(error.message, "error"); }
  finally { setBusy(button, false); }
}

async function deleteMemory(id) {
  try {
    await api(`/v1/memories/${id}`, { method: "DELETE" });
    toast("记忆已删除");
    await loadMemories();
  } catch (error) {
    if (error.status === 409) {
      toast("删除需要你的批准，已转到安全中心");
      await loadSafety();
      showView("safety");
    } else toast(error.message, "error");
  }
}

async function loadSafety() {
  const [confirmations, audit] = await Promise.all([
    api("/v1/confirmations"), api("/v1/audit"),
  ]);
  state.confirmations = (confirmations.confirmations || []).filter((item) => item.status === "pending");
  state.audit = audit.events || [];
  $("#confirmation-count").textContent = state.confirmations.length;
  $("#confirmation-list").innerHTML = state.confirmations.map((item) => `
    <article class="confirmation-item">
      <header><strong>${escapeHtml(item.action)}</strong><span class="state pending">${escapeHtml(item.risk)}</span></header>
      <p>${escapeHtml(item.description)}</p>
      <div class="confirmation-actions">
        <button class="primary" data-confirm="${item.confirmation_id}" data-decision="approve">批准一次</button>
        <button class="danger" data-confirm="${item.confirmation_id}" data-decision="reject">拒绝</button>
      </div>
    </article>
  `).join("") || `<div class="empty-state small"><span>⬡</span><p>没有待确认的高风险操作</p></div>`;
  $("#audit-list").innerHTML = state.audit.slice(0, 100).map((item) => `
    <article class="audit-item"><code>${escapeHtml(item.category)}</code><span>${escapeHtml(item.action)} · ${escapeHtml(item.outcome)}</span><time>${formatTime(item.created_at)}</time></article>
  `).join("") || `<div class="empty-state small"><p>还没有审计记录</p></div>`;
  renderStatus();
}

async function resolveConfirmation(id, decision, button) {
  setBusy(button, true);
  try {
    await api(`/v1/confirmations/${id}/${decision}`, { method: "POST", body: "{}" });
    toast(decision === "approve" ? "已批准一次" : "已拒绝");
    await loadSafety();
  } catch (error) { toast(error.message, "error"); }
  finally { setBusy(button, false); }
}

async function loadMcp() {
  try { state.mcp = await api("/v1/mcp/status"); }
  catch { state.mcp = { enabled: false, servers: [] }; }
  renderStatus();
}

async function testMcp(server, button) {
  if (!server) return;
  setBusy(button, true, "测试中…");
  try {
    const result = await api("/v1/mcp/test", { method: "POST", body: JSON.stringify({ server }) });
    toast(`MCP 链路正常：${result.probe?.echo || "OK"}`);
  } catch (error) { toast(error.message, "error"); }
  finally { setBusy(button, false); }
}

async function refreshAll() {
  const button = $("#refresh-all");
  setBusy(button, true, "…");
  try {
    await loadMeta();
    loadStatus().catch(() => {
      $("#system-pill").innerHTML = "<i></i>本地服务在线";
    });
    const results = await Promise.allSettled([
      loadPlans(),
      loadKnowledge(),
      loadMemories(),
      loadSafety(),
      loadMcp(),
    ]);
    const failed = results.filter((result) => result.status === "rejected");
    if (failed.length) {
      toast(`${failed.length} 个模块暂时未响应，其他功能仍可使用`, "error");
    } else {
      toast("本地状态已刷新");
    }
  } catch (error) {
    $("#system-pill").classList.add("offline");
    $("#system-pill").innerHTML = "<i></i>连接失败";
    toast(error.message, "error");
  } finally { setBusy(button, false); }
}

document.addEventListener("click", async (event) => {
  const nav = event.target.closest("[data-view]");
  if (nav) showView(nav.dataset.view);
  const jump = event.target.closest("[data-jump]");
  if (jump) showView(jump.dataset.jump);
  const plan = event.target.closest("[data-plan-id]");
  if (plan) { showView("tasks"); await selectPlan(plan.dataset.planId); }
  const action = event.target.closest("[data-plan-action]");
  if (action) await planAction(action.dataset.planAction, action);
  const remove = event.target.closest("[data-delete-memory]");
  if (remove) await deleteMemory(remove.dataset.deleteMemory);
  const confirmation = event.target.closest("[data-confirm]");
  if (confirmation) await resolveConfirmation(confirmation.dataset.confirm, confirmation.dataset.decision, confirmation);
  const mcp = event.target.closest("[data-mcp-test]");
  if (mcp) await testMcp(mcp.dataset.mcpTest, mcp);
  const retry = event.target.closest("[data-retry-chat]");
  if (retry && state.lastFailedMessage) {
    retry.closest(".message")?.remove();
    await sendChat(state.lastFailedMessage, $("#chat-form button[type='submit']"));
  }
});

$("#quick-plan-form").addEventListener("submit", (event) => {
  event.preventDefault();
  createPlan($("#quick-goal").value, event.submitter);
});
$("#plan-form").addEventListener("submit", (event) => {
  event.preventDefault();
  createPlan($("#plan-goal").value, event.submitter);
});
$("#chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  sendChat($("#chat-message").value, event.submitter);
});
$("#chat-message").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    $("#chat-form").requestSubmit();
  }
});
$("#knowledge-form").addEventListener("submit", (event) => {
  event.preventDefault();
  searchKnowledge($("#knowledge-query").value, event.submitter);
});
$("#index-knowledge").addEventListener("click", async (event) => {
  setBusy(event.currentTarget, true, "索引中…");
  try {
    const report = await api("/v1/knowledge/index", { method: "POST", body: "{}" });
    toast(`索引完成：更新 ${report.indexed_files} 个文件`);
    await loadKnowledge();
  } catch (error) { toast(error.message, "error"); }
  finally { setBusy(event.currentTarget, false); }
});
$("#memory-form").addEventListener("submit", (event) => {
  event.preventDefault();
  remember($("#memory-content").value, event.submitter);
});
$("#refresh-all").addEventListener("click", refreshAll);

refreshAll();
setInterval(loadStatus, 30000);
