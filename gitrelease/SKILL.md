---
name: "Git Release"
description: "Use when preparing or publishing a repository release under the strict release -> publish -> deploy lifecycle: release is local-only artifact preparation, publish exposes the exact prepared artifacts to GitHub, registries, or stores, and deploy is a separate activation step."
---

# Git Release Skill

Use `$Git Release` for repositories that implement the canonical lifecycle:

- `make release` validates and prepares every artifact locally.
- `make publish` exposes those exact prepared artifacts to their publication targets.
- `make deploy` activates already-published artifacts and is never part of release or publish.

The phases are forward-only. Do not retain an end-to-end release alias, rebuild in
publish, publish missing artifacts from deploy, or add a compatibility path for the
old lifecycle.

## Runtime Routing

Read `agents/runtime.yaml` when the host supports subagents. Keep all live-worktree
edits, local tags, commits, pushes, and publication operations in the controller
unless the host guarantees same-worktree execution.

## Bundled Commands

The scripts in `scripts/` are the canonical implementation:

- `prepare_release.sh` performs local preflight, runs `make ci`, invokes the
  repository's `RELEASE_ARTIFACT_TARGETS`, creates the changelog commit and local
  annotated tag, and writes `.git/mprlab-release/manifest.json`.
- `publish_release.sh` pushes the prepared branch and tag, creates or updates the
  GitHub Release, uploads prepared release assets, and verifies remote state.
- `prepare_container_artifact.sh` builds platform-specific images into local Docker
  archives without authenticating to or writing to a registry.
- `publish_container_artifacts.sh` loads and pushes those prepared archives without
  running a Docker build.
- `prepare_pages_artifact.sh` packages a local static site as the versioned
  `pages.tar.gz` GitHub Release asset.
- `deploy_pages_artifact.sh` downloads and verifies the published Pages asset, then
  replaces the live Pages branch.
- `prepare_go_module_artifact.sh` packages the locally validated module source and
  records its module path, source commit, packages, and `go.mod` hash.
- `deploy_go_module_artifact.sh` verifies the published manifest and remote tag,
  requests the exact version from one Go module proxy, and verifies the cached
  origin commit and `go.mod` hash.
- `release_helper.py` owns deterministic preflight, version information, notes,
  changelog insertion, artifact hashing, publication, and verification.

All prepared metadata and payloads live under `.git/mprlab-release`; release must
not dirty the worktree with generated binaries, archives, mobile bundles, Pages
output, or container archives.

## Release

Run `make release` only when the user asks to prepare a release.

1. Require the local default branch and a clean worktree.
2. Resolve versioning from local refs only. Do not fetch, query GitHub, or inspect a
   registry/store during release.
3. Run the repository's canonical local gate, normally `make ci`.
4. Build every declared local artifact through `RELEASE_ARTIFACT_TARGETS`.
5. Generate deterministic notes from local Git history and update `CHANGELOG.md`.
6. Create a local changelog-only release commit and annotated tag.
7. Finalize the release manifest with hashes for every payload.
8. Stop. Do not push refs, create a GitHub Release, log in to a registry, upload a
   store build, update a Pages branch, dispatch a workflow, or contact deployment.

`make release --dry-run` may inspect local state and select the next version, but it
must not run CI, build artifacts, edit files, commit, or tag.

## Publish

Run `make publish` only when the user asks to make a prepared release available.

1. Require `.git/mprlab-release/manifest.json` and verify all payload hashes.
2. Require the local tag and HEAD to match the manifest.
3. Fetch the remote default branch and fail if it moved beyond the prepared source.
4. Require no open pull requests into the default branch.
5. Push the prepared changelog commit and tag.
6. Create or update the GitHub Release from the exact prepared notes.
7. Upload files under `payloads/release-assets` and download them again to verify
   their hashes.
8. Publish prepared container archives and mobile/store artifacts through the
   repository's publish targets. A publish target must not build or regenerate an
   artifact.
9. Verify every publication target and stop. Do not activate Pages, invoke the
   gateway, run Ansible, or replace a live service.

Publication may be retried after a partial failure, but every successful target must
remain idempotent for the same release manifest.

## Deploy

Deployment is a separate operator-owned phase. When deployment work is requested,
follow the repository deployment guidance and the `mpr-deployment` skill.

- Verify exact published tags, digests, release assets, or store builds first.
- Fail with a direct instruction to run `make publish` when an artifact is absent.
- Do not build, tag, push, upload, or create a GitHub Release from deploy.
- Treat GitHub Pages branch updates, source configuration, and workflow dispatch as
  deployment.
- For a public Go module, deployment means activating the immutable published
  version through the configured module proxy and verifying that the proxy resolves
  to the prepared release commit. Downstream dependency upgrades remain owned by
  each consumer repository.
- Never execute a production MPR deploy or continue past `Gateway sudo password:`.

## Versioning

Use the repository's explicit policy when one exists. Otherwise continue the
established scheme:

- SemVer for libraries, CLIs, packages, APIs, and compatibility-signaling artifacts.
- CalVer for applications, sites, internal tools, and documentation projects.
- The canonical CalVer form is `YY.MDD.HHMMSS`, derived from the local release
  timestamp. Never invent a sequence suffix or move a timestamp backward.
- For a first SemVer release, use `v1.0.0`. For existing SemVer, select patch, minor,
  or major from the actual compatibility impact.

## Guardrails

- Never release from a non-default branch or dirty worktree.
- Never skip the repository CI gate.
- Never permit remote-write commands in release.
- Never permit build commands in publish.
- Never permit build or publication commands in deploy.
- Never hand-edit a prepared payload after the manifest is finalized.
- Never continue when a payload hash, source commit, release commit, tag, remote ref,
  published asset, image digest, or store identity differs from the manifest.
- Never treat a local or published artifact as proof that production was deployed.

## Reporting

For release, report the default branch, version scheme, selected tag, CI command,
artifact inventory, release commit, local tag, manifest path, and clean worktree.

For publish, additionally report pushed refs, GitHub Release URL, release assets,
container digests, store upload identities, and verification results. State clearly
that deployment was not run.
