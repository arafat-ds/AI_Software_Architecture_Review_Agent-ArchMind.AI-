"use client";

import { useState } from "react";
import { validateGitHubUrl } from "@/lib/validate";
import { submitJob } from "@/lib/api";

interface Props {
  onJobSubmitted: (jobId: string) => void;
}

export default function SubmitForm({ onJobSubmitted }: Props) {
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setUrl(e.target.value);
    if (validationError) setValidationError(null);
    if (submitError) setSubmitError(null);
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const err = validateGitHubUrl(url);
    if (err) {
      setValidationError(err);
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    try {
      const result = await submitJob({ repo_url: url.trim() });
      onJobSubmitted(result.job_id);
    } catch (ex) {
      setSubmitError(ex instanceof Error ? ex.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  const isEmpty = !url.trim();
  const isDisabled = submitting || isEmpty;

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div>
        <label
          htmlFor="repo-url"
          className="block text-sm font-medium text-gray-700 mb-1.5"
        >
          GitHub Repository URL
        </label>
        <input
          id="repo-url"
          type="url"
          value={url}
          onChange={handleChange}
          placeholder="https://github.com/owner/repo"
          disabled={submitting}
          autoComplete="url"
          className={[
            "w-full px-3.5 py-2.5 rounded-lg border text-sm shadow-sm",
            "placeholder:text-gray-400",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1",
            "disabled:bg-gray-50 disabled:text-gray-400 disabled:cursor-not-allowed",
            validationError
              ? "border-red-400 bg-red-50 focus-visible:ring-red-400"
              : "border-gray-300 bg-white",
          ].join(" ")}
          aria-describedby={
            validationError
              ? "url-error"
              : submitError
              ? "submit-error"
              : undefined
          }
          aria-invalid={!!validationError}
        />
        {validationError && (
          <p id="url-error" className="mt-1.5 text-xs text-red-600" role="alert">
            {validationError}
          </p>
        )}
      </div>

      {submitError && (
        <p id="submit-error" className="text-xs text-red-600" role="alert">
          {submitError}
        </p>
      )}

      <button
        type="submit"
        disabled={isDisabled}
        className={[
          "w-full py-2.5 px-4 rounded-lg text-sm font-semibold transition-colors duration-150",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2",
          isDisabled
            ? "bg-gray-100 text-gray-400 cursor-not-allowed border border-gray-200"
            : "bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white shadow-sm cursor-pointer",
        ].join(" ")}
      >
        {submitting ? (
          <span className="inline-flex items-center justify-center gap-2">
            <svg
              className="animate-spin h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
            Submitting…
          </span>
        ) : isEmpty ? (
          "Enter a repository URL above"
        ) : (
          "Analyze Repository"
        )}
      </button>
    </form>
  );
}
