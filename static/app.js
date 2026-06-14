"use strict";

// ---- 상태 ----
let pollTimer = null;
let pollInterval = 5000;

// ---- API 헬퍼 ----
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  let body = null;
  try { body = await res.json(); } catch (_) { /* no body */ }
  if (!res.ok) {
    const msg = (body && body.error) || `오류 (${res.status})`;
    throw new Error(msg);
  }
  return body;
}

// ---- 렌더링 ----
const STATE_LABEL = {
  running: "Running",
  stopped: "Idle / Stopped",
  error: "Error",
};

function statusTag(state) {
  const cls = { running: "tag-running", stopped: "tag-stopped", error: "tag-error" }[state] || "tag-stopped";
  return `<span class="tag ${cls}">${STATE_LABEL[state] || state}</span>`;
}

const SCHEDULER_LABEL = {
  always_on: "상시 실행",
  cron: "Cron",
  launchagent: "LaunchAgent",
  manual: "수동",
};

function scheduleSummary(p) {
  // 저장된 값 우선, 없으면 리프레시 시 라이브 매칭된 detected 사용
  const expr = p.schedule_expr || (p.detected && p.detected.schedule_expr);
  const plist = p.plist_path || (p.detected && p.detected.plist_path);
  const live = !p.schedule_expr && !p.plist_path && p.detected ? " <span class=\"badge-live\">자동탐지</span>" : "";

  if (p.scheduler_type === "cron" && expr) {
    return `Cron: <span class="mono">${escapeHtml(expr)}</span>${live}`;
  }
  if (p.scheduler_type === "launchagent" && plist) {
    return `LaunchAgent: <span class="mono">${escapeHtml(basename(plist))}</span>${live}`;
  }
  return SCHEDULER_LABEL[p.scheduler_type] || p.scheduler_type;
}

function fmtNextRun(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d)) return "-";
  const pad = (n) => String(n).padStart(2, "0");
  const s = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return `${s} 예정`;
}

function renderCard(p) {
  const st = p.status || { state: "stopped" };
  const running = st.state === "running";
  const pidInfo = running && st.pid
    ? `PID ${st.pid}${st.detected_by ? ` · ${st.detected_by}` : ""}`
    : "";

  // F-403: 동적 버튼 전환
  const actionBtn = running
    ? `<button class="btn btn-stop btn-sm" onclick="onStop('${p.id}')">■ 강제 중지</button>`
    : `<button class="btn btn-run btn-sm" onclick="onRun('${p.id}')">▶ 바로 실행</button>`;

  return `
    <div class="card" data-id="${p.id}">
      <div class="card-head">
        <div>
          <div class="card-title">${escapeHtml(p.name)}</div>
          ${p.description ? `<div class="card-desc">${escapeHtml(p.description)}</div>` : ""}
        </div>
        ${statusTag(st.state)}
      </div>

      <dl class="meta">
        <dt>스케줄</dt><dd>${scheduleSummary(p)}</dd>
        <dt>실행 예정</dt><dd>${fmtNextRun(p.next_run)}</dd>
        <dt>스크립트</dt><dd class="mono">${escapeHtml(p.script_path)}</dd>
        ${pidInfo ? `<dt>프로세스</dt><dd class="mono">${pidInfo}</dd>` : ""}
      </dl>

      <div class="card-actions">
        ${actionBtn}
        <button class="btn btn-ghost btn-sm" onclick="onLogs('${p.id}','${escapeAttr(p.name)}')">로그</button>
        <span class="spacer"></span>
        <button class="btn btn-ghost btn-sm" onclick="onEdit('${p.id}')">수정</button>
        <button class="btn btn-ghost btn-sm" onclick="onDelete('${p.id}')">삭제</button>
      </div>
    </div>`;
}

async function refresh() {
  try {
    const projects = await api("/api/projects");
    const grid = document.getElementById("grid");
    const empty = document.getElementById("empty-state");
    if (!projects.length) {
      grid.innerHTML = "";
      empty.classList.remove("hidden");
    } else {
      empty.classList.add("hidden");
      grid.innerHTML = projects.map(renderCard).join("");
    }
    const now = new Date();
    document.getElementById("last-updated").textContent =
      `갱신: ${now.toLocaleTimeString()}`;
  } catch (e) {
    toast(e.message, true);
  }
}

