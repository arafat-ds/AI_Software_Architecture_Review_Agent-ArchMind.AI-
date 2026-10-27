import { validateGitHubUrl } from "@/lib/validate";

describe("validateGitHubUrl", () => {
  it("accepts a valid owner/repo URL", () => {
    expect(validateGitHubUrl("https://github.com/owner/repo")).toBeNull();
  });

  it("accepts URL with trailing path segments", () => {
    expect(validateGitHubUrl("https://github.com/owner/repo/tree/main")).toBeNull();
  });

  it("rejects http (not https)", () => {
    expect(validateGitHubUrl("http://github.com/owner/repo")).not.toBeNull();
  });

  it("rejects non-GitHub domain", () => {
    expect(validateGitHubUrl("https://gitlab.com/owner/repo")).not.toBeNull();
  });

  it("rejects URL with only owner, no repo", () => {
    expect(validateGitHubUrl("https://github.com/owner")).not.toBeNull();
  });

  it("rejects bare github.com with no path", () => {
    expect(validateGitHubUrl("https://github.com/")).not.toBeNull();
  });

  it("rejects empty string", () => {
    expect(validateGitHubUrl("")).not.toBeNull();
  });

  it("trims whitespace before validating", () => {
    expect(validateGitHubUrl("  https://github.com/owner/repo  ")).toBeNull();
  });
});
