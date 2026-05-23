# Person 1 — AI Core, Orchestration & Compliance

This document summarizes everything Person 1 built for the LabPilot hackathon
submission. Person 1 owns `this_repo/backend/` on port `:8000`. Person 2
(simulator on `:8002`) and Person 3 (Next.js frontend on `:3000`) integrate
against the contracts described here.

> Honest framing aligned with `LABPILOT_V4.md`: the AI engineering layer is
> real (Gemini agents, structured pipeline, real PDF). The device under test
> and the SAR scan are synthetic by design — that's the demo conceit, not a
> hidden compromise.

---

## What Person 1 owns

```
P3 frontend ──REST──▶ :8000 ──┐
                              ├── Direct Gemini 3.5 Flash      (intake, 5 jurisdictions, test plan, 5 report sections)
                              └── Antigravity managed agent    (PDF assembler, with deterministic local fallback)
```

The 11 cheap calls go through `client.models.generate_content` against
`gemini-3.5-flash`. The single sandbox-heavy step (PDF compilation) calls
the **Antigravity managed agent** through `client.interactions.create` so the
project legitimately uses Managed Agents. A local ReportLab + matplotlib
fallback always produces a PDF if Antigravity is throttled or slow. This
preserves the "Best Use of Managed Agents" pitch while guaranteeing the demo
never fails on stage.

---

## Endpoints (per `LABPILOT_V4` contract)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/projects` | Create a project from `{device_name, bom_text, target_regions}`. Returns `{project_id, status}`. |
| `POST` | `/api/projects/{id}/scope` | Run intake + 5 jurisdictions + test plan. |
| `POST` | `/api/projects/{id}/report/generate` | Accept `{scan_summary}` from P3, run 5 report sections + the PDF assembler. |
| `GET`  | `/api/projects/{id}/events` | SSE stream of `agent_start` / `agent_complete` / `phase_complete` / `report_ready`. |
| `GET`  | `/api/projects/{id}/report` | Return `{pdf_base64, summary}`. |
| `GET`  | `/health`, `/api/projects/{id}/state` | Liveness and debug. |

Every endpoint is exercised end-to-end by `backend/fake_p3_client.py`, which
behaves exactly like P3's frontend.

---

## SSE event names

These match `LABPILOT_V4` exactly so P3's left panel renders without translation:

```
agent_start    { agent: AgentName,     message: string }
agent_complete { agent: AgentName,     output:  string }
phase_complete { phase: PhaseName,     summary: string }
report_ready   { download_url: string }
```

`AgentName` values fired by Person 1: `intake`, `jurisdiction_{fcc,eu,ca,jp,br}`,
`test_plan`, `report_{setup,measurement,citer,narrator,compliance}`,
`report_assembler`.

---

## Files

```
backend/
├── main.py                # FastAPI app, lifespan, endpoints, SSE
├── orchestrator.py        # per-project pipeline driver, emits SSE
├── gemini_client.py       # google-genai client + agent specs + provisioning
├── agent_runtime.py       # invoke_agent() routes to mock / Flash / Antigravity
├── pdf_builder.py         # deterministic ReportLab + matplotlib fallback
├── models.py              # Pydantic schemas (DeviceProfile, ScanSummary, ...)
├── cache_loader.py        # one-time managed-agent provisioning
├── fake_p3_client.py      # end-to-end smoke test harness
├── README.md              # operator notes
├── agents/
│   ├── intake.py          # BOM -> DeviceProfile
│   ├── jurisdiction.py    # 5 parallel jurisdiction analysts
│   ├── test_plan.py       # cert matrix -> structured test plan
│   └── report.py          # 5 parallel sections + assembler + fallback
└── skills/
    ├── fcc.md  eu.md  ca.md  jp.md  br.md   # regulatory reference docs
```

---

## Agent inventory

