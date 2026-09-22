import React, { useCallback, useEffect, useRef, useState } from "react";
import { api, runTask } from "./api";

const APP_VERSION = "0.5.0";
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

function Progress({ progress }) {
  if (!progress) return null;
  const pct = Math.round((progress.progress || 0) * 100);
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
      </div>
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
    <div style={{ display: "inline-flex", background: "#F1EDE8", borderRadius: 10, padding: 3, ...style }}>
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
function Thumb({ projectId, index, tick, onZoom, big, w = 150 }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    let alive = true;
    if (!projectId) return;
    api.thumbUrl(projectId, index).then((u) => alive && setUrl(`${u}?t=${tick}`)).catch(() => {});
    return () => { alive = false; };
  }, [projectId, index, tick]);
  return (
    <div
      onClick={big ? undefined : onZoom}
      style={{
        width: w, height: (w * 9) / 16, flexShrink: 0, borderRadius: 8, overflow: "hidden",
        background: "#F1EDE8", border: `1px solid ${LINE}`, cursor: big ? "default" : "zoom-in",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      {url ? (
        <img src={url} style={{ width: "100%", height: "100%", objectFit: "cover" }} alt={`第${index + 1}页`} />
      ) : (
        <span style={{ color: MUTED, fontSize: 12 }}>渲染中…</span>
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
const STYLES = ["简约商务", "科技渐变", "清新留白", "图文并茂"];

function HomePanel({ project, setProject, goPanel, onProjectChanged }) {
  const [step, setStep] = useState(1); // 1 输入 2 版式 3 预览
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(8);
  const [color, setColor] = useState(COLORS[0][0]);
  const [style, setStyle] = useState(STYLES[0]);
  const [projects, setProjects] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [progress, setProgress] = useState(null);
  const [slides, setSlides] = useState([]);
  const [thumbTick, setThumbTick] = useState(0);

  const refresh = useCallback(() => api.listProjects().then(setProjects).catch(() => {}), []);
  useEffect(() => { refresh(); }, [refresh, project?.id]);

  // 打开已有项目时直接进入预览
  useEffect(() => {
    if (!project?.id) return;
    api.getSlides(project.id).then((d) => { setSlides(d.slides || []); if ((d.slides || []).length) setStep(3); }).catch(() => {});
  }, [project?.id]);

  async function startGenerate() {
    setBusy(true); setMsg(""); setErr(false); setProgress(null);
    try {
      let pid = project?.id;
      if (!pid) {
        const p = await api.createProject(topic);
        pid = p.id;
        setProject({ id: pid, topic });
      }
      await runTask(
        () => api.generatePpt(pid, { slides: count, color, style }),
        (t) => setProgress(t)
      );
      const d = await api.getSlides(pid);
      setSlides(d.slides || []);
      setThumbTick((t) => t + 1);
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
      setStep(3);
      setMsg(`导入成功，共 ${p.slides.length} 页 ✔`);
      refresh();
    } catch (e2) {
      setMsg("导入失败：" + e2.message); setErr(true);
    } finally { setBusy(false); e.target.value = ""; }
  }

  async function savePpt() {
    setBusy(true); setMsg(""); setErr(false);
    try {
      await api.saveSlides(project.id, slides);
      setThumbTick((t) => t + 1);
      setMsg("PPT 已保存 ✔");
    } catch (e) { setMsg("保存失败：" + e.message); setErr(true); }
    finally { setBusy(false); }
  }

  function open(p) {
    setProject({ id: p.id, topic: p.topic });
    setMsg("");
  }

  const stepDots = (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, fontSize: 12, color: MUTED }}>
      <b style={{ color: step === 1 ? ORANGE : INK }}>① {project?.topic || "输入主题"}</b>
      <span style={{ color: "#D5CFC8" }}>→</span>
      <b style={{ color: step === 2 ? ORANGE : step > 2 ? INK : "#C5BFB7" }}>② 选择版式</b>
      <span style={{ color: "#D5CFC8" }}>→</span>
      <b style={{ color: step === 3 ? ORANGE : "#C5BFB7" }}>③ 预览保存</b>
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
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="输入主题，例如：智慧文旅夜游项目汇报"
              style={{ ...inputStyle, fontSize: 15, padding: "14px 16px" }}
              onKeyDown={(e) => e.key === "Enter" && topic.trim() && setStep(2)}
            />
          </div>
          <div style={{ display: "flex", gap: 12, marginTop: 18 }}>
            <Btn icon="arrowR" disabled={!topic.trim()} onClick={() => setStep(2)}>生成 PPT</Btn>
            <label style={{ cursor: "pointer" }}>
              <Btn kind="ghost" icon="upload" disabled={busy}>上传 PPT（.pptx）</Btn>
              <input type="file" accept=".pptx" onChange={importPpt} style={{ display: "none" }} />
            </label>
          </div>
          <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.8, marginTop: 12 }}>
            上传的 PPT 导出视频时直接使用你 PPT 的原始页面（需本机装有 Office 或 WPS）
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
          <Seg options={[[5, "5 页"], [8, "8 页"], [12, "12 页"], [15, "15 页"]]} value={count} onChange={setCount} />
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
          <div style={{ display: "flex", gap: 10, marginTop: 20, alignItems: "center", flexWrap: "wrap" }}>
            <Btn kind="ghost" icon="arrowL" onClick={() => setStep(1)}>上一步</Btn>
            <Btn onClick={startGenerate} disabled={busy}>{busy ? "生成中…" : "开始生成"}</Btn>
            <span style={{ fontSize: 12, color: MUTED }}>分析主题 → 抓取网络资料 → 大纲 → 逐页内容</span>
          </div>
          <Progress progress={progress} />
          <Msg text={msg} error={err} />
        </div>
      )}

      {step === 3 && (
        <>
          <div style={cardStyle}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
              <h3 style={{ margin: 0, fontSize: 15 }}>预览（{slides.length} 页）</h3>
              <span style={{ flex: 1 }} />
              <Btn kind="ghost" icon="save" onClick={savePpt} disabled={busy || !slides.length}>保存 PPT</Btn>
              <Btn icon="arrowR" onClick={() => goPanel("script")} disabled={!slides.length}>生成解说词，进入下一步 →</Btn>
            </div>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              {slides.map((_, i) => (
                <Thumb key={i} projectId={project?.id} index={i} tick={thumbTick} w={132} onZoom={() => {}} />
              ))}
            </div>
            <Msg text={msg} error={err} />
          </div>
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
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [progress, setProgress] = useState(null);
  const [thumbTick, setThumbTick] = useState(0);

  useEffect(() => {
    if (!project?.id) return;
    setMsg(""); setProgress(null);
    api.getSlides(project.id).then((d) => setSlides(d.slides || [])).catch(() => {});
    api.getProject(project.id).then((p) => setScript(p.script || [])).catch(() => {});
    setThumbTick((t) => t + 1);
  }, [project?.id]);

  const updScript = (i, val) => {
    const next = [...script];
    next[i] = val;
    setScript(next);
  };

  async function genScript() {
    setBusy(true); setMsg(""); setErr(false); setProgress(null);
    try {
      const r = await runTask(
        () => api.generateSpeech(project.id, { tone: "专业" }),
        (t) => setProgress(t)
      );
      setScript(r.pages);
      setMsg(r.source === "llm" ? "解说词已根据每页内容生成（AI）✔" : "已按每页内容生成解说词（内置引擎）✔ 接入 LLM 可获得更自然的讲稿");
    } catch (e) { setMsg("失败：" + e.message); setErr(true); }
    finally { setBusy(false); setProgress(null); }
  }

  async function saveScript() {
    setBusy(true); setMsg(""); setErr(false);
    try {
      await api.saveSpeech(project.id, script);
      setMsg("解说词已保存 ✔");
      onScriptReady();
    } catch (e) { setMsg("保存失败：" + e.message); setErr(true); }
    finally { setBusy(false); }
  }

  if (!project?.id) return <p style={{ color: MUTED, fontSize: 13 }}>请先在首页生成或导入 PPT</p>;

  return (
    <>
      <h1 style={{ margin: 0, fontSize: 21 }}>解说词</h1>
      <p style={{ color: MUTED, fontSize: 13, margin: "4px 0 20px" }}>
        基于每页实际内容撰写 · 可逐页修改 · 保存后写入 PPT 演讲者备注
      </p>
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <Btn kind="soft" icon="refresh" onClick={genScript} disabled={busy || !slides.length}>AI 重新生成全部</Btn>
        <Btn kind="ghost" icon="save" onClick={saveScript} disabled={busy || !script.length}>保存解说词</Btn>
        <span style={{ flex: 1 }} />
        {progress && <div style={{ width: 180 }}><Progress progress={progress} /></div>}
      </div>
      <div style={cardStyle}>
        {slides.length === 0 && <p style={{ color: MUTED, fontSize: 13 }}>—</p>}
        {slides.map((s, i) => (
          <div key={i} style={{ display: "flex", gap: 14, padding: "14px 0", borderBottom: i < slides.length - 1 ? `1px solid ${LINE}` : "none" }}>
            <div style={{ width: 132, flexShrink: 0 }}>
              <Thumb projectId={project?.id} index={i} tick={thumbTick} w={132} onZoom={() => {}} />
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
                placeholder="本页解说词（点击上方 AI 重新生成，或直接输入）"
              />
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ fontSize: 13, color: MUTED }}>确认无误后 →</span>
        <Btn icon="arrowR" onClick={() => goPanel("audio")}>下一步：AI 配音 →</Btn>
      </div>
      <Msg text={msg} error={err} />
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
  const [previewUrl, setPreviewUrl] = useState("");
  const previewRef = useRef(null);

  const clampSpeed = (v) => {
    const n = Number(v);
    if (Number.isNaN(n)) return 1.0;
    return Math.round(Math.max(0.1, Math.min(2.0, n)) * 10) / 10;
  };

  useEffect(() => {
    if (!project?.id) { setAudio([]); return; }
    setAudioUrls({});
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
    try {
      const u = `${await api.previewUrl(voice, clampSpeed(speed))}?t=${Date.now()}`;
      setPreviewUrl(u);
      setTimeout(() => previewRef.current?.play().catch(() => {}), 120);
    } catch { setMsg("试听失败，请检查网络"); setErr(true); }
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
          <Btn kind="soft" onClick={preview}>🔊 试听</Btn>
          {previewUrl && <audio ref={previewRef} src={previewUrl} style={{ display: "none" }} />}
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
function VideoPanel({ project }) {
  const [resolution, setResolution] = useState("1080p");
  const [fps, setFps] = useState(30);
  const [subtitle, setSubtitle] = useState(true);
  const [transition, setTransition] = useState(0.5);
  const [followFx, setFollowFx] = useState(false);
  const [progress, setProgress] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [engine, setEngine] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const timer = useRef(null);

  async function poll(tid) {
    try {
      const t = await api.task(tid);
      setProgress(t);
      if (t.status === "done") {
        setVideoUrl(await api.videoDownloadUrl(project.id));
        setEngine(t.result?.engine || "");
        clearInterval(timer.current);
      }
      if (t.status === "error") { setMsg("合成失败：" + t.error); setErr(true); clearInterval(timer.current); }
    } catch (e) { clearInterval(timer.current); setMsg("查询失败：" + e.message); setErr(true); }
  }
  useEffect(() => () => clearInterval(timer.current), []);

  async function exportVideo() {
    setVideoUrl(""); setMsg(""); setErr(false);
    try {
      const r = await api.exportVideo(project.id, { resolution, fps, subtitle, transition, follow_transition: followFx });
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
        渲染画面 + 逐页合成 + 烧录字幕
      </p>
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
        <div style={{ marginTop: 16 }}>
          <Btn onClick={exportVideo} disabled={running} icon="play">{running ? "合成中…" : "开始合成视频"}</Btn>
        </div>
        <Progress progress={progress} />
        <Msg text={msg} error={err} />
      </div>

      {videoUrl && (
        <div style={cardStyle}>
          <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>导出结果{engine ? ` · ${engine}` : ""}</h3>
          <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
            <Btn onClick={() => window.open(videoUrl)}>下载 MP4</Btn>
          </div>
        </div>
      )}
    </>
  );
}

/* ============================================================
   栏目五：高级设置
============================================================ */
function SettingsPanel() {
  const [s, setS] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);

  useEffect(() => { api.getSettings().then(setS).catch((e) => setMsg("加载失败：" + e.message)); }, []);

  const upd = (k, v) => setS((prev) => ({ ...prev, [k]: v }));
  async function save() {
    try { await api.saveSettings(s); setMsg("设置已保存 ✔"); setErr(false); }
    catch (e) { setMsg("保存失败：" + e.message); setErr(true); }
  }

  const LLMFields = ({ prefix, disabled }) => (
    <div style={{ opacity: disabled ? 0.45 : 1, display: "grid", gap: 10 }}>
      <input value={s?.[`${prefix}_api_base`] || ""} disabled={disabled}
        onChange={(e) => upd(`${prefix}_api_base`, e.target.value)}
        style={inputStyle} placeholder="API 地址（https://…/v1）" />
      <div style={{ display: "flex", gap: 10 }}>
        <input value={s?.[`${prefix}_api_key`] || ""} disabled={disabled}
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
        <LLMFields prefix="ppt_llm" />
        <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.8, marginTop: 10 }}>
          生成 PPT 时的资料抓取、大纲与每页要点都走这个模型。留空则使用内置内容引擎。
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
        <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>④ 生成引擎（进阶）</h3>
        <div style={{
          background: ORANGE_SOFT, border: "1px solid #FFD9C4", color: "#B44A1E",
          borderRadius: 10, padding: "10px 14px", fontSize: 12.5, lineHeight: 1.8,
        }}>
          当前：内置 AI 内容引擎（分析主题 → 抓取资料 → 大纲 → 内容，免配置）。<br />
          计划：后续提供「开源专业引擎」可选增强 —— 采用 presenton（GitHub 10.7k★，Apache 2.0 可商用）；banana-slides（15.6k★）因 AGPL 协议 + 依赖海外 Gemini API 不适合内置。
        </div>
      </div>

      <div style={cardStyle}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>关于开发者</h3>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <tbody>
            <tr><td style={{ padding: "8px 0", color: MUTED, width: 110 }}>软件</td><td>PPTVideoStudio v{APP_VERSION}</td></tr>
            <tr><td style={{ padding: "8px 0", color: MUTED }}>版权</td><td>© 2026 梦极</td></tr>
            <tr><td style={{ padding: "8px 0", color: MUTED }}>联系开发者</td><td>微信：mengji333</td></tr>
            <tr><td style={{ padding: "8px 0", color: MUTED }}>检查更新</td>
              <td>
                <span onClick={async () => { const u = await window.pvs.checkUpdate(); alert(u.available ? `发现新版本 v${u.latest}` : "当前已是最新版本"); }}
                  style={{ color: ORANGE, cursor: "pointer" }}>检查更新</span>
                {" "}· GitHub / 夸克网盘
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
  if (!info) return null;
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(30,25,20,.35)", zIndex: 100,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: "#fff", borderRadius: 16, padding: 26, width: 420, boxShadow: "0 12px 40px rgba(0,0,0,.15)",
      }}>
        <h3 style={{ margin: "0 0 6px", fontSize: 17, color: INK }}>
          {info.available ? `发现新版本 v${info.latest}` : "检查更新"}
        </h3>
        <p style={{ color: MUTED, fontSize: 13, margin: "0 0 16px", lineHeight: 1.7 }}>
          当前版本 v{info.current}
          {info.available ? `，最新版本 v${info.latest}。推荐优先从 GitHub 下载；如果 GitHub 打不开或下载太慢，请用夸克网盘（两个渠道安装包一致）。` : info.source === "none" ? "，暂时连不上 GitHub 更新服务，可从夸克网盘手动获取最新版本。" : "，已是最新版本。"}
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {info.available && info.url && <Btn onClick={() => window.pvs.openExternal(info.url)}>GitHub 下载</Btn>}
          <Btn kind={info.available ? "ghost" : "primary"} onClick={() => window.pvs.openExternal(info.quark)}>夸克网盘下载</Btn>
          <Btn kind="ghost" onClick={onClose}>{info.available ? "暂不更新" : "关闭"}</Btn>
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

  useEffect(() => {
    window.pvs.updateInfo().then((u) => { if (u.available) setNewVersion(u); }).catch(() => {});
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
        button { font-family: inherit; }`}</style>

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
          <div style={{ marginTop: "auto", padding: "12px 14px", fontSize: 11, color: "#6d665e", lineHeight: 1.8 }}>
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
              <VideoPanel project={project} />
            )}
            {panel === "settings" && <SettingsPanel />}
          </BackendGate>
        </main>
      </div>

      <UpdateDialog info={update} onClose={() => setUpdate(null)} />
    </div>
  );
}
