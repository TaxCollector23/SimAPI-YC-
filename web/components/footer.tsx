import Link from "next/link";
import { site } from "@/lib/site";
import { Logo } from "./logo";

export function Footer() {
  return (
    <footer className="relative border-t border-white/[0.06] py-16">
      <div className="container-tight">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div className="max-w-xs">
            <Link href="/" className="flex items-center gap-2.5">
              <Logo className="h-8" />
              <span className="text-[15px] font-semibold tracking-tight text-white">SimAPI</span>
            </Link>
            <p className="mt-4 text-sm leading-relaxed text-white/45">
              The validation layer for engineering simulations. Catch bad runs before they reach production.
            </p>
            <Link href="/status" className="mt-5 inline-flex items-center gap-2 text-xs text-white/40 hover:text-white">
              <span className="h-2 w-2 rounded-full bg-pass animate-pulse-soft" />
              All systems operational
            </Link>
          </div>

          {site.footerGroups.map((group) => (
            <nav key={group.title} aria-label={group.title}>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white/40">{group.title}</h3>
              <ul className="mt-4 space-y-2.5">
                {group.links.map((link) => (
                  <li key={link.label}>
                    <Link href={link.href} className="text-sm text-white/55 transition-colors hover:text-white">
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-start justify-between gap-4 border-t border-white/[0.06] pt-8 text-xs text-white/40 sm:flex-row sm:items-center">
          <p>© {new Date().getFullYear()} SimAPI. The CI/CD layer for engineering simulations.</p>
          <p className="font-mono">sim-api.vercel.app</p>
        </div>
      </div>
    </footer>
  );
}
