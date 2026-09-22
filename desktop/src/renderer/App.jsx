import React, { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

const APP_VERSION = "0.3.0";
const ORANGE = "#FF6B35";
const ORANGE_SOFT = "#FFF3EC";
const INK = "#26221E";
const MUTED = "#9B948D";
const LINE = "#ECE7E1";

/* ---------- 全局状态：后端网关 ---------- */
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

/* ---------- 小组件 ---------- */
function Btn({ children, onClick, disabled, kind = "primary", style = {} }) {
  const base = {
    border: "none",
    borderRadius: 10,
    padding: "10px 18px",
    fontSize: 14,
    fontWeight: 600,
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "opacity .15s",
    opacity: disabled ? 0.45 : 1,
  };
  const kinds = {
    primary: { background: ORANGE, color: "#fff" },
    ghost: { background: "#fff", color: INK, border: `1px solid ${LINE}` },
    soft: { background: ORANGE_SOFT, color: ORANGE },
  };
  return (
    <button onClick={onClick} disabled={disabled} style={{ ...base, ...kinds[kind], ...style }}>
      {children}
    </button>
  );
}

function Card({ step, title, desc, active, children }) {
  return (
    <section
      style={{
        background: "#fff",
        border: `1px solid ${active ? "#FFD9C4" : LINE}`,
        borderRadius: 16,
        padding: "22px 26px",
        marginBottom: 18,
        boxShadow: active ? "0 4px 20px rgba(255,107,53,.08)" : "none",
        opacity: active ? 1 : 0.62,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
        <span
          style={{
            width: 26,
            height: 26,
            borderRadius: "50%",
            background: active ? ORANGE : "#EFEAE4",
            color: active ? "#fff" : MUTED,
            fontSize: 13,
            fontWeight: 700,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          {step}
        </span>
        <h2 style={{ margin: 0, fontSize: 17, color: INK }}>{title}</h2>
        {desc && <span style={{ color: MUTED, fontSize: 13 }}>{desc}</span>}
      </div>
      {children}
    </section>
  );
}

function Msg({ text, error }) {
  if (!text) return null;
  return (
    <p style={{ margin: "10px 0 0", fontSize: 13, color: error ? "#D93025" : ORANGE }}>{text}</p>
  );
}

const labelStyle = { fontSize: 13, color: MUTED, margin: "12px 0 6px" };
const inputStyle = {
  width: "100%",
  boxSizing: "border-box",
  border: `1px solid ${LINE}`,
  borderRadius: 10,
  padding: "10px 12px",
  fontSize: 14,
  color: INK,
  outline: "none",
};

/* ---------- 第 1 步：新建 / 导入 ---------- */
function StepCreate({ project, setProject, onCreated, goEdit }) {
  const [topic, setTopic] = useState("");
  const [projects, setProjects] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);

  const refresh = useCallback(
    () => api.listProjects().then(setProjects).catch(() => {}),
    []
  );
  useEffect(() => { refresh(); }, [refresh, project?.id]);

  async function create() {
    if (!topic.trim()) { setMsg("请先输入主题"); setErr(true); return; }
    setBusy(true); setMsg("正在生成 PPT（约几秒钟）…"); setErr(false);
    try {
      const p = await api.createProject(topic);
      await api.generatePpt(p.id, { slides: 8 });
      setProject({ id: p.id, topic });
      setMsg("PPT 已生成 ✔ 可在下方第 2 步编辑");
      refresh();
    } catch (e) {
      setMsg("出错：" + e.message); setErr(true);
    } finally { setBusy(false); }
  }

  async function importPpt(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true); setMsg("正在导入并解析 PPT…"); setErr(false);
    try {
      const p = await api.importPpt(f);
      setProject({ id: p.projectId, topic: f.name.replace(/\.pptx$/i, "") });
      setMsg("导入成功 ✔ 可在下方第 2 步编辑");
      refresh();
    } catch (e2) {
      setMsg("导入失败：" + e2.message); setErr(true);
    } finally { setBusy(false); e.target.value = ""; }
  }

  function open(p) {
    setProject({ id: p.id, topic: p.topic });
    setMsg("");
  }

  return (
    <>
      <div style={{ display: "flex", gap: 10 }}>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="输入主题，例如：智慧文旅夜游项目汇报"
          style={{ ...inputStyle, flex: 1 }}
          onKeyDown={(e) => e.key === "Enter" && create()}
        />
        <Btn onClick={create} disabled={busy}>{busy ? "生成中…" : "生成 PPT"}</Btn>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 12 }}>
        <span style={{ fontSize: 13, color: MUTED }}>或导入已有 PPT（.pptx）：</span>
        <label
          style={{
            fontSize: 13, color: ORANGE, cursor: "pointer", border: `1px dashed ${ORANGE}`,
            borderRadius: 8, padding: "6px 12px", background: ORANGE_SOFT,
          }}
        >
          选择文件
          <input type="file" accept=".pptx" onChange={importPpt} style={{ display: "none" }} />
        </label>
      </div>
      <Msg text={msg} error={err} />

      {projects.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={labelStyle}>最近项目（点击打开）</div>
          {projects.slice(0, 6).map((p) => (
            <div
              key={p.id}
              onClick={() => open(p)}
              style={{
                display: "flex", alignItems: "center", gap: 12, padding: "9px 12px",
                borderRadius: 10, cursor: "pointer", fontSize: 14,
                background: project?.id === p.id ? ORANGE_SOFT : "transparent",
                color: project?.id === p.id ? ORANGE : INK,
              }}
            >
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.topic}</span>
              <span style={{ color: MUTED, fontSize: 12 }}>{p.slides} 页</span>
              {p.has_video && <span style={{ color: "#1a7f37", fontSize: 12 }}>已有视频</span>}
            </div>
          ))}
        </div>
      )}

      {project?.id && (
        <div style={{ marginTop: 12 }}>
          <Btn kind="soft" onClick={goEdit}>继续编辑「{project.topic}」 ↓</Btn>
        </div>
      )}
    </>
  );
}

