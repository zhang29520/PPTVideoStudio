import React, { useEffect, useState } from "react";
import { api } from "../api";

export default function SettingsView() {
  const [s, setS] = useState(null);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.getSettings().then(setS).catch((e) => setMsg(e.message));
  }, []);

  if (!s) return <p>加载中…</p>;

  const upd = (k, v) => setS({ ...s, [k]: v });

  async function save() {
    try {
      await api.saveSettings(s);
      setMsg("设置已保存");
    } catch (e) {
      setMsg("保存失败：" + e.message);
    }
  }

  return (
    <div>
      <h2>设置</h2>

      <h3>LLM（OpenAI 兼容协议，留空则用内置模板）</h3>
      <label>API Base（如 https://api.openai.com/v1）</label>
      <input value={s.llm_api_base} onChange={(e) => upd("llm_api_base", e.target.value)} style={{ width: 420 }} />
      <label>API Key</label>
      <input value={s.llm_api_key} onChange={(e) => upd("llm_api_key", e.target.value)} style={{ width: 420 }} placeholder="sk-..." />
      <label>模型名（如 gpt-4o-mini / deepseek-chat / qwen-plus）</label>
      <input value={s.llm_model} onChange={(e) => upd("llm_model", e.target.value)} style={{ width: 420 }} />

      <h3>默认 TTS</h3>
      <label>音色</label>
      <input value={s.tts_voice} onChange={(e) => upd("tts_voice", e.target.value)} style={{ width: 320 }} />

      <div style={{ marginTop: 18 }}>
        <button onClick={save}>保存设置</button>
      </div>
      <p style={{ color: "#888", marginTop: 12, maxWidth: 560 }}>
        说明：配置任意 OpenAI 兼容接口（OpenAI / DeepSeek / 通义千问 / 本地 Ollama）后，
        PPT 大纲与解说词会自动改用 LLM 生成；不配置也能用内置模板完整跑通全流程。
      </p>
      {msg && <p>{msg}</p>}
    </div>
  );
}
