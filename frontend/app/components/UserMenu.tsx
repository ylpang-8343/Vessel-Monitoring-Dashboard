"use client";

import { useAuth } from "./AuthProvider";
import { btnSecondarySm } from "./ui";

// "email + Log out" control in the site header's white band. It used to be repeated inside every
// page's own coloured header bar; now it appears once, in the one place the header exists.
// Renders nothing while `user` is null/loading - every page that shows the header is itself gated
// behind auth (see AuthProvider), so a logged-out flash would be contradictory anyway.
export default function UserMenu() {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="text-right leading-tight">
        <span className="block font-bold text-ink">{user.email}</span>
        {/* Role is worth showing: it decides whether Settings appears in the nav at all, so an
            admin who can't see the link knows to look at which account they're signed in as. */}
        <span className="block uppercase tracking-wider text-muted">{user.role}</span>
      </span>
      <button onClick={() => logout()} className={btnSecondarySm}>
        Log out
      </button>
    </div>
  );
}