/* ---------- 第 2 步：编辑 PPT + 解说词 ---------- */
function StepEdit({ project, onScriptReady }) {
  const [slides, setSlides] = useState([]);
  const [script, setScript] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);
  const [pptxUrl, setPptxUrl] = useState("");

  useEffect(() => {
    if (!project?.id) return;
    setMsg(""); setScript([]);
    api.getSlides(project.id).then((d) => setSlides(d.slides || [])).catch((e) => { setMsg(e.message); setErr(true); });
    api.getProject(project.id).then((p) => setScript(p.script || [])).catch(() => {});
    api.pptDownloadUrl(project.id).then(setPptxUrl);
  }, [project?.id]);

  const upd = (i, key, val) => {
    const next = [...slides];
    next[i] = { ...next[i], [key]: val };
    setSlides(next);
  };
  const updScript = (i, val) => {
    const next = [...script];
    next[i] = val;
    setScript(next);
  };

  async function savePpt() {
    setBusy(true); setMsg(""); setErr(false);
    try { await api.saveSlides(project.id, slides); setMsg("PPT 已保存并重建 PPTX ✔"); }
    catch (e) { setMsg("保存失败：" + e.message); setErr(true); }
    finally { setBusy(false); }
  }
  async function genScript() {
    setBusy(true); setMsg("AI 正在撰写解说词…"); setErr(false);
    try {
      const r = await api.generateSpeech(project.id, { tone: "专业" });
      setScript(r.pages);
      setMsg(`解说词已生成（${r.source === "llm" ? "LLM" : "模板"}）✔`);
    } catch (e) { setMsg("失败：" + e.message); setErr(true); }
    finally { setBusy(false); }
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

  if (!project?.id) return <p style={{ color: MUTED, fontSize: 13 }}>请先在上方第 1 步生成或导入 PPT</p>;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, color: MUTED }}>当前项目：{project.topic}</span>
        {pptxUrl && <a href={pptxUrl} download style={{ fontSize: 13, color: ORANGE, textDecoration: "none" }}>下载 .pptx</a>}
        <span style={{ flex: 1 }} />
        <Btn kind="ghost" onClick={savePpt} disabled={busy}>保存 PPT</Btn>
        <Btn kind="ghost" onClick={genScript} disabled={busy || !slides.length}>AI 生成解说词</Btn>
        <Btn kind="ghost" onClick={saveScript} disabled={busy || !script.length}>保存解说词</Btn>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, marginTop: 14 }}>
        <div>
          <div style={labelStyle}>页面内容</div>
          {slides.map((s, i) => (
            <div key={i} style={{ border: `1px solid ${LINE}`, padding: 12, marginBottom: 10, borderRadius: 12 }}>
              <div style={{ color: MUTED, fontSize: 12, marginBottom: 6 }}>第 {i + 1} 页</div>
              <input value={s.title || ""} onChange={(e) => upd(i, "title", e.target.value)} style={{ ...inputStyle, marginBottom: 8 }} />
              <textarea
                value={(s.bullets || []).join("\n")}
                onChange={(e) => upd(i, "bullets", e.target.value.split("\n").filter((x) => x.trim()))}
                rows={Math.max(3, (s.bullets || []).length)}
                style={{ ...inputStyle, resize: "vertical" }}
                placeholder="每行一个要点"
              />
            </div>
          ))}
        </div>
        <div>
          <div style={labelStyle}>逐页解说词</div>
          {slides.map((_, i) => (
            <div key={i} style={{ marginBottom: 10 }}>
              <div style={{ color: MUTED, fontSize: 12, marginBottom: 6 }}>第 {i + 1} 页</div>
              <textarea
                value={script[i] || ""}
                onChange={(e) => updScript(i, e.target.value)}
                rows={3}
                style={{ ...inputStyle, resize: "vertical" }}
              />
            </div>
          ))}
          {!slides.length && <p style={{ color: MUTED, fontSize: 13 }}>—</p>}
        </div>
      </div>
      <Msg text={msg} error={err} />
    </>
  );
}

