/* ============================================================
   LQA 工作台 · 前端逻辑（零依赖单页）
   服务端为 api_server.py；本文件只做取数、渲染与交互，不做业务判断。
   
   安全：所有来自动态数据（用例字段、文件名、模型输出）的文本在插入 DOM 前
   一律经 esc() 转义，禁止字符串拼接 HTML。
   ============================================================ */
"use strict";

const $ = (id) => document.getElementById(id);
const API = "";

/* ---------- 全局状态 ---------- */
const state = {
  meta: null,
  cases: [],
  analysis: null,
  docText: "",
  fileName: "",
  skills: [],
  skillFormats: ["json"],
};

/* ============================================================
   工具
   ============================================================ */
function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function scoreClass(s) {
  if (s >= 75) return "ok";
  if (s >= 55) return "mid";
  return "low";
}

function fmtSize(n) {
  if (!n && n !== 0) return "";
  return n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`;
}

function toast(msg, kind = "info", ms = 3600) {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="t-dot"></span><span>${esc(msg)}</span>`;
  $("toasts").appendChild(el);
  setTimeout(() => el.remove(), ms);
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch { /* 非 JSON 错误体沿用状态码描述 */ }
    throw new Error(detail);
  }
  return res;
}

/* ============================================================
   主题
   ============================================================ */
function initTheme() {
  const saved = localStorage.getItem("lqa-theme") || "dark";
  setTheme(saved);
  document.querySelectorAll("[data-theme-set]").forEach((b) => {
    b.classList.toggle("active", b.dataset.themeSet === saved);
    b.onclick = () => setTheme(b.dataset.themeSet);
  });
}
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  localStorage.setItem("lqa-theme", t);
  document.querySelectorAll("[data-theme-set]").forEach((b) => {
    b.classList.toggle("active", b.dataset.themeSet === t);
  });
}

/* ============================================================
   导航
   ============================================================ */
function initNav() {
  document.querySelectorAll(".nav-item").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll(".nav-item").forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".view").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      $(`view-${b.dataset.view}`).classList.add("active");
      if (b.dataset.view === "library") loadLibrary();
      if (b.dataset.view === "skills") loadSkills();
      if (b.dataset.view === "settings") renderCurrentConf();
    };
  });
}

/** 从任意页面跳到指定视图（复用侧栏的 active 状态逻辑，不重复造轮子）。 */
function switchView(name) {
  const btn = document.querySelector(`.nav-item[data-view="${name}"]`);
  if (btn) btn.click();
}

function setStep(n) {
  document.querySelectorAll("#stepper .step").forEach((s, i) => {
    s.classList.toggle("done", i < n);
    s.classList.toggle("active", i === n - 1);
  });
}

/* ============================================================
   元信息装配
   ============================================================ */
