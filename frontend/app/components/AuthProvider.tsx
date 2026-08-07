"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCurrentUser, logout as apiLogout, User } from "@/lib/api";

// The only two routes reachable without being logged in. Every other route (dashboard, vessel
// history, map, settings) requires an authenticated session - "whole app requires login".
const PUBLIC_PATHS = new Set(["/login", "/register"]);

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  /** Re-fetch the current user from the backend and update context state. Called after
   * login/register, and by Settings → Users when the logged-in user demotes themselves (their
   * own role just changed, so the global auth state needs to catch up immediately). */
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** Access the current user/loading state and auth actions from any client component - must be
 * used inside the AuthProvider wrapping the whole app (see app/layout.tsx). */
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

// Wraps the whole app (app/layout.tsx). Resolves who's logged in on mount, then enforces the
// three access rules below on every navigation: logged-out users get sent to /login, logged-in
// users get sent away from /login /register, and non-admins get sent away from /settings.
export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    try {
      const current = await getCurrentUser();
      setUser(current);
    } catch {
      // getCurrentUser() rejects with a 401 ApiError when there's no valid session - that's
      // the normal "not logged in" case, not an error worth surfacing.
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  // Resolve auth state once on initial mount.
  useEffect(() => {
    void (async () => {
      await refresh();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redirect logic, re-evaluated on every user/pathname change (i.e. every navigation and
  // every login/logout/role change).
  useEffect(() => {
    if (loading) return;

    const isPublicPath = PUBLIC_PATHS.has(pathname);
    if (!user && !isPublicPath) {
      router.replace("/login");
      return;
    }
    if (user && isPublicPath) {
      // Already logged in but sitting on /login or /register - bounce to the dashboard
      // instead of showing the form again.
      router.replace("/");
      return;
    }
    if (user && pathname.startsWith("/settings") && user.role !== "admin") {
      // Settings is admin-only (Section 3.9); Map View and everything else just needs login.
      router.replace("/");
    }
  }, [user, loading, pathname, router]);

  async function logout() {
    await apiLogout();
    setUser(null);
    router.replace("/login");
  }

  const isPublicPath = PUBLIC_PATHS.has(pathname);
  const blockedForNonAdmin = !!user && pathname.startsWith("/settings") && user.role !== "admin";
  // Gate rendering `children` until we know for certain the current route is allowed - without
  // this, a protected page would flash its real content for one render before the redirect
  // effect above has a chance to run.
  const ready = !loading && (user || isPublicPath) && !blockedForNonAdmin;

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {ready ? (
        children
      ) : (
        <div className="flex flex-1 items-center justify-center text-sm text-muted">Loading…</div>
      )}
    </AuthContext.Provider>
  );
}
