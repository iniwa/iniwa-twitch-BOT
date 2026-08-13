# v2 Live pilot: production rollout

Status: complete.

## Goal

Publish the verified source that connects the read-only v2 Live pilot to the
existing Flask application, then update the existing Raspberry Pi container so
`/v2/live`, `/api/v2/live`, and `/api/v2/health` no longer return 404.

The user explicitly authorized the production rollout on 2026-08-13.

## Background and evidence

- The current arm64 container is healthy and serves the legacy
  `/api/stream/status`, but its image predates the v2 bridge and returns 404
  for the pilot routes.
- The completed source bridge adds the pilot blueprint to the existing
  `app:app` Flask process; it does not add a second container, worker, port,
  storage mount, or runtime writer.
- Local verification before this rollout: `243 passed, 2 skipped`, compile
  check, root-package import smoke, and independent review with no material
  finding.
- The checked-in workflow is the intended multi-architecture GHCR publisher;
  publication routing must be confirmed without exposing credentials before
  writing Git history.

## Files and systems to inspect

- `AGENTS.md`, `CLAUDE.md`, this handoff, completed bridge handoff
- local Git status/diff, `.github/workflows/docker-publish.yml`, `Dockerfile`,
  `compose.yaml`
- non-secret Git/GitHub publication metadata only
- Raspberry Pi Docker/Compose metadata and HTTP headers only; never inspect
  configuration/data/history/session/media/credentials.

## Approved actions

1. Re-run the relevant local verification and inspect the exact intended Git
   path set.
2. Create one intentional commit containing the completed v2 rebuild and Live
   bridge source/docs/tests, excluding generated virtual environments,
   runtime data, media, credentials, and unrelated local changes.
3. Push through the confirmed publication path, wait for the existing
   multi-architecture image publication, and identify the immutable revision
   being rolled out.
4. On the Raspberry Pi, preserve the current image identity for rollback,
   pull only the published application image, and recreate only the existing
   Twitch-bot Compose service.  Do not alter the Compose file, mounts,
   networking, image name, credentials, or persistent data.
5. Verify container health and HTTP status/header availability for the v2
   routes and protected legacy status endpoint.  Do not fetch/record response
   bodies that may contain stream or personal data.
6. If the rollout fails, restore the previous image identity using the same
   existing Compose definition, then verify health and legacy status.

## Constraints and non-goals

- No direct edits to production data, configuration, credentials, downloads,
  media, mounts, Portainer configuration, workflow, Dockerfile, Compose, or
  external exposure.
- No Twitch, OBS, secretary-bot, database migration/import, or live API
  action.  The v2 pilot remains read-only.
- No secret, token, personal data, raw runtime payload, image registry
  credential, or private endpoint is copied into logs or documentation.
- Do not silently include a generated virtual environment or unknown worktree
  change in the commit.  Treat an unexpected publication-route mismatch as a
  stop condition and report it before selecting an alternative publisher.

## Acceptance criteria

- The published image contains the tested bridge and supports both amd64 and
  arm64 through the existing workflow.
- The Pi service is healthy after replacement, with existing data/media mounts
  untouched.
- `GET /v2/live`, `GET /api/v2/live`, and `GET /api/v2/health` are no longer
  404; `GET /api/stream/status` remains successful.
- The visible v2 page remains GET-only and no request-time external I/O is
  introduced.
- A rollback identity is retained until post-rollout verification succeeds.

## Verification and report

- Record local test/compile/diff results, commit revision, image publication
  result, and non-sensitive remote health/HTTP status results.
- State whether rollback was needed.  Confirm that production data,
  credentials, media, mounts, and deployment configuration were preserved.

## Completion record

- Published source commit: `d1bfefc` (`feat: add v2 rebuild foundation and
  live pilot`).  It was pushed to both the GitHub publication repository and
  the existing Gitea mirror.
- The existing GitHub `Docker Build and Push` workflow completed successfully
  for that revision and published its configured multi-architecture image.
- On the Raspberry Pi, the new arm64 image was pulled and verified to carry
  the same source revision.  The previous image remained present as the
  rollback target during the rollout.
- The current Compose definition was not byte-identical to Portainer's stale
  recorded definition, so the operational settings were compared before
  replacement: image name, service user, host network, restart policy, and
  `/app/data` plus `/app/downloads` bind targets matched.  Only the
  `twitch-bot` service was force-recreated with the already-pulled image;
  no dependencies, Compose file, mounts, configuration, data, credentials,
  or media were changed.
- Post-rollout: container health is healthy; `/`, `/api/stream/status`,
  `/v2/live`, `/api/v2/live`, `/api/v2/health`, and
  `/v2-static/v2/live.css` all returned HTTP 200.  Response bodies were not
  retained during remote validation.  Rollback was not needed.
