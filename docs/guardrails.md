# Guardrails and security controls

| Control | Where | Test |
| --- | --- | --- |
| Entra ID JWT at the edge; issuer, audience, expiry, role in the service | Front Door/APIM design, `auth.py` | `test_claim_checks`, `test_tampered_signature`, `test_alg_none_rejected` |
| Dev tokens refused in prod | `auth.verify` | `test_prod_refuses_dev_tokens` |
| Prompt-injection screen before the model | `guards.injection_hits` | 12 attack templates, 10 benign, 96/100 sets |
| PII redaction in outputs, spans, logs and exception text | `guards.redact`, `RedactingFilter`, `safe_error` | `test_log_filter_redacts_message_and_exception`, `log_leaks()==0` |
| Strict output schema, NaN and extra keys rejected | `llm.parse_triage` | `test_parse_triage_rejects` |
| Fail-safe to a human on bad output or model outage | `Triage` | `test_unparseable_model_output_goes_to_human`, `test_model_outage_goes_to_human` |
| Token and dollar cap per claim | `cost.TokenBudget` | `test_budget_escalates` |
| Request schema: extra fields, NaN, size limits | `app.ClaimIn` | `test_schema_rejects` |
| No keys in pods; key auth off on Azure services | Terraform, Helm | `test_terraform_hardening`, `test_values_hold_no_secret` |
| GitHub Actions deploy uses OIDC, not a client secret; ACR push and namespace-scoped AKS write | `.github/workflows/azure-deploy.yml`, Terraform | `test_deploy_uses_oidc_and_a_values_file`, `test_github_oidc_identity_is_least_privilege` |
| Container hardening | Helm template | `test_pod_hardening` |
| Session pods isolated from each other, from the claims namespace, and from the model except TCP 8080 | `deploy/helm/foundry-on-aks` | `test_session_policies_isolate_peers_and_allow_the_model` |
| Session identity has no Azure data-plane role; dev Foundry identity has none either | Terraform | `test_terraform_identities_and_pools_follow_claims_split` |
| Supply chain: pinned actions, Trivy, cosign keyless, gitleaks, CodeQL | workflows | `test_actions_pinned_to_sha`, `test_cosign_keyless` |
| Model key never committed | `.gitignore`, `.env.example`, gitleaks | `test_env_example_has_empty_secrets`, `test_ci_has_no_model_key` |
