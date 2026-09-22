// 预加载脚本：安全地把后端 API 暴露给渲染层
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("api", {
  backendStatus: () => ipcRenderer.invoke("app:backendStatus"),
  // 渲染层可继续扩展：生成 PPT、生成讲稿、TTS、视频导出等
});
