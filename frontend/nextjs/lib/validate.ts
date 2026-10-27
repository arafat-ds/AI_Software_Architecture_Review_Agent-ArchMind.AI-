// Mirrors backend SubmitJobRequest.validate_github_https_url
export function validateGitHubUrl(url: string): string | null {
  const trimmed = url.trim();
  if (!trimmed.startsWith("https://github.com/")) {
    return "URL must start with https://github.com/";
  }
  // Require at least owner/repo after the base
  const path = trimmed.slice("https://github.com/".length);
  const parts = path.split("/").filter(Boolean);
  if (parts.length < 2) {
    return "URL must include owner and repository name (e.g. https://github.com/owner/repo)";
  }
  return null; // valid
}
