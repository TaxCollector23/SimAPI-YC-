"use client";

import { useEffect, useRef } from "react";

/**
 * Animated "validation graph": drifting simulation nodes connected by faint
 * edges, with occasional pulses traveling along edges (data being validated).
 * Canvas-based, capped DPR, pauses when offscreen, respects reduced-motion.
 */
export function HeroBackground() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const parent = canvas.parentElement;
    if (!parent) return;

    // Typed non-null aliases: TS control-flow narrowing is not carried into the
    // nested closures below, so we bind explicit non-null references here.
    const cvs: HTMLCanvasElement = canvas;
    const context: CanvasRenderingContext2D = ctx;

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    type Node = { x: number; y: number; vx: number; vy: number; r: number };
    let nodes: Node[] = [];

    function resize() {
      const rect = parent!.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      cvs.width = w * dpr;
      cvs.height = h * dpr;
      cvs.style.width = `${w}px`;
      cvs.style.height = `${h}px`;
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      const count = Math.min(56, Math.floor((w * h) / 22000));
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * w,
        y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.22,
        vy: (Math.random() - 0.5) * 0.22,
        r: Math.random() * 1.6 + 0.8,
      }));
    }

    let t = 0;
    function frame() {
      t += 0.006;
      context.clearRect(0, 0, w, h);

      // edges
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        a.x += a.vx;
        a.y += a.vy;
        if (a.x < 0 || a.x > w) a.vx *= -1;
        if (a.y < 0 || a.y > h) a.vy *= -1;
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d = Math.hypot(dx, dy);
          if (d < 140) {
            const alpha = (1 - d / 140) * 0.16;
            context.strokeStyle = `rgba(120,160,255,${alpha})`;
            context.lineWidth = 1;
            context.beginPath();
            context.moveTo(a.x, a.y);
            context.lineTo(b.x, b.y);
            context.stroke();

            // traveling pulse
            const phase = (t * 40 + i * 7) % 100;
            if (phase < 100) {
              const p = phase / 100;
              const px = a.x + (b.x - a.x) * p;
              const py = a.y + (b.y - a.y) * p;
              context.fillStyle = `rgba(34,211,238,${alpha * 3})`;
              context.beginPath();
              context.arc(px, py, 1.2, 0, Math.PI * 2);
              context.fill();
            }
          }
        }
      }

      // nodes
      for (const n of nodes) {
        const glow = 0.5 + 0.5 * Math.sin(t * 6 + n.x * 0.01);
        context.fillStyle = `rgba(180,205,255,${0.35 + glow * 0.35})`;
        context.beginPath();
        context.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        context.fill();
      }

      raf = requestAnimationFrame(frame);
    }

    resize();
    window.addEventListener("resize", resize);
    if (reduce) {
      frame(); // draw one static frame
      cancelAnimationFrame(raf);
    } else {
      frame();
    }

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute inset-0 grid-bg opacity-60" />
      <canvas ref={ref} className="absolute inset-0 opacity-70" aria-hidden="true" />
      <div className="absolute inset-x-0 top-0 h-[520px] bg-radial-fade" />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-ink-950" />
    </div>
  );
}
