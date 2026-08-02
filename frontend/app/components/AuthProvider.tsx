"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getCurrentUser, logout as apiLogout, User } from "@/lib/api";

const PUBLIC_PATHS = new Set(["/login", "/register"]);

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

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
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await refresh();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (loading) return;

    const isPublicPath = PUBLIC_PATHS.has(pathname);
    if (!user && !isPublicPath) {
      router.replace("/login");
      return;
    }
    if (user && isPublicPath) {
      router.replace("/");
      return;
    }
    if (user && pathname.startsWith("/settings") && user.role !== "admin") {
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
  const ready = !loading && (user || isPublicPath) && !blockedForNonAdmin;

  return (
    <AuthContext.Provider value={{ user, loading, refresh, logout }}>
      {ready ? (
        children
      ) : (
        <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">Loading…</div>
      )}
    </AuthContext.Provider>
  );
}