async function loadMeta() {
  try {
    const meta = await (await api("/api/meta")).json();
    state.meta = meta;

    // 语言下拉
    const opts = meta.languages
      .map((l) => `<option value="${esc(l.code)}">${esc(l.label)}（${esc(l.code)}）</option>`)
      .join("");
    $("sourceLang").innerHTML = opts;
    $("targetLang").innerHTML = opts;
    $("sourceLang").value = meta.defaults.source_lang;
    $("targetLang").value = meta.defaults.target_lang;

    // Provider 下拉
    $("provider").innerHTML = meta.providers
      .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`)
      .join("");
    $("provider").value = meta.defaults.provider;

    // 类别 chips
    renderCatChips(meta, meta.core_categories);

    // 说明页类别表
    $("catTable").innerHTML = Object.entries(meta.categories)
      .map(([k, v]) => `<div class="cat-item"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`)
      .join("");

    $("envPathHint").textContent = `勾选后 Key 以明文写入 ${meta.env_path}`;
    updateAiHint();
  } catch (e) {
    toast(`元数据加载失败：${e.message}`, "bad", 8000);
  }
}

function catLabel(code) {
  const m = (state.meta && state.meta.categories) || {};
  return m[code] || code;
}

function loadCustomCats() {
  try {
    const raw = localStorage.getItem("lqa-custom-cats");
    state.customCats = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(state.customCats)) state.customCats = [];
  } catch {
    state.customCats = [];
  }
}

function saveCustomCats() {
  try {
    localStorage.setItem("lqa-custom-cats", JSON.stringify(state.customCats || []));
  } catch {}
}

function addCustomCat() {
  const v = ($("customCat").value || "").trim();
  if (!v) return;
  if ((state.customCats || []).includes(v)) {
    toast("该自定义类别已存在", "warn");
  } else {
    state.customCats = [...(state.customCats || []), v];
    saveCustomCats();
    toast(`已添加自定义类别：${v}`, "ok");
  }
  $("customCat").value = "";
  if (state.meta) renderCatChips(state.meta, getSelectedCats());
}

function removeCustomCat(text) {
  state.customCats = (state.customCats || []).filter((t) => t !== text);
  saveCustomCats();
  if (state.meta) renderCatChips(state.meta, getSelectedCats());
}

function renderCatChips(meta, selected) {
  const cur = new Set(getSelectedCats());
  const builtin = Object.entries(meta.categories).map(([k, v]) => {
    const on = selected.includes(k) || cur.has(k);
    return `<button class="chip ${on ? "on" : ""}" data-cat="${esc(k)}" title="${esc(meta.category_focus?.[k] || "")}">
      <span class="dot"></span>${esc(catLabel(k))}</button>`;
  });
  const custom = (state.customCats || []).map((t) => {
    const on = cur.has(t);
    return `<button class="chip custom ${on ? "on" : ""}" data-cat="${esc(t)}" title="自定义类别">
      <span class="dot"></span>${esc(t)}<span class="x" data-rm="${esc(t)}">×</span></button>`;
  });
  $("catChips").innerHTML = builtin.concat(custom).join("");
  document.querySelectorAll("#catChips .chip").forEach((c) => {
    c.onclick = (e) => {
      if (e.target.dataset.rm) {
        removeCustomCat(e.target.dataset.rm);
        return;
      }
      c.classList.toggle("on");
    };
  });
}

function getSelectedCats() {
  return [...document.querySelectorAll("#catChips .chip.on")].map((c) => c.dataset.cat);
}
$("catCore").onclick = () => renderCatChips(state.meta, state.meta.core_categories);
$("catAll").onclick = () => renderCatChips(state.meta, Object.keys(state.meta.categories));
$("catNone").onclick = () => renderCatChips(state.meta, []);

/* ============================================================
   技能库（领域测试知识包）
   技能数据来自 /api/skills（落盘 skills/，支持 json/md/yaml），生成时以 skill_ids 提交。
   ============================================================ */
function getSelectedSkillIds() {
  return [...document.querySelectorAll("#skillChips .chip.on")].map((c) => c.dataset.skill);
}

function renderSkillChips() {
  const box = $("skillChips");
  const cur = new Set(getSelectedSkillIds());
  const items = state.skills || [];
  if (!items.length) {
    box.innerHTML = `<span class="field-hint">技能库为空，请先到「技能库」页面创建。</span>`;
    updateSkillHint();
    return;
  }
  box.innerHTML = items
    .map((s) => {
      const on = cur.has(s.id);
      return `<button class="chip ${on ? "on" : ""}" data-skill="${esc(s.id)}"
        title="${esc(s.description || s.body.slice(0, 120))}">${esc(s.name)}</button>`;
    })
    .join("");
  box.querySelectorAll(".chip").forEach((c) => {
    c.onclick = () => {
      c.classList.toggle("on");
      updateSkillHint();
    };
  });
  updateSkillHint();
}

function updateSkillHint() {
  const n = getSelectedSkillIds().length;
  $("skillHint").textContent = n
    ? `已选 ${n} 个技能，将注入 AI 提示词（仅 AI 补强时生效）。`
    : "未选择技能。仅启用 AI 补强时生效。";
}

async function loadSkills() {
  try {
    const res = await api("/api/skills");
    const data = res ? await res.json() : {};
    state.skills = data.skills || [];
    state.skillFormats = data.formats || ["json"];
    renderSkillChips();
    renderSkillList();
  } catch (e) {
    toast(`技能加载失败：${e.message}`, "bad", 6000);
  }
}

function renderSkillList() {
  const box = $("skillList");
  const items = state.skills || [];
  if (!items.length) {
    box.innerHTML = `<div class="empty-hint">
      还没有技能。点击右上角「+ 新建技能」，把团队反复用到的领域检查要点沉淀下来。<br>
      例如：赛季结算边界、RTL 布局验收、德语文案长度规范。
    </div>`;
    return;
  }
  box.innerHTML = items
    .map(
      (s) => `<div class="skill-item">
        <div class="skill-main">
          <div class="skill-name">${esc(s.name)}<span class="skill-id">${esc(s.id)}</span></div>
          ${s.description ? `<div class="skill-desc">${esc(s.description)}</div>` : ""}
          <div class="skill-body">${esc(s.body)}</div>
          ${s.tags?.length
            ? `<div class="skill-tags">${s.tags.map((t) => `<span class="skill-tag">${esc(t)}</span>`).join("")}</div>`
            : ""}
        </div>
        <div class="skill-actions">
          <button class="btn sm" data-edit="${esc(s.id)}">编辑</button>
          <button class="btn sm danger" data-del="${esc(s.id)}">删除</button>
        </div>
      </div>`
    )
    .join("");

  box.querySelectorAll("[data-edit]").forEach((b) => {
    b.onclick = () => openSkillEditor(b.dataset.edit);
  });
  box.querySelectorAll("[data-del]").forEach((b) => {
    b.onclick = () => removeSkill(b.dataset.del);
  });
}

let editingSkillId = null;

function openSkillEditor(sid) {
  editingSkillId = sid || null;
  const s = sid ? state.skills.find((x) => x.id === sid) : null;
  $("skillEditorTitle").textContent = s ? "编辑技能" : "新建技能";
  $("skillName").value = s?.name || "";
  $("skillDesc").value = s?.description || "";
  $("skillBody").value = s?.body || "";
  $("skillTags").value = (s?.tags || []).join(", ");
  $("skillBodyCount").textContent = `${($("skillBody").value || "").length} 字`;
  // 落盘格式：新建时可任选（按后端注册状态启用/禁用选项）；
  // 编辑时展示当前格式但锁定——后端更新写回原格式、不迁移
  const fmtSel = $("skillFmt");
  const fmts = state.skillFormats || ["json"];
  [...fmtSel.options].forEach((o) => { o.disabled = !fmts.includes(o.value); });
  if (s) {
    fmtSel.value = s.fmt && fmts.includes(s.fmt) ? s.fmt : "json";
    fmtSel.disabled = true;
  } else {
    fmtSel.value = "json";
    fmtSel.disabled = false;
  }
  $("skillEditor").hidden = false;
  $("skillEditor").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function closeSkillEditor() {
  $("skillEditor").hidden = true;
  editingSkillId = null;
}

async function saveSkill() {
  const name = $("skillName").value.trim();
  const body = $("skillBody").value.trim();
  const description = $("skillDesc").value.trim();
  const tags = $("skillTags").value.split(/[,，]/).map((t) => t.trim()).filter(Boolean);
  if (!name) return toast("技能名称不能为空", "bad");
  if (!body) return toast("知识正文不能为空（该内容会注入 AI 提示词）", "bad");

  const isNew = !editingSkillId;
  const payload = { name, body, description, tags };
  if (isNew) payload.fmt = $("skillFmt").value;
  try {
    const res = editingSkillId
      ? await api(`/api/skills/${encodeURIComponent(editingSkillId)}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        })
      : await api("/api/skills", { method: "POST", body: JSON.stringify(payload) });
    const saved = await res.json();
    toast(isNew ? "技能已创建" : "技能已更新", "ok");
    closeSkillEditor();
    await loadSkills();
    // 新建后自动选中，让用户立刻看到它生效
    if (isNew && saved?.id) {
      const chip = document.querySelector(`#skillChips .chip[data-skill="${CSS.escape(saved.id)}"]`);
      if (chip) chip.classList.add("on");
      updateSkillHint();
    }
  } catch (e) {
    toast(`保存失败：${e.message}`, "bad", 6000);
  }
}

