"use client";

import { useAuth } from "./AuthProvider";

// Small "email + Log out" control shown in every page header (dashboard, vessel history, map,
// settings) once logged in. Renders nothing while `user` is null/loading, since every page that
// uses this is itself gated behind auth (see AuthProvider) so a logged-out flash would be
// contradictory anyway.
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
