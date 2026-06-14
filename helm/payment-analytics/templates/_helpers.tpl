{{/* Common naming + labels */}}
{{- define "pa.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "pa.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s" (include "pa.name" .) -}}
{{- end -}}
{{- end -}}

{{- define "pa.labels" -}}
app.kubernetes.io/part-of: payment-analytics
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/* Secret name: existing one if given, else the chart-managed one */}}
{{- define "pa.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
platform-secrets
{{- end -}}
{{- end -}}

{{/* Resolve an image: explicit value wins, else <registry>/<name>:<tag> */}}
{{- define "pa.image" -}}
{{- $explicit := index . 0 -}}
{{- $name := index . 1 -}}
{{- $root := index . 2 -}}
{{- if $explicit -}}
{{- $explicit -}}
{{- else -}}
{{- printf "%s/%s:%s" $root.Values.image.registry $name $root.Values.image.tag -}}
{{- end -}}
{{- end -}}
