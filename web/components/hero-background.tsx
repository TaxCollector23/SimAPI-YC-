/**
 * Hero backdrop — a static, monochrome hairline grid that fades to pure
 * black. No canvas, no animation, no colored glow. Just a faint blueprint
 * texture behind the headline, in keeping with the flat near-black system.
 */
export function HeroBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="hero-grid absolute inset-0" />
    </div>
  );
}
