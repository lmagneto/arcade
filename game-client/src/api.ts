import type { JackpotInfo } from './arcade/types';
export type RoundStatus =
  | "WAITING"
  | "RUNNING"
  | "CRASHED"
  | "COMPLETED"
  | "ABORTED";

export interface CurrentRound {
  id: string;
  round_number: number;
  status: RoundStatus;
  scheduled_start_at: string | null;
  started_at: string | null;
  crashed_at: string | null;
  display_multiplier: string | null;
  final_multiplier: string | null;
}



interface CurrentRoundResponse {
  round: CurrentRound | null;
  detail?: string;
}

export interface PairingRequest {
  installation_id: string;
  pairing_code: string;
  expires_at: string;
}

export type PairingStatus =
  | "WAITING"
  | "APPROVED"
  | "EXPIRED"
  | "ACTIVATED";

interface PairingStatusResponse {
  status: PairingStatus;
  detail?: string;
}

export interface DeviceStatus {
  installation_id: string;
  device_name: string;
  installation_status: string;
  major_account_id: string;
  major_account_name: string;
  major_account_status: string;
}

export async function verifyDeviceCredential(
  deviceCredential: string,
): Promise<DeviceStatus> {
  const response = await fetch("/api/devices/status/", {
    method: "GET",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  return readResponse<DeviceStatus>(response);
}

export interface DeviceActivation {
  installation_id: string;
  major_account_id: string;
  device_name: string;
  status: string;
  device_credential: string;
}

async function readResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = Array.isArray(data.detail)
      ? data.detail.join(" ")
      : data.detail;

    throw new Error(
      typeof detail === "string"
        ? detail
        : `Server returned HTTP ${response.status}.`,
    );
  }

  return data as T;
}

export async function createPairingRequest(
  installationId: string,
): Promise<PairingRequest> {
  const response = await fetch("/api/devices/pairing-requests/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ installation_id: installationId }),
  });

  return readResponse<PairingRequest>(response);
}

export async function fetchPairingStatus(
  installationId: string,
): Promise<PairingStatusResponse> {
  const response = await fetch(
    `/api/devices/pairing-requests/status/?installation_id=${encodeURIComponent(installationId)}`,
    { cache: "no-store" },
  );

  return readResponse<PairingStatusResponse>(response);
}

export async function activateDevice(
  installationId: string,
  pairingCode: string,
): Promise<DeviceActivation> {
  const response = await fetch("/api/devices/activate/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      installation_id: installationId,
      activation_code: pairingCode,
      device_name: "ARCADE Windows PC",
    }),
  });

  return readResponse<DeviceActivation>(response);
}

export async function fetchCurrentRound(
  deviceCredential: string,
): Promise<CurrentRoundResponse> {
  const response = await fetch("/api/game/rounds/current/", {
    method: "GET",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  return readResponse<CurrentRoundResponse>(response);
}

export interface EngineHealth {
  healthy: boolean;
  status: "RUNNING" | "STARTING" | "UNAVAILABLE" | "UNKNOWN";
  last_heartbeat_at?: string;
  detail?: string;
}

function isEngineHealth(data: unknown): data is EngineHealth {
  if (typeof data !== "object" || data === null || !("status" in data)) {
    return false;
  }

  return (
    "healthy" in data &&
    typeof data.healthy === "boolean" &&
    (data.status === "RUNNING" ||
      data.status === "STARTING" ||
      data.status === "UNAVAILABLE" ||
      data.status === "UNKNOWN")
  );
}

export async function fetchEngineHealth(
  deviceCredential: string,
): Promise<EngineHealth> {
  const response = await fetch("/api/game/engine/health/", {
    method: "GET",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  const data: unknown = await response.clone().json().catch(() => null);
  if (response.status === 503 && isEngineHealth(data)) {
    return data;
  }

  return readResponse<EngineHealth>(response);
}


export interface PlayerStation {
  slot_id: string;
  slot_number: number;
  display_name: string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  wallet_balance: string;
}

export interface PlayerStationsResponse {
  major_account_id: string;
  detected_count: number;
  players: PlayerStation[];
}

export async function syncPlayerStations(
  deviceCredential: string,
  detectedCount: number,
): Promise<PlayerStationsResponse> {
  const response = await fetch("/api/devices/player-slots/sync/", {
    method: "POST",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      detected_count: detectedCount,
    }),
    cache: "no-store",
  });

  return readResponse<PlayerStationsResponse>(response);
}


export interface PlayerStation {
  slot_id: string;
  slot_number: number;
  display_name: string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  wallet_balance: string;
}

export interface PlayerStationsResponse {
  major_account_id: string;
  players: PlayerStation[];
}

export async function fetchPlayerStations(
  deviceCredential: string,
): Promise<PlayerStationsResponse> {
  const response = await fetch("/api/devices/player-slots/", {
    method: "GET",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  return readResponse<PlayerStationsResponse>(response);
}

export interface PlayerBetInfo {
  id: string;
  round_id: string;
  round_number: number;
  slot_number: number;
  stake: string;
  status: "PLACED" | "CASHED_OUT" | "LOST" | "VOID";
  cashout_multiplier: string | null;
  payout: string | null;
  payout_capped: boolean;
}

export async function fetchCurrentBets(
  deviceCredential: string,
): Promise<{ bets: PlayerBetInfo[] }> {
  const response = await fetch("/api/game/bets/current/", {
    method: "GET",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  return readResponse<{ bets: PlayerBetInfo[] }>(response);
}

interface BetActionResponse {
  bet: PlayerBetInfo;
  player_balance: string;
  major_account_balance: string;
}

/** Place a bet on the round that is waiting to start. */
export async function placeBet(
  deviceCredential: string,
  slotNumber: number,
  amount: string,
): Promise<BetActionResponse> {
  const response = await fetch("/api/game/bets/", {
    method: "POST",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ slot_number: slotNumber, amount }),
    cache: "no-store",
  });

  return readResponse<BetActionResponse>(response);
}

/** Exit the running round. The server decides the multiplier and payout. */
export async function cashOutBet(
  deviceCredential: string,
  slotNumber: number,
): Promise<BetActionResponse> {
  const response = await fetch("/api/game/bets/cash-out/", {
    method: "POST",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ slot_number: slotNumber }),
    cache: "no-store",
  });

  return readResponse<BetActionResponse>(response);
}

type JackpotApiInfo = Omit<JackpotInfo, 'amount'> & {
  amount: string | number;
};

interface JackpotResponse {
  jackpots: JackpotApiInfo[];
}

export async function fetchJackpots(
  deviceCredential: string,
): Promise<JackpotInfo[]> {
  const response = await fetch("/api/game/jackpots/", {
    method: "GET",
    headers: {
      Authorization: `Device ${deviceCredential}`,
      Accept: "application/json",
    },
    cache: "no-store",
  });

  const data = await readResponse<JackpotResponse>(response);

  return data.jackpots.map((jackpot) => ({
    ...jackpot,
    amount: Number(jackpot.amount),
  }));
}