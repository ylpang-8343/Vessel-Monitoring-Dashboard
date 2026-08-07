"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ApiError, login } from "@/lib/api";
import { useAuth } from "@/app/components/AuthProvider";
import MicrosoftSignInButton from "@/app/components/MicrosoftSignInButton";
import { Panel, PanelHeader, btnPrimary, inputClass, labelClass } from "@/app/components/ui";

// One of the two public routes (see AuthProvider's PUBLIC_PATHS). Wrapped in Suspense because
// LoginForm below calls useSearchParams(), which this Next.js version requires a Suspense
// boundary for on a full page load (search params aren't known at build time) - see
// frontend/AGENTS.md's warning about this version's breaking changes from what you may expect.
export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

// On success, `refresh()` updates the global auth context, which triggers AuthProvider's own
// redirect away from here (rather than this component navigating directly) - keeps the "where
// do I go after login" logic in one place.
function LoginForm() {
  const { refresh } = useAuth();
  const searchParams = useSearchParams();
  // Set by a failed "Sign in with Microsoft" round trip (backend routers/auth.py's callback
  // redirects here with ?error=... on any failure) - a full-page redirect, so this can't be
  // surfaced any other way than reading it back out of the URL on load.
  const oauthError = searchParams.get("error");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      await refresh();
    } catch (err) {
      // Deliberately generic on the backend side too (see routers/auth.py) - doesn't reveal
      // whether the email exists or the password was wrong.
      setError(err instanceof ApiError ? err.message : "Failed to log in");
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-5 py-12">
      <Panel>
        <PanelHeader title="Sign In" subtitle="Vessel Monitoring Dashboard" />

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-6">
          {oauthError && <p className="text-sm text-red-600">{oauthError}</p>}

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
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button type="submit" disabled={submitting} className={`${btnPrimary} w-full`}>
            {submitting ? "Logging in…" : "Log In"}
          </button>

          <MicrosoftSignInButton label="Sign in with Microsoft" />

          <p className="text-center text-sm text-muted">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="font-bold text-brand hover:underline">
              Register
            </Link>
          </p>
        </form>
      </Panel>
    </div>
  );
}
