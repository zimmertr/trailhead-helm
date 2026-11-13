# trailhead

A Helm chart for [trailhead](https://github.com/zimmertr/trailhead), my personal site rebuilt as a 3D world.

The chart deploys four small services and a database:

| Service | Kind | Replicas | What it is |
|---|---|---|---|
| `web` | Argo `Rollout` | 3, with a PodDisruptionBudget | nginx serving the 3D site and the plain page |
| `api` | Argo `Rollout` | 3, with a PodDisruptionBudget | The public API. Holds no tokens and calls nothing outside the cluster |
| `admin` | Argo `Rollout` | 1, no PodDisruptionBudget | The private panel, on a home-network host and a Gateway of its own |
| `fetcher` | `CronJob` | one run at a time | The only workload that holds API tokens |
| database | CloudNativePG `Cluster` | 3 instances | PostgreSQL, with one login per service |

It is built for my cluster and needs everything that runs there: **Argo Rollouts**, **Istio** (sidecar injection on in the namespace), the **CloudNativePG** operator and the **Prometheus operator**. Argo Rollouts and Istio aren't optional the way they are in bluebird-helm, because the canary steps need Istio to keep visitors off the canary.

Every instance is **release-scoped**: all selectors key on `app.kubernetes.io/instance`, so the stable release and any number of PR previews can share a namespace.

## Before you install

The chart names these Secrets and never creates them. Create them by hand in the release's namespace first.

```bash
# One login per service, for CloudNativePG to create and the service to connect as.
# The chart puts the password in a URL, so keep it hex.
for svc in api admin fetcher; do
  kubectl -n trailhead-system create secret generic "trailhead-$svc-database" \
    --type=kubernetes.io/basic-auth \
    --from-literal=username="trailhead_$svc" \
    --from-literal=password="$(openssl rand -hex 32)"
done

# The fetcher's tokens. Every key becomes an env var of the fetcher.
kubectl -n trailhead-system create secret generic trailhead-fetcher-tokens \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN"
```

Then set the hostnames. Both default to placeholders under `example.test`, which resolve nowhere, and an empty list fails the render.

| Value | What to set |
|---|---|
| `ingress.hosts` | The public hosts. `web` answers every path, `api` answers `/api` and below |
| `admin.ingress.hosts` | The admin panel's home-network host. Never a public one |
| `ingress.tls.credentialName` / `admin.ingress.tls.credentialName` | The TLS Secret for each Gateway, when `tls.enabled` is on |

## Quick start

```bash
helm install trailhead oci://ghcr.io/zimmertr/trailhead-helm --version <version> -n trailhead-system \
  --set 'ingress.hosts[0]=<public host>' --set 'admin.ingress.hosts[0]=<admin host>'
kubectl argo rollouts get rollout trailhead-web -n trailhead-system --watch
```

## Consuming via GitOps

### kustomize

```yaml
# kustomization.yml
namespace: trailhead-system
helmCharts:
  - name: trailhead-helm
    repo: oci://ghcr.io/zimmertr
    version: <version>
    releaseName: trailhead
    # The database subchart ships a ping Job as a Helm test hook, which
    # Argo CD would run as an ordinary Job on every sync.
    skipTests: true
    valuesFile: values.yml
```

### Argo CD ApplicationSet (PR previews)

`values-preview.yaml` ships inside the chart: one pod per service, no PodDisruptionBudgets, no fetcher, and a database of its own with one instance, so a preview never touches the stable release's data. Previews in one namespace share the three database Secrets above, so create them once there.

```yaml
sources:
  - repoURL: oci://ghcr.io/zimmertr/trailhead-helm
    chart: trailhead-helm
    targetRevision: <version>
    helm:
      releaseName: trailhead-pr-{{ .number }}
      valueFiles: [values-preview.yaml]
      valuesObject:
        web: { image: { tag: "pr-{{ .number }}-{{ .head_sha }}" } }
        api: { image: { tag: "pr-{{ .number }}-{{ .head_sha }}" } }
        admin:
          image: { tag: "pr-{{ .number }}-{{ .head_sha }}" }
          ingress: { hosts: ["admin.pr-{{ .number }}.<lan domain>"] }
        ingress: { hosts: ["pr-{{ .number }}.<lan domain>"] }
```

A preview runs the same canary checks as the stable release, so its image must report its own tag as its version.

## Deployment strategy

`web`, `api` and `admin` all roll out the same way. Nothing is judged on live traffic: the site is idle most of the time, so there would be none to judge.

1. `setCanaryScale: 1` brings up one pod of the new version. The VirtualService keeps its weight at 0, so no visitor reaches it.
2. `<release>-version-check` asks the canary Service for its version and compares it with the image's tag. `web` answers on `/version.json`, `api` on `/api/version` and `admin` on `/version`.
3. `<release>-<service>-smoke-test` sends a GET to each path in the service's `analysis.smokeTest` list: health and key pages for `web`, health and the version contract for `api` and `admin`.
4. The new version is promoted.

A non-2xx answer is an error, and five in a row fail the check. A failed check aborts the rollout and the stable version keeps serving. The AnalysisTemplates are rendered by the chart and named for the release, so each preview checks its own canary.

## Who may reach what

With `authorizationPolicy.enabled` (the default), Istio AuthorizationPolicies allow:

- `web`, `api` and `admin`: the ingress gateway (`authorizationPolicy.gatewayPrincipals`), on every path.
- The database: `api`, `admin` and the fetcher on 5432, and the database's own pods, whose standbys stream from the primary.

Three callers are outside the mesh, so their requests carry no identity, and get only what they need from anywhere: the Rollouts controller gets GET on each service's check paths, Prometheus gets `api`'s metrics port and the database's 9187, and the CloudNativePG operator gets the database's status port, 8000.

`admin` also refuses any request that carries a header in `authorizationPolicy.adminDenyHeaders`. Cloudflare adds `CF-Connecting-IP` to every request through a tunnel, so a request from the internet never reaches the panel, whatever its host.

## Database logins

Each service connects as its own role, which CloudNativePG creates from `database.cluster.roles` and the Secrets above. CloudNativePG manages roles but grants no table privileges, so the roles get PostgreSQL's predefined ones:

| Role | Gets | Still needs |
|---|---|---|
| `trailhead_api` | `pg_read_all_data` | INSERT on the register's table, from the app's migrations |
| `trailhead_admin` | `pg_read_all_data` | UPDATE on the register's table, from the app's migrations |
| `trailhead_fetcher` | `pg_read_all_data`, `pg_write_all_data` | Nothing |

The database's owner is `app`, whose Secret (`<release>-database-app`) the operator writes. No service connects as it.

## Values

| Key | Default | Description |
|---|---|---|
| `nameOverride` | `""` | Override `app.kubernetes.io/name` (default `trailhead`) |
| `fullnameOverride` | `""` | Override resource name base (default: release name) |
| `commonLabels` / `commonAnnotations` | `{}` | Merged onto every resource |
| `imagePullSecrets` | `[]` | Image pull secrets, for every pod |
| `podSecurityContext` | `runAsNonRoot`, uid/gid `10001`, `seccompProfile: RuntimeDefault` | Every pod's security context. The images run as 10001 |
| `securityContext` | `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]` | Every container's security context |
| `podAnnotations` / `podLabels` | `{}` | Extra pod metadata, for every pod |
| `nodeSelector` / `tolerations` / `affinity` | `{}` / `[]` / `{}` | Scheduling, for every pod |
| `<service>.replicas` | `3` / `3` / `1` | Replicas of `web`, `api` and `admin` |
| `<service>.image.name` | `ghcr.io/zimmertr/trailhead-<service>` | Image repository, for `web`, `api`, `admin` and `fetcher` |
| `<service>.image.tag` | `""` (chart `appVersion`) | Image tag. The images publish SemVer only, no `latest` |
| `<service>.image.pullPolicy` | `IfNotPresent` | Image pull policy |
| `<service>.port` | `8080` | The container port, which the Services also listen on |
| `<service>.resources` | small requests and limits, CPU and memory | Not measured yet: the services don't exist. Correct them once they run |
| `<service>.writablePaths` | `/tmp` (`web` adds `/var/cache/nginx`) | Paths given an emptyDir, the only places a process can write |
| `<service>.extraEnv` | `[]` | Extra env vars. They come last, so they win over the chart's own |
| `<service>.podDisruptionBudget.enabled` | `true` / `true` / `false` | A budget for `web` and `api`. None for `admin`: a budget on one pod blocks every node drain |
| `<service>.podDisruptionBudget.minAvailable` | `50%` | PDB percentages round **up**, so at 3 replicas this keeps 2 pods; `maxUnavailable: 50%` would instead permit 2 disruptions and leave 1 |
| `<service>.podDisruptionBudget.maxUnavailable` | `""` | Alternative to `minAvailable`; set one, blank the other |
| `<service>.topologySpreadConstraints` | one pod per node for `web` and `api`, `[]` for `admin` | Upstream `spec.topologySpreadConstraints` verbatim, except `labelSelector`, which the chart adds. `nodeTaintsPolicy: Honor` counts only the nodes a pod can land on |
| `<service>.probes` | `GET /healthz`; `api` and `admin` are ready on `GET /readyz` | `startup`, `liveness` and `readiness` probe definitions |
| `<service>.analysis.versionPath` | `/version.json` / `/api/version` / `/version` | Where the canary reports `{"version": ..., "commit": ...}`. The version must equal the image's tag |
| `<service>.analysis.smokeTest` | health, and the version path's contract | The smoke test's GETs: `name`, `path`, and an optional `successCondition` on the body (default `true`). Each path is also let through the AuthorizationPolicy, so add the plain page to `web`'s once it exists |
| `api.metrics.port` | `9464` | The Prometheus metrics server. One value drives the `METRICS_PORT` env, the `metrics` containerPort, and the port the PodMonitor scrapes; `0` removes the port. Never added to the Service, so nothing the gateway routes can reach it |
| `api.metrics.podMonitor.enabled` | `true` | Render a `monitoring.coreos.com/v1` PodMonitor scraping the pod port. The pods' `role` label (`stable` or `canary`) is copied onto every series |
| `<service>.databaseRole` | `trailhead_api` / `trailhead_admin` / `trailhead_fetcher` | The role in `database.cluster.roles` the service connects as. Empty for no `DATABASE_URL` |
| `admin.ingress.hosts` | `[admin.trailhead.example.test]` | The admin panel's hosts. A placeholder: set it. Empty fails the render |
| `admin.ingress.gatewaySelector` | `{istio: gateway}` | The ingress workload admin's Gateway binds to. A home-network-only gateway is a stronger place for it, if one runs |
| `admin.ingress.port` / `httpsRedirect` / `tls.*` | `80` / `false` / off | As for `ingress` below, on admin's Gateway |
| `fetcher.enabled` | `true` | Render the fetcher's CronJob and ServiceAccount |
| `fetcher.schedule` | `23 * * * *` | Hourly |
| `fetcher.tokensSecret` | `trailhead-fetcher-tokens` | The Secret of tokens, created by hand. Every key becomes an env var of the fetcher alone |
| `fetcher.backoffLimit` | `2` | Retries of a failed run, before it waits for the next hour |
| `fetcher.activeDeadlineSeconds` | `600` | A run still going after ten minutes has hung. The fetcher has no server, so no probes |
| `fetcher.successfulJobsHistoryLimit` / `failedJobsHistoryLimit` | `1` / `3` | Finished runs kept |
| `ingress.hosts` | `[trailhead.example.test]` | The public hosts. A placeholder: set it. Empty fails the render |
| `ingress.gatewaySelector` | `{istio: gateway}` | Istio ingress workload selector |
| `ingress.port` | `80` | HTTP listener port |
| `ingress.httpsRedirect` | `false` | Redirect `:80` to `:443` |
| `ingress.tls.enabled` / `ingress.tls.credentialName` | `false` / `""` | Terminate TLS on `:443`. The credential name is required when it's on |
| `canary.versionCheckInitialDelay` | `15s` | The canary Service keeps the stable pod hash for about a second after the canary pod starts, so the version check waits first |
| `canary.timeoutSeconds` | `10` | Timeout of each check's request |
| `authorizationPolicy.enabled` | `true` | Render the AuthorizationPolicies above |
| `authorizationPolicy.trustDomain` | `cluster.local` | The mesh's trust domain, for the services' identities |
| `authorizationPolicy.gatewayPrincipals` | `[cluster.local/ns/istio-gateway/sa/gateway]` | The ingress gateway's identity |
| `authorizationPolicy.adminDenyHeaders` | `[cf-connecting-ip]` | Headers that get a request refused by admin. Empty turns it off |
| `database.enabled` | `true` | Run the database. Off, no service gets a `DATABASE_URL` |
| `database.cluster.roles` | one login per service | CloudNativePG managed roles. Each `passwordSecret` is a `kubernetes.io/basic-auth` Secret created by hand |
| `database.*` | PostgreSQL `18` pinned by digest, three instances, `5Gi` each, a PDB, no superuser | Everything else under `database` is the CloudNativePG [`cluster` chart's values](https://github.com/cloudnative-pg/charts/tree/main/charts/cluster), passed through |

## Environment variables

The chart sets these. Everything else the services read goes in `extraEnv`.

| Variable | Set on | Meaning |
|---|---|---|
| `DATABASE_URL` | `api`, `admin`, `fetcher` | `postgresql://<user>:<password>@<release>-database-rw.<namespace>.svc:5432/app`, built from the service's login Secret |
| `DATABASE_USER` / `DATABASE_PASSWORD` | `api`, `admin`, `fetcher` | The parts of that URL, from the same Secret |
| `METRICS_PORT` | `api` | The port of the Prometheus metrics server |
| every key of `fetcher.tokensSecret` | `fetcher` | The fetcher's tokens |

## License

The chart's templates are GPL-3.0-only, as the repository's
[LICENSE](https://github.com/zimmertr/trailhead-helm/blob/main/LICENSE) states.
The chart is a separate work from the images it installs, which are under
[trailhead's own license](https://github.com/zimmertr/trailhead).
