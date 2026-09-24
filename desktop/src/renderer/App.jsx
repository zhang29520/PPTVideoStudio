import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, runTask } from "./api";

const APP_VERSION = "0.5.4";
const ORANGE = "#FF6B35";
const ORANGE_SOFT = "#FFF3EC";
const INK = "#26221E";
const MUTED = "#9B948D";
const LINE = "#ECE7E1";
const SIDE = "#201B16";
const SIDE_HOVER = "#2C261F";

/* ---------- 线性图标（iconfont 同风格 SVG） ---------- */
const Icon = ({ d, size = 17, extra }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor"
    strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
    {Array.isArray(d) ? d.map((p, i) => <path key={i} d={p} />) : <path d={d} />}
    {extra}
  </svg>
);
const ICONS = {
  home: ["M3 10.5 12 3l9 7.5", "M5 9.5V21h14V9.5"],
  script: ["M12 20h9", "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"],
  audio: ["M9 2h6a0 0 0 0 1 0 0v10a3 3 0 0 1-6 0V2a0 0 0 0 1 0 0Z", "M5 10a7 7 0 0 0 14 0", "M12 17v4"],
  video: ["M2 7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2Z", "m22 8-6 4 6 4V8Z"],
  settings: ["M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.1-.4.1-.8.1-1.2Z"],
  upload: ["M12 16V4", "m7 9 5-5 5 5", "M20 16v3a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-3"],
  arrowR: "m13 6 6 6-6 6M5 12h14",
  arrowL: "m11 18-6-6 6-6M19 12H5",
  save: ["M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z", "M17 21v-8H7v8", "M7 3v5h8"],
  play: "m8 5 11 7-11 7V5Z",
  refresh: ["M21 12a9 9 0 1 1-2.6-6.4", "M21 3v6h-6"],
};

/* ---------- 通用小组件 ---------- */
function Btn({ children, onClick, disabled, kind = "primary", style = {}, icon }) {
  const base = {
    border: "none",
    borderRadius: 10,
    padding: "10px 18px",
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "opacity .15s",
    opacity: disabled ? 0.45 : 1,
    display: "inline-flex",
    alignItems: "center",
    verticalAlign: "middle",
    lineHeight: 1.4,
    gap: 8,
  };
  const kinds = {
    primary: { background: ORANGE, color: "#fff" },
    ghost: { background: "#fff", color: INK, border: `1px solid ${LINE}` },
    soft: { background: ORANGE_SOFT, color: ORANGE },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{ ...base, ...kinds[kind], ...style }}>
      {icon && <Icon d={ICONS[icon]} size={15} />}
      {children}
    </button>
  );
}

/* 触发文件选择的按钮：用 ref 直接触发 input，不用 <label> 包 <button>
   （label 里的 button 属于交互元素，点击不会转发给 input，表现为"点了没反应"） */
function FileBtn({ children, accept, onFile, kind = "ghost", icon, disabled }) {
  const ref = useRef(null);
  return (
    <>
      <Btn kind={kind} icon={icon} disabled={disabled} onClick={() => ref.current?.click()}>{children}</Btn>
      <input type="file" accept={accept} ref={ref} style={{ display: "none" }}
        onChange={(e) => { if (e.target.files?.[0]) onFile(e); e.target.value = ""; }} />
    </>
  );
}

function Progress({ progress, hint }) {
  const t0 = useRef(null);
  const [, force] = useState(0);
  useEffect(() => {
    if (!progress) { t0.current = null; return; }
    if (!t0.current) t0.current = Date.now();
    const t = setInterval(() => force((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [progress]);
  if (!progress) return null;
  const pct = Math.round((progress.progress || 0) * 100);
  const sec = t0.current ? Math.floor((Date.now() - t0.current) / 1000) : 0;
  const elapsed = sec >= 5 ? ` · 已等待 ${sec >= 60 ? `${Math.floor(sec / 60)} 分 ${sec % 60} 秒` : `${sec} 秒`}` : "";
  // 线性 ETA 预估：进度至少到 8% 才有足够样本，避免早期外推出"60 分钟"的误导数字
  const r = progress.progress || 0;
  let eta = "";
  if (sec >= 15 && r >= 0.08 && r < 0.9) {
    const left = Math.round((sec / r) * (1 - r));
    eta = ` · 预计还需 ${left >= 90 ? `约 ${Math.round(left / 60)} 分钟` : `${left} 秒`}`;
  }
  return (
    <div style={{ marginTop: 12, maxWidth: 560 }}>
      <div style={{ background: "#F1EDE8", borderRadius: 8, height: 8, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, background: ORANGE, height: "100%",
          transition: "width .4s", borderRadius: 8,
        }} />
      </div>
      <div style={{ color: MUTED, marginTop: 6, fontSize: 13 }}>
        {progress.message || (progress.status === "done" ? "完成 ✔" : "处理中…")} {pct > 0 && pct < 100 ? `${pct}%` : ""}
        {elapsed}{eta}
      </div>
      {hint && progress.status === "running" && (
        <div style={{ color: "#B0A9A0", marginTop: 3, fontSize: 12 }}>{hint}</div>
      )}
    </div>
  );
}

function Msg({ text, error }) {
  if (!text) return null;
  return (
    <p style={{ margin: "10px 0 0", fontSize: 13, color: error ? "#D93025" : ORANGE }}>{text}</p>
  );
}

const labelStyle = { fontSize: 13, color: MUTED, margin: "14px 0 8px" };
const inputStyle = {
  width: "100%",
  boxSizing: "border-box",
  border: `1px solid ${LINE}`,
  borderRadius: 10,
  padding: "10px 12px",
  fontSize: 14,
  color: INK,
  outline: "none",
  background: "#fff",
};
const cardStyle = {
  background: "#fff", border: `1px solid ${LINE}`, borderRadius: 14,
  padding: "20px 22px", marginBottom: 16,
};

function Seg({ options, value, onChange, style = {} }) {
  return (
    <div style={{ display: "inline-flex", flexWrap: "wrap", rowGap: 4, background: "#F1EDE8", borderRadius: 10, padding: 3, maxWidth: "100%", ...style }}>
      {options.map(([v, label]) => (
        <span key={v}
          onClick={() => onChange(v)}
          style={{
            padding: "7px 16px", borderRadius: 8, fontSize: 13, cursor: "pointer",
            color: String(value) === String(v) ? ORANGE : MUTED,
            fontWeight: String(value) === String(v) ? 600 : 400,
            background: String(value) === String(v) ? "#fff" : "transparent",
            boxShadow: String(value) === String(v) ? "0 1px 4px rgba(0,0,0,.08)" : "none",
          }}>
          {label}
        </span>
      ))}
    </div>
  );
}

/* ---------- 缩略图 ---------- */
function Thumb({ projectId, index, tick, onZoom, big, w = 150, pending }) {
  const [url, setUrl] = useState("");
  const [tried, setTried] = useState(0);
  useEffect(() => {
    let alive = true;
    if (!projectId) return;
    if (pending) { setUrl(""); return; }   // 原始画面提取中：不出图，只显示骨架
    setUrl("");
    api.thumbUrl(projectId, index).then((u) => alive && setUrl(`${u}?t=${tick}-${Date.now()}`)).catch(() => {});
    return () => { alive = false; };
  }, [projectId, index, tick, pending]);
  // 图片还没渲染出来时每 2.5s 自动重试，直到加载成功；失败立即回退占位（不显示裂图）
  function onErr() {
    setUrl("");
    if (tried > 40) return;
    setTimeout(() => {
      api.thumbUrl(projectId, index).then((u) => setUrl(`${u}?t=${Date.now()}`)).catch(() => {});
      setTried((n) => n + 1);
    }, 2500);
  }
  return (
    <div
      onClick={big || pending ? undefined : onZoom}
      style={{
        width: w, height: (w * 9) / 16, flexShrink: 0, borderRadius: 8, overflow: "hidden",
        background: "#F1EDE8", border: `1px solid ${LINE}`, cursor: big || pending ? "default" : "zoom-in",
        display: "flex", alignItems: "center", justifyContent: "center", position: "relative",
      }}
    >
      {pending ? (
        <span style={{ color: "#A89F93", fontSize: 11, textAlign: "center", lineHeight: 1.5, padding: 4, animation: "pvsSkel 1.6s ease-in-out infinite" }}>
          第{index + 1}页<br />提取中…
        </span>
      ) : url ? (
        <img src={url} onError={onErr} style={{ width: "100%", height: "100%", objectFit: "cover" }} alt={`第${index + 1}页`} />
      ) : tried > 8 ? (
        <span style={{ color: "#A89F93", fontSize: 11, textAlign: "center", lineHeight: 1.5, padding: 4 }}>
          第{index + 1}页<br />画面提取失败<br />导出视频将用网页版式渲染
        </span>
      ) : (
        <span style={{ color: "#A89F93", fontSize: 11, textAlign: "center", lineHeight: 1.5, padding: 4 }}>
          渲染中<br />首次约需 10 秒
        </span>
      )}
    </div>
  );
}

/* 点击放大：全屏预览某一页（支持直接编辑该页内容与配图） */
function ZoomModal({ projectId, index, total, onClose, onNav, slides, onSlidesSaved }) {
  const editable = Array.isArray(slides) && !!onSlidesSaved;
  const [url, setUrl] = useState("");
  const [imgTick, setImgTick] = useState(0);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);   // {title, lead, bulletsText, image}
  const [saving, setSaving] = useState(false);
  const [editMsg, setEditMsg] = useState("");
  const imgInputRef = useRef(null);
  const newImgRef = useRef(null);             // 新选的配图 data URI

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") { if (!editing) onClose(); }
      if (!editing && e.key === "ArrowRight" && index < total - 1) onNav(index + 1);
      if (!editing && e.key === "ArrowLeft" && index > 0) onNav(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, total, editing]);
  useEffect(() => {
    setUrl("");
    api.pageUrl(projectId, index).then((u) => setUrl(`${u}?t=${Date.now()}`)).catch(() => {});
  }, [projectId, index, imgTick]);

  function startEdit() {
    const s = slides[index] || {};
    newImgRef.current = null;
    setDraft({
      title: s.title || "",
      lead: s.lead || "",
      bulletsText: (s.bullets || []).join("\n"),
    });
    setEditMsg("");
    setEditing(true);
  }

  function pickImage(e) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    if (!/^image\//.test(f.type)) { setEditMsg("请选择图片文件"); return; }
    const rd = new FileReader();
    rd.onload = () => { newImgRef.current = String(rd.result); setEditMsg("已选择新配图，点击保存生效"); };
    rd.readAsDataURL(f);
  }

  async function saveEdit() {
    setSaving(true); setEditMsg("");
    try {
      const next = slides.map((s, i) => {
        if (i !== index) return s;
        const out = { ...s };
        out.title = draft.title.trim();
        if (draft.lead.trim()) out.lead = draft.lead.trim(); else delete out.lead;
        out.bullets = draft.bulletsText.split("\n").map((x) => x.trim()).filter(Boolean);
        if (newImgRef.current) out.image = newImgRef.current;
        return out;
      });
      await api.saveSlides(projectId, next);
      onSlidesSaved(next);
      setEditing(false);
      setImgTick((t) => t + 1);
    } catch (e) {
      setEditMsg("保存失败：" + e.message);
    } finally { setSaving(false); }
  }

  const cur = (Array.isArray(slides) && slides[index]) || {};

  if (editing && draft) {
    return (
      <div onClick={() => {}} style={{
        position: "fixed", inset: 0, zIndex: 1000, background: "rgba(20,16,12,.72)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <div onClick={(e) => e.stopPropagation()} style={{
          background: "#fff", borderRadius: 14, padding: "22px 26px", width: "min(860px, 92vw)",
          maxHeight: "88vh", overflow: "auto", boxShadow: "0 24px 80px rgba(0,0,0,.4)",
        }}>
          <div style={{ display: "flex", alignItems: "center", marginBottom: 14 }}>
            <h3 style={{ margin: 0, fontSize: 16 }}>编辑第 {index + 1} 页</h3>
            <span style={{ flex: 1 }} />
            <button onClick={() => setEditing(false)} style={{ border: "none", background: "transparent", fontSize: 20, cursor: "pointer", color: MUTED }}>✕</button>
          </div>
          <div style={{ fontSize: 12.5, color: MUTED, marginBottom: 12 }}>
            保存后自动重建 PPT 与本页画面；解说词面板可继续微调本页讲稿
          </div>
          <div style={{ ...labelStyle, marginTop: 0 }}>页面标题</div>
          <input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} style={inputStyle} />
          <div style={labelStyle}>导语（可选，显示在标题下方）</div>
          <input value={draft.lead} onChange={(e) => setDraft({ ...draft, lead: e.target.value })} style={inputStyle}
            placeholder="一句话概括本页（可留空）" />
          <div style={labelStyle}>要点（每行一条，推荐格式「关键词：描述」）</div>
          <textarea value={draft.bulletsText} onChange={(e) => setDraft({ ...draft, bulletsText: e.target.value })}
            rows={7} style={{ ...inputStyle, resize: "vertical", lineHeight: 1.7 }} />
          <div style={labelStyle}>配图（可选：上传你自己的图片，商用零风险）</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <FileBtn icon="upload" accept="image/*" onFile={pickImage}>上传本页配图</FileBtn>
            {cur.image && <span style={{ fontSize: 12, color: MUTED }}>当前已有配图，不上传则保留原图</span>}
          </div>
          {editMsg && <div style={{ marginTop: 10, fontSize: 12.5, color: editMsg.startsWith("保存失败") ? "#C0392B" : "#1a7f37" }}>{editMsg}</div>}
          <div style={{ display: "flex", gap: 10, marginTop: 18, justifyContent: "flex-end" }}>
            <Btn kind="ghost" onClick={() => setEditing(false)}>取消</Btn>
            <Btn onClick={saveEdit} disabled={saving || !draft.title.trim()}>{saving ? "保存中…" : "保存并重建本页"}</Btn>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 1000, background: "rgba(20,16,12,.72)",
      display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 14,
    }}>
      <div style={{ color: "#EDE7DF", fontSize: 13 }}>第 {index + 1} / {total} 页 · 点击任意处或按 Esc 关闭 · ←→ 切页</div>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "#fff", borderRadius: 14, padding: 10, maxWidth: "82vw", boxShadow: "0 24px 80px rgba(0,0,0,.4)",
        position: "relative",
      }}>
        {url ? (
          <img src={url} style={{ maxWidth: "80vw", maxHeight: "72vh", display: "block", borderRadius: 8 }} alt={`第${index + 1}页`} />
        ) : (
          <div style={{ width: 640, height: 360, display: "flex", alignItems: "center", justifyContent: "center", color: MUTED, fontSize: 14 }}>
            加载中…
          </div>
        )}
        {editable && url && (
          <button onClick={startEdit} style={{
            position: "absolute", right: 20, bottom: 20, border: "none", borderRadius: 9,
            background: "rgba(30,26,20,.78)", color: "#fff", fontSize: 13, fontWeight: 600,
            padding: "9px 16px", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6,
          }}>✎ 编辑此页</button>
        )}
      </div>
      {index > 0 && (
        <div onClick={(e) => { e.stopPropagation(); onNav(index - 1); }} style={{
          position: "absolute", left: 26, top: "50%", transform: "translateY(-50%)", cursor: "pointer",
          color: "#fff", fontSize: 40, userSelect: "none", opacity: 0.75, padding: "10px 18px",
        }}>‹</div>
      )}
      {index < total - 1 && (
        <div onClick={(e) => { e.stopPropagation(); onNav(index + 1); }} style={{
          position: "absolute", right: 26, top: "50%", transform: "translateY(-50%)", cursor: "pointer",
          color: "#fff", fontSize: 40, userSelect: "none", opacity: 0.75, padding: "10px 18px",
        }}>›</div>
      )}
    </div>
  );
}

