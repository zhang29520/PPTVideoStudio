// 后端 API 封装（本地 FastAPI）
const BASE = "http://127.0.0.1:8000";

async function req(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  // 项目
  listProjects: () => req("/api/projects"),
  createProject: (topic) =>
    req("/api/projects", { method: "POST", body: JSON.stringify({ topic }) }),
  getProject: (id) => req(`/api/projects/${id}`),

  // PPT
  generatePpt: (id, cfg) =>
    req(`/api/ppt/generate/${id}`, { method: "POST", body: JSON.stringify(cfg || {}) }),
  getSlides: (id) => req(`/api/ppt/${id}`),
  saveSlides: (id, slides) =>
    req(`/api/ppt/${id}`, { method: "PUT", body: JSON.stringify({ slides }) }),
  importPpt: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(BASE + "/api/ppt/import", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "导入失败");
    return res.json();
  },
  pptDownloadUrl: (id) => `${BASE}/api/ppt/${id}/download`,

  // 解说词
  generateSpeech: (id, tone) =>
    req(`/api/speech/generate/${id}`, { method: "POST", body: JSON.stringify({ tone }) }),
  saveSpeech: (id, pages) =>
    req(`/api/speech/${id}`, { method: "PUT", body: JSON.stringify({ pages }) }),

  // TTS
  generateTts: (id, cfg) =>
    req(`/api/tts/generate/${id}`, { method: "POST", body: JSON.stringify(cfg || {}) }),
  audioUrl: (id, file) => `${BASE}/api/tts/${id}/audio/${file}`,

  // 视频
  exportVideo: (id, cfg) =>
    req(`/api/video/export/${id}`, { method: "POST", body: JSON.stringify(cfg || {}) }),
  videoTask: (tid) => req(`/api/video/task/${tid}`),
  videoDownloadUrl: (id) => `${BASE}/api/video/${id}/download`,

  // 设置
  getSettings: () => req("/api/settings"),
  saveSettings: (s) => req("/api/settings", { method: "PUT", body: JSON.stringify(s) }),
};
