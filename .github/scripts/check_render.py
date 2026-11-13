#!/usr/bin/env python3
"""Checks a rendered trailhead chart for the rules its README promises.

Reads `helm template ... | yq -o=json -I=0 '.'` on stdin: one JSON document
per line. `--preview` checks the shape values-preview.yaml must give instead
of the stable one. Prints every broken rule, then exits 1 if there was any.
"""

import argparse
import json
import sys

TOKENS_SECRET = "trailhead-fetcher-tokens"


def load(stream):
    docs = []
    for line in stream:
        line = line.strip()
        if not line or line == "null":
            continue
        doc = json.loads(line)
        if not doc:
            continue
        # Helm test hooks (the database subchart's ping test) are not part of
        # the release; kustomize skips them with skipTests.
        if "helm.sh/hook" in doc.get("metadata", {}).get("annotations", {}):
            continue
        docs.append(doc)
    return docs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    docs = load(sys.stdin)
    errors = []

    def by_kind(kind):
        return [d for d in docs if d["kind"] == kind]

    def name(d):
        return d["metadata"]["name"]

    accounts = {name(d): d for d in by_kind("ServiceAccount")}
    templates = {name(d) for d in by_kind("AnalysisTemplate")}
    services = {name(d) for d in by_kind("Service")}
    vss = {name(d): d for d in by_kind("VirtualService")}

    pods = []
    for r in by_kind("Rollout"):
        pods.append((f"Rollout {name(r)}", r["spec"]["template"]["spec"], True))
    for c in by_kind("CronJob"):
        pods.append(
            (f"CronJob {name(c)}", c["spec"]["jobTemplate"]["spec"]["template"]["spec"], False)
        )

    for label, spec, served in pods:
        if spec.get("automountServiceAccountToken") is not False:
            errors.append(f"{label}: automountServiceAccountToken is not false")
        account = accounts.get(spec.get("serviceAccountName", ""))
        if not account:
            errors.append(f"{label}: its ServiceAccount is not rendered")
        elif account.get("automountServiceAccountToken") is not False:
            errors.append(f"{label}: its ServiceAccount mounts a token")
        psc = spec.get("securityContext", {})
        if psc.get("runAsNonRoot") is not True:
            errors.append(f"{label}: runAsNonRoot is not true")
        if psc.get("seccompProfile", {}).get("type") != "RuntimeDefault":
            errors.append(f"{label}: seccomp is not RuntimeDefault")
        for c in spec["containers"]:
            where = f"{label} container {c['name']}"
            sc = c.get("securityContext", {})
            if sc.get("allowPrivilegeEscalation") is not False:
                errors.append(f"{where}: allowPrivilegeEscalation is not false")
            if sc.get("readOnlyRootFilesystem") is not True:
                errors.append(f"{where}: the root filesystem is writable")
            if "ALL" not in sc.get("capabilities", {}).get("drop", []):
                errors.append(f"{where}: capabilities are not all dropped")
            res = c.get("resources", {})
            for part in ("requests", "limits"):
                for key in ("cpu", "memory"):
                    if key not in res.get(part, {}):
                        errors.append(f"{where}: no {key} {part[:-1]}")
            if served:
                for probe in ("startupProbe", "livenessProbe", "readinessProbe"):
                    if not c.get(probe):
                        errors.append(f"{where}: no {probe}")
            secrets = [e["secretRef"]["name"] for e in c.get("envFrom", []) if "secretRef" in e]
            secrets += [
                e["valueFrom"]["secretKeyRef"]["name"]
                for e in c.get("env", [])
                if "secretKeyRef" in e.get("valueFrom", {})
            ]
            if TOKENS_SECRET in secrets and c["name"] != "fetcher":
                errors.append(f"{where}: reads the fetcher's tokens")

    want_replicas = {"web": 3, "api": 3, "admin": 1}
    if args.preview:
        want_replicas = {"web": 1, "api": 1, "admin": 1}
    rollouts = {r["spec"]["template"]["spec"]["containers"][0]["name"]: r for r in by_kind("Rollout")}
    if set(rollouts) != set(want_replicas):
        errors.append(f"Rollouts are {sorted(rollouts)}, not web, api and admin")
    for component, want in want_replicas.items():
        r = rollouts.get(component)
        if not r:
            continue
        if r["spec"]["replicas"] != want:
            errors.append(f"Rollout {name(r)}: {r['spec']['replicas']} replicas, not {want}")
        canary = r["spec"]["strategy"].get("canary", {})
        steps = canary.get("steps", [])
        if not steps or "setCanaryScale" not in steps[0]:
            errors.append(f"Rollout {name(r)}: the first step is not setCanaryScale")
        if any("setWeight" in s for s in steps):
            errors.append(f"Rollout {name(r)}: a step sends visitors to the canary")
        analyses = [s["analysis"] for s in steps if "analysis" in s]
        if len(analyses) < 2:
            errors.append(f"Rollout {name(r)}: fewer than two analysis steps")
        for a in analyses:
            for t in a["templates"]:
                if t["templateName"] not in templates:
                    errors.append(f"Rollout {name(r)}: AnalysisTemplate {t['templateName']} is not rendered")
        for svc in (canary.get("stableService"), canary.get("canaryService")):
            if svc not in services:
                errors.append(f"Rollout {name(r)}: Service {svc} is not rendered")
        istio = canary.get("trafficRouting", {}).get("istio", {}).get("virtualService", {})
        vs = vss.get(istio.get("name"))
        if not vs:
            errors.append(f"Rollout {name(r)}: its VirtualService is not rendered")
            continue
        routes = {h["name"]: h for h in vs["spec"]["http"]}
        for route in istio.get("routes", []):
            hosts = [d["destination"]["host"] for d in routes.get(route, {}).get("route", [])]
            if hosts != [canary.get("stableService"), canary.get("canaryService")]:
                errors.append(f"Rollout {name(r)}: route {route} does not list stable then canary")

    for t in by_kind("AnalysisTemplate"):
        for m in t["spec"]["metrics"]:
            if "web" not in m["provider"]:
                errors.append(f"AnalysisTemplate {name(t)}: metric {m['name']} is not a scripted web check")

    pdbs = {d["spec"]["selector"]["matchLabels"]["app.kubernetes.io/component"] for d in by_kind("PodDisruptionBudget")}
    want_pdbs = set() if args.preview else {"web", "api"}
    if pdbs != want_pdbs:
        errors.append(f"PodDisruptionBudgets cover {sorted(pdbs)}, not {sorted(want_pdbs)}")

    clusters = by_kind("Cluster")
    want_instances = 1 if args.preview else 3
    if len(clusters) != 1 or clusters[0]["spec"]["instances"] != want_instances:
        errors.append(f"the database is not one Cluster of {want_instances} instances")
    elif clusters[0]["spec"]["enablePDB"] is args.preview:
        errors.append("the database's PodDisruptionBudget is the wrong way round")

    if args.preview and by_kind("CronJob"):
        errors.append("a preview runs the fetcher, which holds the tokens")
    if not args.preview and len(by_kind("CronJob")) != 1:
        errors.append("the fetcher's CronJob is not rendered")
    for c in by_kind("CronJob"):
        if c["spec"].get("concurrencyPolicy") != "Forbid":
            errors.append(f"CronJob {name(c)}: runs can overlap")

    gateways = {name(d): d for d in by_kind("Gateway")}
    admin_vs = [v for v in vss.values() if v["metadata"]["labels"]["app.kubernetes.io/component"] == "admin"]
    public_vs = [v for v in vss.values() if v not in admin_vs]
    if len(admin_vs) != 1 or len(public_vs) != 1:
        errors.append("there is not one public and one admin VirtualService")
    else:
        admin_hosts = set(admin_vs[0]["spec"]["hosts"])
        admin_gws = set(admin_vs[0]["spec"]["gateways"])
        public_gws = set(public_vs[0]["spec"]["gateways"])
        if admin_gws & public_gws:
            errors.append("admin's VirtualService shares a Gateway with the public one")
        for gw in public_gws:
            for server in gateways.get(gw, {}).get("spec", {}).get("servers", []):
                if admin_hosts & set(server["hosts"]):
                    errors.append(f"the public Gateway {gw} serves an admin host")
        if admin_hosts & set(public_vs[0]["spec"]["hosts"]):
            errors.append("the public VirtualService serves an admin host")
        admin_dests = {
            d["destination"]["host"] for v in public_vs for h in v["spec"]["http"] for d in h.get("route", [])
        }
        if any("admin" in host for host in admin_dests):
            errors.append("the public VirtualService routes to admin")

    policies = {
        d["metadata"]["labels"]["app.kubernetes.io/component"]
        for d in by_kind("AuthorizationPolicy")
        if d["spec"].get("action") == "ALLOW"
    }
    for component in ("web", "api", "admin", "database"):
        if component not in policies:
            errors.append(f"no ALLOW AuthorizationPolicy for {component}")

    for e in errors:
        print(f"::error::{e}")
    print(f"{len(docs)} resources checked, {len(errors)} problems", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
