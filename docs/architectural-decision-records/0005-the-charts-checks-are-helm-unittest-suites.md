# 0005. The chart's checks are helm-unittest suites, run by yggdrasil's chart module

- Status: Accepted. Supersedes 0001's PR check
- Date: 2026-11-13
- Decider: TJ, 2026-11-13, on hevy-garmin-sync#67: "Both, and other repos need to align on this solution instead of hand-rolling" (yggdrasil record 0060).
- Issues and PRs: #4
- Cited in code as: decision record 0005, in `.github/workflows/pr.yml`
- Guide: [`CLAUDE.md`](../../CLAUDE.md), Rules, "The README is TJ's"

## Context

Record 0001 checked the chart with a `test` script in the chart job: `helm template` renders piped into `.github/scripts/check_render.py`, about 200 lines of Python. TJ decided that every repo tests a chart with helm-unittest instead of hand-written checks, and yggdrasil's chart module now runs it (yggdrasil record 0060). The module's `test` input is deprecated.

## Decision

- Every rule the chart's README promises is a helm-unittest test in `charts/trailhead/tests/<template>_test.yaml`. yggdrasil's chart module runs every suite there after its lint and default render, with no input.
- Each rule is tested twice: on the defaults (the stable release) and on `values-preview.yaml` with placeholder hosts in `trailhead-pr-system` (a PR preview). The two share their assertions through YAML anchors wherever the rule is the same.
- A rule that spans two resources, such as a Rollout naming a Service, is two tests: the Rollout's suite checks the name, and the Service's suite checks a Service of that name is rendered.
- The database's rules test the CloudNativePG subchart's own template, `charts/database/templates/cluster.yaml`.
- `charts/trailhead/.helmignore` keeps `tests/` out of the packaged chart.

## Evidence

- 2026-11-13: yggdrasil v1.3.0 (`b662606`) runs helm-unittest `4.3.0-1.2.1` on every `*_test.yaml` in the chart's `tests/` folder.
- 2026-11-13: the suites passed on the chart, and failed on a copy that added a `setWeight` step, a Prometheus metric, the fetcher's tokens in a Rollout, a renamed Service and the admin host on the public Gateway and VirtualService.

## Alternatives rejected

- The script over the render (record 0001): it worked, but every repo wrote its own, and a failure named only the broken rule's message.

## Consequences

- `Chart / Chart` holds the suites, and a new rule in the README gets a test in the same PR.
- `helm lint` runs on the defaults only. The old check also linted with `values-preview.yaml`, and helm-unittest has no lint; the preview suites render every template the rules read with that file.
