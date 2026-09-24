// 预加载脚本：安全地把主进程能力暴露给渲染层
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("pvs", {
  backendInfo: () => ipcRenderer.invoke("app:backendInfo"),
  onBackendReady: (cb) => ipcRenderer.on("app:backend-ready", () => cb()),
  openLogs: () => ipcRenderer.invoke("app:openLogs"),
  restartBackend: () => ipcRenderer.invoke("app:restartBackend"),
  checkUpdate: () => ipcRenderer.invoke("app:checkUpdate"),
  updateInfo: () => ipcRenderer.invoke("app:updateInfo"),
  openExternal: (url) => ipcRenderer.invoke("app:openExternal", url),
  saveFileAs: (url, defaultName) => ipcRenderer.invoke("app:saveFileAs", { url, defaultName }),
  onDownloadDone: (cb) => ipcRenderer.on("app:download-done", (_e, info) => cb(info)),
});