async function removeSkill(sid) {
  const s = state.skills.find((x) => x.id === sid);
  if (!confirm(`确定删除技能「${s?.name || sid}」？该操作不可撤销。`)) return;
  try {
    await api(`/api/skills/${encodeURIComponent(sid)}`, { method: "DELETE" });
    toast("技能已删除", "info");
    await loadSkills();
  } catch (e) {
    toast(`删除失败：${e.message}`, "bad", 6000);
  }
}

/* ============================================================
   文件上传
   ============================================================ */
function initUpload() {
  const dz = $("dropzone");
  const input = $("fileInput");

  dz.onclick = (e) => { if (e.target.id !== "fileClear") input.click(); };
  input.onchange = () => input.files?.[0] && upload(input.files[0]);

  ["dragenter", "dragover"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); })
  );
  ["dragleave", "drop"].forEach((ev) =>
    dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); })
  );
  dz.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files?.[0];
    if (f) upload(f);
  });

  $("fileClear").onclick = (e) => {
    e.stopPropagation();
    state.docText = "";
    state.fileName = "";
    input.value = "";
    $("fileChip").hidden = true;
    toast("已移除上传文件", "info", 2000);
  };
}

async function upload(file) {
  const fd = new FormData();
  fd.append("file", file);
  setProgress(true, `解析 ${file.name}…`);
  try {
    const res = await fetch(API + "/api/parse", { method: "POST", body: fd });
    if (!res.ok) {
      let detail = "解析失败";
      try { detail = (await res.json()).detail || detail; } catch { /* 保持默认文案 */ }
      throw new Error(detail);
    }
    const data = await res.json();
    state.docText = data.text;
    state.fileName = data.filename;
    $("fileChip").hidden = false;
    $("fileName").textContent = data.filename;
    $("fileMeta").textContent = `${data.chars} 字符 · ${fmtSize(file.size)}`;
    toast(`解析成功：${data.chars} 字符`, "ok");
    setStep(1);
  } catch (e) {
    toast(`上传失败：${e.message}`, "bad", 6000);
  } finally {
    setProgress(false);
  }
}