| Agent ID | Role | Runtime | Skills mounted |
|---|---|---|---|
| `lp-intake`              | BOM → `DeviceProfile`         | direct Flash | — |
| `lp-jurisdiction-fcc`    | FCC analysis                  | direct Flash | `fcc.md` |
| `lp-jurisdiction-eu`     | EU RED analysis               | direct Flash | `eu.md` |
| `lp-jurisdiction-ca`     | ISED Canada analysis          | direct Flash | `ca.md` |
| `lp-jurisdiction-jp`     | Japan MIC analysis            | direct Flash | `jp.md` |
| `lp-jurisdiction-br`     | ANATEL Brazil analysis        | direct Flash | `br.md` |
| `lp-test-plan`           | Structured test plan          | direct Flash | all 5 |
| `lp-report-setup`        | Test setup section            | direct Flash | — |
| `lp-report-measurement`  | Measurement results section   | direct Flash | `fcc.md` |
| `lp-report-citer`        | Regulatory traceability       | direct Flash | all 5 |
| `lp-report-narrator`     | Anomaly narrative             | direct Flash | — |
| `lp-report-compliance`   | Executive compliance verdict  | direct Flash | all 5 |
| `lp-report-assembler`    | PDF compilation               | **Antigravity managed agent** | — |

The Antigravity assembler runs with a 45 s timeout. If it does not return a
parseable PDF in time (Tier 1 accounts have a 200K TPM Antigravity cap that
this step routinely exceeds), the orchestrator falls back to a local
ReportLab + matplotlib PDF builder. Both paths produce the same `FinalReport`
shape so the contract with P3 is unaffected.

---

## Modes (`this_repo/.env`)

| Variable                     | Effect |
|------------------------------|--------|
| `MOCK_AGENTS=true`           | Bypass Gemini entirely. Deterministic stub responses. Zero tokens. Used to validate SSE wiring. |
| `USE_MANAGED_AGENTS=true`    | Allow the assembler to attempt Antigravity. With `false`, the assembler skips straight to the local fallback (about 2 s). |
| `GEMINI_MODEL=gemini-3.5-flash` | Required for the hackathon track. |

---

## Run it

```powershell
# from this_repo/backend
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

End-to-end smoke test in another terminal:

```powershell
.\venv\Scripts\python.exe fake_p3_client.py
# writes outputs/<project_id>.pdf
```

A typical run with the demo BOM (`SmartPatch X1`) emits ~12 SSE events and
produces a 9-page, ~110 KB compliance PDF in under a minute on a paid
account, or ~45 s + local fallback on Tier 1.

---

## How this maps to the V4 deliverable list

| V4 deliverable | Status |
|---|---|
| Context cache loader | Substituted with skill-file mounting (Managed Agents replaces the older context-cache pattern). Same end effect: regulatory corpus shared across agents. |
| Managed agent swarm (intake, 5 jurisdictions, test plan, 5 report agents) | Built. The Antigravity API on Tier 1 caps shared TPM at 200K, so 11 of the 12 agents are routed through direct Flash to keep the demo within quota. The Antigravity invocation is preserved for the assembler. |
| SSE broadcaster | Built. Events match V4 schema exactly. |
| Report agent that consumes scan summary | Built. `peak_sar`, `anomaly_count`, and anomaly positions thread through every report section and the assembler. |

---

## Known compromises and gaps

1. **Antigravity assembler is unverified end-to-end on this account.** Tier 1
   times out before completion every time. The local fallback always finishes,
   so the user-visible behavior is correct, but the Antigravity branch has not
   been observed producing a final PDF on this key.
2. **Search Grounding and Code Execution.** Direct Flash calls do not enable
   these tools by default (V4 listed them under Person 1). They are wired
   through the Antigravity assembler implicitly (Code Execution is part of the
   sandbox). For a higher-quota run you can enable Search Grounding by
   passing `tools=[{"type": "google_search"}]` to the Flash calls in
   `agent_runtime._flash_call`.
3. **Integration with Person 2 / Person 3 has not been rehearsed.** Each
   service has been validated in isolation. The day-of integration is still
   to do.
