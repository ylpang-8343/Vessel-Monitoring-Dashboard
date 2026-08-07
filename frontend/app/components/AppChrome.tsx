"use client";

import { usePathname } from "next/navigation";
import BackToTop from "./BackToTop";
import SiteFooter from "./SiteFooter";
import SiteHeader from "./SiteHeader";
import { MewahLogo } from "./Brand";

// Wraps every page in the site chrome, so no page has to build its own header or repeat the
// navigation. Rendered inside AuthProvider (see app/layout.tsx), which means it only ever mounts
// once the current route is known to be allowed.

/** Login and register get a reduced shell: the logo and the orange rule, but no navigation bar -
 * there is nothing to navigate to while logged out, and a full menu of links that all bounce
 * straight back to /login would be worse than no menu. */
const BARE_PATHS = new Set(["/login", "/register"]);

export default function AppChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (BARE_PATHS.has(pathname)) {
    return (
      <>
        <div className="border-b-[3px] border-brand bg-white">
          <div className="mx-auto w-full max-w-[1240px] px-5 py-4">
            <MewahLogo />
          </div>
        </div>
        <main className="flex flex-1 flex-col">{children}</main>
        <SiteFooter />
      </>
    );
  }

  return (
    <>
      <SiteHeader />
      <main className="flex flex-1 flex-col">{children}</main>
      <SiteFooter />
      <BackToTop />
    </>
  );
}
