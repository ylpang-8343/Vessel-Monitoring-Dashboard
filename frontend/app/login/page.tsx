"use client";

import { useState } from "react";
import Link from "next/link";
import { ApiError, login } from "@/lib/api";
import { useAuth } from "@/app/components/AuthProvider";

export default function LoginPage() {
  const { refresh } = useAuth();
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
