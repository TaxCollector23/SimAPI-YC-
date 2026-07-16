export const site = {
  name: "SimAPI",
  domain: "sim-api.vercel.app",
  url: "https://sim-api.vercel.app",
  tagline: "CI checks for engineering simulations.",
  description:
    "Validate CFD, FEA, robotics, and multiphysics simulation outputs with deterministic physics checks, statistical analysis, and AI review before they reach production, design review, or ML pipelines.",
  github: "https://github.com/TaxCollector23/SimAPI-YC-",
  nav: [
    { label: "Platform", href: "/platform" },
    { label: "Pricing", href: "/pricing" },
    { label: "Docs", href: "/docs" },
    { label: "Changelog", href: "/changelog" },
    { label: "Blog", href: "/blog" },
    { label: "Dashboard", href: "/dashboard" },
  ],
  footerGroups: [
    { title: "Product", links: [
      { label: "Platform", href: "/platform" },
      { label: "Pricing", href: "/pricing" },
      { label: "Dashboard", href: "/dashboard" },
      { label: "Changelog", href: "/changelog" },
      { label: "Status", href: "/status" },
    ] },
    { title: "Developers", links: [
      { label: "Documentation", href: "/docs" },
      { label: "API reference", href: "https://simapidocs.github.io" },
      { label: "GitHub", href: "https://github.com/TaxCollector23/SimAPI-YC-" },
      { label: "npm", href: "https://www.npmjs.com/package/simapi-cli" },
    ] },
    { title: "Company", links: [
      { label: "Blog", href: "/blog" },
      { label: "FAQ", href: "/faq" },
      { label: "Security", href: "/security" },
      { label: "Privacy", href: "/privacy" },
      { label: "Terms", href: "/terms" },
    ] },
  ],
} as const;