// ---- 액션 ----
async function onRun(id) {
  try {
    await api(`/api/projects/${id}/run`, { method: "POST" });
    toast("실행했습니다.");
    await refresh();
  } catch (e) { toast(e.message, true); }
}

async function onStop(id) {
  if (!confirm("프로세스를 강제 중지하시겠습니까?")) return;
  try {
    await api(`/api/projects/${id}/stop`, { method: "POST" });
    toast("중지했습니다.");
    await refresh();
  } catch (e) { toast(e.message, true); }
}

async function onDelete(id) {
  if (!confirm("이 프로젝트를 대시보드에서 삭제하시겠습니까?")) return;
  try {
    await api(`/api/projects/${id}`, { method: "DELETE" });
    toast("삭제했습니다.");
    await refresh();
  } catch (e) { toast(e.message, true); }
}

async function onLogs(id, name) {
  try {
    const data = await api(`/api/projects/${id}/logs?lines=200`);
    document.getElementById("log-title").textContent = name;
    document.getElementById("log-content").textContent = data.log || "(로그 없음)";
    document.getElementById("log-modal").classList.remove("hidden");
  } catch (e) { toast(e.message, true); }
}
function closeLogModal() {
  document.getElementById("log-modal").classList.add("hidden");
}

// ---- 모달 (추가/수정) ----
function openModal() {
  document.getElementById("modal-title").textContent = "프로젝트 추가";
  document.getElementById("project-form").reset();
  document.getElementById("f-id").value = "";
  document.getElementById("form-error").classList.add("hidden");
  toggleSchedulerRows();
  document.getElementById("modal").classList.remove("hidden");
}
function closeModal() {
  document.getElementById("modal").classList.add("hidden");
}

async function onEdit(id) {
  try {
    const p = await api(`/api/projects/${id}`);
    document.getElementById("modal-title").textContent = "프로젝트 수정";
    document.getElementById("f-id").value = p.id;
    document.getElementById("f-name").value = p.name || "";
    document.getElementById("f-description").value = p.description || "";
    document.getElementById("f-script_path").value = p.script_path || "";
    document.getElementById("f-command").value = p.command || "";
    document.getElementById("f-python_path").value = p.python_path || "";
    document.getElementById("f-working_dir").value = p.working_dir || "";
    document.getElementById("f-args").value = (p.args || []).join(" ");
    document.getElementById("f-scheduler_type").value = p.scheduler_type || "manual";
    document.getElementById("f-schedule_expr").value = p.schedule_expr || "";
    document.getElementById("f-plist_path").value = p.plist_path || "";
    document.getElementById("form-error").classList.add("hidden");
    toggleSchedulerRows();
    document.getElementById("modal").classList.remove("hidden");
  } catch (e) { toast(e.message, true); }
}

function toggleSchedulerRows() {
  const t = document.getElementById("f-scheduler_type").value;
  document.getElementById("row-cron").classList.toggle("hidden", t !== "cron");
  document.getElementById("row-plist").classList.toggle("hidden", t !== "launchagent");
}

// cron/launchagent 선택 시 OS 에 이미 등록된 스케줄을 1회 조회해 자동 채움
async function onSchedulerChange() {
  toggleSchedulerRows();
  const t = document.getElementById("f-scheduler_type").value;
  if (t !== "cron" && t !== "launchagent") return;
  const scriptPath = document.getElementById("f-script_path").value.trim();
  if (!scriptPath) {
    toast("먼저 스크립트 경로를 입력하면 등록된 스케줄을 자동 조회합니다.");
    return;
  }
  try {
    const det = await api(`/api/system/detect?script_path=${encodeURIComponent(scriptPath)}`);
    if (!det.found) {
      toast("시스템에 등록된 스케줄을 찾지 못했습니다.");
      return;
    }
    if (det.scheduler_type === "cron" && det.schedule_expr) {
      document.getElementById("f-schedule_expr").value = det.schedule_expr;
      toast(`등록된 cron 발견: ${det.schedule_expr}`);
    } else if (det.scheduler_type === "launchagent" && det.plist_path) {
      document.getElementById("f-plist_path").value = det.plist_path;
      toast(`등록된 LaunchAgent 발견: ${basename(det.plist_path)}`);
    }
  } catch (e) {
    toast(e.message, true);
  }
}

