import { MewahMark } from "./Brand";

// Corporate footer band, closing the page the way the source site does. Kept to facts the app can
// actually stand behind - what the data is and how often it refreshes - rather than invented
// contact details or links to pages that don't exist here.
export default function SiteFooter() {
  return (
    <footer className="mt-10 border-t-[3px] border-brand bg-[#3f3e42] text-white/70">
      <div className="mx-auto flex w-full max-w-[1240px] flex-wrap items-start justify-between gap-6 px-5 py-7">
        <div className="flex items-start gap-3">
          {/* No colour class: the mark is a bitmap now, and its white areas are transparent, so
              it picks up the footer's dark background by itself. */}
          <MewahMark className="h-8 w-8 shrink-0" />
          <div>
            <p className="text-sm font-bold text-white">Vessel Monitoring Dashboard</p>
            <p className="mt-1 max-w-md text-xs leading-relaxed">
              Unified vessel and container tracking across multiple carrier and AIS sources, with
              movement history, exception alerts and scheduled reporting.
            </p>
          </div>
        </div>

        <div className="text-xs leading-relaxed">
          <p className="font-bold uppercase tracking-wider text-white/90">Data</p>
          <p className="mt-1">Tracking data refreshes automatically</p>
          <p>Times are shown in your local timezone</p>
        </div>
      </div>

      <div className="border-t border-white/10">
        <div className="mx-auto w-full max-w-[1240px] px-5 py-3 text-[11px]">
          Internal operations system — for authorised users only.
        </div>
      </div>
    </footer>
  );
}