/* ============================================================
   进度
   ============================================================ */
function setProgress(on, text = "处理中…") {
  $("progressWrap").hidden = !on;
  $("progressText").textContent = text;
  setBusy(on, text);
}

function setBusy(on, text = "") {
  $("btnGenerate").disabled = on;
  $("btnAnalyze").disabled = on;
  const dot = $("engineDot");
  dot.className = `mini-dot ${on ? "run" : state.cases.length ? "ok" : ""}`;
  if (text) $("engineText").textContent = text;
  else $("engineText").textContent = state.cases.length ? `${state.cases.length} 条就绪` : "等待生成";
}

/* ============================================================
   分析
   ============================================================ */
async function analyze() {
  const text = mergedText();
  if (!text.trim()) {
    toast("请先上传文档或粘贴需求文本", "warn");
    return null;
  }
  setProgress(true, "拆解需求点…");
  try {
    const data = await (await api("/api/analyze", {
      method: "POST",
      body: JSON.stringify({ text }),
    })).json();
    state.analysis = data;
    renderAnalysis(data);
    toast(`拆解完成：${data.points.length} 个需求点`, "ok");
    setStep(2);
    return data;
  } catch (e) {
    toast(`分析失败：${e.message}`, "bad", 6000);
    return null;
  } finally {
    setProgress(false);
  }
}

