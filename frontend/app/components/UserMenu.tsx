"use client";

import { useAuth } from "./AuthProvider";

export default function UserMenu() {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <div className="flex items-center gap-2 text-xs text-white/80">
      <span>{user.email}</span>
      <button onClick={() => logout()} className="rounded-md bg-white/10 px-2.5 py-1.5 font-medium hover:bg-white/20">
        Log out
      </button>
    </div>
  );
}
