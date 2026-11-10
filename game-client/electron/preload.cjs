const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("arcadeUpdater", {
  installUpdate: (update) => ipcRenderer.invoke("arcade:install-update", update),
});
