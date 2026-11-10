
const { app, BrowserWindow, ipcMain } = require("electron");
const { createHash } = require("node:crypto");
const { writeFile, unlink } = require("node:fs/promises");
const { spawn } = require("node:child_process");
const path = require("node:path");

let updateStarted = false;

function powershellLiteral(value) {
  return `'${value.replaceAll("'", "''")}'`;
}

async function downloadAndInstallUpdate(update) {
  if (process.platform !== "win32") {
    throw new Error("Automatic updates are supported only on Windows.");
  }
  if (
    !update ||
    typeof update.version !== "string" ||
    !/^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$/.test(update.version) ||
    typeof update.sha256 !== "string" ||
    !/^[0-9a-f]{64}$/i.test(update.sha256) ||
    typeof update.download_url !== "string"
  ) {
    throw new Error("The update manifest is invalid.");
  }

  const downloadUrl = new URL(update.download_url);
  const expectedPath =
    `/lmagneto/arcade/releases/download/game-client-v${update.version}/`;
  if (
    downloadUrl.protocol !== "https:" ||
    downloadUrl.hostname !== "github.com" ||
    !downloadUrl.pathname.startsWith(expectedPath) ||
    !downloadUrl.pathname.toLowerCase().endsWith(".exe")
  ) {
    throw new Error("The update download URL is not trusted.");
  }

  const response = await fetch(downloadUrl, { redirect: "follow" });
  const finalUrl = new URL(response.url);
  if (
    !response.ok ||
    finalUrl.protocol !== "https:" ||
    ![
      "github.com",
      "objects.githubusercontent.com",
      "release-assets.githubusercontent.com",
    ].includes(finalUrl.hostname)
  ) {
    throw new Error(`The update download failed with HTTP ${response.status}.`);
  }

  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length === 0 || bytes.length > 300 * 1024 * 1024) {
    throw new Error("The downloaded update has an invalid size.");
  }

  const digest = createHash("sha256").update(bytes).digest("hex");
  if (digest.toLowerCase() !== update.sha256.toLowerCase()) {
    throw new Error("The downloaded update failed its SHA-256 check.");
  }

  const installerPath = path.join(
    app.getPath("temp"),
    `arcade-client-update-${update.version}.exe`,
  );
  await writeFile(installerPath, bytes, { mode: 0o700 });

  const appPath = app.getPath("exe");
  const script = [
    "$ErrorActionPreference = 'Stop'",
    "Start-Sleep -Seconds 2",
    `try { $result = Start-Process -FilePath ${powershellLiteral(installerPath)} -ArgumentList '/S' -Wait -PassThru; if ($result.ExitCode -ne 0) { throw 'Installer failed' }; Start-Process -FilePath ${powershellLiteral(appPath)} }`,
    `catch { Start-Process -FilePath ${powershellLiteral(appPath)}; exit 1 }`,
    `finally { Remove-Item -LiteralPath ${powershellLiteral(installerPath)} -Force -ErrorAction SilentlyContinue }`,
  ].join("; ");
  const encodedScript = Buffer.from(script, "utf16le").toString("base64");
  const updater = spawn(
    "powershell.exe",
    [
      "-NoLogo",
      "-NoProfile",
      "-NonInteractive",
      "-WindowStyle",
      "Hidden",
      "-EncodedCommand",
      encodedScript,
    ],
    { detached: true, stdio: "ignore", windowsHide: true },
  );

  await new Promise((resolve, reject) => {
    updater.once("spawn", resolve);
    updater.once("error", reject);
  }).catch(async (error) => {
    await unlink(installerPath).catch(() => undefined);
    throw error;
  });

  updater.unref();
  updateStarted = true;
  app.quit();
}

ipcMain.handle("arcade:install-update", async (event, update) => {
  if (!event.senderFrame?.url.startsWith("file://")) {
    throw new Error("Update requests must originate from the packaged client.");
  }
  if (updateStarted) return;

  await downloadAndInstallUpdate(update);
});

function createWindow() {
  const win = new BrowserWindow({
    fullscreen: true,
    autoHideMenuBar: true,
    title: "ARCADE",
    backgroundColor: "#101820",
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });

  // ESC exits full-screen without closing the application.
  win.webContents.on("before-input-event", (event, input) => {
    if (input.key === "Escape" && win.isFullScreen()) {
      event.preventDefault();
      win.setFullScreen(false);
    }
  });

  win.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
