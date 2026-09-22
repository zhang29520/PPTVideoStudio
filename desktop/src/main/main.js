const { app, BrowserWindow, Menu, ipcMain, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const net = require("net");
const { spawn } = require("child_process");

const isDev = !app.isPackaged;
// 规避部分环境（虚拟机/老显卡）GPU 崩溃导致的白屏
app.disableHardwareAcceleration();
// 公开发布仓库（更新检查）与网盘兜底
const RELEASE_REPO = "zhang29520/PPTVideoStudio-release";
const QUARK_URL = "https://pan.quark.cn/s/465afff8905a";
let win = null;
let backendProc = null;
let backendState = {
  port: 0,
  ready: false,
  error: "",
  logPath: "",
  restarting: false,
};

function logDir() {
  const dir = path.join(app.getPath("userData"), "logs");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function pickFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

function childEnv(port) {
  // 把随包分发的 ffmpeg/ffprobe 加入 PATH，并指定用户数据目录
  const resources = isDev ? path.join(__dirname, "../../resources") : process.resourcesPath;
  const ffmpegDir = path.join(resources, "ffmpeg");
  const env = { ...process.env };
  const sep = process.platform === "win32" ? ";" : ":";
  env.PATH = ffmpegDir + sep + (env.PATH || "");
  env.PVS_DATA_DIR = path.join(app.getPath("userData"), "data");
  env.PVS_PORT = String(port);
  return env;
}

async function waitForHealth(port, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`, { signal: AbortSignal.timeout(1500) });
      if (res.ok) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

async function startBackend(attempt = 1) {
  if (backendProc) {
    try { backendProc.kill(); } catch {}
    backendProc = null;
  }
  const port = await pickFreePort();
  const env = childEnv(port);
  const logFile = path.join(logDir(), `backend-${Date.now()}.log`);
  // 只保留最近 5 个日志文件
  try {
    const old = fs.readdirSync(logDir()).filter((f) => f.startsWith("backend-")).sort();
    while (old.length >= 5) fs.unlinkSync(path.join(logDir(), old.shift()));
  } catch {}
  const logStream = fs.openSync(logFile, "a");
  fs.writeSync(logStream, `\n==== launch ${new Date().toISOString()} port=${port} attempt=${attempt} ====\n`);

  backendState = { port, ready: false, error: "", logPath: logFile, restarting: attempt > 1 };

  let cmd, args, opts;
  if (isDev) {
    const backendDir = path.join(__dirname, "../../../backend");
    const python = process.env.PVS_PYTHON || (process.platform === "win32" ? "python" : "python3");
    cmd = python;
    args = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)];
    opts = { cwd: backendDir, env, stdio: ["ignore", logStream, logStream] };
  } else {
    const backendExe = path.join(process.resourcesPath, "pvs-backend", "pvs-backend.exe");
    if (!fs.existsSync(backendExe)) {
      backendState.error = "后端程序缺失：" + backendExe;
      return;
    }
    cmd = backendExe;
    args = [];
    opts = { env, stdio: ["ignore", logStream, logStream], windowsHide: true };
  }

  backendProc = spawn(cmd, args, opts);
  backendProc.on("error", (err) => {
    fs.writeSync(logStream, `[spawn error] ${err.message}\n`);
    backendState.error = "后端启动失败：" + err.message;
  });
  backendProc.on("exit", (code) => {
    fs.writeSync(logStream, `[exit] code=${code}\n`);
    if (!backendState.ready) {
      backendState.error = `后端进程退出（code=${code}），详见日志`;
    }
    backendProc = null;
  });

  const ok = await waitForHealth(port, 60000);
  if (ok) {
    backendState.ready = true;
    backendState.error = "";
    backendState.restarting = false;
    if (win) win.webContents.send("app:backend-ready");
    return;
  }
  // 首次失败自动重试一次
  if (attempt < 2) {
    backendState.restarting = true;
    await startBackend(attempt + 1);
  } else if (!backendState.error) {
    backendState.error = "后端健康检查超时，详见日志";
  }
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 880,
    minWidth: 980,
    minHeight: 640,
    title: "PPTVideoStudio",
    backgroundColor: "#fafaf9",
    show: false, // 等 ready-to-show 再显示，避免白屏/闪白
    webPreferences: {
      preload: path.join(__dirname, "../preload/preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  const indexUrl = isDev
    ? "http://localhost:5173"
    : "file://" + path.join(__dirname, "../../dist/index.html").replace(/\\/g, "/");
  win.loadURL(indexUrl);
  win.once("ready-to-show", () => win.show());
  // 页面加载失败（打包资源路径异常等）→ 自动重载，最多 3 次
  let reloads = 0;
  win.webContents.on("did-fail-load", (_e, code, desc, url, isMain) => {
    if (!isMain || reloads >= 3) return;
    reloads += 1;
    setTimeout(() => win.loadURL(indexUrl), 800 * reloads);
  });
  // 渲染进程崩溃 → 自动重启渲染进程并重载
  win.webContents.on("render-process-gone", (_e, details) => {
    if (details && details.reason === "clean-exit") return;
    win.webContents.reload();
  });
  Menu.setApplicationMenu(null);
}

ipcMain.handle("app:backendInfo", () => ({ ...backendState }));
ipcMain.handle("app:openLogs", () => { shell.openPath(logDir()); });
ipcMain.handle("app:restartBackend", () => startBackend());

/* ---------- 更新检查 ---------- */
function verNum(v) {
  const parts = String(v || "0").replace(/^v/, "").split(/[.\-]/).map((x) => parseInt(x, 10) || 0);
  while (parts.length < 3) parts.push(0);
  return parts;
}
function isNewer(latest, current) {
  const a = verNum(latest), b = verNum(current);
  for (let i = 0; i < 3; i++) {
    if (a[i] !== b[i]) return a[i] > b[i];
  }
  return false;
}

async function checkUpdate() {
  const current = app.getVersion();
  try {
    const res = await fetch(`https://api.github.com/repos/${RELEASE_REPO}/releases/latest`, {
      signal: AbortSignal.timeout(8000),
      headers: { "User-Agent": "PPTVideoStudio" },
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    const latest = String(data.tag_name || "").replace(/^v/, "");
    if (latest && isNewer(latest, current)) {
      return { available: true, current, latest, url: data.html_url || `https://github.com/${RELEASE_REPO}/releases/latest`, quark: QUARK_URL, source: "github" };
    }
    return { available: false, current, latest: latest || current, quark: QUARK_URL, source: "github" };
  } catch (e) {
    // GitHub 连不上：不弹窗打扰，仅提供网盘入口
    return { available: false, current, latest: "", quark: QUARK_URL, source: "none", githubError: String(e.message || e) };
  }
}

ipcMain.handle("app:checkUpdate", () => checkUpdate());
ipcMain.handle("app:openExternal", (_e, url) => {
  if (/^https:\/\//.test(url)) shell.openExternal(url);
});
let updateCache = null;
app.whenReady().then(async () => {
  createWindow();
  startBackend();
  updateCache = await checkUpdate();
});
ipcMain.handle("app:updateInfo", () => updateCache || checkUpdate());

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("quit", () => {
  if (backendProc && !backendProc.killed) backendProc.kill();
});