/* ---------- 后端网关 ---------- */
function useBackend() {
  const [info, setInfo] = useState({ ready: false, error: "", port: 0, checking: true });
  const refresh = useCallback(async () => {
    const i = await window.pvs.backendInfo();
    setInfo({ ...i, checking: !i.ready && !i.error });
  }, []);
  useEffect(() => {
    refresh();
    window.pvs.onBackendReady(() => setInfo((s) => ({ ...s, ready: true, error: "", checking: false })));
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, []);
  return { info, refresh };
}

/* ============================================================
   栏目一：首页
============================================================ */
const COLORS = [
  ["#FF6B35", "活力橙"], ["#1a3a5c", "深海军蓝"], ["#0F6B4C", "墨绿"],
  ["#5B3A8E", "紫罗兰"], ["#C0392B", "中国红"], ["#2C3E50", "石墨灰"],
];
const STYLES = ["简约商务", "Slidev 极客", "科技渐变", "清新留白", "图文并茂"];

function HomePanel({ project, setProject, goPanel, onProjectChanged }) {
  const [step, setStep] = useState(1); // 1 输入 2 版式 3 预览
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(12);
  const [color, setColor] = useState(COLORS[0][0]);
  const [style, setStyle] = useState(STYLES[0]);
  const [projects, setProjects] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [progress, setProgress] = useState(null);
  const [slides, setSlides] = useState([]);
  const [thumbTick, setThumbTick] = useState(0);
  const [zoomIdx, setZoomIdx] = useState(-1);
  const [noLLM, setNoLLM] = useState(false);
  const [aiList, setAiList] = useState([]);   // [{id,name,model}]
  const [engine, setEngine] = useState(null); // null=未初始化；加载后默认选第一个 AI 配置
  const [fx, setFx] = useState(true);         // 随机切换动效
  const [fromDocx, setFromDocx] = useState(false); // Word 导入项目

  const refresh = useCallback(() => api.listProjects().then(setProjects).catch(() => {}), []);
  useEffect(() => { refresh(); }, [refresh, project?.id]);

  // 读取已保存的 AI 配置列表；默认选中第一个 AI（内置模板仅作备选）
  useEffect(() => {
    api.getSettings().then((st) => {
      const list = (st.ai_profiles || []).filter((p) => p.base && p.model);
      setAiList(list);
      setNoLLM(list.length === 0);
      setEngine((e) => e ?? (list.length ? list[0].id : "builtin"));
    }).catch(() => {});
  }, []);

  // 打开已有项目：有 PPT 成品（生成/导入过）才直接进预览；
  // Word 导入但尚未生成 → 停在版式设置页，绝不自动跳预览
  const [imported, setImported] = useState(false);
  const [genDone, setGenDone] = useState(false);
  // 导入项目的原始画面提取进度（轮询 real-status，就绪后刷新缩略图）
  const [realSt, setRealSt] = useState(null);
  useEffect(() => {
    if (step !== 3 || !project?.id || !imported) { setRealSt(null); return; }
    let alive = true;
    let timer = null;
    const poll = () => {
      api.realStatus(project.id).then((s) => {
        if (!alive) return;
        setRealSt(s);
        if (s.ready) { setThumbTick((t) => t + 1); setRealSt(s); }
        else timer = setTimeout(poll, 3000);
      }).catch(() => { if (alive) timer = setTimeout(poll, 5000); });
    };
    poll();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [step, project?.id, imported]);
  useEffect(() => {
    if (!project?.id) return;
    Promise.all([api.getSlides(project.id), api.getProject(project.id)])
      .then(([d, p]) => {
        setSlides(d.slides || []);
        setImported(p.files?.pptx === "upload.pptx");
        const done = !!p.files?.pptx;
        setGenDone(done);
        setFromDocx(!!p.docx_source);
        if ((d.slides || []).length && done) setStep(3);
        else if (p.docx_source) setStep(2);
      }).catch(() => {});
  }, [project?.id]);

  async function startGenerate() {
    setBusy(true); setMsg(""); setErr(false); setProgress(null);
    try {
      let pid = project?.id;
      // Word 导入项目复用当前项目（docx 素材存在该项目上）；
      // 其他情况一律新建项目，避免新主题覆盖旧项目
      if (!pid || !fromDocx) {
        const p = await api.createProject(topic);
        pid = p.id;
        setProject({ id: pid, topic });
      }
      // 内容引擎：按用户选择；默认已选第一个 AI 配置
      await runTask(
        () => api.generatePpt(pid, {
          slides: count, color, style,
          engine: engine === "builtin" ? "builtin" : "ai",
          profile_id: engine && engine !== "builtin" ? engine : undefined,
          effects: fx,
          use_docx: true,   // Word 导入项目：基于文档内容 AI 分析生成
        }),
        (t) => setProgress(t)
      ).then((r) => {
        if (r?.warning) { setMsg("AI 调用失败，已用内置引擎兜底：" + r.warning); setErr(true); }
      });
      const d = await api.getSlides(pid);
      setSlides(d.slides || []);
      setThumbTick((t) => t + 1);
      setGenDone(true);
      setStep(3);
      refresh();
      onProjectChanged?.();
    } catch (e) {
      setMsg("出错：" + e.message); setErr(true);
    } finally { setBusy(false); setProgress(null); }
  }

  async function importPpt(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setMsg(""); setErr(false); setProgress(null);
    try {
      const p = await api.importPpt(f);
      const pid = p.projectId;
      setProject({ id: pid, topic: f.name.replace(/\.pptx$/i, "") });
      const d = await api.getSlides(pid);
      setSlides(d.slides || []);
      setThumbTick((t) => t + 1);
      setGenDone(true);
      setStep(3);
      setMsg(`导入成功，共 ${p.slides.length} 页 ✔`);
      refresh();
    } catch (e2) {
      setMsg("导入失败：" + e2.message); setErr(true);
    } finally { setBusy(false); e.target.value = ""; }
  }

  async function importDocx(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setMsg(""); setErr(false); setProgress(null);
    try {
      const p = await api.importDocx(f);
      const pid = p.projectId;
      setProject({ id: pid, topic: f.name.replace(/\.docx$/i, "") });
      setSlides([]);
      setFromDocx(true);
      setGenDone(false);
      setStep(2);   // 进入版式选择，点「开始生成」时基于 Word 内容 AI 分析生成
      setMsg(`文档解析成功 ✔ 请选择版式与风格，点「开始生成」后 AI 分析文档内容并重新设计框架（通常 1~3 分钟）`);
      refresh();
    } catch (e2) {
      setMsg("Word 解析失败：" + e2.message); setErr(true);
    } finally { setBusy(false); e.target.value = ""; }
  }

  async function savePpt() {
    setBusy(true); setMsg(""); setErr(false);
    try {
      // 1) 保存到项目目录（保证项目数据一致）
      await api.saveSlides(project.id, slides);
      setThumbTick((t) => t + 1);
      // 2) 弹出系统对话框，让用户选择保存位置
      const safeTopic = (project.topic || "PPTVideoStudio").replace(/[\\/:*?"<>|]/g, "_").slice(0, 50);
      const u = await api.pptDownloadUrl(project.id);
      const r = window.pvs?.saveFileAs ? await window.pvs.saveFileAs(u, `${safeTopic}.pptx`) : { saved: false };
      if (r?.saved) {
        setMsg(`PPT 已保存到：${r.path}`);
      } else if (r?.canceled) {
        setMsg("PPT 已保存到项目（未选择导出位置）");
      } else {
        setMsg("PPT 已保存到项目 ✔");
      }
    } catch (e) { setMsg("保存失败：" + e.message); setErr(true); }
    finally { setBusy(false); }
  }

  function open(p) {
    setProject({ id: p.id, topic: p.topic });
    setMsg("");
  }

  // 返回首页重新开始：清空当前项目回到输入主题
  function restartAll() {
    setProject(null); setSlides([]); setTopic(""); setStep(1); setFromDocx(false);
    setGenDone(false);
    setMsg(""); setProgress(null); setBusy(false);
    onProjectChanged?.();
  }

  const stepDots = (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, fontSize: 12, color: MUTED }}>
      <b onClick={() => { if (!busy) { setProject(null); setSlides([]); setStep(1); } }} title="点击返回输入主题" style={{
        color: step === 1 ? ORANGE : INK, cursor: "pointer",
        textDecoration: step !== 1 ? "underline dotted rgba(0,0,0,.35)" : "none",
      }}>① {project?.topic || "输入主题"}</b>
      <span style={{ color: "#D5CFC8" }}>→</span>
      <b onClick={() => { if (!busy && topic) setStep(2); }} title="点击返回选择版式" style={{
        color: step === 2 ? ORANGE : step > 2 ? INK : "#C5BFB7", cursor: topic ? "pointer" : "default",
        textDecoration: step > 2 ? "underline dotted rgba(0,0,0,.35)" : "none",
      }}>② 选择版式</b>
      <span style={{ color: "#D5CFC8" }}>→</span>
      <b onClick={() => { if (!busy && slides.length && genDone) setStep(3); }} style={{
        color: step === 3 ? ORANGE : "#C5BFB7", cursor: slides.length && genDone ? "pointer" : "default",
      }}>③ 预览保存</b>
    </div>
  );

  return (
    <>
      <h1 style={{ margin: 0, fontSize: 21 }}>首页</h1>
      <p style={{ color: MUTED, fontSize: 13, margin: "4px 0 20px" }}>
        输入主题一键生成，或上传已有 PPT · 上传的 PPT 导出视频时保留原始页面
      </p>
      {stepDots}

      {step === 1 && (
        <div style={{ ...cardStyle, padding: "34px 30px" }}>
          <div style={{ display: "flex", gap: 10 }}>
            <input
              autoFocus
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="输入主题，例如：智慧文旅夜游项目汇报"
              style={{ ...inputStyle, fontSize: 15, padding: "14px 16px", WebkitUserSelect: "text" }}
              onKeyDown={(e) => e.key === "Enter" && topic.trim() && setStep(2)}
            />
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 18, flexWrap: "wrap", alignItems: "center" }}>
            <Btn icon="arrowR" disabled={!topic.trim()} onClick={() => setStep(2)}>生成 PPT</Btn>
            <FileBtn icon="upload" accept=".pptx" disabled={busy} onFile={importPpt}>上传 PPT（.pptx）</FileBtn>
            <FileBtn icon="upload" accept=".docx" disabled={busy} onFile={importDocx}>上传 Word，AI 生成 PPT（.docx）</FileBtn>
          </div>
          <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.8, marginTop: 12 }}>
            上传的 PPT 导出视频时直接使用你 PPT 的原始页面（需本机装有 Office 或 WPS）；上传 Word 后自动分析文档结构生成 PPT 页面
          </div>
          {projects.length > 0 && (
            <div style={{ marginTop: 22, borderTop: `1px solid ${LINE}`, paddingTop: 16 }}>
              <div style={{ ...labelStyle, marginTop: 0 }}>最近项目（点击打开）</div>
              {projects.slice(0, 6).map((p) => (
                <div key={p.id} onClick={() => open(p)}
                  style={{
                    display: "flex", alignItems: "center", gap: 12, padding: "9px 12px",
                    borderRadius: 10, cursor: "pointer", fontSize: 14,
                    background: project?.id === p.id ? ORANGE_SOFT : "transparent",
                    color: project?.id === p.id ? ORANGE : INK,
                  }}>
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.topic}</span>
                  <span style={{ color: MUTED, fontSize: 12 }}>{p.slides} 页</span>
                  {p.has_video && <span style={{ color: "#1a7f37", fontSize: 12 }}>已有视频</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div style={cardStyle}>
          <div style={labelStyle}>页面数量</div>
          <Seg options={[[5, "5 页"], [8, "8 页"], [12, "12 页"], [15, "15 页"], [20, "20 页"]]} value={count} onChange={setCount} />
          <div style={labelStyle}>PPT 主色（封面与标题配色）</div>
          <div style={{ display: "flex", gap: 10 }}>
            {COLORS.map(([c, name]) => (
              <div key={c} title={name} onClick={() => setColor(c)}
                style={{
                  width: 34, height: 34, borderRadius: 9, cursor: "pointer", background: c,
                  border: color === c ? `2px solid ${ORANGE}` : "2px solid transparent",
                  position: "relative",
                }}>
                {color === c && (
                  <span style={{
                    position: "absolute", inset: 0, display: "flex", alignItems: "center",
                    justifyContent: "center", color: "#fff", fontWeight: 700, textShadow: "0 1px 3px rgba(0,0,0,.4)",
                  }}>✓</span>
                )}
              </div>
            ))}
          </div>
          <div style={labelStyle}>版式风格</div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {STYLES.map((s) => (
              <div key={s} onClick={() => setStyle(s)}
                style={{
                  border: style === s ? `1.5px solid ${ORANGE}` : `1.5px solid ${LINE}`,
                  background: style === s ? ORANGE_SOFT : "#fff",
                  color: style === s ? ORANGE : INK, fontWeight: style === s ? 600 : 400,
                  borderRadius: 12, padding: "10px 14px", fontSize: 13, cursor: "pointer",
                }}>{s}</div>
            ))}
          </div>
          <div style={labelStyle}>内容引擎（AI 生成质量远高于内置模板）</div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <Seg
              options={[
                ...aiList.map((p) => [p.id, `AI·${p.name || p.model}`]),
                ["builtin", "内置模板（免费·内容较简单）"],
              ]}
              value={engine ?? "builtin"}
              onChange={setEngine}
            />
          </div>
          <div style={{ display: "flex", gap: 22, marginTop: 16, flexWrap: "wrap", alignItems: "center" }}>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
              <input type="checkbox" checked={fx} onChange={(e) => setFx(e.target.checked)}
                style={{ accentColor: ORANGE, width: 16, height: 16 }} />
              随机切换动效
              <span style={{ fontSize: 11, color: MUTED, background: "#F1EDE8", padding: "2px 8px", borderRadius: 99 }}>
                写入 PPT 放映 + 视频随机镜头
              </span>
            </label>
          </div>
          <div style={{ display: "flex", gap: 10, marginTop: 20, alignItems: "center", flexWrap: "wrap" }}>
            <Btn kind="ghost" icon="arrowL" onClick={() => setStep(1)}>上一步</Btn>
            <Btn onClick={startGenerate} disabled={busy}>{busy ? "生成中…" : "开始生成"}</Btn>
            <span style={{ fontSize: 12, color: MUTED }}>
              {fromDocx
                ? "将基于 Word 文档内容：AI 分析 → 框架设计 → 逐页生成"
                : "分析主题 → 抓取网络资料 → 大纲 → 逐页内容"}
            </span>
          </div>
          {noLLM && (
            <div style={{
              marginTop: 14, padding: "10px 14px", borderRadius: 10, fontSize: 12.5, lineHeight: 1.7,
              background: "#FFF7E8", border: "1px solid #F2DDB4", color: "#8A6116",
            }}>
              💡 内置 AI 完全免费、无需配置，开箱即用。想要更强的内容质量，可在「高级设置 → ① PPT 生成 AI」里填入任意大模型 API（DeepSeek / 智谱 GLM / Kimi 等，注册即送额度）。
            </div>
          )}
          <Progress progress={progress}
            hint={fromDocx ? "AI 分析 Word 内容 → 框架设计 → 逐页生成，通常 1~3 分钟，请勿关闭窗口" : "分析主题 → 检索资料 → 大纲 → 逐页生成，通常 1~3 分钟"} />
          <Msg text={msg} error={err} />
        </div>
      )}

      {step === 3 && (
        <>
          <div style={cardStyle}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>预览（{slides.length} 页）</h3>
              <span style={{ fontSize: 12, color: MUTED }}>点击任意一页可放大预览</span>
              <span style={{ flex: 1 }} />
              <Btn kind="ghost" icon="arrowL" disabled={busy} onClick={() => setStep(2)}>← 返回修改</Btn>
              <Btn kind="ghost" onClick={restartAll}>⟲ 返回首页</Btn>
              <Btn kind="ghost" icon="save" onClick={savePpt} disabled={busy || !slides.length}>保存 PPT</Btn>
              <Btn icon="arrowR" onClick={() => goPanel("script")} disabled={!slides.length}>生成解说词，进入下一步 →</Btn>
            </div>
            {/* 导入项目：原始画面提取进度（就绪后缩略图自动刷新） */}
            {imported && realSt && !realSt.ready && !realSt.failed && (
              <div style={{
                marginBottom: 14, padding: "12px 16px", borderRadius: 10,
                background: ORANGE_SOFT, border: `1px solid ${LINE}`,
              }}>
                <div style={{ fontSize: 13, color: INK, fontWeight: 600, marginBottom: 6 }}>
                  {realSt.stage === "render"
                    ? `正在生成页面图片 ${realSt.done}/${realSt.total} 页…`
                    : "正在将 PPT 转换为高清画面（大文件约需 2~5 分钟）…"}
                </div>
                {realSt.stage === "render" ? (
                  <div style={{ background: "#F1EDE8", borderRadius: 6, height: 7, overflow: "hidden", maxWidth: 480 }}>
                    <div style={{
                      width: `${realSt.total ? Math.round((realSt.done / realSt.total) * 100) : 0}%`,
                      background: ORANGE, height: "100%", transition: "width .5s", borderRadius: 6,
                    }} />
                  </div>
                ) : (
                  <div className="pvs-indet" style={{ maxWidth: 480 }}><div /></div>
                )}
                <div style={{ fontSize: 12, color: MUTED, marginTop: 5 }}>
                  转换期间进度条流动属正常现象，请勿关闭窗口；完成后缩略图会自动出现
                </div>
              </div>
            )}
            {realSt?.failed && (
              <div style={{
                marginBottom: 14, padding: "10px 14px", borderRadius: 10, fontSize: 12.5,
                background: "#FFF7E8", border: "1px solid #F2DDB4", color: "#8A6116",
              }}>
                ⚠️ 本机转换引擎暂时不可用，预览显示的是内置版式；视频画面同样会使用内置版式。
              </div>
            )}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {slides.map((_, i) => (
                <Thumb key={i} projectId={project?.id} index={i} tick={thumbTick} w={132}
                  pending={imported && realSt && !realSt.ready && !realSt.failed}
                  onZoom={() => setZoomIdx(i)} />
              ))}
            </div>
            <Msg text={msg} error={err} />
          </div>
          {zoomIdx >= 0 && (
            <ZoomModal
              projectId={project?.id}
              index={zoomIdx}
              total={slides.length}
              slides={imported ? null : slides}
              onSlidesSaved={imported ? null : (next) => { setSlides(next); setThumbTick((t) => t + 1); }}
              onClose={() => setZoomIdx(-1)}
              onNav={(i) => setZoomIdx(i)}
            />
          )}
        </>
      )}
    </>
  );
}

/* ============================================================
   栏目二：解说词
============================================================ */
function ScriptPanel({ project, goPanel, onScriptReady }) {
  const [slides, setSlides] = useState([]);
  const [script, setScript] = useState([]);
  const [busy, setBusy] = useState(false);
  const [busyOne, setBusyOne] = useState(-1);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [progress, setProgress] = useState(null);
  const [thumbTick, setThumbTick] = useState(0);
  const [zoomIdx, setZoomIdx] = useState(-1);
  const [imported, setImported] = useState(false);
  const loadedRef = useRef(false);   // 首次加载完成前不触发自动保存
  const saveTimer = useRef(null);

  useEffect(() => {
    if (!project?.id) return;
    loadedRef.current = false;
    setMsg(""); setProgress(null);
    Promise.all([
      api.getSlides(project.id),
      api.getProject(project.id),
    ]).then(([d, p]) => {
      setSlides(d.slides || []);
      setScript(p.script || []);
      setImported(p.files?.pptx === "upload.pptx");
      loadedRef.current = true;
    }).catch(() => { loadedRef.current = true; });
    setThumbTick((t) => t + 1);
  }, [project?.id]);

  // 自动保存：停止输入 800ms 后静默保存，无需手动点按钮
  useEffect(() => {
    if (!loadedRef.current || !project?.id || !script.length) return;
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      api.saveSpeech(project.id, script).catch(() => {});
    }, 800);
    return () => clearTimeout(saveTimer.current);
  }, [script, project?.id]);

  const updScript = (i, val) => {
    const next = [...script];
    next[i] = val;
    setScript(next);
  };

  async function genScript() {
    setBusy(true); setMsg(""); setErr(false); setProgress(null);
    setMsg("AI 正在撰写解说词，通常 30~120 秒，请耐心等待…");
    try {
      const r = await runTask(
        () => api.generateSpeech(project.id, { tone: "专业" }),
        (t) => setProgress(t)
      );
      setScript(r.pages);
      if (r.warning) setMsg("AI 调用失败，已用内置引擎兜底：" + r.warning), setErr(true);
      else setMsg(r.source === "llm" ? "解说词已根据每页内容生成（AI）✔" : "已按每页内容生成解说词（内置引擎）✔ 接入 LLM 可获得更自然的讲稿");
      onScriptReady();
    } catch (e) { setMsg("失败：" + e.message); setErr(true); }
    finally { setBusy(false); setProgress(null); }
  }

  // 只重新生成某一页的解说词
  async function genOne(i) {
    setBusyOne(i); setMsg(""); setErr(false);
    try {
      const r = await api.generateSpeechOne(project.id, i);
      updScript(i, r.page);
      setMsg(`第 ${i + 1} 页解说词已重新生成 ✔`);
      onScriptReady();
    } catch (e) { setMsg("重新生成失败：" + e.message); setErr(true); }
    finally { setBusyOne(-1); }
  }

  const notesCount = slides.filter((s) => (s?.notes || "").trim()).length;

  // 使用上传 PPT 自带的演讲者备注作为解说词
  async function useNotes() {
    setBusy(true); setMsg(""); setErr(false);
    try {
      const r = await api.useSpeechNotes(project.id);
      setScript(r.script);
      setMsg(`已使用 PPT 自带演讲稿（${r.used} 页）✔ 空白页可点「AI 重新生成本页」补齐`);
      onScriptReady();
    } catch (e) { setMsg(e.message); setErr(true); }
    finally { setBusy(false); }
  }

  if (!project?.id) return <p style={{ color: MUTED, fontSize: 13 }}>请先在首页生成或导入 PPT</p>;

  return (
    <>
      <h1 style={{ margin: 0, fontSize: 21 }}>解说词</h1>
      <p style={{ color: MUTED, fontSize: 13, margin: "4px 0 20px" }}>
        分析式讲解（不是逐字念 PPT） · 修改自动保存并写入 PPT 备注 · 每页可单独 AI 重新生成
      </p>
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <Btn kind="ghost" icon="arrowL" onClick={() => goPanel("home")}>← 返回首页</Btn>
        <Btn kind="soft" icon="refresh" onClick={genScript} disabled={busy || !slides.length}>
          {script.some((s) => (s || "").trim()) ? "AI 重新生成全部" : "AI 生成全部解说词"}
        </Btn>
        {notesCount > 0 && (
          <Btn kind="ghost" icon="script" onClick={useNotes} disabled={busy}>
            📄 使用 PPT 自带演讲稿（{notesCount} 页）
          </Btn>
        )}
        <span style={{ flex: 1 }} />
        {progress && <div style={{ width: 180 }}><Progress progress={progress} /></div>}
      </div>
      <div style={cardStyle}>
        {slides.length === 0 && <p style={{ color: MUTED, fontSize: 13 }}>—</p>}
        {slides.map((s, i) => (
          <div key={i} style={{ display: "flex", gap: 14, padding: "14px 0", borderBottom: i < slides.length - 1 ? `1px solid ${LINE}` : "none" }}>
            <div style={{ width: 132, flexShrink: 0 }}>
              <Thumb projectId={project?.id} index={i} tick={thumbTick} w={132} onZoom={() => setZoomIdx(i)} />
              <div style={{ color: MUTED, fontSize: 12, marginTop: 6, textAlign: "center" }}>
                第 {i + 1} 页 · {s.title || ""}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <textarea
                value={script[i] || ""}
                onChange={(e) => updScript(i, e.target.value)}
                rows={3}
                style={{ ...inputStyle, resize: "vertical" }}
                placeholder="本页解说词（可点击右侧 AI 重新生成，或直接输入，修改自动保存）"
              />
              <div style={{ marginTop: 6, textAlign: "right" }}>
                <button
                  onClick={() => genOne(i)}
                  disabled={busyOne >= 0 || busy}
                  style={{
                    border: `1px solid ${busyOne === i ? ORANGE : LINE}`, borderRadius: 8,
                    background: busyOne === i ? ORANGE_SOFT : "#fff", color: busyOne === i ? ORANGE : INK,
                    fontSize: 12, padding: "5px 12px", cursor: busyOne >= 0 || busy ? "wait" : "pointer",
                    fontWeight: 600,
                  }}
                >
                  {busyOne === i ? "AI 生成中…" : "⟲ AI 重新生成本页"}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ fontSize: 13, color: MUTED }}>确认无误后 →</span>
        <Btn icon="arrowR" onClick={() => goPanel("audio")}>下一步：AI 配音 →</Btn>
      </div>
      <Msg text={msg} error={err} />
      {zoomIdx >= 0 && (
        <ZoomModal
          projectId={project?.id}
          index={zoomIdx}
          total={slides.length}
          slides={imported ? null : slides}
          onSlidesSaved={imported ? null : (next) => { setSlides(next); setThumbTick((t) => t + 1); }}
          onClose={() => setZoomIdx(-1)}
          onNav={(i) => setZoomIdx(i)}
        />
      )}
    </>
  );
}

/* ============================================================
   栏目三：AI 配音
============================================================ */
const VOICES = [
  ["zh-CN-XiaoxiaoNeural", "晓晓 女·温柔"],
  ["zh-CN-YunxiNeural", "云希 男·年轻"],
  ["zh-CN-YunjianNeural", "云健 男·沉稳"],
  ["zh-CN-XiaoyiNeural", "晓伊 女·活泼"],
  ["zh-CN-YunxiaNeural", "云夏 女·清脆"],
];

function AudioPanel({ project, goPanel, onAudioReady }) {
  const [voice, setVoice] = useState("zh-CN-XiaoxiaoNeural");
  const [speed, setSpeed] = useState(1.0);
  const [audio, setAudio] = useState([]);
  const [audioUrls, setAudioUrls] = useState({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [progress, setProgress] = useState(null);
  const [previewing, setPreviewing] = useState(false);

  const clampSpeed = (v) => {
    const n = Number(v);
    if (Number.isNaN(n)) return 1.0;
    return Math.round(Math.max(0.1, Math.min(2.0, n)) * 10) / 10;
  };

  useEffect(() => {
    if (!project?.id) { setAudio([]); return; }
    setAudioUrls({});
    // 恢复已生成的配音与音色设置（切面板回来不丢失）
    api.getProject(project.id).then((p) => {
      if (p.files?.audio?.length) setAudio(p.files.audio);
      if (p.tts_settings?.voice) setVoice(p.tts_settings.voice);
      if (p.tts_settings?.speed) setSpeed(p.tts_settings.speed);
    }).catch(() => {});
  }, [project?.id]);

  useEffect(() => {
    (async () => {
      const urls = {};
      for (const f of audio) urls[f] = await api.audioUrl(project.id, f);
      setAudioUrls(urls);
    })();
  }, [audio, project?.id]);

  function nudge(d) {
    setSpeed((s) => clampSpeed((parseFloat(s) || 1) + d));
  }

  async function preview() {
    setPreviewing(true); setMsg(""); setErr(false);
    try {
      // 直接用 <audio> 元素加载（与缩略图 <img> 同一网络通道，稳定可达），
      // 不走 fetch —— fetch 在部分代理环境下会被拦截
      const u = `${await api.previewUrl(voice, clampSpeed(speed))}?t=${Date.now()}`;
      const fetchDetail = async () => {
        // 播放失败时向后端要具体错误（如：无法连接微软 TTS / SSL 错误）
        try {
          const res = await fetch(u);
          const data = await res.json().catch(() => null);
          if (data?.detail) return String(data.detail);
        } catch {}
        return "";
      };
      await new Promise((resolve, reject) => {
        const a = new Audio(u);
        const to = setTimeout(() => { a.src = ""; reject(new Error("试听超时，请检查网络后重试")); }, 20000);
        a.onended = () => { clearTimeout(to); resolve(); };
        a.onerror = async () => {
          clearTimeout(to);
          reject(new Error(await fetchDetail() || "试听播放失败，请重试（配音需要联网使用 Edge-TTS）"));
        };
        a.play().catch(async () => {
          clearTimeout(to);
          reject(new Error(await fetchDetail() || "播放被拦截，请重试（若多次失败请检查网络）"));
        });
      });
    } catch (e) {
      const m = typeof e?.message === "string" && e.message ? e.message : "请检查网络";
      setMsg("试听失败：" + m);
      setErr(true);
    } finally {
      setPreviewing(false);
    }
  }

  async function generate() {
    setBusy(true); setMsg(""); setErr(false); setProgress(null);
    try {
      const r = await runTask(
        () => api.generateTts(project.id, { voice, speed: clampSpeed(speed) }),
        (t) => setProgress(t)
      );
      setAudio(r.audio);
      setMsg(`配音已生成（${r.engine}）✔`);
      onAudioReady();
    } catch (e) { setMsg("失败：" + e.message); setErr(true); }
    finally { setBusy(false); setProgress(null); }
  }

  if (!project?.id) return <p style={{ color: MUTED, fontSize: 13 }}>请先完成前面步骤</p>;

  const speedLabel = Number(speed) === 1 ? "正常" : Number(speed) < 1 ? `慢放 ×${Number(speed).toFixed(1)}` : `快放 ×${Number(speed).toFixed(1)}`;

  return (
    <>
      <h1 style={{ margin: 0, fontSize: 21 }}>AI 配音</h1>
      <p style={{ color: MUTED, fontSize: 13, margin: "4px 0 20px" }}>
        Edge-TTS 逐页合成 · 失败页自动静音兜底
      </p>
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <Btn kind="ghost" icon="arrowL" onClick={() => goPanel("script")}>← 返回上一步</Btn>
        <Btn kind="ghost" onClick={() => goPanel("home")}>⟲ 返回首页</Btn>
      </div>
      <div style={cardStyle}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: MUTED }}>音色</span>
          <Seg options={VOICES} value={voice} onChange={setVoice} />
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", marginTop: 16, flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: MUTED }}>语速</span>
          <div style={{ display: "inline-flex", alignItems: "center", border: `1px solid ${LINE}`, borderRadius: 10, background: "#fff", overflow: "hidden" }}>
            <button onClick={() => nudge(-0.1)} style={{ width: 34, height: 36, border: "none", background: "#F7F4F0", cursor: "pointer", fontSize: 16, fontWeight: 600 }}>−</button>
            <input
              value={speed}
              onChange={(e) => setSpeed(e.target.value)}
              onBlur={(e) => setSpeed(clampSpeed(e.target.value))}
              style={{ width: 64, textAlign: "center", border: "none", outline: "none", fontSize: 15, fontWeight: 700, color: ORANGE }}
            />
            <button onClick={() => nudge(0.1)} style={{ width: 34, height: 36, border: "none", background: "#F7F4F0", cursor: "pointer", fontSize: 16, fontWeight: 600 }}>＋</button>
          </div>
          <span style={{
            fontSize: 12, color: ORANGE, background: ORANGE_SOFT,
            borderRadius: 99, padding: "4px 10px", fontWeight: 600,
          }}>{speedLabel}</span>
          <span style={{ fontSize: 12, color: MUTED }}>0.1 步进 · 1=正常 · 最慢 0.1 · 最快 2.0</span>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <Btn kind="soft" onClick={preview} disabled={previewing}>{previewing ? "合成试听中…" : "🔊 试听"}</Btn>
          <Btn onClick={generate} disabled={busy}>{busy ? "合成中…" : "生成配音"}</Btn>
        </div>
        <Progress progress={progress} />
        <Msg text={msg} error={err} />
      </div>

      {audio.length > 0 && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 10px", fontSize: 15 }}>逐页试听</h3>
          {audio.map((f, i) => (
            <div key={f} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 0", borderBottom: `1px solid ${LINE}` }}>
              <span style={{ color: MUTED, fontSize: 13, width: 56 }}>第 {i + 1} 页</span>
              {audioUrls[f] && <audio controls src={audioUrls[f]} style={{ height: 34 }} />}
            </div>
          ))}
        </div>
      )}
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ fontSize: 13, color: MUTED }}>配音完成 →</span>
        <Btn icon="arrowR" onClick={() => goPanel("video")}>下一步：生成视频 →</Btn>
      </div>
    </>
  );
}

