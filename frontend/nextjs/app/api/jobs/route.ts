import { NextRequest, NextResponse } from "next/server";
import { getBackendConfig } from "@/lib/server-config";
import { validateGitHubUrl } from "@/lib/validate";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const repoUrl: string = typeof body?.repo_url === "string" ? body.repo_url : "";

    const validationError = validateGitHubUrl(repoUrl);
    if (validationError) {
      return NextResponse.json({ detail: validationError }, { status: 422 });
    }

    const { baseUrl, apiKey } = getBackendConfig();
    const res = await fetch(`${baseUrl}/api/v1/jobs`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ repo_url: repoUrl }),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ detail: msg }, { status: 502 });
  }
}

export async function GET() {
  try {
    const { baseUrl, apiKey } = getBackendConfig();
    const res = await fetch(`${baseUrl}/api/v1/jobs`, {
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
