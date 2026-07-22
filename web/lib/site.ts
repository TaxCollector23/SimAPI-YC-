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
    { label: "Benchmarks", href: "/benchmark" },
    { label: "Pricing", href: "/pricing" },
    { label: "Docs", href: "/docs" },
    { label: "Changelog", href: "/changelog" },
    { label: "Blog", href: "/blog" },
    { label: "Dashboard", href: "/dashboard" },
  ],
  navGroups: [
    {
      label: "Product",
      items: [
        { label: "Dashboard", href: "/dashboard", desc: "Access your API keys, usage analytics, and playground." },
        { label: "Platform", href: "/platform", desc: "The validation engine, AI orchestrator, and pre-flight checks." },
        { label: "Enterprise Workflows", href: "/enterprise-workflows", desc: "Best practices for production integration." },
        { label: "Use Cases", href: "/use-cases", desc: "Real-world impact from aerospace to semiconductors." },
        { label: "Benchmarks", href: "/benchmark", desc: "Full methodology, dataset, and honest limitations." },
        { label: "Pricing", href: "/pricing", desc: "Plans and API quotas." },
      ],
    },
    {
      label: "Developers",
      items: [
        { label: "Documentation", href: "/docs", desc: "Quick start, API reference, CLI." },
        { label: "API reference", href: "https://simapidocs.github.io", desc: "Full endpoint docs.", external: true },
        { label: "GitHub", href: "https://github.com/TaxCollector23/SimAPI-YC-", desc: "Source, issues, and PRs.", external: true },
        { label: "npm — simapi-cli", href: "https://www.npmjs.com/package/simapi-cli", desc: "`npm install -g simapi-cli`", external: true },
      ],
    },
    {
      label: "Company",
      items: [
        { label: "Blog", href: "/blog", desc: "The SimAPI Journal." },
        { label: "FAQ", href: "/faq", desc: "Common questions." },
        { label: "Changelog", href: "/changelog", desc: "Every release, honestly described." },
        { label: "Roadmap", href: "/roadmap", desc: "Shipped, in progress, and planned." },
        { label: "Status", href: "/status", desc: "Live system status." },
        { label: "Security", href: "/security", desc: "How we handle keys and data." },
      ],
    },
  ] satisfies { label: string; items: { label: string; href: string; desc: string; external?: boolean }[] }[],
  footerGroups: [
    { title: "Product", links: [
      { label: "Platform", href: "/platform" },
      { label: "Benchmarks", href: "/benchmark" },
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
      { label: "Roadmap", href: "/roadmap" },
      { label: "Security", href: "/security" },
      { label: "Privacy", href: "/privacy" },
      { label: "Terms", href: "/terms" },
    ] },
  ],
} as const;