/* ---------- 第 3 步：配音 ---------- */
const VOICES = [
  ["zh-CN-XiaoxiaoNeural", "晓晓（女·温柔）"],
  ["zh-CN-YunxiNeural", "云希（男·年轻）"],
  ["zh-CN-YunjianNeural", "云健（男·沉稳）"],
  ["zh-CN-XiaoyiNeural", "晓伊（女·活泼）"],
];

function StepAudio({ project, scriptReady, onAudioReady }) {
  const [voice, setVoice] = useState("zh-CN-XiaoxiaoNeural");
  const [rate, setRate] = useState("+0%");
  const [audio, setAudio] = useState([]);
  const [audioUrls, setAudioUrls] = useState({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState(false);

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

  async function generate() {
    setBusy(true); setMsg("正在逐页合成配音（首次较慢）…"); setErr(false);
    try {
      const r = await api.generateTts(project.id, { voice, rate });
      setAudio(r.audio);
      setMsg(`${r.message}（${r.engine}）✔`);
      onAudioReady();
    } catch (e) { setMsg("失败：" + e.message); setErr(true); }
    finally { setBusy(false); }
  }

  if (!project?.id) return <p style={{ color: MUTED, fontSize: 13 }}>请先完成上方第 1、2 步</p>;

  return (
    <>
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <label style={{ fontSize: 13, color: MUTED }}>
          音色：
          <select value={voice} onChange={(e) => setVoice(e.target.value)} style={{ ...inputStyle, width: 160, marginLeft: 6 }}>
            {VOICES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label style={{ fontSize: 13, color: MUTED }}>
          语速：
          <select value={rate} onChange={(e) => setRate(e.target.value)} style={{ ...inputStyle, width: 90, marginLeft: 6 }}>
            {["-20%", "-10%", "+0%", "+10%", "+20%"].map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
        <Btn onClick={generate} disabled={busy}>{busy ? "合成中…" : "生成配音"}</Btn>
      </div>

      {audio.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {audio.map((f, i) => (
            <div key={f} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span style={{ color: MUTED, fontSize: 13, width: 56 }}>第 {i + 1} 页</span>
              {audioUrls[f] && <audio controls src={audioUrls[f]} style={{ height: 34 }} />}
            </div>
          ))}
        </div>
      )}
      <Msg text={msg} error={err} />
    </>
  );
}

/* ---------- 第 4 步：导出视频 ---------- */
function StepVideo({ project }) {
  const [resolution, setResolution] = useState("1080p");
  const [fps, setFps] = useState(30);
  const [subtitle, setSubtitle] = useState(true);
  const [transition, setTransition] = useState(0.5);
  const [progress, setProgress] = useState(null);
  const [videoUrl, setVideoUrl] = useState("");
  const [msg, setMsg] = useState("");
  const timer = useRef(null);

  async function poll(tid) {
    try {
      const t = await api.videoTask(tid);
      setProgress(t);
      if (t.status === "done") {
        setVideoUrl(await api.videoDownloadUrl(project.id));
        clearInterval(timer.current);
      }
      if (t.status === "error") { setMsg("合成失败：" + t.error); clearInterval(timer.current); }
    } catch (e) { clearInterval(timer.current); setMsg("查询失败：" + e.message); }
  }

  useEffect(() => () => clearInterval(timer.current), []);

  async function exportVideo() {
    setVideoUrl(""); setMsg("");
    try {
      const r = await api.exportVideo(project.id, { resolution, fps, subtitle, transition });
      setProgress({ status: "running", progress: 0.05, message: "任务已提交" });
      timer.current = setInterval(() => poll(r.taskId), 2000);
    } catch (e) { setMsg("提交失败：" + e.message); }
  }

  const running = progress?.status === "running";
  if (!project?.id) return <p style={{ color: MUTED, fontSize: 13 }}>请先完成上方第 1–3 步</p>;

  return (
    <>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: 13, color: MUTED }}>
          分辨率
          <select value={resolution} onChange={(e) => setResolution(e.target.value)} style={{ ...inputStyle, width: 100, marginLeft: 6 }}>
            <option value="720p">720p</option>
            <option value="1080p">1080p</option>
          </select>
        </label>
        <label style={{ fontSize: 13, color: MUTED }}>
          帧率
          <select value={fps} onChange={(e) => setFps(Number(e.target.value))} style={{ ...inputStyle, width: 80, marginLeft: 6 }}>
            <option value={30}>30</option>
            <option value={60}>60</option>
          </select>
        </label>
        <label style={{ fontSize: 13, color: MUTED }}>
          转场（秒）
          <input type="number" step="0.1" min="0" max="1" value={transition}
            onChange={(e) => setTransition(Number(e.target.value))}
            style={{ ...inputStyle, width: 70, marginLeft: 6 }} />
        </label>
        <label style={{ fontSize: 13, color: MUTED }}>
          <input type="checkbox" checked={subtitle} onChange={(e) => setSubtitle(e.target.checked)} /> 烧录字幕
        </label>
        <Btn onClick={exportVideo} disabled={running}>{running ? "合成中…" : "开始合成视频"}</Btn>
      </div>

      {progress && (
        <div style={{ marginTop: 16, maxWidth: 560 }}>
          <div style={{ background: "#F1EDE8", borderRadius: 8, height: 8, overflow: "hidden" }}>
            <div style={{
              width: `${Math.round((progress.progress || 0) * 100)}%`,
              background: ORANGE, height: "100%", transition: "width .4s", borderRadius: 8,
            }} />
          </div>
          <div style={{ color: MUTED, marginTop: 6, fontSize: 13 }}>
            {progress.status === "running"
              ? `合成中… ${Math.round((progress.progress || 0) * 100)}%`
              : progress.status === "done" ? "合成完成 ✔"
              : progress.status === "error" ? "失败：" + progress.error : progress.status}
          </div>
        </div>
      )}

      {videoUrl && (
        <div style={{ marginTop: 14 }}>
          <Btn onClick={() => window.open(videoUrl)}>下载 MP4 视频</Btn>
        </div>
      )}
      {msg && <p style={{ marginTop: 10, fontSize: 13, color: "#D93025" }}>{msg}</p>}
    </>
  );
}

/* ---------- 设置卡片 ---------- */
function SettingsCard() {
  const [open, setOpen] = useState(false);
  const [s, setS] = useState(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (open && !s) api.getSettings().then(setS).catch((e) => setMsg("加载失败：" + e.message));
  }, [open, s]);

  const upd = (k, v) => setS({ ...s, [k]: v });
  async function save() {
    try { await api.saveSettings(s); setMsg("已保存 ✔"); }
    catch (e) { setMsg("保存失败：" + e.message); }
  }

  return (
    <section style={{ background: "#fff", border: `1px solid ${LINE}`, borderRadius: 16, padding: "18px 26px", marginBottom: 18 }}>
      <div onClick={() => setOpen(!open)} style={{ display: "flex", alignItems: "center", cursor: "pointer", gap: 12 }}>
        <span style={{ width: 26, height: 26, borderRadius: "50%", background: "#EFEAE4", color: MUTED, fontSize: 13, fontWeight: 700, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>⚙</span>
        <h2 style={{ margin: 0, fontSize: 17, color: INK }}>高级设置</h2>
        <span style={{ color: MUTED, fontSize: 13 }}>接入 LLM 可提升生成质量（可选）</span>
        <span style={{ flex: 1 }} />
        <span style={{ color: MUTED }}>{open ? "收起 ▲" : "展开 ▼"}</span>
      </div>
      {open && (
        <div style={{ marginTop: 8 }}>
          {!s && <p style={{ color: MUTED, fontSize: 13 }}>{msg || "加载中…"}</p>}
          {s && (
            <>
              <div style={labelStyle}>LLM API Base（OpenAI 兼容，如 https://api.openai.com/v1）</div>
              <input value={s.llm_api_base} onChange={(e) => upd("llm_api_base", e.target.value)} style={inputStyle} />
              <div style={labelStyle}>API Key</div>
              <input value={s.llm_api_key} onChange={(e) => upd("llm_api_key", e.target.value)} style={inputStyle} placeholder="sk-..." />
              <div style={labelStyle}>模型名（如 gpt-4o-mini / deepseek-chat / qwen-plus）</div>
              <input value={s.llm_model} onChange={(e) => upd("llm_model", e.target.value)} style={inputStyle} />
              <div style={labelStyle}>默认 TTS 音色</div>
              <input value={s.tts_voice} onChange={(e) => upd("tts_voice", e.target.value)} style={inputStyle} />
              <div style={{ marginTop: 14 }}>
                <Btn onClick={save}>保存设置</Btn>
              </div>
              {msg && <Msg text={msg} error={msg.includes("失败")} />}
              <p style={{ color: MUTED, fontSize: 12, marginTop: 10 }}>
                不配置也能完整使用（内置模板模式）；配置后 PPT 大纲与解说词自动改用 LLM 生成。
              </p>
            </>
          )}
        </div>
      )}
    </section>
  );
}

/* ---------- 后端状态页 ---------- */
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

/* ---------- 更新检查 ---------- */
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
          {info.available && info.url && (
            <Btn onClick={() => window.pvs.openExternal(info.url)}>GitHub 下载</Btn>
          )}
          <Btn kind={info.available ? "ghost" : "primary"} onClick={() => window.pvs.openExternal(info.quark)}>
            夸克网盘下载
          </Btn>
          {info.available && <Btn kind="ghost" onClick={onClose}>暂不更新</Btn>}
          {!info.available && <Btn kind="ghost" onClick={onClose}>关闭</Btn>}
        </div>
      </div>
    </div>
  );
}

