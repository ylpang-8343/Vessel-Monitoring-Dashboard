import Image from "next/image";

// The Mewah house mark.
//
// `public/mewah-mark.png` is the real artwork, not a redrawing: it's the circular "M" lifted out
// of Mewah's own logo file (mewahgroup.com's image/BG_MewahLogo.jpg), squared up around the
// circle and with the white background converted to transparency so the same file works on the
// white header and the dark footer.
//
// The mark is only 66x66 in that source file, so it is slightly soft when scaled up much beyond
// the sizes used here. To swap in a higher-resolution copy, just overwrite
// `frontend/public/mewah-mark.png` - nothing in the code needs to change.

/** The circular "M" monogram on its own. `className` sizes it; the width/height below are only
 * the intrinsic size Next.js needs, and any `h-*`/`w-*` class overrides them. */
export function MewahMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <Image
      src="/mewah-mark.png"
      // Decorative: every place this appears, the word "Mewah" is already next to it in text.
      alt=""
      width={64}
      height={64}
      className={className}
      priority
    />
  );
}

/** Mark + "Mewah" wordmark, as they appear together in the site header. */
export function MewahLogo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 text-brand ${className}`}>
      <MewahMark />
      <span className="text-[26px] font-bold leading-none tracking-tight">Mewah</span>
    </span>
  );
}
