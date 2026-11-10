/// <reference types="vite/client" />

declare const __APP_VERSION__: string;

interface Window {
  arcadeUpdater?: {
    installUpdate(update: {
      version: string;
      download_url: string;
      sha256: string;
    }): Promise<void>;
  };
}
