# 0004. Only the ingress gateway reaches web, api and admin, and only the services reach the database

- Status: Accepted
- Date: 2026-11-12
- Decider: TJ, 2026-11-12, in trailhead's PRD (Istio policies) and on trailhead#4: an AuthorizationPolicy so only the gateway can reach `admin`. The holes for callers outside the mesh were proposed in #3.
- Issues and PRs: #3, trailhead#4
- Cited in code as: decision record 0004, in `templates/authorizationpolicy.yaml`
- Guide: [`CLAUDE.md`](../../CLAUDE.md), Rules

## Context

`admin` has no login yet (trailhead#4), so the network is its only guard. bluebird-helm has no AuthorizationPolicy to copy.

## Decision

- An ALLOW policy on each of `web`, `api` and `admin` admits the ingress gateway's identity on every path.
- The same policy admits GET and HEAD on the service's check paths from anywhere, and `api`'s metrics port, because the Rollouts controller and Prometheus run outside the mesh and carry no identity.
- A DENY policy on `admin` refuses a request carrying `CF-Connecting-IP`, which Cloudflare adds to every request through a tunnel.
- An ALLOW policy on the database admits `api`, `admin`, the fetcher and the database's own pods on 5432, and anyone on 8000 and 9187.

## Evidence

- 2026-11-12, read-only on the cluster: `argo-system` and `prometheus-system` have no sidecar injection, and the CloudNativePG operator runs in `postgres-system`, also without one. Bluebird's database pods carry sidecars.
- 2026-11-12: the ingress gateway runs as service account `gateway` in `istio-gateway`. No PeerAuthentication exists, so the mesh is permissive.

## Alternatives rejected

- Allowing the Rollouts controller by namespace: a request with no sidecar carries no namespace either.

## Consequences

- A pod anywhere in the cluster can still read each service's health and version paths.
- A new check path is let through by adding it to `analysis.smokeTest`, which the chart reads for the policy.
