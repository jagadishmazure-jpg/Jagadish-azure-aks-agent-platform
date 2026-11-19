{{- define "foa.labels" -}}
app.kubernetes.io/name: foundry-on-aks
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: foundry-on-aks
{{- end -}}

{{- define "foa.image" -}}
{{- if .digest -}}
{{- printf "%s@%s" .repository .digest -}}
{{- else -}}
{{- printf "%s:%s" .repository .tag -}}
{{- end -}}
{{- end -}}

{{- define "foa.modelSelector" -}}
app.kubernetes.io/name: foundry-on-aks
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: model
{{- end -}}
