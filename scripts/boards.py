"""Render results/evidence_board.png and docs/architecture.png from results/metrics.json."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
M = json.loads((ROOT / "results" / "metrics.json").read_text())


def board() -> None:
    fig, ax = plt.subplots(2, 3, figsize=(15, 8.5))
    fig.suptitle("Northfield Mutual claims agents on AKS: evidence board (SIMULATED / SYNTHETIC, stub model)", fontsize=13, weight="bold")
    o = M["claims_run"]["outcomes"]
    a = ax[0, 0]
    a.barh(list(o), list(o.values()), color="#4c72b0")
    a.set_title(f"Outcomes, {M['claims_run']['claims']} synthetic claims")
    for i, v in enumerate(o.values()):
        a.text(v, i, f" {v}", va="center")
    a = ax[0, 1]
    shared, local = M["claims_run"]["trace_continuity"], M["pod_kill_baseline_pod_local_storage"]["trace_continuity"]
    a.bar(["shared checkpoints", "pod-local disk"], [shared * 100, local * 100], color=["#55a868", "#c44e52"])
    a.set_ylim(0, 110)
    a.set_title("Paused claims finished on another pod\nafter pod kill, same trace id (%)")
    for i, v in enumerate([shared * 100, local * 100]):
        a.text(i, v + 2, f"{v:.0f}%", ha="center")
    a = ax[0, 2]
    inj = M["injection"]
    a.bar(["attacks blocked", "benign blocked"], [inj["block_rate"] * 100, inj["false_positive_rate"] * 100], color=["#55a868", "#dd8452"])
    a.set_ylim(0, 110)
    a.set_title(f"Injection screen ({inj['attacks']} attacks, {inj['benign']} benign)")
    for i, v in enumerate([inj["block_rate"] * 100, inj["false_positive_rate"] * 100]):
        a.text(i, v + 2, f"{v:.0f}%", ha="center")
    a = ax[1, 0]
    rb = M["rollback_simulated"]
    a.bar(["p50", "p95", "max"], [rb["p50_s"], rb["p95_s"], rb["max_s"]], color="#8172b2")
    a.set_title(f"Canary auto-rollback time, s ({rb['trials']} simulated bad releases)")
    for i, v in enumerate([rb["p50_s"], rb["p95_s"], rb["max_s"]]):
        a.text(i, v + 2, f"{v}", ha="center")
    a = ax[1, 1]
    c = M["cost"]
    a.axis("off")
    a.text(0, 0.85, "Cost per request (stub token estimate x list price)", weight="bold")
    a.text(0, 0.6, f"${c['per_request_usd']:.6f} per claim", fontsize=16)
    a.text(0, 0.42, f"${c['per_1000_requests_usd']} per 1,000 claims")
    a.text(0, 0.24, f"prices as of {c['prices_as_of']}; cap $0.01 / 4,000 tokens per claim")
    a = ax[1, 2]
    p = M["pii_leaks"]
    a.bar(list(p), list(p.values()), color="#937860")
    a.set_ylim(0, 5)
    a.set_title("Raw PII found in outputs / spans / logs+errors")
    for i, v in enumerate(p.values()):
        a.text(i, v + 0.1, str(v), ha="center")
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "evidence_board.png", dpi=110)


BOXES = [
    # x, y, w, h, title, body, colour, fix-number
    (0.2, 7.6, 3.0, 1.1, "Users / partner systems", "web, adjuster console", "#eeeeee", None),
    (3.6, 7.6, 3.6, 1.1, "Front Door + WAF", "Entra ID sign-in, JWT checked at edge", "#ffe7c2", 1),
    (7.6, 7.6, 4.0, 1.1, "GitHub Actions -> GHCR/ACR", "test, Trivy, cosign keyless, kind smoke", "#ffd6d6", 5),
    (
        3.6,
        5.3,
        3.6,
        1.7,
        "AKS (claims namespace)",
        "claims-agent pods (MAF 1.x)\nHPA, PDB, NetworkPolicy\nArgo Rollouts canary",
        "#d9e8ff",
        None,
    ),
    (7.6, 5.3, 4.0, 1.7, "Argo CD (GitOps)", "Helm chart from git\nself-heal, auto rollback\non failed analysis", "#ffd6d6", 5),
    (0.2, 5.3, 3.0, 1.7, "Key Vault + workload ID", "no keys in pods or images\nCSI secret sync", "#e2f5e2", 2),
    (
        0.2,
        2.6,
        3.0,
        2.0,
        "AI layer",
        "Azure OpenAI gpt-4o-mini\nFoundry project for evals\ninjection screen, PII redaction\ntoken + cost caps",
        "#efe0ff",
        4,
    ),
    (
        3.6,
        2.6,
        3.6,
        2.0,
        "Data (one store each)",
        "Service Bus: jobs + events\nPostgres + pgvector:\nstate, checkpoints, vectors",
        "#fff6c2",
        3,
    ),
    (
        7.6,
        2.6,
        4.0,
        2.0,
        "Observability",
        "OpenTelemetry traces\nPrometheus metrics, Grafana\nAzure Monitor / Log Analytics",
        "#e8e8e8",
        None,
    ),
    (
        0.2,
        0.4,
        11.4,
        1.6,
        "Terraform (validate only in CI)",
        "AKS, ACR, Key Vault, identity, Service Bus, Postgres flexible + pgvector, Azure OpenAI, Foundry, Front Door WAF, Monitor, budget alert",
        "#f4f4f4",
        None,
    ),
]
FIXES = {
    1: "identity + front door",
    2: "secrets out of code",
    3: "one queue, one store (no queue+log platform, no 2nd search engine)",
    4: "AI layer: model, evals, guards, caps",
    5: "release safety: scan, sign, canary, rollback",
}


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.set_xlim(0, 15.5)
    ax.set_ylim(0, 9)
    ax.axis("off")
    ax.set_title("Northfield Mutual (fictional) claims agent platform: improved production stack", fontsize=14, weight="bold")
    for x, y, w, h, t, b, col, fix in BOXES:
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05", fc=col, ec="#333"))
        ax.text(x + 0.1, y + h - 0.3, t, weight="bold", fontsize=10)
        ax.text(x + 0.1, y + h - 0.55, b, fontsize=8.5, va="top")
        if fix:
            ax.text(
                x + w - 0.25,
                y + h - 0.25,
                str(fix),
                fontsize=11,
                weight="bold",
                color="white",
                ha="center",
                va="center",
                bbox={"boxstyle": "circle", "fc": "#c44e52"},
            )
    arrows = [
        ((3.2, 8.15), (3.6, 8.15)),
        ((5.4, 7.6), (5.4, 7.0)),
        ((9.6, 7.6), (9.6, 7.0)),
        ((7.6, 6.1), (7.2, 6.1)),
        ((3.6, 6.1), (3.2, 6.1)),
        ((4.4, 5.3), (2.6, 4.6)),
        ((5.4, 5.3), (5.4, 4.6)),
        ((6.6, 5.3), (8.4, 4.6)),
    ]
    for a, b in arrows:
        ax.annotate("", b, a, arrowprops={"arrowstyle": "->", "lw": 1.4})
    ax.text(11.9, 8.5, "Gaps fixed vs the common stack", weight="bold")
    for i, (k, v) in enumerate(FIXES.items()):
        ax.text(11.9, 8.0 - i * 0.75, f"{k}. {v}", fontsize=9, wrap=True)
    fig.savefig(ROOT / "docs" / "architecture.png", dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    board()
    architecture()
    print("wrote results/evidence_board.png docs/architecture.png")
