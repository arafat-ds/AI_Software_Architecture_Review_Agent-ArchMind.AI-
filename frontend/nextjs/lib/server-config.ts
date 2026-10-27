import "server-only";

export function getBackendConfig(): { baseUrl: string; apiKey: string } {
  const baseUrl = process.env.ARCHMIND_API_URL;
  const apiKey = process.env.ARCHMIND_API_KEY;

  if (!baseUrl) throw new Error("ARCHMIND_API_URL is not set");
  if (!apiKey) throw new Error("ARCHMIND_API_KEY is not set");

  return { baseUrl: baseUrl.replace(/\/$/, ""), apiKey };
}
