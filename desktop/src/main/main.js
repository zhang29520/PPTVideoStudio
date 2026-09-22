const { app, BrowserWindow, Menu, ipcMain, shell } = require("electron");
const path = require("path");
const fs = require("fs");
const net = require("net");
const { spawn } = require("child_process");

const isDev = !app.isPackaged;
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
    const python = process.platform === "win32" ? "python" : "python3";
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
    webPreferences: {
      preload: path.join(__dirname, "../preload/preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  if (isDev) {
    win.loadURL("http://localhost:5173");
  } else {
    win.loadFile(path.join(__dirname, "../../dist/index.html"));
  }
  Menu.setApplicationMenu(null);
}

ipcMain.handle("app:backendInfo", () => ({ ...backendState }));
ipcMain.handle("app:openLogs", () => { shell.openPath(logDir()); });
ipcMain.handle("app:restartBackend", () => startBackend());

app.whenReady().then(() => {
  createWindow();
  startBackend();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("quit", () => {
  if (backendProc && !backendProc.killed) backendProc.kill();
});
