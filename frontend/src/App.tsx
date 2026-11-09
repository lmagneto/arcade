

import { useEffect, useState } from "react";

import {
  ArrowDownLeft,
  ArrowUpRight,
  CircleDollarSign,
  Copy,
  KeyRound,
  LogOut,
  Plus,
  RefreshCw,
  ShieldCheck,
  Wallet,
  Building2,
  BookOpen,
  CreditCard,
  LayoutDashboard,
  MonitorSmartphone,
  Users,
} from "lucide-react";

import {
  changePassword,
  refreshAccessToken,
  createPlatformMajorAccount,
  getMajorAccounts,
  getMajorAccountPlayers,
  getPlatformMajorAccounts,
  getPlatformReserve,
  getPlatformTransactions,
  issuePlatformCredits,
  allocatePlatformCredits,
  login,
  resetMajorOwnerPassword,
  transferPlayerCredits,
  type MajorAccount,
  type ManagedPlayer,
  type PlatformMajorAccount,
  type PlatformReserve,
  type PlatformTransaction,
  claimPCPairing,
} from "./api";

function App() {
  // Authentication
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
const [accessToken, setAccessToken] = useState(
  () => localStorage.getItem("arcade_access") || "",
);

const [role, setRole] = useState(
  () => localStorage.getItem("arcade_role") || "",
);

const [activeSection, setActiveSection] = useState(() => {
  const saved = localStorage.getItem("arcade_active_section");
  const savedRole = localStorage.getItem("arcade_role");

  if (saved) return saved;
  return savedRole === "PLATFORM_ADMIN" ? "accounts" : "dashboard";
});

function navigateTo(section: string) {
  setActiveSection(section);
  localStorage.setItem("arcade_active_section", section);
}


const [, setRefreshToken] = useState(
  () => localStorage.getItem("arcade_refresh") || "",
);

const [authInitializing, setAuthInitializing] = useState(true);

  // Mandatory password change
  const [mustChangePassword, setMustChangePassword] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  // General UI state
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);



  // Platform administrator state
  const [platformAccounts, setPlatformAccounts] = useState<
    PlatformMajorAccount[]
  >([]);
  const [accountName, setAccountName] = useState("");
  const [ownerUsername, setOwnerUsername] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [creatingAccount, setCreatingAccount] = useState(false);
  const [resettingAccountId, setResettingAccountId] = useState("");

   
  // Platform finance state
  const [platformReserve, setPlatformReserve] =
    useState<PlatformReserve | null>(null);
  const [platformTransactions, setPlatformTransactions] =
    useState<PlatformTransaction[]>([]);

  const [issueAmount, setIssueAmount] = useState("");
  const [issueDescription, setIssueDescription] = useState("");

  const [allocationAccountId, setAllocationAccountId] = useState("");
  const [allocationAmount, setAllocationAmount] = useState("");
  const [allocationDescription, setAllocationDescription] = useState("");

  const [issuingCredits, setIssuingCredits] = useState(false);
  const [allocatingCredits, setAllocatingCredits] = useState(false);

  // A generated temporary password is displayed only in this session.
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const [temporaryPasswordOwner, setTemporaryPasswordOwner] = useState("");
  const [temporaryPasswordPurpose, setTemporaryPasswordPurpose] =
    useState("");

  // Major-account owner dashboard state
  const [accounts, setAccounts] = useState<MajorAccount[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [players, setPlayers] = useState<ManagedPlayer[]>([]);
  const [selectedPlayerId, setSelectedPlayerId] = useState("");
  const [direction, setDirection] = useState<"CREDIT" | "DEBIT">("CREDIT");
  const [amount, setAmount] = useState("");
  const [transferring, setTransferring] = useState(false);
  const [pairingCode, setPairingCode] = useState("");
const [linkingPC, setLinkingPC] = useState(false);
  const selectedAccount = accounts.find(
    (account) => account.id === selectedAccountId,
  );

  const selectedPlayer = players.find(
    (player) => player.id === selectedPlayerId,
  );

  useEffect(() => {
    document.title = "ARCADE | Account Management";
  }, []);

  // ==========================================
  // Shared helpers
  // ==========================================

  function clearTemporaryPassword() {
    setTemporaryPassword("");
    setTemporaryPasswordOwner("");
    setTemporaryPasswordPurpose("");
  }

  function clearOwnerDashboard() {
    setAccounts([]);
    setSelectedAccountId("");
    setPlayers([]);
    setSelectedPlayerId("");
    setAmount("");
  }

  function clearPlatformDashboard() {
    setPlatformAccounts([]);
    setAccountName("");
    setOwnerUsername("");
    setOwnerEmail("");
    clearTemporaryPassword();
  }


  // ==========================================
  // Load major-account owner dashboard
  // ==========================================

  async function loadAccounts(token: string) {
    const result = await getMajorAccounts(token);
    setAccounts(result.accounts);

    const firstAccount = result.accounts[0];
    setSelectedAccountId(firstAccount?.id ?? "");

    if (firstAccount) {
      await loadPlayers(token, firstAccount.id);
    } else {
      setPlayers([]);
      setSelectedPlayerId("");
    }
  }

  async function loadPlayers(token: string, accountId: string) {
    const result = await getMajorAccountPlayers(token, accountId);

    setPlayers(result.players);

    const firstActive = result.players.find(
      (player) => player.status === "ACTIVE",
    );

    setSelectedPlayerId(firstActive?.id ?? "");
  }

  // ==========================================
  // Load platform administrator dashboard
  // ==========================================

  async function loadPlatformAccounts(token: string) {
    const result = await getPlatformMajorAccounts(token);
    setPlatformAccounts(result.accounts);
  }

   
  async function loadPlatformFinance(token: string) {
    const [reserveResult, transactionResult] = await Promise.all([
      getPlatformReserve(token),
      getPlatformTransactions(token, 50),
    ]);

    

    setPlatformReserve(reserveResult);
    setPlatformTransactions(transactionResult.transactions);
  }

useEffect(() => {
  let cancelled = false;

  async function restoreSession() {
    const savedRefresh = localStorage.getItem("arcade_refresh");
    const savedRole = localStorage.getItem("arcade_role");

    if (!savedRefresh || !savedRole) {
      setAuthInitializing(false);
      return;
    }

    try {
      // Restore the access token.
      const result = await refreshAccessToken(savedRefresh);

      if (cancelled) return;

      localStorage.setItem("arcade_access", result.access);
      setAccessToken(result.access);
      setRefreshToken(savedRefresh);
      setRole(savedRole);

      const passwordChangeRequired =
        localStorage.getItem("arcade_must_change_password") === "true";

      setMustChangePassword(passwordChangeRequired);

      // Do not load dashboards until a required password change is completed.
      if (passwordChangeRequired) {
        return;
      }

      // Restore the correct dashboard according to the saved role.
      if (savedRole === "PLATFORM_ADMIN") {
        await Promise.all([
          loadPlatformAccounts(result.access),
          loadPlatformFinance(result.access),
        ]);
      } else if (savedRole === "MAJOR_OWNER") {
        await loadAccounts(result.access);
      } else {
        throw new Error("Your account role is not recognized.");
      }

    } catch (err) {
      if (!cancelled) {
        console.error("Session restoration failed:", err);

        localStorage.removeItem("arcade_access");
        localStorage.removeItem("arcade_refresh");
        localStorage.removeItem("arcade_role");
        localStorage.removeItem("arcade_must_change_password");

        setAccessToken("");
        setRefreshToken("");
        setRole("");
        setMustChangePassword(false);

        clearOwnerDashboard();
        clearPlatformDashboard();

        setError(true);
        setMessage("Your session could not be restored. Please sign in again.");
      }
    } finally {
      if (!cancelled) {
        setAuthInitializing(false);
      }
    }
  }

  void restoreSession();

  return () => {
    cancelled = true;
  };
}, []);


  // ==========================================
  // Login and role-based routing
  // ==========================================

  async function handleLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setLoading(true);
    setMessage("");
    setError(false);
    clearTemporaryPassword();

    try {
      const result = await login(username.trim(), password);

setAccessToken(result.access);
setRefreshToken(result.refresh);
setRole(result.role);

localStorage.setItem("arcade_access", result.access);
localStorage.setItem("arcade_refresh", result.refresh);
localStorage.setItem("arcade_role", result.role);
localStorage.setItem(
  "arcade_must_change_password",
  String(result.must_change_password),
);

setPassword("");
      // Enforce password change before loading either dashboard.
      if (result.must_change_password) {
        setMustChangePassword(true);
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
        clearOwnerDashboard();
        clearPlatformDashboard();

        setMessage(
          "Change your temporary password before continuing.",
        );
        return;
      }

      setMustChangePassword(false);


      if (result.role === "PLATFORM_ADMIN") {
        clearOwnerDashboard();

        await Promise.all([
          loadPlatformAccounts(result.access),
          loadPlatformFinance(result.access),
        ]);

        setMessage("Platform administrator signed in successfully.");
      } else if (result.role === "MAJOR_OWNER") {
        clearPlatformDashboard();
        await loadAccounts(result.access);
        setMessage("Signed in successfully.");
      } else {
        setAccessToken("");
        setRole("");
        setError(true);
        setMessage(
          "This account does not have access to the account management portal.",
        );
      }


    } catch (err) {
      setAccessToken("");
      setRole("");
      setMustChangePassword(false);
      clearOwnerDashboard();
      clearPlatformDashboard();

      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to sign in.",
      );
    } finally {
      setLoading(false);
    }
  }



  // ==========================================
  // Change temporary password
  // ==========================================

  async function handleChangePassword(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!accessToken || !mustChangePassword) {
      setError(true);
      setMessage("Please sign in again to change your password.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError(true);
      setMessage("The new passwords do not match.");
      return;
    }

    if (newPassword === currentPassword) {
      setError(true);
      setMessage("Choose a password different from your current password.");
      return;
    }

    setChangingPassword(true);
    setMessage("");
    setError(false);

    try {
      await changePassword(accessToken, currentPassword, newPassword);

      setAccessToken("");
      setRole("");
      setMustChangePassword(false);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPassword("");

      clearOwnerDashboard();
      clearPlatformDashboard();

      setMessage(
        "Password changed successfully. Sign in with your new password.",
      );
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to change password.",
      );
    } finally {
      setChangingPassword(false);
    }
  }

  // ==========================================
  // Create major account
  // ==========================================

  async function handleCreateAccount(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!accountName.trim() || !ownerUsername.trim()) {
      setError(true);
      setMessage("Enter an account name and owner username.");
      return;
    }

    setCreatingAccount(true);
    setMessage("");
    setError(false);
    clearTemporaryPassword();

    try {
      const result = await createPlatformMajorAccount(
        accessToken,
        accountName.trim(),
        ownerUsername.trim(),
        ownerEmail.trim(),
      );

      // Show the generated password once, in the current UI session.
      setTemporaryPassword(result.temporary_password);
      setTemporaryPasswordOwner(result.account.owner_username);
      setTemporaryPasswordPurpose("Account created");

      setAccountName("");
      setOwnerUsername("");
      setOwnerEmail("");

      await loadPlatformAccounts(accessToken);

      setMessage(result.detail);
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to create account.",
      );
    } finally {
      setCreatingAccount(false);
    }
  }

  // ==========================================
  // Reset major-owner password
  // ==========================================

  async function handleResetPassword(account: PlatformMajorAccount) {
    const confirmed = window.confirm(
      `Reset the password for ${account.owner_username}? ` +
        "The owner will need to change the new temporary password at next login.",
    );

    if (!confirmed) return;

    setResettingAccountId(account.id);
    setMessage("");
    setError(false);
    clearTemporaryPassword();

    try {
      const result = await resetMajorOwnerPassword(
        accessToken,
        account.id,
      );

      setTemporaryPassword(result.temporary_password);
      setTemporaryPasswordOwner(result.owner_username);
      setTemporaryPasswordPurpose("Password reset");

      setMessage(result.detail);
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to reset password.",
      );
    } finally {
      setResettingAccountId("");
    }
  }

  
  // ==========================================
  // Issue virtual credits to platform reserve
  // ==========================================

  async function handleIssueCredits(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!/^\d+(\.\d{1,2})?$/.test(issueAmount) || Number(issueAmount) <= 0) {
      setError(true);
      setMessage("Enter an amount greater than zero with up to 2 decimal places.");
      return;
    }

    if (!issueDescription.trim()) {
      setError(true);
      setMessage("Enter a description for this issuance.");
      return;
    }

    setIssuingCredits(true);
    setMessage("");
    setError(false);

    let reference = "";

    try {
      const result = await issuePlatformCredits(
        accessToken,
        issueAmount,
        issueDescription.trim(),
      );

      reference = result.reference;
      setIssueAmount("");
      setIssueDescription("");
      setMessage(`Virtual credits issued successfully. Reference: ${reference}`);

      try {
        await Promise.all([
          loadPlatformFinance(accessToken),
          loadPlatformAccounts(accessToken),
        ]);
      } catch {
        setError(true);
        setMessage(
          `Credits were issued successfully (Reference: ${reference}), but refreshing the dashboard failed. Use Refresh to reload the data.`,
        );
      }
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to issue virtual credits.",
      );
    } finally {
      setIssuingCredits(false);
    }
  }

  // ==========================================
  // Allocate reserve credits to a major account
  // ==========================================

  async function handleAllocateCredits(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!allocationAccountId) {
      setError(true);
      setMessage("Select a major account.");
      return;
    }

    if (
      !/^\d+(\.\d{1,2})?$/.test(allocationAmount) ||
      Number(allocationAmount) <= 0
    ) {
      setError(true);
      setMessage("Enter an amount greater than zero with up to 2 decimal places.");
      return;
    }

    if (!allocationDescription.trim()) {
      setError(true);
      setMessage("Enter a description for this allocation.");
      return;
    }

    setAllocatingCredits(true);
    setMessage("");
    setError(false);

    try {
      const result = await allocatePlatformCredits(
        accessToken,
        allocationAccountId,
        allocationAmount,
        allocationDescription.trim(),
      );

      const reference = result.reference;

      setAllocationAmount("");
      setAllocationDescription("");
      setMessage(`Credits allocated successfully. Reference: ${reference}`);

      try {
        await Promise.all([
          loadPlatformFinance(accessToken),
          loadPlatformAccounts(accessToken),
        ]);
      } catch {
        setError(true);
        setMessage(
          `Credits were allocated successfully (Reference: ${reference}), but refreshing the dashboard failed. Use Refresh to reload the data.`,
        );
      }
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to allocate virtual credits.",
      );
    } finally {
      setAllocatingCredits(false);
    }
  }


  // ==========================================
  // Refresh data
  // ==========================================

  
  async function refreshPlatformAccounts() {
    setLoading(true);
    setMessage("");
    setError(false);

    try {
      await Promise.all([
        loadPlatformAccounts(accessToken),
        loadPlatformFinance(accessToken),
      ]);
      setMessage("Platform accounts and finance data refreshed.");
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to refresh platform data.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleAccountChange(accountId: string) {
    setSelectedAccountId(accountId);
    setMessage("");
    setError(false);
    setLoading(true);

    try {
      await loadPlayers(accessToken, accountId);
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Unable to load players.",
      );
    } finally {
      setLoading(false);
    }
  }

async function refreshOwnerData() {
  if (!accessToken) return;

  setLoading(true);
  setMessage("");
  setError(false);

  try {
    const result = await getMajorAccounts(accessToken);

    setAccounts(result.accounts);

    // Preserve the selected account if it still exists.
    const accountStillExists = result.accounts.some(
      (account) => account.id === selectedAccountId,
    );

    const accountToLoad = accountStillExists
      ? selectedAccountId
      : result.accounts[0]?.id ?? "";

    setSelectedAccountId(accountToLoad);

    if (accountToLoad) {
      await loadPlayers(accessToken, accountToLoad);
    } else {
      setPlayers([]);
      setSelectedPlayerId("");
    }

    setMessage("Account details and balances refreshed.");

  } catch (err) {
    setError(true);
    setMessage(
      err instanceof Error ? err.message : "Refresh failed.",
    );
  } finally {
    setLoading(false);
  }
}

  // ==========================================
  // Transfer virtual credits
  // ==========================================

  async function handleTransfer(
    event: React.FormEvent<HTMLFormElement>,
  ) {
    event.preventDefault();

    if (!selectedAccountId || !selectedPlayerId) {
      setError(true);
      setMessage("Select a major account and an active player.");
      return;
    }

    if (!/^\d+(\.\d{1,2})?$/.test(amount) || Number(amount) <= 0) {
      setError(true);
      setMessage(
        "Enter an amount greater than zero with up to 2 decimal places.",
      );
      return;
    }

    setTransferring(true);
    setMessage("");
    setError(false);

    try {
      const result = await transferPlayerCredits(
        accessToken,
        selectedAccountId,
        selectedPlayerId,
        direction,
        amount,
      );

      setMessage(`${result.detail} Reference: ${result.reference}`);
      setAmount("");

      const accountResult = await getMajorAccounts(accessToken);
      setAccounts(accountResult.accounts);
      await loadPlayers(accessToken, selectedAccountId);
    } catch (err) {
      setError(true);
      setMessage(
        err instanceof Error ? err.message : "Transfer failed.",
      );
    } finally {
      setTransferring(false);
    }
  }

async function handleLinkPC(event: React.FormEvent<HTMLFormElement>) {
  event.preventDefault();

  const normalizedCode = pairingCode.trim().toUpperCase();

  if (!/^[A-HJ-NP-Z2-9]{8}$/.test(normalizedCode)) {
    setError(true);
    setMessage("Enter the valid 8-character pairing code shown on the PC.");
    return;
  }

  setLinkingPC(true);
  setMessage("");
  setError(false);

  try {
    const result = await claimPCPairing(accessToken, normalizedCode);
    setPairingCode("");
    setMessage(
      `${result.detail} Installation: ${result.installation_id}`,
    );
  } catch (err) {
    setError(true);
    setMessage(
      err instanceof Error ? err.message : "Unable to link this PC.",
    );
  } finally {
    setLinkingPC(false);
  }
}



  // ==========================================
  // Logout
  // ==========================================
  
function logout() {
  // Remove saved authentication credentials.
  localStorage.removeItem("arcade_access");
  localStorage.removeItem("arcade_refresh");
  localStorage.removeItem("arcade_role");
  localStorage.removeItem("arcade_must_change_password");

  // Clear authentication state.
  setAccessToken("");
  setRefreshToken("");
  setRole("");
  setPassword("");
  setMustChangePassword(false);

  // Clear password-change fields.
  setCurrentPassword("");
  setNewPassword("");
  setConfirmPassword("");

  // Clear dashboard messages and data.
  setMessage("");
  setError(false);
  clearOwnerDashboard();
  clearPlatformDashboard();

  setAuthInitializing(false);
}
  

  // ==========================================
  // Shared brand header
  // ==========================================

function BrandHeader({
  accountName,
  accountType,
  actions,
}: {
  accountName: string;
  accountType: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="topbar dashboard-topbar">
      <div className="brand">
        <div className="brand-mark">A</div>
        <div>
          <strong>{accountName}</strong>
          <span>{accountType}</span>
        </div>
      </div>

      <div className="header-actions">
        {actions}
      </div>
    </header>
  );
}

function DashboardSidebar({
  role,
  activeSection,
  onNavigate,
}: {
  role: string;
  activeSection: string;
  onNavigate: (section: string) => void;
}) {
  const items =
    role === "PLATFORM_ADMIN"
      ? [
          { id: "accounts", label: "Accounts", icon: Building2 },
          { id: "finance", label: "Finance", icon: CreditCard },
          { id: "ledger", label: "Ledger", icon: BookOpen },
        ]
      : [
          { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
          { id: "link-device", label: "Link Device", icon: MonitorSmartphone },
          { id: "players", label: "Players", icon: Users },
          { id: "ledger", label: "Ledger", icon: BookOpen },
        ];

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">A</div>
        <div>
          <strong>ARCADE</strong>
          <span>{role === "PLATFORM_ADMIN" ? "PLATFORM ADMIN" : "MAJOR OWNER"}</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        {items.map((item) => {
          const Icon = item.icon;

          return (
            <button
              key={item.id}
              type="button"
              className={`sidebar-link ${
                activeSection === item.id ? "active" : ""
              }`}
              onClick={() => onNavigate(item.id)}
            >
              <Icon size={18} />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}

  function StatusMessage() {
    if (!message) return null;

    return (
      <p
        role="status"
        className={`connection-message ${error ? "error-message" : ""}`}
      >
        {message}
      </p>
    );
  }

  // ==========================================
  // Temporary-password screen
  // ==========================================

  if (accessToken && mustChangePassword) {
    return (
      <main className="app-shell auth-shell">
        <BrandHeader
          accountName="ARCADE"
          accountType="SECURE ACCOUNT SETUP"/>

        <section className="login-panel">
          <div className="login-icon">
            <ShieldCheck size={28} />
          </div>

          <span className="eyebrow">FIRST-TIME SIGN-IN</span>
          <h1>Change your password</h1>
          <p>
            Choose a new password before accessing ARCADE account management.
          </p>

          <form
            onSubmit={handleChangePassword}
            className="management-form"
          >
            <label className="credential-field">
              Current temporary password
              <input
                type="password"
                value={currentPassword}
                onChange={(event) =>
                  setCurrentPassword(event.target.value)
                }
                autoComplete="current-password"
                required
                disabled={changingPassword}
              />
            </label>

            <label className="credential-field">
              New password
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                autoComplete="new-password"
                minLength={8}
                required
                disabled={changingPassword}
              />
            </label>

            <label className="credential-field">
              Confirm new password
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) =>
                  setConfirmPassword(event.target.value)
                }
                autoComplete="new-password"
                minLength={8}
                required
                disabled={changingPassword}
              />
            </label>

            <StatusMessage />

            <button
              className="primary-button"
              type="submit"
              disabled={
                changingPassword ||
                !currentPassword ||
                !newPassword ||
                !confirmPassword
              }
            >
              {changingPassword ? "Updating..." : "Change password"}
            </button>

            <button
              className="logout-button"
              type="button"
              onClick={logout}
              disabled={changingPassword}
            >
              <LogOut size={17} />
              Sign out
            </button>
          </form>
        </section>

        <footer className="app-footer">
          <span>ARCADE · ACCOUNT MANAGEMENT</span>
          <span>Virtual credits</span>
        </footer>
      </main>
    );
  }

  // ==========================================
  // Login screen
  // ==========================================

  if (!accessToken) {

    if (authInitializing) {
  return (
    <main className="app-shell auth-shell">
      <section className="login-panel">
        <div className="login-icon">
          <ShieldCheck size={28} />
        </div>
        <h1>ARCADE</h1>
        <p>Restoring your secure session...</p>
      </section>
    </main>
  );
}
    return (
      <main className="app-shell auth-shell">
        <BrandHeader
          accountName="ARCADE"
          accountType="VIRTUAL CREDIT MANAGEMENT"/>

        <section className="login-panel">
          <div className="login-icon">
            <Wallet size={28} />
          </div>

          <span className="eyebrow">SECURE ACCOUNT PORTAL</span>
          <h1>Welcome to ARCADE</h1>
          <p>
            Sign in to manage your account and virtual credits.
          </p>

          <form onSubmit={handleLogin} className="management-form">
            <label className="credential-field">
              Username
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
                placeholder="Enter username"
              />
            </label>

            <label className="credential-field">
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
                placeholder="Enter password"
              />
            </label>

            <StatusMessage />

            <button
              className="primary-button"
              type="submit"
              disabled={loading}
            >
              {loading ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </section>

        <footer className="app-footer">
          <span>ARCADE · ACCOUNT MANAGEMENT</span>
          <span>Virtual credits</span>
        </footer>
      </main>
    );
  }

  // ==========================================
  // Platform administrator dashboard
  // ==========================================

if (role === "PLATFORM_ADMIN") {
  return (
    <div className="dashboard-shell">
      <DashboardSidebar
        role="PLATFORM_ADMIN"
        activeSection={activeSection}
        onNavigate={navigateTo}
      />

      <main className="dashboard-main">
         <BrandHeader
          accountName="Platform Administration"
          accountType="PLATFORM ADMIN"
          actions={
            <div className="header-actions">
              <button
                className="icon-button"
                type="button"
                onClick={refreshPlatformAccounts}
                disabled={loading || creatingAccount || !!resettingAccountId}
                aria-label="Refresh major accounts"
                title="Refresh major accounts"
              >
                <RefreshCw size={18} />
              </button>

              <button
                className="logout-button"
                type="button"
                onClick={logout}
              >
                <LogOut size={17} />
                Sign out
              </button>
            </div>
          }
        />

        <section className="welcome-section">
          <div>
            <span className="eyebrow">PLATFORM CONTROL</span>
            <h1>Major-account management</h1>
            <p>Create accounts and manage account-owner access.</p>
          </div>

          <span className="virtual-badge">
            <ShieldCheck size={15} />
            Administrator
          </span>
        </section>

        <section className="summary-grid">
          <article className="summary-card">
            <Wallet size={21} />
            <span>Total major accounts</span>
            <strong>{platformAccounts.length}</strong>
          </article>

          <article className="summary-card">
            <ShieldCheck size={21} />
            <span>Active accounts</span>
            <strong>
              {platformAccounts.filter(
                (account) => account.status === "ACTIVE",
              ).length}
            </strong>
          </article>

          <article className="summary-card">
            <CircleDollarSign size={21} />
            <span>Account balances</span>
            <strong>
              {platformAccounts
                .reduce(
                  (total, account) =>
                    total + Number(account.wallet_balance || 0),
                  0,
                )
                .toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
            </strong>
          </article>
        </section>

         {activeSection === "finance" && (
             <>
             <section className="summary-grid">
              <article className="summary-card">
                <Wallet size={21} />
            <span>Platform reserve — available</span>
            <strong>
              {Number(platformReserve?.available_balance ?? 0).toLocaleString(
                undefined,
                { minimumFractionDigits: 2, maximumFractionDigits: 2 },
              )}
            </strong>
          </article>

          <article className="summary-card">
            <CircleDollarSign size={21} />
            <span>Platform reserve — reserved</span>
            <strong>
              {Number(platformReserve?.reserved_balance ?? 0).toLocaleString(
                undefined,
                { minimumFractionDigits: 2, maximumFractionDigits: 2 },
              )}
            </strong>
          </article>

          <article className="summary-card">
            <ShieldCheck size={21} />
            <span>Recent transactions loaded</span>
            <strong>{platformTransactions.length}</strong>
          </article>
        </section>
 

        {/* Platform finance actions */}
        <section className="management-layout">
          <div className="management-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">CREDIT ISSUANCE</span>
                <h2>Issue virtual credits</h2>
              </div>
              <CircleDollarSign size={20} />
            </div>

            <p>
              Add virtual credits to the platform reserve. This action does
              not involve real money.
            </p>

            <form
              onSubmit={handleIssueCredits}
              className="management-form"
            >
              <label className="credential-field">
                Amount
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={issueAmount}
                  onChange={(event) => setIssueAmount(event.target.value)}
                  placeholder="e.g. 10000.00"
                  required
                  disabled={issuingCredits || loading}
                />
              </label>

              <label className="credential-field">
                Description
                <input
                  value={issueDescription}
                  onChange={(event) => setIssueDescription(event.target.value)}
                  maxLength={255}
                  placeholder="Reason for issuing credits"
                  required
                  disabled={issuingCredits || loading}
                />
              </label>

              <button
                className="primary-button"
                type="submit"
                disabled={
                  issuingCredits ||
                  allocatingCredits ||
                  loading ||
                  !issueAmount ||
                  !issueDescription.trim()
                }
              >
                {issuingCredits ? "Issuing..." : "Issue credits"}
              </button>
            </form>
          </div>

          <aside className="management-panel transfer-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">CREDIT ALLOCATION</span>
                <h2>Allocate to major account</h2>
              </div>
              <ArrowDownLeft size={20} />
            </div>

            <p>
              Move credits from the platform reserve to an active major
              account.
            </p>

            <form
              onSubmit={handleAllocateCredits}
              className="management-form"
            >
              <label className="credential-field">
                Major account
                <select
                  value={allocationAccountId}
                  onChange={(event) =>
                    setAllocationAccountId(event.target.value)
                  }
                  required
                  disabled={allocatingCredits || loading}
                >
                  <option value="">Select a major account</option>
                  {platformAccounts
                    .filter((account) => account.status === "ACTIVE")
                    .map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.name} — {account.owner_username}
                      </option>
                    ))}
                </select>
              </label>

              <label className="credential-field">
                Amount
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={allocationAmount}
                  onChange={(event) =>
                    setAllocationAmount(event.target.value)
                  }
                  placeholder="e.g. 500.00"
                  required
                  disabled={allocatingCredits || loading}
                />
              </label>

              <label className="credential-field">
                Description
                <input
                  value={allocationDescription}
                  onChange={(event) =>
                    setAllocationDescription(event.target.value)
                  }
                  maxLength={255}
                  placeholder="Reason for allocation"
                  required
                  disabled={allocatingCredits || loading}
                />
              </label>

              <button
                className="primary-button"
                type="submit"
                disabled={
                  allocatingCredits ||
                  issuingCredits ||
                  loading ||
                  !allocationAccountId ||
                  !allocationAmount ||
                  !allocationDescription.trim()
                }
              >
                {allocatingCredits ? "Allocating..." : "Allocate credits"}
              </button>


            </form>
          </aside>
        </section>
  </>
)}


{activeSection === "ledger" && (
  <>
        {/* Recent transaction history */}
        <section className="management-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">AUDIT TRAIL</span>
              <h2>Recent transactions</h2>
            </div>

            <span className="slot-count">
              Latest {platformTransactions.length}
            </span>
          </div>

          <p>
            Review recent virtual-credit transactions, their references,
            timestamps, and ledger entries.
          </p>

          {platformTransactions.length === 0 ? (
            <p>No transactions are available yet.</p>
          ) : (
            <div className="transaction-table-wrap">
              <table className="transaction-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Created by</th>
                    <th>Reference</th>
                    <th>Ledger entries</th>
                  </tr>
                </thead>

                <tbody>
                  {platformTransactions.map((item) => (
                    <tr key={item.id}>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                      <td>{item.transaction_type}</td>
                      <td>{item.description}</td>
                      <td>{item.created_by}</td>
                      <td className="transaction-reference">
                        {item.reference}
                      </td>
                      <td>
                        {item.entries.map((entry, index) => (
                          <div key={`${item.id}-${index}`}>
                            <strong>{entry.direction}</strong>{" "}
                            {entry.wallet_name}:{" "}
                            {Number(entry.amount).toLocaleString(undefined, {
                              minimumFractionDigits: 2,
                              maximumFractionDigits: 2,
                            })}
                          </div>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
  </>
)}
{/*
        
      <section className="management-panel pc-link-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">DEVICE MANAGEMENT</span>
            <h2>Link PC</h2>
          </div>
        </div>

        <p>
          Open ARCADE on the Windows PC and enter the pairing code
          displayed on its screen below.
        </p>

        <form onSubmit={handleLinkPC} className="connect-form">
          <label htmlFor="pc-pairing-code">
            8-character pairing code
          </label>

          <input
            id="pc-pairing-code"
            type="text"
            value={pairingCode}
            onChange={(event) =>
              setPairingCode(
                event.target.value.toUpperCase().slice(0, 8),
              )
            }
            placeholder="ABCD2345"
            maxLength={8}
            autoComplete="off"
            required
            disabled={linkingPC}
          />

          <button
            className="primary-button"
            type="submit"
            disabled={linkingPC || pairingCode.length !== 8}
          >
            {linkingPC ? "Linking PC..." : "Approve and link PC"}
          </button>
        </form>
      </section>
*/}

{activeSection === "accounts" && (
  <>
        <section className="management-layout">
          <div className="management-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">ACCOUNT DIRECTORY</span>
                <h2>Major accounts</h2>
              </div>
              <span className="slot-count">
                {platformAccounts.length} accounts
              </span>
            </div>

            <StatusMessage />

            {platformAccounts.length === 0 ? (
              <p>No major accounts found. Create one using the form.</p>
            ) : (
              <div className="account-list">
                {platformAccounts.map((account) => (
                  <article className="account-row" key={account.id}>
                    <span className="account-icon">
                      <Wallet size={20} />
                    </span>

                    <span className="account-details">
                      <strong>{account.name}</strong>
                      <small>
                        Owner: {account.owner_username}
                      </small>
                      <small>{account.owner_email || "No email recorded"}</small>
                      <small>
                        Status: {account.status}
                      </small>
                    </span>

                    <span className="account-balance">
                      {account.wallet_balance}
                    </span>

                    <button
                      className="icon-button"
                      type="button"
                      title={`Reset password for ${account.owner_username}`}
                      aria-label={`Reset password for ${account.owner_username}`}
                      disabled={
                        loading ||
                        creatingAccount ||
                        !!resettingAccountId
                      }
                      onClick={() => handleResetPassword(account)}
                    >
                      {resettingAccountId === account.id ? (
                        <RefreshCw size={17} />
                      ) : (
                        <KeyRound size={17} />
                      )}
                    </button>
                  </article>
                ))}
              </div>
            )}
          </div>

          <aside className="management-panel transfer-panel">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">NEW ACCOUNT</span>
                <h2>Create major account</h2>
              </div>
              <Plus size={20} />
            </div>

            <p>
              A new owner will receive a generated temporary password and
              must change it at first login.
            </p>

            <form
              onSubmit={handleCreateAccount}
              className="management-form"
            >
              <label className="credential-field">
                Major-account name
                <input
                  value={accountName}
                  onChange={(event) => setAccountName(event.target.value)}
                  required
                  maxLength={150}
                  placeholder="e.g. Account One"
                  disabled={creatingAccount}
                />
              </label>

              <label className="credential-field">
                Owner username
                <input
                  value={ownerUsername}
                  onChange={(event) => setOwnerUsername(event.target.value)}
                  required
                  maxLength={150}
                  autoComplete="off"
                  placeholder="Choose a unique username"
                  disabled={creatingAccount}
                />
              </label>

              <label className="credential-field">
                Owner email (optional)
                <input
                  type="email"
                  value={ownerEmail}
                  onChange={(event) => setOwnerEmail(event.target.value)}
                  maxLength={254}
                  placeholder="owner@example.com"
                  disabled={creatingAccount}
                />
              </label>

              <button
                className="primary-button"
                type="submit"
                disabled={
                  creatingAccount ||
                  !accountName.trim() ||
                  !ownerUsername.trim()
                }
              >
                {creatingAccount
                  ? "Creating account..."
                  : "Create major account"}
              </button>
            </form>
          </aside>
        </section>
        </>
        )}

        {temporaryPassword && (
          <section className="management-panel" aria-live="polite">
            <div className="panel-heading">
              <div>
                <span className="eyebrow">
                  {temporaryPasswordPurpose.toUpperCase()}
                </span>
                <h2>Temporary password</h2>
              </div>
              <KeyRound size={20} />
            </div>

            <p>
              This password is displayed in this session only. Deliver it
              securely to the owner. They must change it when signing in.
            </p>

            <p>
              <strong>Owner:</strong> {temporaryPasswordOwner}
            </p>

            <div className="credential-field">
              <label htmlFor="temporary-password-value">
                Generated password
              </label>
              <input
                id="temporary-password-value"
                type="text"
                readOnly
                value={temporaryPassword}
                autoComplete="off"
              />
            </div>

            <div className="header-actions">
              <button
                className="primary-button"
                type="button"
                onClick={() => {
                  void navigator.clipboard
                    .writeText(temporaryPassword)
                    .then(() => {
                      setMessage("Temporary password copied.");
                      setError(false);
                    })
                    .catch(() => {
                      setError(true);
                      setMessage(
                        "Copy failed. Select the password and copy it manually.",
                      );
                    });
                }}
              >
                <Copy size={16} />
                Copy password
              </button>

              <button
                className="logout-button"
                type="button"
                onClick={clearTemporaryPassword}
              >
                Hide password
              </button>
            </div>
          </section>
        )}

        <footer className="app-footer">
          <span>ARCADE</span>
          <span>POWERED BY MDMIT 2026.</span>
        </footer>
           </main>
    </div>
    );
  }

  // ==========================================
  // Major-account owner dashboard
  // ==========================================

  if (role !== "MAJOR_OWNER") {
    return (
      <main className="app-shell auth-shell">
        <section className="login-panel">
          <h1>Access unavailable</h1>
          <p>This account cannot access this dashboard.</p>
          <button className="primary-button" onClick={logout} type="button">
            Return to sign in
          </button>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
       <BrandHeader
        accountName={selectedAccount?.name || "Major Account"}
        accountType="MAJOR ACCOUNT OWNER"
        actions={
          <div className="header-actions">
            <button
              className="icon-button"
              type="button"
              onClick={refreshOwnerData}
              disabled={loading || transferring}
              aria-label="Refresh balances"
              title="Refresh balances"
            >
              <RefreshCw size={18} />
            </button>

            <button
              className="logout-button"
              type="button"
              onClick={logout}
            >
              <LogOut size={17} />
              Sign out
            </button>
          </div>
        }
      />

      

      <section className="summary-grid">

        
           <section className="management-panel pc-link-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">DEVICE MANAGEMENT</span>
            <h2>Link PC</h2>
          </div>
        </div>

        <p>
          Open ARCADE on the Windows PC and enter the pairing code
          displayed on its screen below.
        </p>

        <form onSubmit={handleLinkPC} className="connect-form">
          <label htmlFor="pc-pairing-code">
            8-character pairing code
          </label>

          <input
            id="pc-pairing-code"
            type="text"
            value={pairingCode}
            onChange={(event) =>
              setPairingCode(
                event.target.value.toUpperCase().slice(0, 8),
              )
            }
            placeholder="ABCD2345"
            maxLength={8}
            autoComplete="off"
            required
            disabled={linkingPC}
          />

          <button
            className="primary-button"
            type="submit"
            disabled={linkingPC || pairingCode.length !== 8}
          >
            {linkingPC ? "Linking PC..." : "Approve and link PC"}
          </button>
        </form>
      </section>
      </section>

  

      <section className="management-layout">
        <div className="management-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">YOUR ACCOUNTS</span>
              <h2>Select major account</h2>
            </div>
          </div>

          {accounts.length === 0 ? (
            <p>No major accounts are assigned to this user.</p>
          ) : (
            <div className="account-list">
              {accounts.map((account) => (
                <button
                  key={account.id}
                  type="button"
                  className={`account-row ${
                    selectedAccountId === account.id ? "selected" : ""
                  }`}
                  onClick={() => handleAccountChange(account.id)}
                  disabled={loading || transferring}
                >
                  <span className="account-icon">
                    <Wallet size={20} />
                  </span>

                  <span className="account-details">
                    <strong>{account.name}</strong>
                    <small>{account.status}</small>
                  </span>

                  <span className="account-balance">
                    {account.wallet_balance}
                  </span>
                </button>
              ))}
            </div>
          )}

          <div className="panel-heading players-heading">
            <div>
              <span className="eyebrow">PLAYER WALLETS</span>
              <h2>Select a player</h2>
            </div>
            <span className="slot-count">{players.length} slots</span>
          </div>

          <div className="player-list">
            {players.map((player) => (
              <button
                key={player.id}
                type="button"
                className={`player-row ${
                  selectedPlayerId === player.id ? "selected" : ""
                }`}
                onClick={() => setSelectedPlayerId(player.id)}
                disabled={
                  player.status !== "ACTIVE" || loading || transferring
                }
              >
                <span className="player-avatar">{player.slot_number}</span>

                <span className="player-details">
                  <strong>{player.display_name}</strong>
                  <small>{player.status}</small>
                </span>

                <span className="player-balance">
                  <CircleDollarSign size={14} />
                  {player.wallet_balance}
                </span>
              </button>
            ))}
          </div>
        </div>

        <aside className="management-panel transfer-panel">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">WALLET TRANSFER</span>
              <h2>Manage credits</h2>
            </div>
          </div>

          <div className="selected-player-card">
            <span className="player-avatar large">
              {selectedPlayer?.slot_number ?? "—"}
            </span>

            <div>
              <span>Selected player</span>
              <strong>
                {selectedPlayer?.display_name ?? "Select a player"}
              </strong>
              <small>
                Balance: {selectedPlayer?.wallet_balance ?? "—"}
              </small>
            </div>
          </div>

          <form onSubmit={handleTransfer} className="management-form">
            <label className="credential-field">
              Transfer direction
              <select
                value={direction}
                onChange={(event) =>
                  setDirection(event.target.value as "CREDIT" | "DEBIT")
                }
                disabled={transferring}
              >
                <option value="CREDIT">
                  Credit player from major account
                </option>
                <option value="DEBIT">
                  Return credits to major account
                </option>
              </select>
            </label>

            <label className="credential-field">
              Amount
              <input
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                placeholder="e.g. 100.00"
                required
                disabled={transferring}
              />
            </label>

            <div className="transfer-note">
              {direction === "CREDIT" ? (
                <>
                  <ArrowDownLeft size={17} />
                  <span>
                    Credits move from your account to the selected player.
                  </span>
                </>
              ) : (
                <>
                  <ArrowUpRight size={17} />
                  <span>
                    Credits move from the selected player back to your account.
                  </span>
                </>
              )}
            </div>

            <StatusMessage />

            <button
              className="primary-button"
              type="submit"
              disabled={
                transferring ||
                loading ||
                !selectedAccountId ||
                !selectedPlayerId ||
                selectedPlayer?.status !== "ACTIVE"
              }
            >
              {transferring
                ? "Processing transfer..."
                : direction === "CREDIT"
                  ? "Credit player"
                  : "Return credits"}
            </button>
          </form>

{/*       
<form
  onSubmit={handleReturnCredits}
 className="management-form"
>
  <div className="panel-heading">
    <div>
      <span className="eyebrow">RESERVE RETURN</span>
      <h2>Return credits to platform</h2>
    </div>
  </div>

  <p>
    Move available virtual credits from your major account
    back to the platform reserve.
  </p>

  <label className="credential-field">
    Amount to return
    <input
      type="number"
      inputMode="decimal"
      min="0.01"
      step="0.01"
      value={returnAmount}
      onChange={(event) => setReturnAmount(event.target.value)}
      placeholder="e.g. 100.00"
      required
      disabled={returningCredits || loading || transferring}
    />
  </label>

  <button
    className="primary-button"
    type="submit"
    disabled={
      returningCredits ||
      transferring ||
      loading ||
      !selectedAccountId
    }
  >
    {returningCredits
      ? "Returning credits..."
      : "Return to platform reserve"}
  </button>
</form>
*/}

          
        </aside>
      </section>



      <footer className="app-footer">
        <span>ARCADE </span>
        <span>POWERED BY MDMIT 2026</span>
      </footer>
    </main>
  );
}

export default App;

/* Platform finance transaction history */
