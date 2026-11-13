# trailhead-helm

The Helm chart for zimmertr/trailhead (`charts/trailhead`), published as an OCI artifact to GHCR. The chart's values, the Secrets it needs and the hostnames to set are in [`charts/trailhead/README.md`](charts/trailhead/README.md). It is modelled on zimmertr/bluebird-helm: when in doubt, do what that repo does.

When a change here makes a decision, write its record in [`docs/architectural-decision-records/`](docs/architectural-decision-records/README.md).

## Rules

- **A merge to `main` that changes `charts/**` is a release.** yggdrasil's release module tags it from the PR title and pushes the chart. Record: [0001](docs/architectural-decision-records/0001-the-chart-goes-through-yggdrasils-modules.md)
- **`appVersion` comes from trailhead.** trailhead's release bumps it here by PR, and the chart ships with what `Chart.yaml` says. Don't edit it by hand. Record: [0001](docs/architectural-decision-records/0001-the-chart-goes-through-yggdrasils-modules.md)
- **A canary is never judged on live traffic.** Every gate is a scripted check against the canary Service, and its weight stays 0. No Prometheus analysis. Record: [0002](docs/architectural-decision-records/0002-a-canary-is-promoted-on-scripted-checks-alone.md)
- **Each service gets its own database login.** The chart never creates a Secret: logins and tokens are made by hand. Record: [0003](docs/architectural-decision-records/0003-one-database-login-per-service.md)
- **Only the gateway reaches the services.** `admin` is never on the public Gateway. A new check path is let through the AuthorizationPolicy by the chart, so add it to `analysis.smokeTest`, not to the policy. Record: [0004](docs/architectural-decision-records/0004-only-the-gateway-reaches-the-services.md)
- **No real hostname in the repo.** Hosts are values with `example.test` placeholders.
- **The README is TJ's.** Keep it accurate and in TJ's voice, and never restructure it. A value change updates `charts/trailhead/README.md` in the same PR, and a rule the README promises gets a check in `.github/scripts/check_render.py`.

## Issues

File issues with the `create-issue` skill from zimmertr/ai-config. The skill reads the four things below from this section.

- **The reader**: someone who installs the chart and knows Helm and Kubernetes, but not trailhead's code.
- **The gates**: `Chart / Chart`, `PR Title / PR Title` and the three `Lint /` checks pass; `charts/trailhead/README.md` changes with any value; the README changes only to stay accurate.
- **The constraints**: no secret values, real hostnames or addresses in the repo or in logs; a release must not break the stable app or the PR previews; the chart stays GPLv3.
- **The areas**: `chart` (the templates and values), `ci` (the workflows and Renovate), `security`.

## Working in this repo

- Work in a fresh clone in the session's scratchpad, never in TJ's checkout. Branch from the latest `origin/main`.
- Everything reaches main through a squash-merged PR. Never push to main.
- CI runs on zimmertr/yggdrasil's `pr-title`, `lint`, `chart` and `release` modules, pinned by commit SHA with the version beside it. Renovate bumps the pin as soon as a release ships.
- Actions are pinned to commit SHAs with the version in a comment. Helm's version is the one yggdrasil's modules install; no workflow here installs it.
- To render locally, run Helm in Docker: `docker run --rm -v "$PWD":/w -w /w alpine/helm:4.3.1 template trailhead charts/trailhead`, after `dependency update charts/trailhead` the same way.