/* ============================================================
   栏目四：生成视频
============================================================ */
function VideoPanel({ project, goPanel }) {
  const [resolution, setResolution] = useState("1080p");
  const [fps, setFps] = useState(30);
  const [subtitle, setSubtitle] = useState(true);
  const [transition, setTransition] = useState(0.5);
  const [followFx, setFollowFx] = useState(false);
  const [fx, setFx] = useState(true);   // 随机镜头动效（Ken Burns）
  const [bgm, setBgm] = useState(true); // 内置背景音乐
  const [bgmStyle, setBgmStyle] = useState("calm");
  const [bgmStyles, setBgmStyles] = useState([]);
  const [previewBgm, setPreviewBgm] = useState(null); // 正在试听的风格 id
  const bgmAudio = useRef(null);

  useEffect(() => {
    api.bgmList().then((d) => setBgmStyles((d.styles || []).filter((s) => s.exists))).catch(() => {});
    return () => { if (bgmAudio.current) bgmAudio.current.src = ""; };
  }, []);

  function previewBgmStyle() {
    if (bgmAudio.current) { bgmAudio.current.src = ""; bgmAudio.current = null; }
    if (previewBgm) { setPreviewBgm(null); return; }
    api.bgmFileUrl(bgmStyle).then((u) => {
      const a = new Audio(u);
      a.onended = () => setPreviewBgm(null);
      a.onerror = () => { setPreviewBgm(null); setMsg("背景音乐试听失败：音乐文件加载失败，请重启应用后重试"); setErr(true); };
      bgmAudio.current = a;
      setPreviewBgm(bgmStyle);
      a.play().catch(() => { setPreviewBgm(null); setMsg("背景音乐试听失败：播放被拦截，请重试"); setErr(true); });
    }).catch(() => { setMsg("背景音乐试听失败：无法连接本地引擎"); setErr(true); });
  }

  const bgmName = (bgmStyles.find((s) => s.id === bgmStyle) || {}).name || "舒缓";
  const [progress, setProgress] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [engine, setEngine] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const timer = useRef(null);

  // 恢复已导出的视频入口（切面板回来不丢失）
  useEffect(() => {
    if (!project?.id) return;
    api.getProject(project.id).then((p) => {
      if (p.files?.video) {
        api.videoDownloadUrl(project.id).then(setVideoUrl).catch(() => {});
        setEngine("上次导出");
      }
    }).catch(() => {});
  }, [project?.id]);

  async function poll(tid) {
    try {
      const t = await api.task(tid);
      if (t.status === "done") {
        setProgress(null);
        setVideoUrl(await api.videoDownloadUrl(project.id));
        setEngine(t.result?.engine || "");
        setMsg("视频合成完成 ✔");
        clearInterval(timer.current);
      } else if (t.status === "error") {
        setProgress(null);
        setMsg("合成失败：" + t.error); setErr(true);
        clearInterval(timer.current);
      } else {
        setProgress(t);
      }
    } catch (e) { clearInterval(timer.current); setMsg("查询失败：" + e.message); setErr(true); }
  }
  useEffect(() => () => clearInterval(timer.current), []);

  async function exportVideo() {
    setVideoUrl(""); setEngine(""); setMsg(""); setErr(false);
    try {
      const r = await api.exportVideo(project.id, { resolution, fps, subtitle, transition, follow_transition: followFx, effects: fx, bgm, bgm_style: bgmStyle });
      setProgress({ status: "running", progress: 0.02, message: "任务已提交" });
      timer.current = setInterval(() => poll(r.taskId), 2000);
    } catch (e) { setMsg("提交失败：" + e.message); setErr(true); }
  }

  const running = progress?.status === "running";
  if (!project?.id) return <p style={{ color: MUTED, fontSize: 13 }}>请先完成前面步骤</p>;

  return (
    <>
      <h1 style={{ margin: 0, fontSize: 21 }}>生成视频</h1>
      <p style={{ color: MUTED, fontSize: 13, margin: "4px 0 20px" }}>
        渲染画面 + 逐页合成 + 烧录字幕 · 每页时长与该页解说词严格同步
      </p>
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <Btn kind="ghost" icon="arrowL" onClick={() => goPanel("audio")}>← 返回上一步</Btn>
        <Btn kind="ghost" onClick={() => goPanel("home")}>⟲ 返回首页</Btn>
      </div>
      <div style={cardStyle}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: MUTED }}>分辨率</span>
          <Seg options={[["720p", "720p"], ["1080p", "1080p"]]} value={resolution} onChange={setResolution} />
          <span style={{ fontSize: 13, color: MUTED }}>帧率</span>
          <Seg options={[[30, "30"], [60, "60"]]} value={fps} onChange={setFps} />
          <span style={{ fontSize: 13, color: MUTED }}>转场</span>
          <Seg options={[[0, "0"], [0.5, "0.5s"], [1, "1s"]]} value={transition} onChange={setTransition} />
        </div>
        <div style={{ display: "flex", gap: 22, marginTop: 14, flexWrap: "wrap", alignItems: "center" }}>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
            <input type="checkbox" checked={subtitle} onChange={(e) => setSubtitle(e.target.checked)} style={{ accentColor: ORANGE, width: 16, height: 16 }} /> 烧录字幕
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
            <input type="checkbox" checked={bgm} onChange={(e) => setBgm(e.target.checked)} style={{ accentColor: ORANGE, width: 16, height: 16 }} />
            背景音乐（推荐）
            <span style={{ fontSize: 11, color: MUTED, background: "#F1EDE8", padding: "2px 8px", borderRadius: 99 }}>
              内置 5 风格 · 可商用 · 自动压低音量不抢解说
            </span>
          </label>
          {bgm && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginTop: 10 }}>
              <Seg
                options={(bgmStyles.length ? bgmStyles.map((s) => [s.id, s.name]) : [["calm", "舒缓"]])}
                value={bgmStyle}
                onChange={setBgmStyle}
              />
              <button onClick={previewBgmStyle}
                style={{
                  border: `1px solid ${previewBgm ? ORANGE : LINE}`, borderRadius: 8,
                  background: previewBgm ? ORANGE_SOFT : "#fff", color: previewBgm ? ORANGE : INK,
                  fontSize: 12, padding: "5px 12px", cursor: "pointer", fontWeight: 600,
                }}>
                {previewBgm ? "◼ 停止试听" : `🔊 试听《${bgmName}》`}
              </button>
            </div>
          )}
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
            <input type="checkbox" checked={fx} onChange={(e) => setFx(e.target.checked)} style={{ accentColor: ORANGE, width: 16, height: 16 }} />
            随机镜头动效（推荐）
            <span style={{ fontSize: 11, color: MUTED, background: "#F1EDE8", padding: "2px 8px", borderRadius: 99 }}>
              每页随机推近/拉远/平移
            </span>
          </label>
          <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
            <input type="checkbox" checked={followFx} onChange={(e) => setFollowFx(e.target.checked)} style={{ accentColor: ORANGE, width: 16, height: 16 }} />
            跟随 PPT 原始切换动效
            <span style={{ fontSize: 11, color: MUTED, background: "#F1EDE8", padding: "2px 8px", borderRadius: 99 }}>
              需本机装有 Office / WPS
            </span>
          </label>
        </div>
        <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.8, marginTop: 10 }}>
          勾选后：你 PPT 里设置的翻页切换效果会应用到视频对应页面的转场上（硬切保持硬切；其他动效按其时长平滑过渡）。未设置动效的页面使用上方全局转场。
        </div>
        <div style={{ marginTop: 16, display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
          {running ? (
            <Btn onClick={() => {}} disabled icon="play">合成中…</Btn>
          ) : videoUrl ? (
            <Btn onClick={async () => {
              try {
                await api.downloadFile(videoUrl, "PPTVideoStudio.mp4");
                setMsg("视频已开始下载，请留意系统下载提示 ✔"); setErr(false);
              } catch (e) { setMsg("下载失败：" + e.message); setErr(true); }
            }} icon="save">下载 MP4</Btn>
          ) : (
            <Btn onClick={exportVideo} icon="play">开始合成视频</Btn>
          )}
          {videoUrl && !running && (
            <span style={{ fontSize: 12, color: MUTED }}>
              {engine ? `合成引擎：${engine} · ` : ""}<span onClick={exportVideo} style={{ color: ORANGE, cursor: "pointer" }}>重新合成</span>
            </span>
          )}
        </div>
        <Progress progress={progress} />
        <Msg text={msg} error={err} />
      </div>
    </>
  );
}

