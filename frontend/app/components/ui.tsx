// Shared presentation primitives for the Mewah-styled UI.
//
// Every page used to hand-roll its own card, header bar, tab strip and filter pills, which meant
// nine copies of the same Tailwind class strings that had to be kept in step by hand. These are
// the house-style building blocks instead: squared-off white panels ruled with silver hairlines,
// an orange accent tick on each panel heading, and orange (never navy) as the one accent colour -
// matching mewahgroup.com's own visual language.

import type { ReactNode } from "react";

/* ------------------------------------------------------------------ *
 * Class-string constants
 *
 * Exported as plain strings rather than wrapper components so they can be dropped onto a native
 * <button>/<input> that already has its own props (type, disabled, onChange…) without every call
 * site having to forward them through.
 * ------------------------------------------------------------------ */

const BUTTON_BASE =
  "inline-flex items-center justify-center gap-2 rounded-sm px-4 py-2 text-sm font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-50";

/** Solid orange - the main action on a screen (Add, Save, Export). */
export const btnPrimary = `${BUTTON_BASE} bg-brand text-white hover:bg-brand-dark`;

/** Outlined - secondary actions that sit next to a primary one. Hover picks up the brand colour
 * the same way the source site's navigation does. */
export const btnSecondary = `${BUTTON_BASE} border border-rule-strong bg-white text-body hover:border-brand hover:text-brand`;

/** Destructive actions (Remove). Kept red rather than orange - orange is the house colour and
 * would stop reading as a warning. */
export const btnDanger = `${BUTTON_BASE} border border-red-300 bg-white text-red-700 hover:bg-red-50`;

/** Same three variants at the smaller size used inside table rows and panel headers. */
const BUTTON_SMALL_BASE =
  "inline-flex items-center justify-center gap-1.5 rounded-sm px-3 py-1.5 text-xs font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-50";
export const btnPrimarySm = `${BUTTON_SMALL_BASE} bg-brand text-white hover:bg-brand-dark`;
export const btnSecondarySm = `${BUTTON_SMALL_BASE} border border-rule-strong bg-white text-body hover:border-brand hover:text-brand`;
export const btnDangerSm = `${BUTTON_SMALL_BASE} border border-red-300 bg-white text-red-700 hover:bg-red-50`;

/** Text input / select / textarea.
 *
 * Deliberately carries no width: a caller appending `w-72` to a string that already said `w-full`
 * would not win - Tailwind emits both rules and the stylesheet's own order decides, not the order
 * the classes appear in the attribute. Every call site states the width it wants. */
export const inputClass =
  "rounded-sm border border-rule-strong bg-white px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand";

/** The small uppercase caption above a form field, matching the source site's label styling. */
export const labelClass = "block text-[11px] font-bold uppercase tracking-wider text-muted";

/** Table header row - squared off and ruled in silver, as on the source site's own tables. */
export const theadClass =
  "border-y border-rule bg-[#faf9f8] text-left text-[11px] font-bold uppercase tracking-wider text-muted";

/* ------------------------------------------------------------------ *
 * Layout
 * ------------------------------------------------------------------ */

/** The centred fixed-width column everything sits in. The source site centres a 1280px table
 * with side gutters; this is the same idea in a responsive form. */
export function Shell({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-[1240px] px-5 ${className}`}>{children}</div>;
}

/**
 * The orange banner at the top of each page, standing in for the source site's hero photo strip:
 * same position and full-bleed width, but a gradient wash and a wave silhouette rather than
 * photography, since an operations screen needs the table below it to stay above the fold.
 */
export function PageBanner({
  title,
  subtitle,
  actions,
  children,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  /** Optional content below the title row - the dashboard uses this for its stat tiles. */
  children?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden bg-gradient-to-r from-brand to-[#e2760a]">
      {/* Soft highlight in the top-right corner so the band reads as lit rather than flat. */}
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_82%_-30%,rgba(255,255,255,0.32),transparent_58%)]"
        aria-hidden
      />
      <Shell className="relative pb-9 pt-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-[26px] font-bold leading-tight text-white">{title}</h1>
            {subtitle && <p className="mt-1 text-sm text-white/85">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
        {children}
      </Shell>
      {/* Wave silhouette along the bottom edge - the one nautical flourish in the design, and
          what makes the banner feel like a hero image rather than a coloured rectangle. */}
      <svg
        className="block h-6 w-full text-canvas"
        viewBox="0 0 1440 40"
        preserveAspectRatio="none"
        aria-hidden
      >
        <path d="M0 40 L0 22 C 240 2 480 40 720 24 C 960 8 1200 34 1440 16 L1440 40 Z" fill="currentColor" />
      </svg>
    </div>
  );
}

/** A squared white content panel with a silver hairline border. */
export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`border border-rule bg-white ${className}`}>{children}</section>;
}

/** A panel's heading strip: orange accent tick, title, optional subtitle and right-hand actions. */
export function PanelHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-5 py-3">
      <div className="flex items-center gap-3">
        <span className="h-6 w-[3px] shrink-0 bg-brand" aria-hidden />
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** The muted strip at the bottom of a panel carrying counts and caveats. */
export function PanelFooter({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule bg-[#faf9f8] px-5 py-3 text-xs text-muted">
      {children}
    </div>
  );
}

/**
 * Explanatory strip for the "here's what this screen does and doesn't do" notes. Orange-tinted
 * with a solid left rule, so it reads as part of the house style rather than as a warning - these
 * notes are context, not alarms.
 */
export function NoticeBar({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-rule border-l-[3px] border-l-brand bg-brand-tint px-5 py-3 text-xs leading-relaxed text-body">
      {children}
    </div>
  );
}

/** Inline error strip, used where a fetch failed but the rest of the page still renders. */
export function ErrorBar({ children }: { children: ReactNode }) {
  return (
    <div className="border-b border-red-200 border-l-[3px] border-l-red-500 bg-red-50 px-5 py-2 text-sm text-red-700">
      {children}
    </div>
  );
}

/** Centred "loading…" / "nothing here" message inside a panel body. */
export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="px-5 py-16 text-center text-sm text-muted">{children}</div>;
}

/* ------------------------------------------------------------------ *
 * Controls
 * ------------------------------------------------------------------ */

/**
 * A tab in a panel's tab strip (Active/Archived, and Settings' three sections). The active tab is
 * marked with a thick orange underline - the same "orange marks where you are" cue the site
 * navigation uses.
 */
export function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`-mb-px border-b-[3px] px-4 py-2.5 text-sm font-bold transition-colors ${
        active
          ? "border-brand text-brand"
          : "border-transparent text-muted hover:border-rule-strong hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

/**
 * A filter pill (the dashboard's status chips, the exceptions page's kind chips). Squared rather
 * than fully rounded, to sit with the rest of the blocky house style.
 */
export function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center rounded-sm border px-3 py-1.5 text-xs font-bold transition-colors ${
        active
          ? "border-brand bg-brand text-white"
          : "border-rule-strong bg-white text-body hover:border-brand hover:text-brand"
      }`}
    >
      {children}
    </button>
  );
}

/** One label/value pair in a page's summary grid. */
export function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <p className={labelClass}>{label}</p>
      <div className="mt-1.5 text-sm font-bold text-ink">{children}</div>
    </div>
  );
}