function mergedText() {
  const paste = $("pasteText").value.trim();
  if (state.docText && paste) return `${state.docText}\n\n${paste}`;
  return state.docText || paste;
}

function renderAnalysis(data) {
  $("analysisCard").hidden = false;
  $("analysisBadge").textContent = data.summary;
  $("moduleRow").innerHTML = data.modules
    .map((m) => `<span class="badge cat">${esc(m)}</span>`)
    .join("");
  $("pointsBody").innerHTML = data.points
    .map(
      (p) => `<tr>
        <td style="color:var(--text-faint)">${p.index}</td>
        <td><strong>${esc(p.module)}</strong></td>
        <td>${esc(p.text)}</td>
      </tr>`
    )
    .join("");
}

/* ============================================================
   生成
   ============================================================ */
async function generate() {
  const text = mergedText();
  if (!text.trim()) {
    toast("请先上传文档或粘贴需求文本", "warn");
    return;
  }
  const cats = getSelectedCats();
  const useAi = $("useAi").checked;

  if (!state.analysis) await analyze();
  if (!state.analysis) return;

  setProgress(true, useAi ? "调用模型补强…" : "规则打底…");
  try {
    const data = await (await api("/api/generate", {
      method: "POST",
      body: JSON.stringify({
        text,
        task_name: $("taskName").value || "本地化需求",
        source_lang: $("sourceLang").value,
        target_lang: $("targetLang").value,
        count: parseInt($("count").value) || 0,
        categories: cats,
        extra: $("extra").value,
        use_ai: useAi,
        skill_ids: getSelectedSkillIds(),
      }),
    })).json();

    state.cases = data.cases || [];
    renderResult(data);
    setStep(3);
    toast(`生成 ${state.cases.length} 条用例 · 引擎 ${data.generator}`, "ok");
    if (data.ai_error) toast(data.ai_error, "warn", 6000);
  } catch (e) {
    toast(`生成失败：${e.message}`, "bad", 8000);
  } finally {
    setProgress(false);
  }
}

function renderResult(data) {
  $("wizardEmpty").hidden = true;
  $("resultCard").hidden = false;

  const g = data.gate || {};
  const avg = g.avg_score ?? data.avg_score ?? 0;
  const issue = g.issue_count ?? 0;

  $("metrics").innerHTML = [
    { l: "用例数", v: g.count ?? state.cases.length, c: "" },
    { l: "平均质量分", v: avg, c: scoreClass(avg) },
    { l: "门禁问题", v: issue, c: issue === 0 ? "ok" : "warn" },
    { l: "生成引擎", v: data.generator || "-", c: "" },
  ]
    .map(
      (m) => `<div class="metric">
        <span class="metric-label">${esc(m.l)}</span>
        <span class="metric-value ${m.c}">${esc(m.v)}</span>
      </div>`
    )
    .join("");

  renderCases();

  const issues = g.issues || [];
  $("gateBox").innerHTML = issue === 0
    ? `<span class="badge ok">全部通过门禁</span><span style="color:var(--text-faint)">共 ${g.count} 条，最低分 ${g.min_score ?? "-"}</span>`
    : `<span class="badge warn">${issue} 项待优化</span>
       <span style="color:var(--text-faint)">${esc(issues.slice(0, 3).join(" · "))}${issues.length > 3 ? " …" : ""}</span>`;
}