/* ============================================================
   栏目五：高级设置
============================================================ */
const AI_PRESETS = {
  deepseek: { name: "DeepSeek", base: "https://api.deepseek.com", model: "deepseek-chat" },
  zhipu: { name: "智谱 GLM", base: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-air" },
  kimi: { name: "Kimi 月之暗面", base: "https://api.moonshot.cn/v1", model: "moonshot-v1-8k" },
  qwen: { name: "通义千问", base: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  openai: { name: "OpenAI", base: "https://api.openai.com/v1", model: "gpt-4o-mini" },
};

function SettingsPanel({ onUpdate }) {
  const [s, setS] = useState(null);
  const [showWechat, setShowWechat] = useState(false);
  const [wechatCopied, setWechatCopied] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [editing, setEditing] = useState(null);   // 正在编辑/新增的 profile（null=关闭）
  const [testingId, setTestingId] = useState(null);
  const [testResults, setTestResults] = useState({}); // {profileId: {ok, model|error}}

  useEffect(() => { api.getSettings().then(setS).catch((e) => setMsg("加载失败：" + e.message)); }, []);

  const upd = (k, v) => setS((prev) => ({ ...prev, [k]: v }));
  async function save() {
    try { await api.saveSettings(s); setMsg("设置已保存 ✔"); setErr(false); }
    catch (e) { setMsg("保存失败：" + e.message); setErr(true); }
  }

  function saveProfile() {
    const p = { ...editing };
    if (!p.name?.trim() || !p.base?.trim() || !p.model?.trim()) {
      setMsg("名称、API 地址、模型名都要填"); setErr(true); return;
    }
    const list = [ ...(s.ai_profiles || []) ];
    const i = list.findIndex((x) => x.id === p.id);
    if (i >= 0) list[i] = p; else list.push(p);
    const next = { ...s, ai_profiles: list };
    if (!next.default_profile) next.default_profile = p.id;
    setS(next);
    setEditing(null);
    api.saveSettings(next).then(() => setMsg("AI 配置已保存 ✔")).catch((e) => setMsg("保存失败：" + e.message));
  }

  function deleteProfile(id) {
    const list = (s.ai_profiles || []).filter((x) => x.id !== id);
    const next = { ...s, ai_profiles: list };
    if (next.default_profile === id) next.default_profile = list[0]?.id || "";
    setS(next);
    api.saveSettings(next).then(() => setMsg("已删除 ✔")).catch((e) => setMsg("删除失败：" + e.message));
  }

  function setDefault(id) {
    const next = { ...s, default_profile: id };
    setS(next);
    api.saveSettings(next).then(() => setMsg("已设为默认 ✔")).catch((e) => setMsg("设置失败：" + e.message));
  }

  async function testProfile(id) {
    setTestingId(id);
    try {
      const r = await api.testLlm(id);
      setTestResults((m) => ({ ...m, [id]: r }));
    } catch (e) {
      setTestResults((m) => ({ ...m, [id]: { ok: false, error: e.message } }));
    } finally { setTestingId(null); }
  }

  const profiles = s?.ai_profiles || [];

  const profileEditor = editing && (
    <div style={{ border: `1.5px solid ${ORANGE}`, borderRadius: 12, padding: 14, display: "grid", gap: 10 }}>
      <select
        value=""
        onChange={(e) => {
          const p = AI_PRESETS[e.target.value];
          if (p) setEditing({ ...editing, base: p.base, model: p.model, name: editing.name || p.name });
        }}
        style={{ ...inputStyle, color: MUTED }}
      >
        <option value="">选择服务商，自动填充地址和模型名…</option>
        {Object.entries(AI_PRESETS).map(([k, p]) => (
          <option key={k} value={k}>{p.name}（{p.model}）</option>
        ))}
      </select>
      <input value={editing.name || ""} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
        style={inputStyle} placeholder="配置名称（如：DeepSeek 官方 / 我的 API 中转）" />
      <input value={editing.base || ""} onChange={(e) => setEditing({ ...editing, base: e.target.value })}
        style={inputStyle} placeholder="API 地址（https://…/v1）" />
      <div style={{ display: "flex", gap: 10 }}>
        <input type="password" value={editing.key || ""} onChange={(e) => setEditing({ ...editing, key: e.target.value })}
          style={{ ...inputStyle, flex: 1 }} placeholder="API Key（sk-…）" />
        <input value={editing.model || ""} onChange={(e) => setEditing({ ...editing, model: e.target.value })}
          style={{ ...inputStyle, width: 180 }} placeholder="模型名" />
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <Btn onClick={saveProfile}>保存此配置</Btn>
        <Btn kind="ghost" onClick={() => setEditing(null)}>取消</Btn>
      </div>
    </div>
  );

  const profileList = (
    <div style={{ display: "grid", gap: 8 }}>
      {profiles.length === 0 && (
        <div style={{ color: MUTED, fontSize: 13 }}>还没有保存的 AI 配置，点下面「＋ 添加 AI」开始。</div>
      )}
      {profiles.map((p) => {
        const isDefault = s?.default_profile === p.id;
        const tr = testResults[p.id];
        return (
          <div key={p.id} style={{
            display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
            border: `1px solid ${isDefault ? ORANGE : LINE}`, borderRadius: 12,
            padding: "10px 14px", background: isDefault ? ORANGE_SOFT : "#fff",
          }}>
            {isDefault && (
              <span style={{ fontSize: 11, color: "#fff", background: ORANGE, borderRadius: 99, padding: "2px 10px", fontWeight: 700 }}>
                默认
              </span>
            )}
            <div style={{ minWidth: 140 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{p.name}</div>
              <div style={{ fontSize: 12, color: MUTED }}>{p.model} · {p.base}</div>
            </div>
            <span style={{ flex: 1 }} />
            {!isDefault && <Btn kind="ghost" onClick={() => setDefault(p.id)}>设为默认</Btn>}
            <Btn kind="ghost" onClick={() => testProfile(p.id)} disabled={testingId === p.id}>
              {testingId === p.id ? "测试中…" : "测试"}
            </Btn>
            <Btn kind="ghost" onClick={() => setEditing({ ...p })}>修改</Btn>
            <Btn kind="ghost" onClick={() => deleteProfile(p.id)}
              style={{ color: "#D93025", borderColor: "#F2C7C2" }}>删除</Btn>
            {tr && tr.ok && <span style={{ fontSize: 12, color: "#1a7f37", width: "100%" }}>✔ 连通正常（{tr.model}）</span>}
            {tr && !tr.ok && <span style={{ fontSize: 12, color: "#D93025", width: "100%" }}>✘ {tr.error}</span>}
          </div>
        );
      })}
      {!editing && (
        <div>
          <Btn kind="soft" onClick={() => setEditing({ id: `p${Date.now()}`, name: "", base: "", key: "", model: "" })}>
            ＋ 添加 AI
          </Btn>
        </div>
      )}
    </div>
  );

  const LLMFields = ({ prefix, disabled }) => (
    <div style={{ opacity: disabled ? 0.45 : 1, display: "grid", gap: 10 }}>
      <select
        value=""
        disabled={disabled}
        onChange={(e) => {
          const p = AI_PRESETS[e.target.value];
          if (p) {
            upd(`${prefix}_api_base`, p.base);
            upd(`${prefix}_model`, p.model);
          }
        }}
        style={{ ...inputStyle, color: MUTED }}
      >
        <option value="">选择服务商，自动填充地址和模型名…</option>
        {Object.entries(AI_PRESETS).map(([k, p]) => (
          <option key={k} value={k}>{p.name}（{p.model}）</option>
        ))}
      </select>
      <input value={s?.[`${prefix}_api_base`] || ""} disabled={disabled}
        onChange={(e) => upd(`${prefix}_api_base`, e.target.value)}
        style={inputStyle} placeholder="API 地址（https://…/v1）" />
      <div style={{ display: "flex", gap: 10 }}>
        <input type="password" value={s?.[`${prefix}_api_key`] || ""} disabled={disabled}
          onChange={(e) => upd(`${prefix}_api_key`, e.target.value)}
          style={{ ...inputStyle, flex: 1 }} placeholder="API Key（sk-…）" />
        <input value={s?.[`${prefix}_model`] || ""} disabled={disabled}
          onChange={(e) => upd(`${prefix}_model`, e.target.value)}
          style={{ ...inputStyle, width: 180 }} placeholder="模型名" />
      </div>
    </div>
  );

  return (
    <>
      <h1 style={{ margin: 0, fontSize: 21 }}>高级设置</h1>
      <p style={{ color: MUTED, fontSize: 13, margin: "4px 0 20px" }}>
        不同环节的 AI 分开配置 · 关于开发者
      </p>

      <div style={cardStyle}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, display: "flex", gap: 8, alignItems: "center" }}>
          ① PPT 生成 AI
          <span style={{ fontSize: 11, color: ORANGE, background: ORANGE_SOFT, padding: "2px 8px", borderRadius: 99, fontWeight: 600 }}>用于：大纲 + 逐页内容</span>
        </h3>
        {profileList}
        {profileEditor}
        <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.8, marginTop: 10 }}>
          可保存多个 AI 配置，标记「默认」的会被首页生成时优先选用（首页也可以临时切换）。<br />
          常见模型名：DeepSeek 填 <b>deepseek-chat</b> / <b>deepseek-reasoner</b>；智谱 GLM 填 glm-4-air 等；Kimi 填 moonshot-v1-8k。API 地址填到根路径即可（如 https://api.deepseek.com）。
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, display: "flex", gap: 8, alignItems: "center" }}>
          ② 解说词 AI
          <span style={{ fontSize: 11, color: ORANGE, background: ORANGE_SOFT, padding: "2px 8px", borderRadius: 99, fontWeight: 600 }}>用于：逐页讲稿撰写</span>
        </h3>
        <label style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer", marginBottom: 10 }}>
          <input type="checkbox" checked={s ? s.script_llm_same !== false : true}
            onChange={(e) => upd("script_llm_same", e.target.checked)}
            style={{ accentColor: ORANGE, width: 16, height: 16 }} />
          与「PPT 生成 AI」使用相同配置
        </label>
        {s && s.script_llm_same === false && <LLMFields prefix="script_llm" />}
        <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.8, marginTop: 10 }}>
          解说词对文笔要求更高，可以取消勾选单独配一个写作强的模型。
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15, display: "flex", gap: 8, alignItems: "center" }}>
          ③ 配音引擎
          <span style={{ fontSize: 11, color: MUTED, background: "#F1EDE8", padding: "2px 8px", borderRadius: 99 }}>不是文字 AI · 是语音合成</span>
        </h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <tbody>
            <tr><td style={{ padding: "8px 0", color: MUTED, width: 110 }}>当前引擎</td><td>Edge-TTS（微软，免费，需联网）</td></tr>
            <tr><td style={{ padding: "8px 0", color: MUTED }}>自定义 TTS</td><td style={{ color: MUTED }}>预留接口，后续版本支持接入你自己的语音合成服务</td></tr>
          </tbody>
        </table>
      </div>

      <div style={cardStyle}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>关于开发者</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <tbody>
            <tr><td style={{ padding: "8px 0", color: MUTED, width: 110 }}>软件</td><td>PPTVideoStudio v{APP_VERSION}</td></tr>
            <tr><td style={{ padding: "8px 0", color: MUTED }}>版权</td><td>© 2026 梦极</td></tr>
            <tr><td style={{ padding: "8px 0", color: MUTED }}>联系开发者</td>
              <td>
                {showWechat
                  ? <span>微信：<b style={{ color: INK }}>mengji333</b>（点击复制）<span onClick={() => { try { navigator.clipboard.writeText("mengji333"); setWechatCopied(true); setTimeout(() => setWechatCopied(false), 2000); } catch {} }} style={{ color: ORANGE, cursor: "pointer", marginLeft: 6 }}>{wechatCopied ? "已复制 ✔" : "复制"}</span></span>
                  : <span onClick={() => setShowWechat(true)} style={{ color: ORANGE, cursor: "pointer" }}>点击显示联系方式</span>}
              </td></tr>
            <tr><td style={{ padding: "8px 0", color: MUTED }}>检查更新</td>
              <td>
                <span onClick={async () => { const u = await window.pvs.checkUpdate(); onUpdate?.(u); }}
                  style={{ color: ORANGE, cursor: "pointer" }}>检查更新（GitHub）</span>
                {" "}· <span onClick={() => window.pvs.openExternal((typeof window !== "undefined" && window.pvs) ? "https://pan.quark.cn/s/b76fc109e73d" : "#")} style={{ color: ORANGE, cursor: "pointer" }}>夸克网盘</span>
              </td></tr>
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <Btn onClick={save}>保存设置</Btn>
        <Msg text={msg} error={err} />
      </div>
    </>
  );
}

