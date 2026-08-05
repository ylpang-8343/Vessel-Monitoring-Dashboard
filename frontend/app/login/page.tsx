"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ApiError, login } from "@/lib/api";
import { useAuth } from "@/app/components/AuthProvider";
import MicrosoftSignInButton from "@/app/components/MicrosoftSignInButton";

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
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="bg-[#0b3d5c] px-6 py-4">
          <h1 className="text-lg font-semibold text-white">Vessel Monitoring Dashboard</h1>
          <p className="text-xs text-white/70">Log in to continue</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 bg-white px-6 py-6 dark:bg-zinc-900">
          {oauthError && <p className="text-sm text-red-600">{oauthError}</p>}

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
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642] disabled:opacity-50"
          >
            {submitting ? "Logging in…" : "Log In"}
          </button>

          <MicrosoftSignInButton label="Sign in with Microsoft" />

          <p className="text-center text-sm text-zinc-500">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="font-medium text-[#0b3d5c] underline dark:text-blue-400">
              Register
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