async function onSubmit(e) {
  e.preventDefault();
  const id = document.getElementById("f-id").value;
  const payload = {
    name: document.getElementById("f-name").value,
    description: document.getElementById("f-description").value,
    script_path: document.getElementById("f-script_path").value,
    command: document.getElementById("f-command").value,
    python_path: document.getElementById("f-python_path").value,
    working_dir: document.getElementById("f-working_dir").value,
    args: document.getElementById("f-args").value,
    scheduler_type: document.getElementById("f-scheduler_type").value,
    schedule_expr: document.getElementById("f-schedule_expr").value,
    plist_path: document.getElementById("f-plist_path").value,
  };
  try {
    if (id) {
      await api(`/api/projects/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/api/projects", { method: "POST", body: JSON.stringify(payload) });
    }
    closeModal();
    toast("저장했습니다.");
    await refresh();
  } catch (err) {
    const el = document.getElementById("form-error");
    el.textContent = err.message;
    el.classList.remove("hidden");
  }
}

// ---- 파일/디렉토리 탐색기 ----
let fsTargetField = null;   // 선택 결과를 채울 input id
let fsMode = "file";        // "file" | "dir"
let fsCurrentPath = "";

async function openBrowser(targetFieldId, mode) {
  fsTargetField = targetFieldId;
  fsMode = mode || "file";
  document.getElementById("fs-select-dir").classList.toggle("hidden", fsMode !== "dir");
  // 입력란에 이미 경로가 있으면 그 위치에서 시작
  const cur = document.getElementById(targetFieldId).value.trim();
  await fsLoad(cur || "");
  document.getElementById("fs-modal").classList.remove("hidden");
}
function closeBrowser() {
  document.getElementById("fs-modal").classList.add("hidden");
}

async function fsLoad(path) {
  try {
    const data = await api(`/api/fs?path=${encodeURIComponent(path)}`);
    fsCurrentPath = data.path;
    document.getElementById("fs-path").textContent = data.path;

    const rows = [];
    if (data.parent) {
      rows.push(`<div class="fs-item fs-dir" onclick="fsLoad('${escapeAttr(data.parent)}')">📂 ..</div>`);
    }
    for (const d of data.dirs) {
      rows.push(`<div class="fs-item fs-dir" onclick="fsLoad('${escapeAttr(d.path)}')">📁 ${escapeHtml(d.name)}</div>`);
    }
    if (fsMode === "file") {
      for (const f of data.files) {
        rows.push(`<div class="fs-item fs-file" onclick="fsPick('${escapeAttr(f.path)}')">📄 ${escapeHtml(f.name)}</div>`);
      }
    }
    document.getElementById("fs-list").innerHTML =
      rows.join("") || `<div class="muted" style="padding:12px">(항목 없음)</div>`;
  } catch (e) {
    toast(e.message, true);
  }
}

function fsPick(path) {
  if (fsTargetField) document.getElementById(fsTargetField).value = path;
  closeBrowser();
}
function selectCurrentDir() {
  fsPick(fsCurrentPath);
}

// ---- 유틸 ----
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(s) { return escapeHtml(s).replace(/'/g, "\\'"); }
function basename(p) { return String(p).split("/").pop(); }

let toastTimer = null;
function toast(msg, isErr = false) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.toggle("err", isErr);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2800);
}

// ---- 초기화 ----
async function init() {
  try {
    const cfg = await api("/api/config");
    pollInterval = (cfg.ui_poll_sec || 5) * 1000;
  } catch (_) { /* 기본값 사용 */ }

  document.getElementById("btn-add").addEventListener("click", openModal);
  document.getElementById("btn-refresh").addEventListener("click", refresh);
  document.getElementById("project-form").addEventListener("submit", onSubmit);
  document.getElementById("f-scheduler_type").addEventListener("change", onSchedulerChange);

  // 백드롭 클릭 시 닫기
  document.getElementById("modal").addEventListener("click", (e) => {
    if (e.target.id === "modal") closeModal();
  });
  document.getElementById("log-modal").addEventListener("click", (e) => {
    if (e.target.id === "log-modal") closeLogModal();
  });
  document.getElementById("fs-modal").addEventListener("click", (e) => {
    if (e.target.id === "fs-modal") closeBrowser();
  });

  await refresh();
  pollTimer = setInterval(refresh, pollInterval);
}

document.addEventListener("DOMContentLoaded", init);
