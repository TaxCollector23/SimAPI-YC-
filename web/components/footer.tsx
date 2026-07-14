import Link from "next/link";
import { site } from "@/lib/site";
import { Logo } from "./logo";

const pages = [
  { label: "Home", href: "/" },
  { label: "Dashboard", href: "/dashboard" },
  { label: "Run a validation in the web", href: "/dashboard" },
  { label: "Documentation", href: "/docs" },
  { label: "GitHub", href: site.github },
];

export function Footer() {
  return (
    <footer className="relative border-t border-white/[0.06] py-16">
      <div className="container-tight">
        <div className="flex flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <Link href="/" className="flex items-center gap-2.5">
              <Logo className="h-8" />
              <span className="text-[15px] font-semibold tracking-tight text-white">SimAPI</span>
            </Link>
            <div className="mt-5 flex items-center gap-2 text-xs text-white/40">
              <span className="h-2 w-2 rounded-full bg-pass animate-pulse-soft" />
              All systems operational
            </div>
          </div>

          <nav aria-label="Pages">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-white/40">Pages</h3>
            <ul className="mt-4 grid grid-cols-2 gap-x-10 gap-y-2.5">
              {pages.map((link) => (
                <li key={link.label}>
                  <Link
                    href={link.href}
                    className="text-sm text-white/55 transition-colors hover:text-white"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <div className="mt-14 flex flex-col items-start justify-between gap-4 border-t border-white/[0.06] pt-8 text-xs text-white/40 sm:flex-row sm:items-center">
          <p>© {new Date().getFullYear()} SimAPI.</p>
          <div className="flex gap-5">
            <Link href="/privacy" className="hover:text-white">Privacy</Link>
            <Link href="/terms" className="hover:text-white">Terms</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
