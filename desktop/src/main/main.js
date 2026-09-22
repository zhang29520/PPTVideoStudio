const { app, BrowserWindow, Menu, ipcMain } = require("electron");
const path = require("path");
const { spawn } = require("child_process");

const isDev = !app.isPackaged;
let win = null;
let backendProc = null;

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    title: "PPTVideoStudio",
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

function childEnv() {
  // 把随包分发的 ffmpeg/ffprobe 加入 PATH，并指定用户数据目录
  const resources = isDev ? path.join(__dirname, "../../resources") : process.resourcesPath;
  const ffmpegDir = path.join(resources, "ffmpeg");
  const env = { ...process.env };
  const sep = process.platform === "win32" ? ";" : ":";
  env.PATH = ffmpegDir + sep + (env.PATH || "");
  env.PVS_DATA_DIR = path.join(app.getPath("userData"), "data");
  return env;
}

function startBackend() {
  const env = childEnv();
  if (isDev) {
    // 开发模式：用本机 Python 跑源码
    const backendDir = path.join(__dirname, "../../../backend");
    const python = process.platform === "win32" ? "python" : "python3";
    backendProc = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"], {
      cwd: backendDir,
      env,
      stdio: "inherit",
    });
  } else {
    // 生产模式：随包分发的后端 exe（由 PyInstaller 在 CI 构建）
    const backendExe = path.join(process.resourcesPath, "pvs-backend", "pvs-backend.exe");
    backendProc = spawn(backendExe, [], { env, stdio: "ignore", windowsHide: true });
  }
}

ipcMain.handle("app:backendStatus", () => ({
  running: !!backendProc && !backendProc.killed,
}));

app.whenReady().then(() => {
  startBackend();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("quit", () => {
  if (backendProc && !backendProc.killed) backendProc.kill();
});
