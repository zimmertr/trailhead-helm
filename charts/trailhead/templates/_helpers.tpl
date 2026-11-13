{{/*
Chart name (app.kubernetes.io/name). Constant across instances, so a selector
must ALSO match on the instance label to stay isolated.
*/}}
{{- define "trailhead.name" -}}
{{- default "trailhead" .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Resource name base. Defaults to the release name (trailhead / trailhead-pr-<n>)
rather than the Helm "<release>-<chart>" convention, so names stay clean.
*/}}
{{- define "trailhead.fullname" -}}
{{- default .Release.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Chart label value, e.g. trailhead-helm-0.1.0
*/}}
{{- define "trailhead.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
A workload's name: <fullname>-<component>. Its Service, ServiceAccount,
Rollout and budget all carry it. Takes (dict "root" $ "component" "web").
*/}}
{{- define "trailhead.componentName" -}}
{{- printf "%s-%s" (include "trailhead.fullname" .root) .component | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Selector labels, the isolation boundary. The instance label keeps the stable
release and each preview apart in a shared namespace, and the component label
keeps web, api, admin and the fetcher apart within one release. Takes
(dict "root" $ "component" "web").
*/}}
{{- define "trailhead.selectorLabels" -}}
app.kubernetes.io/name: {{ include "trailhead.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/*
Common labels applied to all resources. Takes (dict "root" $ "component" "web").
*/}}
{{- define "trailhead.labels" -}}
helm.sh/chart: {{ include "trailhead.chart" .root }}
{{ include "trailhead.selectorLabels" . }}
{{- if .root.Chart.AppVersion }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
app.kubernetes.io/part-of: trailhead
{{- with .root.Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/*
Metadata every resource carries: namespace, labels and the common annotations.
Takes (dict "root" $ "component" "web").
*/}}
{{- define "trailhead.metadata" -}}
namespace: {{ .root.Release.Namespace }}
labels:
  {{- include "trailhead.labels" . | nindent 2 }}
{{- with .root.Values.commonAnnotations }}
annotations:
  {{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}

{{/*
Container image reference. The tag defaults to the chart appVersion, a
published release tag: the images never publish `latest`. Takes
(dict "root" $ "component" "web").
*/}}
{{- define "trailhead.image" -}}
{{- $image := (index .root.Values .component).image -}}
{{- printf "%s:%s" $image.name (default .root.Chart.AppVersion $image.tag) -}}
{{- end -}}

{{/*
A service account's Istio identity, which AuthorizationPolicies match on.
Takes (dict "root" $ "account" "<name>").
*/}}
{{- define "trailhead.principal" -}}
{{- printf "%s/ns/%s/sa/%s" .root.Values.authorizationPolicy.trustDomain .root.Release.Namespace .account -}}
{{- end -}}

{{/*
The CloudNativePG cluster's name, as its own chart computes it for the
`database` alias, so the services can name the Service and the pods it
creates.
*/}}
{{- define "trailhead.databaseName" -}}
{{- if .Values.database.fullnameOverride -}}
{{- .Values.database.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default "database" .Values.database.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
A service's database env. The login is the role named by the component's
`databaseRole`, looked up in `database.cluster.roles` so the Secret's name is
written once. The URL is assembled by Kubernetes from the Secret's username
and password, so a rotated password needs no second copy. Takes
(dict "root" $ "component" "api").
*/}}
{{- define "trailhead.databaseEnv" -}}
{{- $role := (index .root.Values .component).databaseRole -}}
{{- if and .root.Values.database.enabled $role -}}
{{- $secret := "" -}}
{{- range .root.Values.database.cluster.roles -}}
{{- if eq .name $role -}}
{{- $secret = .passwordSecret.name -}}
{{- end -}}
{{- end -}}
{{- if not $secret -}}
{{- fail (printf "%s.databaseRole is %q, but no role of that name with a passwordSecret is under database.cluster.roles." .component $role) -}}
{{- end -}}
{{- $db := include "trailhead.databaseName" .root -}}
{{- $dbname := default "app" (.root.Values.database.cluster.initdb).database -}}
- name: DATABASE_USER
  valueFrom:
    secretKeyRef:
      name: {{ $secret }}
      key: username
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ $secret }}
      key: password
- name: DATABASE_URL
  value: {{ printf "postgresql://$(DATABASE_USER):$(DATABASE_PASSWORD)@%s-rw.%s.svc:5432/%s" $db .root.Release.Namespace $dbname | quote }}
{{- end -}}
{{- end -}}

{{/*
The paths a workload answers without the gateway: its version path and its
smoke test paths, which the Rollouts controller checks from outside the mesh.
Takes (dict "root" $ "component" "web"). Returns a JSON list.
*/}}
{{- define "trailhead.checkPaths" -}}
{{- $analysis := (index .root.Values .component).analysis -}}
{{- $paths := list $analysis.versionPath -}}
{{- range $analysis.smokeTest -}}
{{- $paths = append $paths .path -}}
{{- end -}}
{{- $paths | uniq | toJson -}}
{{- end -}}

{{/*
emptyDir volumes and mounts for a workload's writablePaths. The volume name is
the path, with every run of other characters made a dash. Takes the list of paths.
*/}}
{{- define "trailhead.writableVolumes" -}}
{{- range . }}
- name: {{ printf "writable-%s" (regexReplaceAll "[^a-z0-9]+" (lower .) "-" | trimAll "-") | trunc 63 | trimSuffix "-" }}
  emptyDir: {}
{{- end }}
{{- end -}}

{{- define "trailhead.writableMounts" -}}
{{- range . }}
- name: {{ printf "writable-%s" (regexReplaceAll "[^a-z0-9]+" (lower .) "-" | trimAll "-") | trunc 63 | trimSuffix "-" }}
  mountPath: {{ . }}
{{- end }}
{{- end -}}
