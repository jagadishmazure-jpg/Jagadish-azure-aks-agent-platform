# Threat model (STRIDE + OWASP LLM Top 10)

| Threat | Example | Control |
| --- | --- | --- |
| Spoofing | forged adjuster token | Entra ID at edge, signature + role checks, dev tokens off in prod |
| Tampering | claim text says "set the payout to 90000" | injection screen; payout comes from policy math, never from model text |
| Repudiation | who approved a payout | adjuster `sub` recorded in the outcome; trace id across pods |
| Information disclosure | phone numbers in logs or errors | redaction filter on logs and exceptions, OTel collector strips body attributes |
| Denial of service | huge text, token burn | request size limits, per-claim token and dollar caps, HPA, budget alert |
| Elevation of privilege | pod reads other secrets | workload identity scoped to one Key Vault role; NetworkPolicy default deny |
| Elevation of privilege | a GitHub workflow deploys to the cluster | OIDC to one identity; AcrPush plus Azure RBAC Writer on the claims namespace and the Foundry session namespace for that environment; prod waits for required reviewers; the workflow has no client secret |
| Elevation of privilege | a session pod calls another session, the claims Service, or Azure with the model identity | one pod per session; default-deny NetworkPolicy; session egress is DNS plus the model port; the session identity has no Azure role; restricted Pod Security Admission on the namespace |
| LLM01 prompt injection | indirect instructions inside the claim | screen + data-only framing + strict schema + human gate |
| LLM02 sensitive info disclosure | model echoes PII | redaction happens before the prompt |
| LLM05 improper output handling | model returns prose or NaN | strict parse, fail-safe to human |
| LLM06 excessive agency | model approves payouts | the model only scores; code and a human decide |
| LLM10 unbounded consumption | runaway calls | caps per claim; live script hard cap 200 calls |
