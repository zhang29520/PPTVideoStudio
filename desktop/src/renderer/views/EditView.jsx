import React, { useEffect, useState } from "react";
import { api } from "../api";

export default function EditView({ project, setTab }) {
  const [slides, setSlides] = useState([]);
  const [script, setScript] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!project?.id) return;
    api.getSlides(project.id).then((d) => setSlides(d.slides || [])).catch((e) => setMsg(e.message));
    api
      .getProject(project.id)
      .then((p) => setScript(p.script || []))
      .catch(() => {});
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
    setBusy(true);
    try {
      await api.saveSlides(project.id, slides);
      setMsg("PPT 已保存并重建 PPTX");
    } catch (e) {
      setMsg("保存失败：" + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function genScript() {
    setBusy(true);
    setMsg("正在生成解说词…");
    try {
      const r = await api.generateSpeech(project.id, { tone: "专业" });
      setScript(r.pages);
      setMsg(`解说词已生成（${r.source === "llm" ? "LLM" : "模板"}）`);
    } catch (e) {
      setMsg("失败：" + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveScript() {
    setBusy(true);
    try {
      await api.saveSpeech(project.id, script);
      setMsg("解说词已保存（已同步到 PPT 备注）");
    } catch (e) {
      setMsg("保存失败：" + e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h2 style={{ margin: 0 }}>PPT 编辑</h2>
        <span style={{ color: "#888" }}>{project?.topic}</span>
        <a href={api.pptDownloadUrl(project?.id)} target="_blank" rel="noreferrer">
          下载 .pptx
        </a>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 14 }}>
        <div>
          <h3>
            页面内容{" "}
            <button onClick={savePpt} disabled={busy}>
              保存并重建 PPTX
            </button>
          </h3>
          {slides.map((s, i) => (
            <div key={i} style={{ border: "1px solid #dfe5ee", padding: 10, marginBottom: 10, borderRadius: 8 }}>
              <div style={{ color: "#888", fontSize: 12 }}>第 {i + 1} 页</div>
              <input value={s.title || ""} onChange={(e) => upd(i, "title", e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
              <textarea
                value={(s.bullets || []).join("\n")}
                onChange={(e) => upd(i, "bullets", e.target.value.split("\n").filter((x) => x.trim()))}
                rows={Math.max(3, (s.bullets || []).length)}
                style={{ width: "100%" }}
                placeholder="每行一个要点"
              />
            </div>
          ))}
        </div>

        <div>
          <h3>
            逐页解说词{" "}
            <button onClick={genScript} disabled={busy || !slides.length}>
              AI 生成
            </button>{" "}
            <button onClick={saveScript} disabled={busy || !script.length}>
              保存
            </button>
          </h3>
          {slides.map((_, i) => (
            <div key={i} style={{ marginBottom: 10 }}>
              <div style={{ color: "#888", fontSize: 12 }}>第 {i + 1} 页</div>
              <textarea
                value={script[i] || ""}
                onChange={(e) => updScript(i, e.target.value)}
                rows={3}
                style={{ width: "100%" }}
              />
            </div>
          ))}
          {!slides.length && <p style={{ color: "#888" }}>请先在首页生成或导入 PPT</p>}
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <button onClick={() => setTab("audio")} disabled={!script.length}>
          下一步：生成配音 →
        </button>
      </div>
      {msg && <p style={{ marginTop: 10 }}>{msg}</p>}
    </div>
  );
}
