
const configuredApiOrigin = import.meta.env.VITE_API_URL;
const configuredApiBaseUrl =
  (configuredApiOrigin
    ? `${configuredApiOrigin.replace(/\/+$/, "")}/api`
    : import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api");
const API_BASE_URL = configuredApiBaseUrl.replace(/\/+$/, "");

// ==============================
// Device API types
// ==============================

export interface DeviceStatus {
  installation_id: string;
  device_name: string;
  status: string;
  major_account: {
    id: string;
    name: string;
    status: string;
  };
}

export interface PlayerSlot {
  slot_id: string;
  slot_number: number;
  display_name: string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  wallet_balance: string;
}

export interface PlayerSlotsResponse {
  major_account_id: string;
  detected_count: number;
  players: PlayerSlot[];
}

// ==============================
// Authentication types
// ==============================

export interface LoginResponse {
  access: string;
  refresh: string;
  must_change_password: boolean;
  role: string;
}

export interface ChangePasswordResponse {
  detail: string;
  must_change_password: boolean;
}

// ==============================
// Major-account types
// ==============================

export interface MajorAccount {
  id: string;
  name: string;
  status: string;
  wallet_balance: string;
}

export interface MajorAccountsResponse {
  accounts: MajorAccount[];
}

export interface ManagedPlayer {
  id: string;
  slot_number: number;
  display_name: string;
  status: "ACTIVE" | "INACTIVE" | "SUSPENDED";
  wallet_balance: string;
}

export interface ManagedPlayersResponse {
  major_account_id: string;
  major_account_name: string;
  account_status: string;
  players: ManagedPlayer[];
}

export interface TransferResponse {
  detail: string;
  reference: string;
  direction: "CREDIT" | "DEBIT";
  amount: string;
  major_account_balance: string;
  player_balance: string;
}

// ==============================
// Shared API request helper
// ==============================

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  credential?: string,
  authScheme: "Bearer" | "Device" = "Bearer",
): Promise<T> {
  const headers = new Headers(options.headers);

  headers.set("Accept", "application/json");

  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (credential) {
    headers.set("Authorization", `${authScheme} ${credential}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const detail =
      data?.detail ??
      data?.non_field_errors?.[0] ??
      `Request failed with HTTP ${response.status}`;

    throw new Error(
      Array.isArray(detail) ? detail.join(", ") : String(detail),
    );
  }

  return data as T;
}

// ==============================
// Login
// ==============================

export function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  return apiRequest<LoginResponse>("/token/", {
    method: "POST",
    body: JSON.stringify({
      username,
      password,
    }),
  });
}

// ==============================
// Refresh authentication token
// ==============================

export interface RefreshTokenResponse {
  access: string;
  refresh?: string;
}


export function refreshAccessToken(
  refresh: string,
): Promise<{ access: string }> {
  return apiRequest<{ access: string }>("/token/refresh/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
}

// ==============================
// Change temporary password
// ==============================

export function changePassword(
  accessToken: string,
  currentPassword: string,
  newPassword: string,
): Promise<ChangePasswordResponse> {
  return apiRequest<ChangePasswordResponse>(
    "/accounts/change-password/",
    {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    },
    accessToken,
  );
}


export interface PlatformMajorAccount {
  id: string;
  name: string;
  account_code: string;
  status: string;
  owner_id: number;
  owner_username: string;
  owner_email: string;
  wallet_balance: string;
  created_at: string;
}

export interface PlatformMajorAccountsResponse {
  accounts: PlatformMajorAccount[];
}

export interface CreateMajorAccountResponse {
  detail: string;
  account: PlatformMajorAccount & {
    must_change_password: boolean;
  };
  temporary_password: string;
}

export interface ResetOwnerPasswordResponse {
  detail: string;
  owner_username: string;
  must_change_password: boolean;
  temporary_password: string;
}


export function getPlatformMajorAccounts(
  accessToken: string,
): Promise<PlatformMajorAccountsResponse> {
  return apiRequest<PlatformMajorAccountsResponse>(
    "/tenants/major-accounts/",
    {},
    accessToken,
  );
}

export function createPlatformMajorAccount(
  accessToken: string,
  name: string,
  username: string,
  email: string,
): Promise<CreateMajorAccountResponse> {
  return apiRequest<CreateMajorAccountResponse>(
    "/tenants/major-accounts/",
    {
      method: "POST",
      body: JSON.stringify({
        name,
        username,
        email,
      }),
    },
    accessToken,
  );
}

export function resetMajorOwnerPassword(
  accessToken: string,
  majorAccountId: string,
): Promise<ResetOwnerPasswordResponse> {
  return apiRequest<ResetOwnerPasswordResponse>(
    `/tenants/major-accounts/${encodeURIComponent(
      majorAccountId,
    )}/reset-password/`,
    {
      method: "POST",
    },
    accessToken,
  );
}

// ==============================
// Major-account owner endpoints
// ==============================

export function getMajorAccounts(
  accessToken: string,
): Promise<MajorAccountsResponse> {
  return apiRequest<MajorAccountsResponse>(
    "/wallets/major-accounts/",
    {},
    accessToken,
  );
}

export function getMajorAccountPlayers(
  accessToken: string,
  majorAccountId: string,
): Promise<ManagedPlayersResponse> {
  return apiRequest<ManagedPlayersResponse>(
    `/wallets/major-accounts/${encodeURIComponent(
      majorAccountId,
    )}/players/`,
    {},
    accessToken,
  );
}

export function transferPlayerCredits(
  accessToken: string,
  majorAccountId: string,
  playerSlotId: string,
  direction: "CREDIT" | "DEBIT",
  amount: string,
): Promise<TransferResponse> {
  return apiRequest<TransferResponse>(
    `/wallets/major-accounts/${encodeURIComponent(
      majorAccountId,
    )}/players/${encodeURIComponent(playerSlotId)}/transfer/`,
    {
      method: "POST",
      body: JSON.stringify({
        direction,
        amount,
        idempotency_key: crypto.randomUUID(),
      }),
    },
    accessToken,
  );
}


export interface MajorAccountCreditReturnResponse {
  detail: string;
  reference: string;
  amount: string;
  major_account_id: string;
  major_account_name: string;
  major_account_balance: string;
  reserve_balance: string;
}

export function returnMajorAccountCredits(
  accessToken: string,
  majorAccountId: string,
  amount: string,
): Promise<MajorAccountCreditReturnResponse> {
  return apiRequest<MajorAccountCreditReturnResponse>(
    `/wallets/major-accounts/${encodeURIComponent(
      majorAccountId,
    )}/return/`,
    {
      method: "POST",
      body: JSON.stringify({
        amount,
        idempotency_key: crypto.randomUUID(),
        description: "Major account return to platform reserve",
      }),
    },
    accessToken,
  );
}

// ==============================
// Windows device endpoints
// ==============================

export function getDeviceStatus(
  deviceCredential: string,
): Promise<DeviceStatus> {
  return apiRequest<DeviceStatus>(
    "/devices/status/",
    {},
    deviceCredential,
    "Device",
  );
}

export function syncPlayerSlots(
  deviceCredential: string,
  detectedCount: number,
): Promise<PlayerSlotsResponse> {
  return apiRequest<PlayerSlotsResponse>(
    "/devices/player-slots/sync/",
    {
      method: "POST",
      body: JSON.stringify({
        detected_count: detectedCount,
      }),
    },
    deviceCredential,
    "Device",
  );
}


 // ==============================
// Platform finance types
// ==============================

export interface PlatformReserve {
  available_balance: string;
  reserved_balance: string;
}

export interface PlatformTransactionEntry {
  wallet_id: string;
  wallet_name: string;
  direction: "DEBIT" | "CREDIT";
  amount: string;
}

export interface PlatformTransaction {
  id: string;
  reference: string;
  transaction_type: string;
  description: string;
  created_by: string;
  created_at: string;
  entries: PlatformTransactionEntry[];
}

export interface PlatformTransactionsResponse {
  transactions: PlatformTransaction[];
}

export interface MajorAccountTransactionsResponse {
  transactions: PlatformTransaction[];
}

export interface PlatformCreditActionResponse {
  detail?: string;
  reference: string;
  transaction_type?: string;
  amount: string;
  reserve_balance?: string;
  major_account_balance?: string;
  major_account?: {
    id: string;
    name: string;
  };
}

// ==============================
// Platform finance endpoints
// ==============================

export function getPlatformReserve(
  accessToken: string,
): Promise<PlatformReserve> {
  return apiRequest<PlatformReserve>(
    "/wallets/platform/reserve/",
    {},
    accessToken,
  );
}

export function getPlatformTransactions(
  accessToken: string,
  limit = 50,
): Promise<PlatformTransactionsResponse> {
  return apiRequest<PlatformTransactionsResponse>(
    `/wallets/platform/transactions/?limit=${encodeURIComponent(
      String(limit),
    )}`,
    {},
    accessToken,
  );
}

export function getMajorAccountTransactions(
  accessToken: string,
  majorAccountId: string,
  limit = 50,
): Promise<MajorAccountTransactionsResponse> {
  return apiRequest<MajorAccountTransactionsResponse>(
    `/wallets/major-accounts/${encodeURIComponent(
      majorAccountId,
    )}/transactions/?limit=${encodeURIComponent(String(limit))}`,
    {},
    accessToken,
  );
}

export function issuePlatformCredits(
  accessToken: string,
  amount: string,
  description: string,
): Promise<PlatformCreditActionResponse> {
  return apiRequest<PlatformCreditActionResponse>(
    "/wallets/platform/issue/",
    {
      method: "POST",
      body: JSON.stringify({
        amount,
        description,
        idempotency_key: crypto.randomUUID(),
      }),
    },
    accessToken,
  );
}

export function allocatePlatformCredits(
  accessToken: string,
  majorAccountId: string,
  amount: string,
  description: string,
): Promise<PlatformCreditActionResponse> {
  return apiRequest<PlatformCreditActionResponse>(
    "/wallets/platform/allocate/",
    {
      method: "POST",
      body: JSON.stringify({
        major_account_id: majorAccountId,
        amount,
        description,
        idempotency_key: crypto.randomUUID(),
      }),
    },
    accessToken,
  );
}


export interface ClaimPCPairingResponse {
  detail: string;
  installation_id: string;
}

export function claimPCPairing(
  accessToken: string,
  pairingCode: string,
): Promise<ClaimPCPairingResponse> {
  return apiRequest<ClaimPCPairingResponse>(
    "/devices/pairing-requests/claim/",
    {
      method: "POST",
      body: JSON.stringify({
        pairing_code: pairingCode.trim().toUpperCase(),
      }),
    },
    accessToken,
  );
}
