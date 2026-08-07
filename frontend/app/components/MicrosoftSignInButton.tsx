"use client";

import { useEffect, useState } from "react";
import { getMicrosoftAuthStatus, microsoftLoginUrl } from "@/lib/api";
import { btnSecondary } from "./ui";

// "Sign in with Microsoft" / "Sign up with Microsoft" button, shared by the login and register
// pages. Checks on mount whether the backend actually has an Azure app configured (Section 6's
// notification channels use the same "hide/disable rather than show a button that just fails"
// posture for unconfigured integrations) - renders nothing at all while that check is in
// flight or if it comes back false, rather than a button that would just 503.
export default function MicrosoftSignInButton({ label }: { label: string }) {
  // null = still checking, true/false = known.
  const [configured, setConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const status = await getMicrosoftAuthStatus();
        setConfigured(status.configured);
      } catch {
        // Backend unreachable or errored - fail closed (no button) rather than offering a
        // sign-in path that's unlikely to work anyway.
        setConfigured(false);
      }
    })();
  }, []);

  if (!configured) return null;

  return (
    <>
      <div className="flex items-center gap-3 text-xs text-muted">
        <span className="h-px flex-1 bg-rule" />
        or
        <span className="h-px flex-1 bg-rule" />
      </div>
      <button
        type="button"
        onClick={() => {
          // Full-page navigation, not a fetch - see lib/api.ts's microsoftLoginUrl().
          window.location.href = microsoftLoginUrl();
        }}
        className={`${btnSecondary} w-full`}
      >
        <MicrosoftLogo />
        {label}
      </button>
    </>
  );
}

// The four-colour Microsoft "windows" logo (official brand mark), used the same way any app's
// "Sign in with Microsoft" button does per Microsoft's own identity branding guidelines.
function MicrosoftLogo() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
      <rect x="1" y="1" width="6.5" height="6.5" fill="#F25022" />
      <rect x="8.5" y="1" width="6.5" height="6.5" fill="#7FBA00" />
      <rect x="1" y="8.5" width="6.5" height="6.5" fill="#00A4EF" />
      <rect x="8.5" y="8.5" width="6.5" height="6.5" fill="#FFB900" />
    </svg>
  );
}