/* ============================================================
   后端网关页 & 更新弹窗
============================================================ */
function BackendGate({ info, children }) {
  const [slowStart, setSlowStart] = useState(false);
  useEffect(() => {
    if (info.ready || info.error) { setSlowStart(false); return; }
    const t = setTimeout(() => setSlowStart(true), 30000);
    return () => clearTimeout(t);
  }, [info.ready, info.error]);
  if (info.ready) return children;
  return (
    <div style={{ minHeight: "70vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ textAlign: "center", maxWidth: 460 }}>
        {!info.error ? (
          <>
            <div style={{
              width: 42, height: 42, border: `4px solid ${LINE}`, borderTopColor: ORANGE,
              borderRadius: "50%", margin: "0 auto 18px", animation: "spin 1s linear infinite",
            }} />
            <h2 style={{ color: INK, fontSize: 18 }}>正在启动本地引擎…</h2>
            <p style={{ color: MUTED, fontSize: 13 }}>首次启动需要几秒钟，请稍候</p>
            {slowStart && (
              <div style={{ marginTop: 16 }}>
                <p style={{ color: MUTED, fontSize: 12, lineHeight: 1.7 }}>
                  启动时间比预期长（老电脑首次启动可能需要 1~2 分钟）<br />如果一直无响应，可查看日志或重试
                </p>
                <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 12 }}>
                  <Btn kind="ghost" onClick={() => window.pvs.openLogs()}>打开日志文件夹</Btn>
                  <Btn onClick={() => window.pvs.restartBackend()}>重试启动</Btn>
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            <div style={{ fontSize: 40, marginBottom: 10 }}>⚠️</div>
            <h2 style={{ color: INK, fontSize: 18 }}>本地引擎未能启动</h2>
            <p style={{ color: MUTED, fontSize: 13, lineHeight: 1.7 }}>{info.error}</p>
            <div style={{ display: "flex", gap: 10, justifyContent: "center", marginTop: 14 }}>
              <Btn kind="ghost" onClick={() => window.pvs.openLogs()}>打开日志文件夹</Btn>
              <Btn onClick={() => window.pvs.restartBackend()}>重试启动</Btn>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function UpdateDialog({ info, onClose }) {
  const [dlState, setDlState] = useState(null); // {pct, received, total}
  const [dlMsg, setDlMsg] = useState("");
  const [dlErr, setDlErr] = useState("");
  const [slowHint, setSlowHint] = useState(false);
  const lastTick = useRef({ time: Date.now(), received: 0 });
  if (!info) return null;

  useEffect(() => {
    window.pvs.onUpdateProgress?.((p) => {
      setDlState(p);
      const now = Date.now();
      if (p.received !== lastTick.current.received) lastTick.current = { time: now, received: p.received };
    });
    // 下载速度监控：60 秒无进度变化 → 提示网盘
    const timer = setInterval(() => {
      setDlState((s) => {
        if (s && Date.now() - lastTick.current.time > 60000) setSlowHint(true);
        return s;
      });
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  async function oneClickUpdate() {
    if (!info.asset?.url) { setDlErr("未找到当前平台的安装包，请用 GitHub / 夸克网盘下载"); return; }
    setDlErr(""); setSlowHint(false); setDlMsg("正在下载更新…（完成后自动打开安装包）");
    setDlState({ pct: 0, received: 0, total: info.asset.size || 0 });
    lastTick.current = { time: Date.now(), received: 0 };
    const r = await window.pvs.downloadUpdate(info.asset);
    if (!r.ok) { setDlErr(r.error || "下载失败"); setDlMsg(""); setDlState(null); setSlowHint(true); return; }
    setDlMsg("下载完成，正在打开安装包…");
    const ir = await window.pvs.installUpdate(r.path);
    if (!ir.ok) { setDlErr(ir.error || "打开安装包失败"); setDlMsg(""); return; }
    setDlMsg("已打开安装包，请按提示完成安装（安装后重新打开应用即为新版本）");
    setDlState(null);
  }

  const showQuarkHint = dlErr || slowHint;
  return (
    <div onClick={dlState ? undefined : onClose} style={{
      position: "fixed", inset: 0, background: "rgba(30,25,20,.35)", zIndex: 100,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "#fff", borderRadius: 16, padding: 26, width: 440, boxShadow: "0 12px 40px rgba(0,0,0,.15)",
      }}>
        <h3 style={{ margin: "0 0 6px", fontSize: 17, color: INK }}>
          {info.available ? `发现新版本 v${info.latest}` : "检查更新"}
        </h3>
        <p style={{ color: MUTED, fontSize: 13, margin: "0 0 16px", lineHeight: 1.7 }}>
          当前版本 v{info.current}
          {info.available ? `，最新版本 v${info.latest}。可一键更新（应用内直接下载并打开安装包），也可从 GitHub / 夸克网盘手动下载。` : info.source === "none" ? "，暂时连不上 GitHub 更新服务，可从夸克网盘手动获取最新版本。" : "，已是最新版本。"}
        </p>
        {dlMsg && <p style={{ color: INK, fontSize: 13, margin: "0 0 10px" }}>{dlMsg}</p>}
        {dlState && (
          <div style={{ marginBottom: 12 }}>
            <div className="pvs-indet" style={{ display: dlState.pct >= 0 ? "none" : "block" }}><div /></div>
            {dlState.pct >= 0 && (
              <>
                <div style={{ height: 8, background: "#F1EDE8", borderRadius: 6, overflow: "hidden" }}>
                  <div style={{ width: `${dlState.pct}%`, height: "100%", background: ORANGE, borderRadius: 6, transition: "width .3s" }} />
                </div>
                <div style={{ color: MUTED, fontSize: 12, marginTop: 6 }}>
                  {dlState.pct}%{dlState.total ? `（${(dlState.received / 1048576).toFixed(1)} / ${(dlState.total / 1048576).toFixed(1)} MB）` : ""}
                </div>
              </>
            )}
          </div>
        )}
        {showQuarkHint && (
          <div onClick={() => window.pvs.openExternal(info.quark)} style={{
            background: "#FFF4EC", border: `1px solid ${ORANGE}`, borderRadius: 10,
            padding: "10px 14px", marginBottom: 12, cursor: "pointer", fontSize: 13, color: INK, lineHeight: 1.6,
          }}>
            💡 下载{dlErr ? "失败" : "太慢"}？<b style={{ color: ORANGE }}>点此用夸克网盘下载</b>，国内速度更快（安装包一致）
          </div>
        )}
        {dlErr && <p style={{ color: "#C0392B", fontSize: 12, margin: "0 0 10px" }}>{dlErr}</p>}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {info.available && info.asset?.url && (
            <Btn onClick={oneClickUpdate} disabled={!!dlState}>⚡ 一键更新{info.asset.size ? `（${(info.asset.size / 1048576).toFixed(0)} MB）` : ""}</Btn>
          )}
          {info.available && info.url && <Btn kind="ghost" onClick={() => window.pvs.openExternal(info.url)} disabled={!!dlState}>GitHub 下载</Btn>}
          <Btn kind={showQuarkHint ? "primary" : info.available ? "ghost" : "primary"} onClick={() => window.pvs.openExternal(info.quark)} disabled={!!dlState}>夸克网盘</Btn>
          <Btn kind="ghost" onClick={onClose} disabled={!!dlState}>{info.available ? "暂不更新" : "关闭"}</Btn>
        </div>
      </div>
    </div>
  );
}

/* ============================================================
   App 外壳：左侧导航 + 右侧内容
============================================================ */
const NAVS = [
  ["home", "首页", "home"],
  ["script", "解说词", "script"],
  ["audio", "AI 配音", "audio"],
  ["video", "生成视频", "video"],
  ["settings", "高级设置", "settings"],
];

export default function App() {
  const { info } = useBackend();
  const [panel, setPanel] = useState("home");
  const [project, setProject] = useState({ id: null, topic: "" });
  const [badges, setBadges] = useState({ script: "待生成", audio: "待生成", video: "待导出" });
  const [update, setUpdate] = useState(null);
  const [newVersion, setNewVersion] = useState(null);
  const [downloadToast, setDownloadToast] = useState(null);

  useEffect(() => {
    window.pvs.updateInfo().then((u) => { if (u.available) setNewVersion(u); }).catch(() => {});
    // 原生下载完成通知（主进程 will-download 钩子推送）
    window.pvs.onDownloadDone?.((d) => {
      setDownloadToast(d.ok
        ? `已保存到「下载」文件夹：${d.name}`
        : `下载未完成：${d.name}`);
      setTimeout(() => setDownloadToast(null), 6000);
    });
  }, []);

  const goPanel = (p) => setPanel(p);
  const setBadge = (k, v) => setBadges((b) => ({ ...b, [k]: v }));

  return (
    <div style={{
      height: "100vh", background: "#FAFAF9", color: INK,
      fontFamily: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
      display: "flex", flexDirection: "column",
    }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }
        input:focus, textarea:focus { border-color: ${ORANGE} !important; }
        ::selection { background: #FFD9C4; }
        ::-webkit-scrollbar { width: 8px; } ::-webkit-scrollbar-thumb { background: #E5DFD8; border-radius: 4px; }
        button { font-family: inherit; }
        @keyframes pvsIndet { 0% { left: -35%; } 100% { left: 100%; } }
        .pvs-indet { position: relative; overflow: hidden; background: #F1EDE8; border-radius: 6px; height: 7px; }
        .pvs-indet > div { position: absolute; top: 0; width: 35%; height: 100%; border-radius: 6px; background: ${ORANGE}; animation: pvsIndet 1.4s ease-in-out infinite; }
        @keyframes pvsSkel { 0%, 100% { opacity: .45; } 50% { opacity: 1; } }`}</style>

      {/* 更新横幅 */}
      {newVersion && (
        <div onClick={() => setUpdate(newVersion)} style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          padding: "7px 20px", background: ORANGE, color: "#fff", fontSize: 13,
          cursor: "pointer", fontWeight: 600,
        }}>
          发现新版本 v{newVersion.latest}，点击立即更新（GitHub / 夸克网盘）
        </div>
      )}

      {/* 下载完成提示（右下角浮层） */}
      {downloadToast && (
        <div style={{
          position: "fixed", right: 18, bottom: 18, zIndex: 99,
          background: INK, color: "#fff", fontSize: 13,
          padding: "10px 16px", borderRadius: 10,
          boxShadow: "0 8px 24px rgba(0,0,0,.25)",
        }}>{downloadToast}</div>
      )}

      <div style={{ flex: 1, display: "flex", minHeight: 0 }}>
        {/* 左侧导航 */}
        <aside style={{
          width: 200, background: SIDE, flexShrink: 0,
          padding: "14px 10px", display: "flex", flexDirection: "column", gap: 4,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "8px 14px 16px" }}>
            <span style={{
              width: 26, height: 26, borderRadius: 8,
              background: `linear-gradient(135deg, ${ORANGE}, #FF9A6B)`,
              display: "inline-flex", alignItems: "center", justifyContent: "center", color: "#fff",
            }}><Icon d={ICONS.play} size={12} /></span>
            <strong style={{ color: "#fff", fontSize: 14 }}>PPTVideoStudio</strong>
          </div>
          {NAVS.map(([key, label, icon]) => (
            <div key={key} onClick={() => setPanel(key)}
              style={{
                display: "flex", alignItems: "center", gap: 11, padding: "11px 14px",
                borderRadius: 10, cursor: "pointer", fontSize: 14,
                background: panel === key ? ORANGE : "transparent",
                color: panel === key ? "#fff" : "#B5ADA4",
                fontWeight: panel === key ? 600 : 400,
              }}
              onMouseEnter={(e) => { if (panel !== key) e.currentTarget.style.background = SIDE_HOVER; }}
              onMouseLeave={(e) => { if (panel !== key) e.currentTarget.style.background = "transparent"; }}
            >
              <Icon d={ICONS[icon]} />
              {label}
              {badges[key] && (
                <span style={{
                  marginLeft: "auto", fontSize: 11,
                  background: badges[key].includes("✔") ? "rgba(120,200,140,.3)" : "rgba(255,255,255,.14)",
                  padding: "1px 8px", borderRadius: 99,
                }}>{badges[key]}</span>
              )}
            </div>
          ))}
          <div style={{ marginTop: "auto", padding: "8px 14px 4px" }}>
            <div onClick={async () => setUpdate(await window.pvs.checkUpdate())}
              style={{
                display: "flex", alignItems: "center", gap: 9, padding: "9px 12px",
                borderRadius: 10, cursor: "pointer", fontSize: 13, color: "#B5ADA4",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = SIDE_HOVER; e.currentTarget.style.color = "#fff"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#B5ADA4"; }}
            >
              <span style={{ fontSize: 14 }}>⬆</span> 检查更新
            </div>
          </div>
          <div style={{ padding: "6px 14px 14px", fontSize: 11, color: "#6d665e", lineHeight: 1.8 }}>
            © 2026 梦极<br />联系开发者微信：mengji333
          </div>
        </aside>

        {/* 右侧内容 */}
        <main style={{ flex: 1, overflowY: "auto", padding: "26px 30px", minWidth: 0 }}>
          <BackendGate info={info}>
            {panel === "home" && (
              <HomePanel project={project} setProject={setProject} goPanel={goPanel}
                onProjectChanged={() => { setBadge("script", "待生成"); setBadge("audio", "待生成"); setBadge("video", "待导出"); }} />
            )}
            {panel === "script" && (
              <ScriptPanel project={project} goPanel={goPanel}
                onScriptReady={() => { setBadge("script", "已完成 ✔"); setBadge("audio", "待生成"); }} />
            )}
            {panel === "audio" && (
              <AudioPanel project={project} goPanel={goPanel}
                onAudioReady={() => { setBadge("audio", "已完成 ✔"); setBadge("video", "待导出"); }} />
            )}
            {panel === "video" && (
              <VideoPanel project={project} goPanel={goPanel} />
            )}
            {panel === "settings" && <SettingsPanel onUpdate={setUpdate} />}
          </BackendGate>
        </main>
      </div>

      <UpdateDialog info={update} onClose={() => setUpdate(null)} />
    </div>
  );
}
