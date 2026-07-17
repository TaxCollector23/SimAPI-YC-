"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu, X, ArrowUpRight, ChevronDown } from "lucide-react";
import { site } from "@/lib/site";
import { cn } from "@/lib/utils";
import { Logo } from "./logo";

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [openMobileGroup, setOpenMobileGroup] = useState<string | null>(null);

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
          {site.navGroups.map((group) => (
            <div
              key={group.label}
              className="relative"
              onMouseEnter={() => setOpenGroup(group.label)}
              onMouseLeave={() => setOpenGroup((g) => (g === group.label ? null : g))}
            >
              <button
                className={cn(
                  "flex items-center gap-1 rounded-full px-3.5 py-1.5 text-sm text-white/60 transition-colors hover:text-white",
                  openGroup === group.label && "text-white",
                )}
              >
                {group.label}
                <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", openGroup === group.label && "rotate-180")} />
              </button>
              {openGroup === group.label && (
                <div className="absolute left-1/2 top-full w-72 -translate-x-1/2 pt-2">
                  <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-ink-950/95 p-2 shadow-2xl backdrop-blur-xl">
                    {group.items.map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        target={item.external ? "_blank" : undefined}
                        rel={item.external ? "noreferrer" : undefined}
                        className="flex flex-col gap-0.5 rounded-xl px-3.5 py-2.5 transition-colors hover:bg-white/[0.05]"
                      >
                        <span className="flex items-center gap-1 text-sm text-white">
                          {item.label}
                          {item.external && <ArrowUpRight className="h-3 w-3 text-white/30" />}
                        </span>
                        <span className="text-xs text-white/40">{item.desc}</span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
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
        <div className="max-h-[calc(100vh-4rem)] overflow-y-auto border-t border-white/[0.06] bg-ink-950/95 px-6 py-4 md:hidden">
          <div className="flex flex-col gap-1">
            {site.navGroups.map((group) => (
              <div key={group.label}>
                <button
                  onClick={() => setOpenMobileGroup((g) => (g === group.label ? null : group.label))}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium text-white/80"
                >
                  {group.label}
                  <ChevronDown className={cn("h-4 w-4 transition-transform", openMobileGroup === group.label && "rotate-180")} />
                </button>
                {openMobileGroup === group.label && (
                  <div className="ml-2 flex flex-col gap-0.5 border-l border-white/[0.08] pl-3">
                    {group.items.map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setOpen(false)}
                        target={item.external ? "_blank" : undefined}
                        rel={item.external ? "noreferrer" : undefined}
                        className="flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-white/60 hover:bg-white/5 hover:text-white"
                      >
                        {item.label}
                        {item.external && <ArrowUpRight className="h-3 w-3 text-white/30" />}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <Link href="/dashboard" onClick={() => setOpen(false)} className="btn-primary mt-2">
              Get API Key
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}