/* ---------- App ---------- */
export default function App() {
  const { info, refresh: refreshBackend } = useBackend();
  const [project, setProject] = useState({ id: null, topic: "" });
  const [scriptReady, setScriptReady] = useState(false);
  const [audioReady, setAudioReady] = useState(false);
  const mainRef = useRef(null);
  const [update, setUpdate] = useState(null);        // 对话框内容
  const [newVersion, setNewVersion] = useState(null); // 顶栏横幅

  useEffect(() => {
    window.pvs.updateInfo().then((u) => { if (u.available) setNewVersion(u); }).catch(() => {});
  }, []);

  async function manualCheck() {
    try {
      const u = await window.pvs.checkUpdate();
      setUpdate(u);
      if (u.available) setNewVersion(u);
    } catch { setUpdate({ available: false, current: APP_VERSION, source: "none", quark: "" }); }
  }

  const goEdit = () => mainRef.current?.scrollTo({ top: 99999, behavior: "smooth" });

  const step2 = !!project?.id;
  const step3 = step2 && scriptReady;
  const step4 = step3 && audioReady;

  return (
    <div style={{
      minHeight: "100vh", background: "#FAFAF9", color: INK,
      fontFamily: '"PingFang SC", "Microsoft YaHei", system-ui, sans-serif',
      display: "flex", flexDirection: "column",
    }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }
        input:focus, textarea:focus, select:focus { border-color: ${ORANGE} !important; }
        ::selection { background: #FFD9C4; }
        ::-webkit-scrollbar { width: 8px; } ::-webkit-scrollbar-thumb { background: #E5DFD8; border-radius: 4px; }`}</style>

      {/* 顶栏 */}
      <header style={{
        display: "flex", alignItems: "center", gap: 10, padding: "14px 28px",
        background: "#fff", borderBottom: `1px solid ${LINE}`, position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{
          width: 30, height: 30, borderRadius: 9, background: `linear-gradient(135deg, ${ORANGE}, #FF9A6B)`,
          display: "inline-flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 15,
        }}>▶</div>
        <strong style={{ fontSize: 16 }}>PPTVideoStudio</strong>
        <span style={{ color: MUTED, fontSize: 12 }}>v{APP_VERSION}</span>
        <span style={{ flex: 1 }} />
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12,
          color: info.ready ? "#1a7f37" : info.error ? "#D93025" : MUTED,
          background: info.ready ? "#EAF7EE" : info.error ? "#FDECEA" : "#F1EDE8",
          borderRadius: 99, padding: "5px 12px",
        }}>
          <span style={{
            width: 7, height: 7, borderRadius: "50%",
            background: info.ready ? "#1a7f37" : info.error ? "#D93025" : "#C9C2BA",
          }} />
          {info.ready ? "引擎运行中" : info.error ? "引擎异常" : "启动中…"}
        </span>
      </header>

      {/* 更新横幅 */}
      {newVersion && (
        <div onClick={() => setUpdate(newVersion)} style={{
          display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
          padding: "8px 20px", background: ORANGE, color: "#fff", fontSize: 13,
          cursor: "pointer", fontWeight: 600,
        }}>
          🎉 发现新版本 v{newVersion.latest}，点击立即更新（GitHub / 夸克网盘）
        </div>
      )}

      {/* 主体 */}
      <main ref={mainRef} style={{ flex: 1, width: "100%", maxWidth: 880, margin: "0 auto", padding: "26px 24px" }}>
        <BackendGate info={info}>
          <div style={{ marginBottom: 20 }}>
            <h1 style={{ margin: 0, fontSize: 24 }}>把 PPT 变成视频，只需四步</h1>
            <p style={{ color: MUTED, fontSize: 13, margin: "6px 0 0" }}>输入主题或上传 PPT → 编辑解说词 → AI 配音 → 导出 MP4</p>
          </div>

          <Card step={1} title="创建项目" desc="输入主题生成，或导入已有 PPT" active>
            <StepCreate project={project} setProject={setProject} goEdit={goEdit} />
          </Card>

          <Card step={2} title="编辑 PPT 与解说词" desc="改内容、写讲稿" active={step2}>
            <StepEdit project={project} onScriptReady={() => setScriptReady(true)} />
          </Card>

          <Card step={3} title="AI 配音" desc="Edge-TTS 逐页合成" active={step3}>
            <StepAudio project={project} scriptReady={scriptReady} onAudioReady={() => setAudioReady(true)} />
          </Card>

          <Card step={4} title="导出视频" desc="渲染画面 + 合成 MP4" active={step4}>
            <StepVideo project={project} />
          </Card>

          <SettingsCard />
        </BackendGate>
      </main>

      {/* 页脚 */}
      <footer style={{
        textAlign: "center", padding: "18px 0 22px", fontSize: 12, color: MUTED,
        borderTop: `1px solid ${LINE}`, background: "#fff",
      }}>
        © 2026 梦极 · PPTVideoStudio v{APP_VERSION} ·{" "}
        <span onClick={manualCheck} style={{ color: ORANGE, cursor: "pointer" }}>检查更新</span>
        {" "}· 联系开发者微信：<span style={{ color: ORANGE }}>mengji333</span>
      </footer>

      <UpdateDialog info={update} onClose={() => setUpdate(null)} />
    </div>
  );
}