function renderCases() {
  const q = $("caseSearch").value.trim().toLowerCase();
  const rows = state.cases
    .map((c, i) => ({ c, i }))
    .filter(({ c }) =>
      !q ||
      `${c.module} ${c.feature} ${c.category} ${c.priority}`.toLowerCase().includes(q)
    );

  $("casesEmpty").hidden = rows.length > 0;
  $("casesBody").innerHTML = rows
    .map(({ c, i }) => {
      const s = +c.quality_score || 0;
      return `<tr data-idx="${i}">
        <td class="col-toggle"><span class="row-arrow">›</span></td>
        <td style="color:var(--text-faint);font-variant-numeric:tabular-nums">LQA-${String(i + 1).padStart(3, "0")}</td>
        <td><strong>${esc(c.module)}</strong></td>
        <td style="min-width:170px">${esc(c.feature)}</td>
        <td><span class="badge cat">${esc(catLabel(c.category))}</span></td>
        <td><span class="badge pri ${esc(c.priority)}">${esc(c.priority)}</span></td>
        <td>
          <div class="score-wrap">
            <span class="score-bar"><span class="score-fill" style="width:${Math.max(0, Math.min(100, s))}%;background:${
              s >= 75 ? "var(--ok)" : s >= 55 ? "var(--warn)" : "var(--bad)"
            }"></span></span>
            <span class="score-num ${scoreClass(s)}">${s}</span>
          </div>
        </td>
      </tr>`;
    })
    .join("");

  document.querySelectorAll("#casesBody tr").forEach((tr) => {
    tr.onclick = () => openDrawer(+tr.dataset.idx, tr);
  });
}

/* ============================================================
   用例详情抽屉
   ============================================================ */
function openDrawer(idx, tr) {
  const c = state.cases[idx];
  if (!c) return;
  document.querySelectorAll("#casesBody .row-arrow").forEach((a) => a.classList.remove("open"));
  tr?.querySelector(".row-arrow")?.classList.add("open");

  $("drawerId").textContent = `LQA-${String(idx + 1).padStart(3, "0")}`;
  $("drawerTitle").textContent = c.feature || "(无功能点)";

  const blocks = [
    ["模块 / 优先级", `${c.module} · ${c.priority} · ${catLabel(c.category)}`],
    ["语言", `${c.source_lang} → ${c.target_lang}`],
  ];

  $("drawerBody").innerHTML = `
    <div class="dl-grid">
      ${blocks.map(([k, v]) => `<div class="dl-block"><div class="dl-key">${esc(k)}</div><div class="dl-val">${esc(v)}</div></div>`).join("")}
    </div>
    ${c.source_text || c.target_text ? `
    <div class="dl-grid">
      <div class="dl-block bilingual-src"><div class="dl-key">源文案（${esc(c.source_lang)}）</div>
        <div class="dl-val mono">${esc(c.source_text || "—")}</div></div>
      <div class="dl-block bilingual-tgt"><div class="dl-key">目标文案（${esc(c.target_lang)}）</div>
        <div class="dl-val mono">${esc(c.target_text || "—")}</div></div>
    </div>` : ""}
    <div class="dl-row"><div class="dl-key">前置条件</div><div class="dl-val">${esc(c.preconditions || "—")}</div></div>
    <div class="dl-row"><div class="dl-key">操作步骤</div><div class="dl-val">${esc(c.steps || "—")}</div></div>
    <div class="dl-row"><div class="dl-key">预期结果</div><div class="dl-val">${esc(c.expected || "—")}</div></div>
    ${c.notes ? `<div class="dl-row"><div class="dl-key">备注（质量分 ${+c.quality_score || 0}）</div><div class="dl-val">${esc(c.notes)}</div></div>` : ""}
  `;

  $("drawer").hidden = false;
  $("drawerMask").hidden = false;
}

function closeDrawer() {
  $("drawer").hidden = true;
  $("drawerMask").hidden = true;
  document.querySelectorAll("#casesBody .row-arrow").forEach((a) => a.classList.remove("open"));
}

/* ============================================================
   导出
   ============================================================ */
