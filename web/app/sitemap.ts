import type { MetadataRoute } from "next";
import { site } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const routes = ["", "/platform", "/benchmark", "/pricing", "/changelog", "/roadmap", "/status", "/security", "/blog", "/faq", "/docs", "/dashboard", "/privacy", "/terms"];
  const now = new Date();
  return routes.map((path) => ({
    url: `${site.url}${path}`,
    lastModified: now,
    changeFrequency: "weekly",
    priority: path === "" ? 1 : 0.7,
  }));
}
