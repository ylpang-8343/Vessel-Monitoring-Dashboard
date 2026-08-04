"use client";

import { useState } from "react";
import Link from "next/link";
import { ApiError, register } from "@/lib/api";
import { useAuth } from "@/app/components/AuthProvider";

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
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="bg-[#0b3d5c] px-6 py-4">
          <h1 className="text-lg font-semibold text-white">Vessel Monitoring Dashboard</h1>
          <p className="text-xs text-white/70">Create an account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 bg-white px-6 py-6 dark:bg-zinc-900">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Email</label>
            <input
              required
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Password</label>
            <input
              required
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
            <ul className="mt-2 space-y-0.5 text-xs">
              {RULES.map((rule) => {
                const met = rule.test(password);
                return (
                  <li key={rule.label} className={met ? "text-green-600" : "text-zinc-400"}>
                    {met ? "✓" : "○"} {rule.label}
                  </li>
                );
              })}
            </ul>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Confirm Password
            </label>
            <input
              required
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
            {!passwordsMatch && <p className="mt-1 text-xs text-red-600">Passwords do not match</p>}
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642] disabled:opacity-50"
          >
            {submitting ? "Creating account…" : "Register"}
          </button>

          <p className="text-center text-sm text-zinc-500">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-[#0b3d5c] underline dark:text-blue-400">
              Log in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
