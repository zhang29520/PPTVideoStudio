import React, { useState } from "react";
import HomeView from "./views/HomeView";
import EditView from "./views/EditView";
import AudioView from "./views/AudioView";
import VideoView from "./views/VideoView";
import SettingsView from "./views/SettingsView";

const tabs = [
  ["home", "首页"],
  ["edit", "PPT 编辑"],
  ["audio", "配音"],
  ["video", "视频导出"],
  ["settings", "设置"],
];

export default function App() {
  const [tab, setTab] = useState("home");
  const [project, setProject] = useState({ id: null, topic: "" });

  const views = {
    home: <HomeView setTab={setTab} setProject={setProject} />,
    edit: <EditView project={project} setTab={setTab} />,
    audio: <AudioView project={project} setTab={setTab} />,
    video: <VideoView project={project} />,
    settings: <SettingsView />,
  };

  return (
    <div style={{ display: "flex", fontFamily: "system-ui", height: "100vh" }}>
      <aside style={{ width: 200, borderRight: "1px solid #e5e9f0", padding: 16 }}>
        <h2 style={{ margin: "0 0 16px", fontSize: 17, color: "#1a3a5c" }}>PPTVideoStudio</h2>
        {tabs.map(([key, label]) => (
          <div
            key={key}
            onClick={() => setTab(key)}
            style={{
              padding: "10px 12px",
              cursor: "pointer",
              borderRadius: 8,
              background: tab === key ? "#1a3a5c" : "transparent",
              color: tab === key ? "#fff" : "#333",
              marginBottom: 6,
            }}
          >
            {label}
          </div>
        ))}
      </aside>
      <main style={{ flex: 1, padding: 20, overflowY: "auto" }}>{views[tab]}</main>
    </div>
  );
}
