import type { ExceptionKind } from "@/lib/api";

// Styling for Phase 6's exception kinds (Section 7). "Delayed" is red, which finally uses the
// colour Section 6.E's table assigns to it and Figure 4's map legend shows - until Phase 6 gave
// the app a real reported ETA to measure against, nothing could legitimately be marked delayed.
//
// Same single-source-of-truth shape as StatusDot's COLOURS map, so exception styling stays
// consistent wherever it appears (the Exceptions page, the vessel history panel, the dashboard).
const STYLES: Record<ExceptionKind, { label: string; dot: string; chipBg: string; chipText: string }> = {
  delayed: {
    label: "Delayed",
    dot: "bg-red-500",
    chipBg: "bg-red-50 dark:bg-red-950",
    chipText: "text-red-700 dark:text-red-300",
  },
  long_port_stay: {
    label: "Long Port Stay",
    dot: "bg-amber-500",
    chipBg: "bg-amber-50 dark:bg-amber-950",
    chipText: "text-amber-700 dark:text-amber-300",
  },
  unexpected_port_call: {
    label: "Unexpected Port Call",
    dot: "bg-purple-500",
    chipBg: "bg-purple-50 dark:bg-purple-950",
    chipText: "text-purple-700 dark:text-purple-300",
  },
};

/** Look up the label/colours for an exception kind. Exported so the Exceptions page's filter
 * chips can render the same dot colours as the rows they filter to. */
export function exceptionMeta(kind: ExceptionKind) {
  return STYLES[kind];
}

/** Coloured pill naming one exception kind. */
export default function ExceptionBadge({ kind }: { kind: ExceptionKind }) {
  const meta = exceptionMeta(kind);
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${meta.chipBg} ${meta.chipText}`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${meta.dot}`} />
      {meta.label}
    </span>
  );
}
