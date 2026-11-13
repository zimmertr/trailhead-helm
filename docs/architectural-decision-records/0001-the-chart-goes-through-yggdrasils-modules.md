# 0001. The chart is checked, pushed and released by yggdrasil's modules, with the `appVersion` in `Chart.yaml`

- Status: Accepted
- Date: 2026-11-12
- Decider: TJ, 2026-11-12, asking for this repo's first chart to be modelled on bluebird-helm, its CI wiring included.
- Issues and PRs: #3
- Cited in code as: decision record 0001, in `.github/workflows/pr.yml` and `release.yml`
- Guide: [`CLAUDE.md`](../../CLAUDE.md), Rules

## Context

trailhead needs a chart in a repo of its own, as Bluebird has bluebird-helm. bluebird-helm already settled how a chart repo is checked and released (its records 0004 and 0005).

## Decision

- On a PR, the `Chart` job calls yggdrasil's `chart.yml`, pinned like bluebird-helm's. Its `test` input renders the stable and preview values and runs `.github/scripts/check_render.py` on each. The check is `Chart / Chart`.
- On main, `release.yml` calls yggdrasil's `release.yml` with `charts` alone. It tags the commit and pushes the chart to `oci://ghcr.io/zimmertr/trailhead-helm`.
- The chart ships with the `appVersion` in `Chart.yaml`, which trailhead's release sets by PR.
- No `deploys` yet: nothing in Kubernetes-Manifests installs the chart. They join `release.yml` when the stable app and the preview ApplicationSet exist.

## Evidence

- 2026-11-12: yggdrasil v1.2.9 (`f805e7b`) is its latest release, and the pin bluebird-helm runs.
- 2026-11-12: bluebird-helm's `Chart / Chart` renders its stable and preview scenarios the same way.

## Alternatives rejected

- helm-unittest: bluebird-helm has none, and its record 0002 found that every Helm test tool compares a render with values kept in the repo. A script over the render does the same with no new tool.

## Consequences

- The first release resolves `appVersion` 0.1.0, which no trailhead image carries yet. Nothing installs that chart.
