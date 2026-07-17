import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * SIMAPI_SITE_MODE lets us deploy this exact codebase to separate Vercel
 * projects (simapiplayground.vercel.app, simapistatus.vercel.app,
 * simapiquicklinks.vercel.app) that always show the same UI as the main
 * site and always stay in sync — they're the same deployment, not a
 * hand-maintained copy that can drift. Each project just sets a different
 * env var and gets its root path rewritten to the matching internal route.
 */
const SITE_MODE_ROUTES: Record<string, string> = {
  playground: "/play",
  status: "/status",
  quicklinks: "/quicklinks",
};

export function middleware(request: NextRequest) {
  const mode = process.env.SIMAPI_SITE_MODE;
  const target = mode ? SITE_MODE_ROUTES[mode] : undefined;
  if (target && request.nextUrl.pathname === "/") {
    return NextResponse.rewrite(new URL(target, request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: "/",
};
