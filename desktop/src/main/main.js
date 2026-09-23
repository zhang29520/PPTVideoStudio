const { app, BrowserWindow, Menu, ipcMain, shell, session } = require("electron");
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
  if (restarting) return;
  killSpawnedBackends();
  backendProc = null;
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
    const backendName = process.platform === "win32" ? "pvs-backend.exe" : "pvs-backend";
    const backendExe = path.join(process.resourcesPath, "pvs-backend", backendName);
    if (!fs.existsSync(backendExe)) {
      backendState.error = "后端程序缺失：" + backendExe;
      return;
    }
    cmd = backendExe;
    args = [];
    opts = { env, stdio: ["ignore", logStream, logStream], windowsHide: true };
  }

  backendProc = spawn(cmd, args, opts);
  spawnedBackends.add(backendProc);
  backendProc.on("error", (err) => {
    fs.writeSync(logStream, `[spawn error] ${err.message}\n`);
    backendState.error = "后端启动失败：" + err.message;
  });
  backendProc.on("exit", (code) => {
    spawnedBackends.delete(backendProc);
    fs.writeSync(logStream, `[exit] code=${code}\n`);
    if (!backendState.ready) {
      backendState.error = `后端进程退出（code=${code}），详见日志`;
    }
    backendProc = null;
    // 意外退出自动重启（应用退出时 quitting 已置位，跳过）
    if (app.isReady() && !quitting) {
      backendState.ready = false;
      restartBackend(`process exited code=${code}`);
    }
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
  // 一切新窗口请求一律拦截：外链交给系统浏览器，杜绝应用内弹空白窗
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: "deny" };
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

/* ---------- HTML 幻灯片渲染工作器 ----------
 * 后端把 slides HTML 登记为任务，这里用离屏窗口逐页截图回传 PNG。
 * 出图质量即真实浏览器渲染效果（渐变/卡片/圆角/现代排版）。
 */
const { BrowserWindow: OffscreenWin } = require("electron");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function renderOneJob(job) {
  const base = `http://127.0.0.1:${backendState.port}`;
  const bw = new OffscreenWin({
    show: false,
    width: 1920,
    height: 1080,
    useContentSize: true,
    webPreferences: { offscreen: true },
  });
  try {
    await bw.loadURL(`${base}/api/render/jobs/${job.id}.html`);
    let ready = false;
    for (let t = 0; t < 40 && !ready; t++) {
      ready = await bw.webContents.executeJavaScript("window.__READY__===true").catch(() => false);
      if (!ready) await sleep(250);
    }
    if (!ready) throw new Error("slides html not ready");
    for (let i = 0; i < job.count; i++) {
      await bw.webContents.executeJavaScript(`window.__goto(${i})`);
      await sleep(350); // 等字体/渐变绘制
      const img = await bw.webContents.capturePage();
      const buf = img.toPNG();
      const r = await fetch(`${base}/api/render/jobs/${job.id}/png/${i}`, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream" },
        body: buf,
      });
      if (!r.ok) throw new Error(`png upload failed: ${i}`);
    }
    await fetch(`${base}/api/render/jobs/${job.id}/done`, { method: "POST" });
  } catch (e) {
    try {
      await fetch(`${base}/api/render/jobs/${job.id}/fail`, { method: "POST" });
    } catch {}
  } finally {
    try { bw.destroy(); } catch {}
  }
}

function startRenderWorker() {
  setInterval(async () => {
    if (!backendState.ready) return;
    try {
      const res = await fetch(`http://127.0.0.1:${backendState.port}/api/render/jobs/next`);
      const job = await res.json();
      if (job && job.id) await renderOneJob(job);
    } catch {}
  }, 2500);
}
ipcMain.handle("app:openExternal", (_e, url) => {
  if (/^https:\/\//.test(url)) shell.openExternal(url);
});
let updateCache = null;
app.whenReady().then(async () => {
  // 关键：本机若开了系统代理（127.0.0.1），会把对本地后端的请求也拦成 502，
  // 导致试听/缩略图/接口全部失败。渲染进程只需要访问本地后端，直接禁用代理。
  try {
    await session.defaultSession.setProxy({ mode: "direct" });
  } catch {}
  // 应用内下载：拦截 <a download> 触发的下载，直接存到系统「下载」文件夹（极简，不弹对话框）
  session.defaultSession.on("will-download", (_e, item) => {
    try {
      const name = item.getFilename() || `PPTVideoStudio-${Date.now()}.mp4`;
      item.setSavePath(path.join(app.getPath("downloads"), name));
      item.once("done", (_ev, state) => {
        if (win && !win.isDestroyed()) {
          win.webContents.send("app:download-done", {
            name,
            ok: state === "completed",
            path: item.getSavePath(),
          });
        }
      });
    } catch {}
  });
  createWindow();
  startBackend();
  startRenderWorker();
  startBackendWatchdog();
  updateCache = await checkUpdate();
});
ipcMain.handle("app:updateInfo", () => updateCache || checkUpdate());

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

/* ---------- 后端自愈：进程退出或健康检查连续失败时自动重启 ---------- */
let restarting = false;
let restartCount = 0;
let quitting = false;
app.on("before-quit", () => { quitting = true; });
const spawnedBackends = new Set(); // 所有 spawn 过的后端进程，重启时统一清杀，防孤儿

function killSpawnedBackends() {
  for (const p of spawnedBackends) {
    try { if (!p.killed) p.kill(); } catch {}
  }
  spawnedBackends.clear();
}

function restartBackend(reason) {
  if (restarting || quitting) return;
  restarting = true;
  restartCount += 1;
  if (restartCount > 8) return; // 防止无限重启
  killSpawnedBackends();
  backendProc = null;
  backendState.ready = false;
  console.log(`[watchdog] backend restart (#${restartCount}): ${reason}`);
  setTimeout(() => {
    restarting = false;
    if (!quitting) startBackend();
  }, 2500);
}

function startBackendWatchdog() {
  let fails = 0;
  setInterval(async () => {
    // 仅在后端完全就绪后监视；启动窗口内（ready=false）不判失败，避免误杀启动慢的实例
    if (restarting || quitting || !backendProc || !backendState.ready) return;
    try {
      const res = await fetch(`http://127.0.0.1:${backendState.port}/health`, {
        signal: AbortSignal.timeout(6000),
      });
      if (res.ok) { fails = 0; return; }
      fails += 1;
    } catch { fails += 1; }
    if (fails >= 3) { fails = 0; restartBackend("health check failed 3 times"); }
  }, 10000);
}

app.on("quit", () => {
  killSpawnedBackends();
});
