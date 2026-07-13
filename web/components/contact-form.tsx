"use client";

import { useState } from "react";
import { Check, Loader2 } from "lucide-react";

export function ContactForm() {
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    // Demo: simulate submission. Wire to a real endpoint in production.
    setTimeout(() => setState("sent"), 900);
  }

  if (state === "sent") {
    return (
      <div className="flex min-h-[360px] flex-col items-center justify-center rounded-2xl border border-white/[0.07] bg-ink-900/50 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-pass/15">
          <Check className="h-6 w-6 text-pass" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-white">Thanks — message received</h3>
        <p className="mt-2 max-w-sm text-sm text-white/50">
          We&apos;ll get back to you within one business day with next steps and an API key.
        </p>
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-4 rounded-2xl border border-white/[0.07] bg-ink-900/50 p-6"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" name="name" placeholder="Ada Lovelace" required />
        <Field label="Work email" name="email" type="email" placeholder="ada@company.com" required />
      </div>
      <Field label="Company" name="company" placeholder="Acme Aerospace" />
      <div>
        <label className="mb-1.5 block text-xs font-medium text-white/55">What are you simulating?</label>
        <select
          name="domain"
          className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white/80 outline-none focus:border-accent-blue/50"
        >
          {["Aerospace / CFD", "Structural / FEA", "Robotics", "Automotive", "Energy", "Scientific computing", "Other"].map(
            (o) => (
              <option key={o} className="bg-ink-900">
                {o}
              </option>
            ),
          )}
        </select>
      </div>
      <div>
        <label className="mb-1.5 block text-xs font-medium text-white/55">Message</label>
        <textarea
          name="message"
          rows={4}
          placeholder="Tell us about your validation workflow…"
          className="w-full resize-none rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white/80 outline-none focus:border-accent-blue/50"
        />
      </div>
      <button type="submit" className="btn-accent w-full" disabled={state === "sending"}>
        {state === "sending" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {state === "sending" ? "Sending…" : "Request API key"}
      </button>
    </form>
  );
}

function Field({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium text-white/55">{label}</label>
      <input
        {...props}
        className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white/80 outline-none placeholder:text-white/25 focus:border-accent-blue/50"
      />
    </div>
  );
}