async function downloadXlsx() {
  if (!state.cases.length) return toast("没有可导出的用例", "warn");
  try {
    const res = await api("/api/export", {
      method: "POST",
      body: JSON.stringify({ cases: state.cases, task_name: $("taskName").value || "需求" }),
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `LQA_${$("taskName").value || "需求"}.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
    toast("已下载 Excel", "ok");
  } catch (e) {
    toast(`导出失败：${e.message}`, "bad");
  }
}

async function saveOutputs() {
  if (!state.cases.length) return toast("没有可保存的用例", "warn");
  try {
    const data = await (await api("/api/save", {
      method: "POST",
      body: JSON.stringify({ cases: state.cases, task_name: $("taskName").value || "需求" }),
    })).json();
    toast(`已保存 ${data.count} 条到 outputs/`, "ok", 6000);
  } catch (e) {
    toast(`保存失败：${e.message}`, "bad");
  }
}

/* ============================================================
   模型配置
   ============================================================ */
function modelPayload() {
  return {
    provider: $("provider").value,
    base_url: $("baseUrl").value || null,
    model: $("modelName").value || null,
    api_key: $("apiKey").value || null,
  };
}

async function testConn() {
  if (!$("apiKey").value) return toast("请先填写 API Key", "warn");
  $("btnTestConn").disabled = true;
  try {
    const data = await (await api("/api/settings/test", {
      method: "POST",
      body: JSON.stringify(modelPayload()),
    })).json();
    showNotice(data.message, data.ok ? "ok" : "bad");
    renderCurrentConf(data.settings);
  } catch (e) {
    showNotice(`连通失败：${e.message}`, "bad");
  } finally {
    $("btnTestConn").disabled = false;
  }
}

async function saveSettings() {
  const persist = $("persistKey").checked;
  if (persist && !$("apiKey").value) return toast("勾选落盘时请填写 API Key", "warn");
  try {
    const data = await (await api("/api/settings/save", {
      method: "POST",
      body: JSON.stringify({ ...modelPayload(), persist }),
    })).json();
    if (data.persisted) {
      showNotice(`已写入 ${data.path}（明文存储，请注意本机安全）`, "ok");
      toast("Key 已明文写入 .env，请勿提交到版本库", "warn", 7000);
    } else {
      showNotice("配置已应用到本次会话（未写入磁盘）", "ok");
    }
    renderCurrentConf(data.settings);
    updateAiHint();
  } catch (e) {
    showNotice(`保存失败：${e.message}`, "bad");
  }
}

function showNotice(msg, kind = "") {
  const n = $("settingsNotice");
  n.textContent = msg;
  n.className = `notice show ${kind}`;
}

function renderCurrentConf(s) {
  const d = (state.meta?.defaults) || {};
  const conf = s || d;
  const items = [
    ["Provider", conf.provider],
    ["Model", conf.model],
    ["Base URL", conf.base_url],
    ["API Key", conf.api_key_masked || "未配置"],
  ];
  $("currentConf").innerHTML = items
    .map(([k, v]) => `<div class="conf-item"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`)
    .join("");
}

function updateAiHint() {
  const has = state.meta?.defaults?.has_api_key || $("apiKey").value;
  $("aiHint").textContent = has
    ? "Key 已就绪，可在「生成向导」勾选启用"
    : "需先在「模型配置」填入 API Key";
}

/* ============================================================
   参考案例库
   ============================================================ */
async function loadLibrary() {
  try {
    const data = await (await api("/api/case-library")).json();
    if (!data.files.length) {
      $("libList").innerHTML = `<div class="empty-hint">案例库为空，可把历史 LQA 文件放入 case_library/ 目录</div>`;
      return;
    }
    $("libList").innerHTML = data.files
      .map(
        (f) => `<div class="lib-item">
          <span class="lib-ico">▤</span>
          <span class="lib-name">${esc(f.name)}</span>
          <span class="lib-meta">${esc(fmtSize(f.size))} · ${esc(f.modified)}</span>
        </div>`
      )
      .join("");
  } catch (e) {
    toast(`案例库加载失败：${e.message}`, "bad");
  }
}

/* ============================================================
   绑定
   ============================================================ */
function initBindings() {
  loadCustomCats();
  $("count").oninput = () => {
    const v = parseInt($("count").value) || 0;
    $("countVal").textContent = v ? String(v) : "不限";
  };
  $("btnAddCat").onclick = addCustomCat;
  $("customCat").onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); addCustomCat(); } };

  $("pasteText").oninput = () => {
    $("pasteHint").textContent = `${$("pasteText").value.length} 字符`;
  };

  $("btnAnalyze").onclick = analyze;
  $("btnGenerate").onclick = generate;
  $("btnDownload").onclick = downloadXlsx;
  $("btnSave").onclick = saveOutputs;
  $("btnReloadLib").onclick = loadLibrary;
  $("btnReloadSkills").onclick = loadSkills;
  $("btnSkillNew").onclick = () => openSkillEditor(null);
  $("btnSkillSave").onclick = saveSkill;
  $("btnSkillCancel").onclick = closeSkillEditor;
  $("skillEditorClose").onclick = closeSkillEditor;
  $("skillGoLib").onclick = () => switchView("skills");
  $("skillBody").oninput = () => {
    $("skillBodyCount").textContent = `${$("skillBody").value.length} 字`;
  };
  updateSkillHint();
  $("btnTestConn").onclick = testConn;
  $("btnSaveSettings").onclick = saveSettings;
  $("caseSearch").oninput = renderCases;

  $("drawerClose").onclick = closeDrawer;
  $("drawerMask").onclick = closeDrawer;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeDrawer(); });

  $("btnReset").onclick = () => {
    state.cases = [];
    state.analysis = null;
    state.docText = "";
    $("pasteText").value = "";
    $("pasteHint").textContent = "0 字符";
    $("fileInput").value = "";
    $("fileChip").hidden = true;
    $("resultCard").hidden = true;
    $("analysisCard").hidden = true;
    $("wizardEmpty").hidden = false;
    setStep(1);
    setBusy(false);
    toast("已重置", "info", 1800);
  };

  $("btnStop").onclick = stopService;
}

let _stopConfirmTimer = null;

async function stopService() {
  const btn = $("btnStop");
  // 两步确认：避免误触；且不依赖任何环境被禁用的 window.confirm
  if (btn.dataset.confirming !== "1") {
    btn.dataset.confirming = "1";
    btn.classList.add("confirming");
    btn.textContent = "再次点击确认退出";
    clearTimeout(_stopConfirmTimer);
    _stopConfirmTimer = setTimeout(() => {
      btn.dataset.confirming = "0";
      btn.classList.remove("confirming");
      btn.textContent = "⏻ 退出服务";
    }, 4000);
    return;
  }
  // 确认阶段：执行退出
  clearTimeout(_stopConfirmTimer);
  btn.dataset.confirming = "0";
  btn.classList.remove("confirming");
  btn.disabled = true;
  btn.textContent = "停止中…";
  try {
    const r = await fetch("/api/shutdown", { method: "POST" });
    if (r.ok) {
      toast("服务已停止，可关闭此页面", "ok");
      btn.textContent = "已停止";
      return;
    }
    const d = await r.json().catch(() => ({}));
    toast(d.detail || "停止失败，请改用 stop_web.bat / 直接关闭进程", "err", 6000);
  } catch (e) {
    // 服务可能在返回 200 前已关闭连接，视为已停止
    toast("服务已停止，可关闭此页面", "ok");
    btn.textContent = "已停止";
    return;
  }
  // 走到这里说明失败，恢复按钮
  btn.disabled = false;
  btn.textContent = "⏻ 退出服务";
}

/* ---------- 启动 ---------- */
initTheme();
initNav();
initUpload();
initBindings();
loadMeta();
loadSkills();
setStep(1);
