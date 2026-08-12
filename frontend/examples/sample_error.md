# Sample Pipeline Output — Error Cards

> **Purpose:** Manual testing and demos only. Not loaded by the Pipelines server.
> Shows what the pipeline yields for each error type.

---

## Error type: `invalid_url`

> ❌ **Invalid Repository URL**
>
> **Provided:** `github.com/pallets/flask`
>
> ArchMind requires a full GitHub URL starting with `https://github.com/`.
>
> Supported formats:
> - `https://github.com/owner/repository`
> - `https://github.com/owner/repository.git`
>
> Submit a corrected URL to try again.

---

## Error type: `job_failed`

> ❌ **Analysis Failed**
>
> **Repository:** owner/private-repo
> **Job ID:** `3fa85f64-5717-4562-b3fc-2c963f66afa6`
>
> **Error:** Repository clone failed — not found or repository is private.
>
> Possible causes:
> - Repository is private (ArchMind analyses public repositories only)
> - URL is incorrect
> - GitHub is temporarily unavailable
>
> Submit a corrected URL to try again.

---

## Error type: `service_unavailable`

> ❌ **Service Unavailable**
>
> Could not connect to the ArchMind backend.
>
> The analysis service is temporarily unavailable. Try again in a few minutes.
> If the problem persists, contact your administrator.

---

## Error type: `rate_limited`

> ❌ **Server at Capacity**
>
> The ArchMind server is currently at maximum capacity.
>
> Try again in a few minutes. If analyses are consistently failing, the administrator
> may need to increase `MAX_CONCURRENT_JOBS`.

---

## Error type: `timeout`

> ❌ **Analysis Timeout**
>
> **Repository:** pallets/flask
> **Job ID:** `3fa85f64-5717-4562-b3fc-2c963f66afa6`
>
> The analysis exceeded the maximum wait time (1800s). The job may still be running
> on the backend. Contact your administrator with the Job ID above to check status.

---

## Error type: `repo_too_large`

*(Available after M16.3 backend deployment)*

> ❌ **Repository Too Large**
>
> **Repository:** large-org/monorepo
>
> This repository exceeds the maximum size limit for analysis.
> ArchMind is optimised for repositories up to [limit defined at M16.3].
