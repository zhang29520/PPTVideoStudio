import React, { useState } from "react";
import { api } from "../api";

const VOICES = [
  ["zh-CN-XiaoxiaoNeural", "晓晓（女·温柔）"],
  ["zh-CN-YunxiNeural", "云希（男·年轻）"],
  ["zh-CN-YunjianNeural", "云健（男·沉稳）"],
  ["zh-CN-XiaoyiNeural", "晓伊（女·活泼）"],
];

export default function AudioView({ project, setTab }) {
  const [voice, setVoice] = useState("zh-CN-XiaoxiaoNeural");
  const [rate, setRate] = useState("+0%");
  const [audio, setAudio] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function generate() {
    setBusy(true);
    setMsg("正在逐页合成配音（首次较慢）…");
    try {
      const r = await api.generateTts(project.id, { voice, rate });
      setAudio(r.audio);
      setMsg(`${r.message}（${r.engine}）`);
    } catch (e) {
      setMsg("失败：" + e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>配音（Edge-TTS）</h2>
      <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
        <label style={{ marginTop: 0 }}>
          音色：
          <select value={voice} onChange={(e) => setVoice(e.target.value)}>
            {VOICES.map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ marginTop: 0 }}>
          语速：
          <select value={rate} onChange={(e) => setRate(e.target.value)}>
            {["-20%", "-10%", "+0%", "+10%", "+20%"].map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </label>
        <button onClick={generate} disabled={busy}>
          {busy ? "合成中…" : "生成配音"}
        </button>
      </div>

      {audio.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <h3>逐页试听</h3>
          {audio.map((f, i) => (
            <div key={f} style={{ marginBottom: 8 }}>
              <span style={{ color: "#666", marginRight: 8 }}>第 {i + 1} 页</span>
              <audio controls src={api.audioUrl(project.id, f)} style={{ height: 32 }} />
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 20 }}>
        <button onClick={() => setTab("video")} disabled={!audio.length}>
          下一步：导出视频 →
        </button>
      </div>
      {msg && <p style={{ marginTop: 10 }}>{msg}</p>}
    </div>
  );
}
