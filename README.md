# trailhead-helm

Helm chart for [trailhead](https://github.com/zimmertr/trailhead), published as an OCI artifact to GHCR.

- **Chart:** [`charts/trailhead`](./charts/trailhead). See its [README](./charts/trailhead/README.md) for values and usage.
- **OCI location:** `oci://ghcr.io/zimmertr/trailhead-helm`

## Release process

| Event | Action |
|---|---|
| Merge to `main` | [yggdrasil](https://github.com/zimmertr/yggdrasil)'s release module runs GitVersion, which computes a SemVer from the squash commit's title (the PR title) alone: `!` before the colon is a major, `feat` a minor, every other prefix a patch, and a `BREAKING CHANGE:` footer in the body counts for nothing. The module creates the `v<semver>` git tag + GitHub release, then the chart is packaged and `helm push`ed to the OCI repo under that version. A re-run skips a chart that is already pushed, so it finishes a failed release. |
| Manual run (`workflow_dispatch`) | The same release, from `main` only: a run started from another branch publishes nothing. |
| Pull request | `Chart / Chart` (yggdrasil's chart module) lints the chart and renders it, then runs the helm-unittest suites in `charts/trailhead/tests/`, which check the stable and the preview values against the rules in the chart's README. |
| Pull request title | The `PR Title / PR Title` check (yggdrasil's pr-title module) fails a title the release can't read. It runs on every PR, forks included, and again when the title is edited. |
| Renovate PR | Anything below a major merges itself once the required checks pass. Majors wait for review. |

Every action in the workflows is pinned to a full commit SHA with its version in a comment, and Renovate moves the pins by PR (`.github/renovate.json`). Helm is pinned to an exact version in yggdrasil's chart and release modules, and arrives with their pin.

Consuming repos (e.g. `Kubernetes-Manifests`) pin a chart `version`/`targetRevision`: the latest SemVer, written by this repo's release.
