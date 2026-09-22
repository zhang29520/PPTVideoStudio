import React, { useRef, useState } from "react";
import { api } from "../api";

export default function VideoView({ project }) {
  const [resolution, setResolution] = useState("1080p");
  const [fps, setFps] = useState(30);
  const [subtitle, setSubtitle] = useState(true);
  const [transition, setTransition] = useState(0.5);
  const [progress, setProgress] = useState(null); // {status, progress, message, error}
  const [videoUrl, setVideoUrl] = useState("");
  const timer = useRef(null);

  async function poll(tid) {
    try {
      const t = await api.videoTask(tid);
      setProgress(t);
      if (t.status === "done") {
        setVideoUrl(api.videoDownloadUrl(project.id));
        clearInterval(timer.current);
      }
      if (t.status === "error") {
        setMsg("合成失败：" + t.error);
        clearInterval(timer.current);
      }
    } catch (e) {
      clearInterval(timer.current);
      setMsg("查询失败：" + e.message);
    }
  }

  const [msg, setMsg] = useState("");

  async function exportVideo() {
    setVideoUrl("");
    setMsg("");
    try {
      const r = await api.exportVideo(project.id, { resolution, fps, subtitle, transition });
      setProgress({ status: "running", progress: 0.05, message: "任务已提交" });
      timer.current = setInterval(() => poll(r.taskId), 2000);
    } catch (e) {
      setMsg("提交失败：" + e.message);
    }
  }

  const running = progress?.status === "running";

  return (
    <div>
      <h2>视频导出</h2>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <label style={{ marginTop: 0 }}>
          分辨率
          <select value={resolution} onChange={(e) => setResolution(e.target.value)}>
            <option value="720p">720p</option>
            <option value="1080p">1080p</option>
          </select>
        </label>
        <label style={{ marginTop: 0 }}>
          帧率
          <select value={fps} onChange={(e) => setFps(Number(e.target.value))}>
            <option value={30}>30</option>
            <option value={60}>60</option>
          </select>
        </label>
        <label style={{ marginTop: 0 }}>
          转场（秒）
          <input
            type="number"
            step="0.1"
            min="0"
            max="1"
            value={transition}
            onChange={(e) => setTransition(Number(e.target.value))}
            style={{ width: 70 }}
          />
        </label>
        <label style={{ marginTop: 0 }}>
          <input type="checkbox" checked={subtitle} onChange={(e) => setSubtitle(e.target.checked)} /> 烧录字幕
        </label>
        <button onClick={exportVideo} disabled={running}>
          {running ? "合成中…" : "开始合成视频"}
        </button>
      </div>

      {progress && (
        <div style={{ marginTop: 18, maxWidth: 560 }}>
          <div style={{ background: "#e8edf4", borderRadius: 8, height: 10, overflow: "hidden" }}>
            <div
              style={{
                width: `${Math.round((progress.progress || 0) * 100)}%`,
                background: "#1a3a5c",
                height: "100%",
                transition: "width .4s",
              }}
            />
          </div>
          <div style={{ color: "#666", marginTop: 6 }}>
            {progress.status === "running"
              ? `合成中… ${Math.round((progress.progress || 0) * 100)}%`
              : progress.status === "done"
                ? "合成完成"
                : progress.status === "error"
                  ? "失败：" + progress.error
                  : progress.status}
          </div>
        </div>
      )}

      {videoUrl && (
        <div style={{ marginTop: 18 }}>
          <a href={videoUrl} download>
            <button>下载 MP4</button>
          </a>
        </div>
      )}
      {msg && <p style={{ marginTop: 10, color: "#b00" }}>{msg}</p>}
    </div>
  );
}
