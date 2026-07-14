"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu, X, ArrowUpRight } from "lucide-react";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";
import { Logo } from "./logo";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled ? "border-b border-white/[0.06] bg-ink-950/70 backdrop-blur-xl" : "",
      )}
    >
      <nav className="container-tight flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2.5" aria-label="SimAPI home">
          <Logo className="h-9" />
          <span className="text-[17px] font-semibold tracking-tight text-white">SimAPI</span>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {site.nav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-full px-3.5 py-1.5 text-sm text-white/60 transition-colors hover:text-white"
            >
              {item.label}
            </Link>
          ))}
          <a
            href={site.github}
            target="_blank"
            rel="noreferrer"
            className="rounded-full px-3.5 py-1.5 text-sm text-white/60 transition-colors hover:text-white"
          >
            GitHub
          </a>
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <Link href="/dashboard" className="btn-primary">
            Get API Key
          </Link>
        </div>

        <button
          className="rounded-lg p-2 text-white/80 md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </nav>

      {open && (
        <div className="border-t border-white/[0.06] bg-ink-950/95 px-6 py-4 md:hidden">
          <div className="flex flex-col gap-1">
            {site.nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-2.5 text-sm text-white/70 hover:bg-white/5 hover:text-white"
              >
                {item.label}
              </Link>
            ))}
            <a
              href={site.github}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1 rounded-lg px-3 py-2.5 text-sm text-white/70 hover:bg-white/5 hover:text-white"
            >
              GitHub <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
            <Link href="/dashboard" onClick={() => setOpen(false)} className="btn-primary mt-2">
              Get API Key
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
