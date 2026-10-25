{{- define "ca.labels" -}}
app.kubernetes.io/name: claims-agent
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
