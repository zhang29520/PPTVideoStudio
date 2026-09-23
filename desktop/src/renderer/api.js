// 后端 API 封装（本地 FastAPI，端口由主进程动态分配）
let basePromise = null;

function getBase() {
  if (!basePromise) {
    basePromise = (window.pvs ? window.pvs.backendInfo() : Promise.resolve({ port: 8000 })).then(
      (info) => `http://127.0.0.1:${info.port || 8000}`
    );
  }
  return basePromise;
}

async function req(path, options = {}) {
  const base = await getBase();
  const res = await fetch(base + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
      if (typeof detail !== "string") detail = JSON.stringify(detail); // 防止 "[object Object]"
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

  // 通用后台任务
  task: (tid) => req(`/api/tasks/${tid}`),

  // PPT
  generatePpt: (id, cfg) =>
    req(`/api/ppt/generate/${id}`, { method: "POST", body: JSON.stringify(cfg || {}) }),
  getSlides: (id) => req(`/api/ppt/${id}`),
  saveSlides: (id, slides) =>
    req(`/api/ppt/${id}`, { method: "PUT", body: JSON.stringify({ slides }) }),
  importPpt: async (file) => {
    const base = await getBase();
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(base + "/api/ppt/import", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "导入失败");
    return res.json();
  },
  importDocx: async (file) => {
    const base = await getBase();
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(base + "/api/ppt/import-docx", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || "Word 解析失败");
    return res.json();
  },
  pptDownloadUrl: async (id) => `${await getBase()}/api/ppt/${id}/download`,
  thumbUrl: async (id, index) => `${await getBase()}/api/ppt/${id}/thumb/${index}.png`,
  pageUrl: async (id, index) => `${await getBase()}/api/ppt/${id}/page/${index}.png`,
  // 应用内下载（不弹新窗口）：fetch → blob → a[download]
  downloadFile: async (url, filename) => {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`下载失败 (${res.status})`);
    const blob = await res.blob();
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = objUrl;
    a.download = filename || "";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(objUrl), 30000);
  },

  // 解说词
  generateSpeech: (id, tone) =>
    req(`/api/speech/generate/${id}`, { method: "POST", body: JSON.stringify({ tone }) }),
  generateSpeechOne: (id, index) =>
    req(`/api/speech/generate-one/${id}`, { method: "POST", body: JSON.stringify({ index }) }),
  useSpeechNotes: (id) =>
    req(`/api/speech/use-notes/${id}`, { method: "POST", body: "{}" }),
  saveSpeech: (id, pages) =>
    req(`/api/speech/${id}`, { method: "PUT", body: JSON.stringify({ pages }) }),

  // TTS
  generateTts: (id, cfg) =>
    req(`/api/tts/generate/${id}`, { method: "POST", body: JSON.stringify(cfg || {}) }),
  audioUrl: async (id, file) => `${await getBase()}/api/tts/${id}/audio/${file}`,
  previewUrl: async (voice, speed) =>
    `${await getBase()}/api/tts/preview?voice=${encodeURIComponent(voice || "")}&speed=${speed}`,

  // 视频
  exportVideo: (id, cfg) =>
    req(`/api/video/export/${id}`, { method: "POST", body: JSON.stringify(cfg || {}) }),
  videoTask: (tid) => req(`/api/video/task/${tid}`),
  videoDownloadUrl: async (id) => `${await getBase()}/api/video/${id}/download`,

  // 背景音乐（内置 5 种风格，可商用）
  bgmList: () => req("/api/bgm/list"),
  bgmFileUrl: async (styleId) => `${await getBase()}/api/bgm/${styleId}/file`,

  // 设置
  getSettings: () => req("/api/settings"),
  saveSettings: (s) => req("/api/settings", { method: "PUT", body: JSON.stringify(s) }),
  testLlm: (profileId) => req("/api/settings/test_llm", {
    method: "POST",
    body: JSON.stringify(profileId ? { profile_id: profileId } : {}),
  }),
};

/**
 * 启动后台任务并轮询进度。
 * start: () => Promise<{taskId}>；onProgress(t: task状态)
 * 返回 task.result；出错抛异常。
 */
export async function runTask(start, onProgress) {
  const r = await start();
  for (;;) {
    await new Promise((res) => setTimeout(res, 1200));
    const t = await api.task(r.taskId);
    onProgress && onProgress(t);
    if (t.status === "done") return t.result || {};
    if (t.status === "error") throw new Error(t.error || "任务失败");
  }
}
