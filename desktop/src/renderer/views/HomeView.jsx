import React, { useEffect, useState } from "react";
import { api } from "../api";

export default function HomeView({ setTab, setProject }) {
  const [topic, setTopic] = useState("");
  const [projects, setProjects] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const refresh = () =>
    api.listProjects().then(setProjects).catch(() => setProjects([]));
  useEffect(() => {
    refresh();
  }, []);

  async function create() {
    if (!topic.trim()) return setMsg("请先输入主题");
    setBusy(true);
    try {
      const p = await api.createProject(topic);
      setProject({ id: p.id, topic });
      setMsg("项目已创建，正在生成 PPT…");
      await api.generatePpt(p.id, { slides: 8 });
      setMsg("PPT 已生成");
      setTab("edit");
    } catch (e) {
      setMsg("出错：" + e.message);
    } finally {
      setBusy(false);
    }
  }

  async function importPpt(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    setBusy(true);
    setMsg("正在导入并解析 PPT…");
    try {
      const p = await api.importPpt(f);
      setProject({ id: p.projectId, topic: f.name.replace(/\.pptx$/i, "") });
      setMsg(p.message);
      refresh();
      setTab("edit");
    } catch (e2) {
      setMsg("导入失败：" + e2.message);
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  function open(p) {
    setProject({ id: p.id, topic: p.topic });
    setTab("edit");
  }

  return (
    <div>
      <h2>新建项目</h2>
      <div style={{ display: "flex", gap: 10 }}>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="输入主题，例如：智慧文旅夜游项目汇报"
          style={{ flex: 1, maxWidth: 480 }}
          onKeyDown={(e) => e.key === "Enter" && create()}
        />
        <button onClick={create} disabled={busy}>
          {busy ? "处理中…" : "一键生成 PPT"}
        </button>
      </div>

      <div style={{ marginTop: 18 }}>
        <label style={{ marginTop: 0 }}>
          或导入已有 PPT（.pptx）：
          <input type="file" accept=".pptx" onChange={importPpt} style={{ marginLeft: 8 }} />
        </label>
      </div>

      <hr style={{ margin: "24px 0" }} />
      <h2>我的项目</h2>
      {projects.length === 0 && <p style={{ color: "#888" }}>暂无项目</p>}
      <table style={{ borderCollapse: "collapse", width: "100%", maxWidth: 720 }}>
        <tbody>
          {projects.map((p) => (
            <tr key={p.id} style={{ borderBottom: "1px solid #e5e9f0" }}>
              <td style={{ padding: 10 }}>{p.topic}</td>
              <td style={{ padding: 10, color: "#888" }}>{p.slides} 页</td>
              <td style={{ padding: 10, color: "#888" }}>{p.created_at}</td>
              <td style={{ padding: 10 }}>
                {p.has_video && <span style={{ color: "#1a7f37", marginRight: 8 }}>已有视频</span>}
                <button onClick={() => open(p)}>打开</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {msg && <p style={{ marginTop: 12 }}>{msg}</p>}
    </div>
  );
}
