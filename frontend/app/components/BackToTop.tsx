"use client";

import { useEffect, useState } from "react";

// Floating "back to top" button, one of the source site's own fixtures (it hides the control
// until you've scrolled 100px, then fades it in bottom-right - reproduced here in React rather
// than the jQuery the original uses).
export default function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 100);
    onScroll(); // Handle a page that loads already scrolled (e.g. a restored position).
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <button
      type="button"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      aria-label="Back to top"
      // Kept mounted and faded rather than unmounted, so it animates in and out instead of
      // popping. `pointer-events-none` while hidden stops it swallowing clicks.
      className={`fixed bottom-6 right-6 z-40 flex h-11 w-11 items-center justify-center rounded-sm bg-brand text-white shadow-lg transition-opacity hover:bg-brand-dark ${
        visible ? "opacity-100" : "pointer-events-none opacity-0"
      }`}
    >
      <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden>
        <path
          d="M12 19 L12 6 M5 12 L12 5 L19 12"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  );
}
