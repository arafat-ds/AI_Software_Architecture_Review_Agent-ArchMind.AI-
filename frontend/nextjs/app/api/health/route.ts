import { NextResponse } from "next/server";
import { getBackendConfig } from "@/lib/server-config";

export async function GET() {
  try {
    const { baseUrl, apiKey } = getBackendConfig();
    const res = await fetch(`${baseUrl}/api/v1/health`, {
      headers: { "X-API-Key": apiKey },
      next: { revalidate: 0 },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}
