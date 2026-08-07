"use client";

import { useState } from "react";
import Link from "next/link";
import { ApiError, register } from "@/lib/api";
import { useAuth } from "@/app/components/AuthProvider";
import MicrosoftSignInButton from "@/app/components/MicrosoftSignInButton";
import { Panel, PanelHeader, btnPrimary, inputClass, labelClass } from "@/app/components/ui";

// Mirrors validate_password_complexity() in backend/app/schemas.py - kept as a separate literal
// list (not shared code) so the checklist can render live per-rule feedback as the user types.
// The backend re-validates the same rules regardless; this is purely for UX.
const RULES: { label: string; test: (v: string) => boolean }[] = [
  { label: "At least 8 characters", test: (v) => v.length >= 8 },
  { label: "One uppercase letter", test: (v) => /[A-Z]/.test(v) },
  { label: "One lowercase letter", test: (v) => /[a-z]/.test(v) },
  { label: "One symbol", test: (v) => /[^A-Za-z0-9]/.test(v) },
];

// The other public route (see AuthProvider's PUBLIC_PATHS). Always results in a `user`-role
// account server-side - there's no "become admin" option here or anywhere in the UI, by design
// (see README.md's "First-time setup" section).
export default function RegisterPage() {
  const { refresh } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const failedRules = RULES.filter((rule) => !rule.test(password));
  // Don't show a "doesn't match" error before the user has typed anything into confirm yet.
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword;

  /** Client-side re-check of the same rules the checklist already shows live, so submitting
   * with an invalid password gives an immediate error instead of a round-trip to the backend
   * (which would reject it anyway via UserRegister's validators). */
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (failedRules.length > 0) {
      setError("Password does not meet the requirements below");
      return;
    }
    if (password !== confirmPassword) {
      setError("Password and confirmation do not match");
      return;
    }

    setSubmitting(true);
    try {
      await register({ email, password, confirm_password: confirmPassword });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to register");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-5 py-12">
      <Panel>
        <PanelHeader title="Create Account" subtitle="Vessel Monitoring Dashboard" />

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-6">
          <div>
            <label className={labelClass}>Email</label>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={`${inputClass} mt-1 w-full`}
            />
          </div>

          <div>
            <label className={labelClass}>Password</label>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={`${inputClass} mt-1 w-full`}
            />
            <ul className="mt-2 space-y-0.5 text-xs">
              {RULES.map((rule) => {
                const met = rule.test(password);
                return (
                  <li key={rule.label} className={met ? "font-bold text-green-700" : "text-muted"}>
                    {met ? "✓" : "○"} {rule.label}
                  </li>
                );
              })}
            </ul>
          </div>

          <div>
            <label className={labelClass}>Confirm Password</label>
            <input
              required
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className={`${inputClass} mt-1 w-full`}
            />
            {!passwordsMatch && <p className="mt-1 text-xs text-red-600">Passwords do not match</p>}
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button type="submit" disabled={submitting} className={`${btnPrimary} w-full`}>
            {submitting ? "Creating account…" : "Register"}
          </button>

          <MicrosoftSignInButton label="Sign up with Microsoft" />

          <p className="text-center text-sm text-muted">
            Already have an account?{" "}
            <Link href="/login" className="font-bold text-brand hover:underline">
              Log in
            </Link>
          </p>
        </form>
      </Panel>
    </div>
  );
}
