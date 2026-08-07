import type { Metadata } from "next";
import AppChrome from "./components/AppChrome";
import AuthProvider from "./components/AuthProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vessel Monitoring Dashboard",
  description: "Unified vessel tracking, history, and status monitoring",
};

// Root layout shared by every route (Next.js App Router convention). Wrapping everything in
// AuthProvider here - rather than per-page - is what makes the whole app require login by
// default; AppChrome inside it supplies the shared header, navigation and footer, so each page
// only needs to worry about its own content.
//
// No webfont is loaded: the house style follows mewahgroup.com's own Arial/Verdana stack (set in
// globals.css), which also means no font request on first paint.
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          <AppChrome>{children}</AppChrome>
        </AuthProvider>
      </body>
    </html>
  );
}
