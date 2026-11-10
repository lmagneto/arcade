import { ArcadeGame } from "./arcade/ArcadeGame";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  activateDevice,
  createPairingRequest,
  fetchCurrentRound,
  fetchPairingStatus,
  fetchEngineHealth,
  fetchClientUpdate,
  fetchJackpots,
  verifyDeviceCredential,
  type CurrentRound,
  type EngineHealth,
  type ClientUpdate,
  type PlayerStation,
  type PlayerBetInfo,
  fetchPlayerStations,
  fetchCurrentBets,
  syncPlayerStations,
} from "./api";

import type { JackpotInfo } from "./arcade/types";
const INSTALLATION_KEY = "arcade-installation-id";
const CREDENTIAL_KEY = "arcade-device-credential";

function getInstallationId(): string {
  let id = localStorage.getItem(INSTALLATION_KEY);

  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(INSTALLATION_KEY, id);
  }

  return id;
}

function App() {
  const [installationId] = useState(getInstallationId);
  const [pairingCode, setPairingCode] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [pairingStatus, setPairingStatus] = useState("STARTING");
  const [message, setMessage] = useState("");
  const [deviceCredential, setDeviceCredential] = useState(
    () => localStorage.getItem(CREDENTIAL_KEY) ?? "",
  );
  const [round, setRound] = useState<CurrentRound | null>(null);
  const [accountName, setAccountName] = useState("");
  const [health, setHealth] = useState<EngineHealth | null>(null);
  const [pendingClientUpdate, setPendingClientUpdate] =
    useState<ClientUpdate | null>(null);
  const updateApplying = useRef(false);
  const [busy, setBusy] = useState(false);
  const [players, setPlayers] = useState<PlayerStation[]>([]);
  const [bets, setBets] = useState<PlayerBetInfo[]>([]);
  const [jackpots, setJackpots] = useState<JackpotInfo[]>([]);
  const [mouseEvents, setMouseEvents] = useState<
  Record<
    number,
    {
      button: string;
      eventId: number;
      batch: Array<{ button: string; eventId: number }>;
    }
  >
>({});

useEffect(() => {
  let cancelled = false;

  async function startDevice() {
    const savedCredential = localStorage.getItem(CREDENTIAL_KEY);

    // First verify any previously saved device credential.
    if (savedCredential) {
      try {
        setPairingStatus("REQUESTING");

        await verifyDeviceCredential(savedCredential);

        if (cancelled) return;

        setDeviceCredential(savedCredential);
        setPairingStatus("CONNECTED");
        setMessage("");
        return;
      } catch (error) {
        if (cancelled) return;

        // A rejected credential means the server no longer recognises
        // this installation. Remove it and start pairing again.
        console.warn("Saved device credential is no longer valid:", error);

        localStorage.removeItem(CREDENTIAL_KEY);
        setDeviceCredential("");
      }
    }

    // No valid credential: request a fresh pairing code.
    try {
      setPairingStatus("REQUESTING");

      const result = await createPairingRequest(installationId);

      if (cancelled) return;

      setPairingCode(result.pairing_code);
      setExpiresAt(result.expires_at);
      setSecondsLeft(
        Math.max(
          0,
          Math.floor(
            (new Date(result.expires_at).getTime() - Date.now()) / 1000,
          ),
        ),
      );

      setPairingStatus("WAITING");
      setMessage("");
    } catch (error) {
      if (cancelled) return;

      setPairingStatus("ERROR");
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to request a pairing code.",
      );
    }
  }

  void startDevice();

  return () => {
    cancelled = true;
  };
}, [installationId]);

        

  useEffect(() => {
  if (!deviceCredential) {
    setJackpots([]);
    return;
  }

  let cancelled = false;
  let checking = false;

  async function updateJackpots() {
    if (checking || cancelled) return;

    checking = true;

    try {
      const result = await fetchJackpots(deviceCredential);

      if (!cancelled) {
        setJackpots(result);
      }
    } catch (error) {
      if (!cancelled) {
        console.error("Unable to retrieve jackpots:", error);
      }
    } finally {
      checking = false;
    }
  }

  void updateJackpots();

  const timer = window.setInterval(
    () => void updateJackpots(),
    10000,
  );

  return () => {
    cancelled = true;
    window.clearInterval(timer);
  };
}, [deviceCredential]);

  useEffect(() => {
    if (!expiresAt || pairingStatus !== "WAITING") return;

    const updateCountdown = () => {
      const remaining = Math.max(
        0,
        Math.ceil((new Date(expiresAt).getTime() - Date.now()) / 1000),
      );

      setSecondsLeft(remaining);

      if (remaining <= 0) {
        setPairingStatus("EXPIRED");
        setMessage("This pairing code has expired.");
      }
    };

    updateCountdown();
    const timer = window.setInterval(updateCountdown, 1000);

    return () => window.clearInterval(timer);
  }, [expiresAt, pairingStatus]);

  useEffect(() => {
    if (
      pairingStatus !== "WAITING" &&
      pairingStatus !== "APPROVED"
    ) {
      return;
    }

    let cancelled = false;
    let checking = false;

    async function checkStatus() {
      if (checking || cancelled) return;
      checking = true;

      try {
        const result = await fetchPairingStatus(installationId);
        if (cancelled) return;

        if (result.status === "EXPIRED") {
          setPairingStatus("EXPIRED");
          setMessage("This pairing code has expired.");
          return;
        }

        if (result.status === "ACTIVATED") {
          setPairingStatus("ACTIVATED");
          setMessage(
            "This installation has already been activated. Reopen the authorized installation to continue.",
          );
          return;
        }

        if (result.status === "APPROVED") {
          setMessage("Approved. Completing activation...");

          const activated = await activateDevice(
            installationId,
            pairingCode,
          );

          if (cancelled) return;

          localStorage.setItem(
            CREDENTIAL_KEY,
            activated.device_credential,
          );
          setDeviceCredential(activated.device_credential);
          setAccountName(activated.major_account_id);
          setPairingStatus("CONNECTED");
          setMessage("");
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Could not check pairing status.",
          );
        }
      } finally {
        checking = false;
      }
    }

    void checkStatus();
    const timer = window.setInterval(() => void checkStatus(), 2000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [installationId, pairingCode, pairingStatus]);

  useEffect(() => {
    if (!deviceCredential) return;

    let cancelled = false;
    let checking = false;

    async function updateRound() {
      if (checking || cancelled) return;
      checking = true;

      try {
        const result = await fetchCurrentRound(deviceCredential);
        if (!cancelled) setRound(result.round);
      } catch (error) {
        if (!cancelled) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Unable to retrieve the current round.",
          );
        }
      } finally {
        checking = false;
      }
    }

    void updateRound();
    const timer = window.setInterval(() => void updateRound(), 1000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [deviceCredential]);

  useEffect(() => {
    if (!deviceCredential || !window.arcadeUpdater) return;

    let cancelled = false;
    let checking = false;

    async function checkForClientUpdate() {
      if (checking || cancelled) return;
      checking = true;

      try {
        const update = await fetchClientUpdate(deviceCredential);
        if (!cancelled && update.update_available) {
          setPendingClientUpdate(update);
        }
      } catch (error) {
        if (!cancelled) {
          console.error("Unable to check for game client updates:", error);
        }
      } finally {
        checking = false;
      }
    }

    void checkForClientUpdate();
    const timer = window.setInterval(
      () => void checkForClientUpdate(),
      10 * 60 * 1000,
    );

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [deviceCredential]);

  useEffect(() => {
    if (
      !pendingClientUpdate ||
      !round ||
      round.status === "RUNNING" ||
      !window.arcadeUpdater ||
      updateApplying.current
    ) {
      return;
    }

    updateApplying.current = true;
    void window.arcadeUpdater
      .installUpdate(pendingClientUpdate)
      .catch((error: unknown) => {
        updateApplying.current = false;
        console.error("Unable to install game client update:", error);
      });
  }, [pendingClientUpdate, round]);

  useEffect(() => {
    if (!deviceCredential) return;

    let cancelled = false;
    let checking = false;

    async function updateHealth() {
      if (checking || cancelled) return;
      checking = true;

      try {
        const result = await fetchEngineHealth(deviceCredential);
        if (!cancelled) setHealth(result);
      } catch {
        if (!cancelled) {
          setHealth({
            healthy: false,
            status: "UNAVAILABLE",
          });
        }
      } finally {
        checking = false;
      }
    }

    void updateHealth();
    const timer = window.setInterval(() => void updateHealth(), 3000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [deviceCredential]);


  // Balances and bets are fetched together and set in one batch, so a
  // wallet change and the bet that caused it always appear on the same frame.
  const refreshPlayersAndBets = useCallback(async () => {
    if (!deviceCredential) return;

    const [stations, current] = await Promise.all([
      fetchPlayerStations(deviceCredential),
      fetchCurrentBets(deviceCredential),
    ]);

    setPlayers(stations.players);
    setBets(current.bets);
  }, [deviceCredential]);

  useEffect(() => {
    if (!deviceCredential) {
      setPlayers([]);
      setBets([]);
      return;
    }

    let cancelled = false;
    let checking = false;

    async function updatePlayers() {
      if (checking || cancelled) return;
      checking = true;

      try {
        await refreshPlayersAndBets();
      } catch (error) {
        if (!cancelled) {
          console.error("Unable to retrieve player stations:", error);
        }
      } finally {
        checking = false;
      }
    }

    void updatePlayers();
    const timer = window.setInterval(() => void updatePlayers(), 1000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [deviceCredential, refreshPlayersAndBets]);


  useEffect(() => {
    if (!deviceCredential) {
      setMouseEvents({});
      return;
    }

    let cancelled = false;
    let checking = false;
    let lastSyncedCount: number | null = null;
    let lastEventId = 0;

    async function pollMouseBridge() {
      if (checking || cancelled) return;
      checking = true;

      try {
        // 1. Read the physical mice detected by Windows Raw Input.
        const devicesResponse = await fetch("/mouse-bridge/devices", {
          cache: "no-store",
        });

        if (!devicesResponse.ok) {
          throw new Error(
            `Mouse bridge devices request failed: HTTP ${devicesResponse.status}`,
          );
        }

        const devicesData: unknown = await devicesResponse.json();

        if (
          typeof devicesData !== "object" ||
          devicesData === null ||
          !("count" in devicesData) ||
          typeof devicesData.count !== "number" ||
          !Number.isInteger(devicesData.count)
        ) {
          throw new Error("Invalid devices response from mouse bridge.");
        }

const count = Math.max(1, Math.min(8, devicesData.count));

// Synchronize whenever the effective player count changes.
if (count !== lastSyncedCount) {
  await syncPlayerStations(deviceCredential, count);

  if (cancelled) return;

  lastSyncedCount = count;
  console.log(
    `Mouse bridge: ${devicesData.count} physical mouse(s) detected. ` +
    `${count} player slot(s) active.`,
  );
}

        // 2. Read new events, preserving each event's player slot.
        const eventsResponse = await fetch(
          `/mouse-bridge/events?since=${lastEventId}`,
          { cache: "no-store" },
        );

        if (!eventsResponse.ok) {
          throw new Error(
            `Mouse bridge events request failed: HTTP ${eventsResponse.status}`,
          );
        }

        const eventsData: unknown = await eventsResponse.json();

        if (
          typeof eventsData !== "object" ||
          eventsData === null ||
          !("events" in eventsData) ||
          !Array.isArray(eventsData.events) ||
          !("latest_id" in eventsData) ||
          typeof eventsData.latest_id !== "number"
        ) {
          throw new Error("Invalid events response from mouse bridge.");
        }

        if (cancelled) return;

        const newEvents = eventsData.events as Array<{
          id: number;
          player_slot: number;
          button: string;
        }>;

        if (newEvents.length > 0) {
          setMouseEvents((previous) => {
            const updated = { ...previous };
            // Every event from this poll is kept (not only the last one per
            // slot), so fast scrolling / repeated clicks are never lost.
            const currentBatches: Record<number, Array<{ button: string; eventId: number }>> = {};

            for (const event of newEvents) {
              if (
                Number.isInteger(event.player_slot) &&
                event.player_slot >= 1 &&
                event.player_slot <= 8 &&
                typeof event.button === "string"
              ) {
const batch = currentBatches[event.player_slot] ?? [];
                batch.push({ button: event.button, eventId: event.id });
                currentBatches[event.player_slot] = batch;

                updated[event.player_slot] = {
                  button: event.button,
                  eventId: event.id,
                  batch,
                };
              }
            }

            return updated;
          });
        }

        lastEventId = eventsData.latest_id;
      } catch (error) {
        if (!cancelled) {
          console.error("Mouse bridge connection failed:", error);
        }
      } finally {
        checking = false;
      }
    }

    void pollMouseBridge();

    const timer = window.setInterval(() => {
      void pollMouseBridge();
    }, 500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [deviceCredential]);



  async function renewPairingCode() {
    setBusy(true);
    setMessage("");
    setPairingCode("");
    setExpiresAt("");
    setPairingStatus("REQUESTING");

    try {
      const result = await createPairingRequest(installationId);
      setPairingCode(result.pairing_code);
      setExpiresAt(result.expires_at);
      setSecondsLeft(
        Math.max(
          0,
          Math.floor(
            (new Date(result.expires_at).getTime() - Date.now()) / 1000,
          ),
        ),
      );
      setPairingStatus("WAITING");
    } catch (error) {
      setPairingStatus("ERROR");
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to request another pairing code.",
      );
    } finally {
      setBusy(false);
    }
  }

  // Paired: show the Arcade Bets game screen. The pairing screen below is unchanged.

if (deviceCredential) {
  return (
    <ArcadeGame
      round={round}
      players={players}
      bets={bets}
      jackpots={jackpots}
      deviceCredential={deviceCredential}
      onRefresh={refreshPlayersAndBets}
      health={health}
      message={message}
      mouseEvents={mouseEvents}
    />
  );
}

  const status = round?.status ?? "WAITING";
  const multiplier = Number(round?.display_multiplier ?? "0");
  const crashed = status === "CRASHED" || status === "COMPLETED";

  return (
    <main className="game-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">✈</span>
          <div>
            <h1>ARCADE</h1>
            <p>FLYING HIGHER</p>
          </div>
        </div>

                <div className="connection">
          <span className="status-dot" />
          {deviceCredential ? "CONNECTED" : "PAIRING REQUIRED"}
        </div>

        {deviceCredential && (
          <div className="connection">
            <span className="status-dot" />
            {!health
              ? "ENGINE CHECKING"
              : health.healthy
                ? "ENGINE ONLINE"
                : "ENGINE UNAVAILABLE"}
          </div>
        )}
      </header>






      {!deviceCredential ? (
        <section className="flight-panel connection-panel">
          <div className="flight-heading">
            <span>LINK THIS PC</span>
            <span className="demo-tag">DEVICE ACTIVATION</span>
          </div>

          <h2>
            {pairingStatus === "ERROR"
              ? "Unable to create pairing code"
              : "Connect your major account"}
          </h2>

          <p className="connect-description">
            Open your major account portal, choose Link a PC, and enter the
            code shown below. Keep this window open until approval.
          </p>

          <div className="pairing-code">
            {pairingStatus === "REQUESTING" ||
            pairingStatus === "STARTING"
              ? "REQUESTING CODE..."
              : pairingCode || "—"}
          </div>

          {pairingStatus === "WAITING" && (
            <>
              <p className="countdown">
                Expires in {Math.floor(secondsLeft / 60)}:
                {String(secondsLeft % 60).padStart(2, "0")}
              </p>
              <p className="waiting-message">
                Waiting for your major account owner to approve this PC...
              </p>
            </>
          )}

          {pairingStatus === "APPROVED" && (
            <p className="waiting-message">
              Account approved. Activating PC...
            </p>
          )}

          {pairingStatus === "CONNECTED" && (
            <p className="waiting-message">PC successfully linked.</p>
          )}

          {message && <p className="error-message">{message}</p>}

          {(pairingStatus === "EXPIRED" ||
            pairingStatus === "ERROR") && (
            <button
              className="primary-button"
              disabled={busy}
              onClick={() => void renewPairingCode()}
            >
              {busy ? "Requesting..." : "Request a new code"}
            </button>
          )}

         
        </section>
      ) : (
        <>
          

<section className="round-strip history-panel">
  <div className="history">
      </div>

  <div className="history-list">
    {Array.from({ length: 20 }, (_, index) => (
      <div className="history-item" key={index}>
        <strong>—</strong>
      </div>
    ))}
  </div>
</section>



         
<section className="flight-panel">
  <div className="sky-grid" />
  <div className="sky-glow" />

  {status === "WAITING" && (
    <div className="flight-result waiting-result">
      WAITING FOR TAKEOFF
    </div>
  )}

  {(status === "RUNNING" || crashed) && (
    <div
      className={`flight-instrument ${crashed ? "instrument-crashed" : ""}`}
      style={{
        left: `${Math.min(78, 12 + Math.max(0, multiplier - 1) * 4)}%`,
        bottom: `${Math.min(68, 18 + Math.max(0, multiplier - 1) * 3)}%`,
      }}
    >
      <div className={`aircraft ${crashed ? "aircraft-crashed" : ""}`}>
        ✈
      </div>

      <div className="multiplier">
        {Number.isFinite(multiplier)
          ? `${multiplier.toFixed(2)}×`
          : "—"}
      </div>
    </div>
  )}

  {crashed && (
    <div className="flight-result">
      FLEW AWAY!
    </div>
  )}
</section>


           

          <section className="players-section">
           
            
<div className="player-grid">
  {Array.from({ length: 8 }, (_, index) => {
    const slotNumber = index + 1;
    const player = players.find(
      (item) => item.slot_number === slotNumber,
    );
    const active = player?.status === "ACTIVE";

    return (
      <article
        className={`player-card ${active ? "" : "inactive"}`}
        key={slotNumber}
      >
        <div className="player-card-top">
          <span className="player-icon">
            {String(slotNumber).padStart(2, "0")}
          </span>

          <span className="player-status">
            {player?.status ?? "NO SLOT"}
          </span>
        </div>

        <h3>
          {player?.display_name ?? `PLAYER ${String(slotNumber).padStart(2, "0")}`}
        </h3>

        <div className="balance-label">VIRTUAL BALANCE</div>

        <div className="balance">
          {player
            ? Number(player.wallet_balance).toLocaleString("en-KE", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })
            : "—"}
        </div>


      </article>
    );
  })}
</div>
</section>

 

          {accountName && (
            <p className="server-info">Account: {accountName}</p>
          )}

          {message && <p className="error-message">{message}</p>}
        </>
      )}

      
<footer className="footer">
  <span className="footer-brand">NOT FOR PERSONS UNDER THE AGE OF 18</span>

  <div className="age-warning" role="note" aria-label="Age restriction">
    <span className="age-badge">18+</span>
    <span className="age-warning-text">
      
    </span>
    <span className="regulatory-warning">
      .BCLB-LICENSED SERVICE
    </span>
  </div>
</footer>

    </main>
  );
}

export default App;
