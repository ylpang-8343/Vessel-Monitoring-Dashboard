"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MewahLogo } from "./Brand";
import UserMenu from "./UserMenu";
import { useAuth } from "./AuthProvider";

// Site header, laid out like mewahgroup.com's: a white band carrying the logo on the left, then a
// full-bleed orange navigation bar beneath it whose items are separated by thin white rules and
// invert to white-on-orange when hovered.
//
// Navigation lives here, once, instead of being repeated in each page's own header bar - which is
// how it used to work, with every page listing a slightly different subset of links (the map page
// only ever offered "Back to Dashboard", so getting from the map to Reports meant two clicks).

interface NavItem {
  href: string;
  label: string;
  /** Admin-only items are hidden outright for regular users, matching how /settings is gated. */
  adminOnly?: boolean;
  /** Extra path prefixes that also belong to this section. A vessel's own history page lives at
   * /vessels/[imo] but is reached from - and belongs to - the Dashboard, so the nav should say so
   * rather than highlighting nothing at all while you're on it. */
  alsoMatches?: string[];
}

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", alsoMatches: ["/vessels"] },
  { href: "/containers", label: "Containers" },
  { href: "/map", label: "Map View" },
  { href: "/exceptions", label: "Exceptions" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings", adminOnly: true },
];

export default function SiteHeader() {
  const { user } = useAuth();
  const pathname = usePathname();

  const items = NAV_ITEMS.filter((item) => !item.adminOnly || user?.role === "admin");

  return (
    <header>
      <div className="bg-white">
        <div className="mx-auto flex w-full max-w-[1240px] flex-wrap items-center justify-between gap-4 px-5 py-4">
          <Link href="/" className="flex items-center gap-4" aria-label="Vessel Monitoring Dashboard home">
            <MewahLogo />
            {/* Vertical rule + system name, so the branding reads as "Mewah's dashboard" rather
                than implying the whole site is the corporate one. */}
            <span className="hidden h-9 w-px bg-rule sm:block" aria-hidden />
            <span className="hidden text-xs font-bold uppercase leading-tight tracking-[0.12em] text-muted sm:block">
              Vessel Monitoring
              <br />
              Dashboard
            </span>
          </Link>
          <UserMenu />
        </div>
      </div>

      <nav className="bg-brand">
        <div className="mx-auto w-full max-w-[1240px] px-5">
          <ul className="flex flex-wrap">
            {items.map((item) => {
              // Exact match for the dashboard (every path starts with "/"), prefix match
              // elsewhere so a booking's own history page still highlights Containers.
              const active =
                (item.href === "/" ? pathname === "/" : pathname.startsWith(item.href)) ||
                (item.alsoMatches?.some((prefix) => pathname.startsWith(prefix)) ?? false);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`block border-r border-white/40 px-5 py-2.5 text-sm font-bold transition-colors ${
                      active ? "bg-white text-brand" : "text-white hover:bg-white hover:text-brand"
                    }`}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      </nav>
    </header>
  );
}
