# 0002. A canary is promoted on scripted checks alone, never on live traffic

- Status: Accepted
- Date: 2026-11-12
- Decider: TJ, 2026-11-12, in the planning interview for trailhead: the site is idle most of the time, so the canary cannot be judged on production traffic, and every gate is a scripted check, as Bluebird's `version-check` and `api-test` are.
- Issues and PRs: #3
- Cited in code as: decision record 0002, in `templates/rollouts.yaml` and `virtualservice.yaml`
- Guide: [`CLAUDE.md`](../../CLAUDE.md), Rules

## Context

An error-rate gate needs requests to count, and a site nobody is visiting sends none. Bluebird's Rollout already brings its canary up with no visitor traffic and checks it with scripts first; its third gate, `error-rate`, reads Prometheus.

## Decision

- `web`, `api` and `admin` run the same steps: `setCanaryScale: 1`, `<release>-version-check`, `<release>-<service>-smoke-test`, then promotion. No `setWeight`, so the canary's weight stays 0 throughout.
- Both checks are Argo Rollouts `web` metrics against the canary Service. There is no Prometheus analysis.
- The chart renders the AnalysisTemplates and names them for the release, where Bluebird keeps its templates in Kubernetes-Manifests. Their URLs name the release's canary Services, so each preview in a shared namespace checks its own.
- The version check accepts the image as `name:tag` or `name:tag@digest`, where Bluebird's accepts only the second, because a preview's image is not pinned by digest.

## Evidence

- 2026-11-12: Argo Rollouts refuses `setCanaryScale` without `trafficRouting` (`InvalidSetCanaryScaleTrafficPolicy` in its `validation.go`), so every Rollout routes through a VirtualService the chart renders.
- 2026-11-12: in Argo Rollouts' analysis code an error does not count toward a metric's `count`, so a check that never gets a 2xx ends in Error after `consecutiveErrorLimit`, not in success.

## Alternatives rejected

- Bluebird's `error-rate` template: it judges the canary's own requests, which here would be the probes and the checks alone.
- AnalysisTemplates kept in Kubernetes-Manifests: every preview release would need its own copy with its own URLs.

## Consequences

- A check that a request can fail only under real load is not caught before promotion.
- An image must report its own tag as its version, a preview's image included.
