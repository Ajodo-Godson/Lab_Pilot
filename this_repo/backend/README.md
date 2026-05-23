# LabPilot Backend (Person 1)

FastAPI service on port `:8000`. Owns the AI core: intake, 5 jurisdiction agents,
test plan, 5 report agents, and the final PDF assembler.

## Architecture

```
P3 frontend ──REST──> :8000 ──┐
                              ├── Gemini 3.5 Flash  (intake, 5 jurisdictions, test plan, 5 report sections)
                              └── Antigravity managed agent (PDF assembler — with local fallback)
```

We use **direct Gemini 3.5 Flash** for the 11 fast/cheap calls and the
**Antigravity managed agent** for the report assembly step that benefits from
Code Execution. The local PDF builder (`pdf_builder.py`) is a deterministic
fallback so the demo never breaks if Antigravity is throttled or slow.

## Endpoints (per LABPILOT_V4 contract)

```
POST /api/projects                       create
POST /api/projects/{id}/scope            run intake + 5 jurisdictions + test plan
POST /api/projects/{id}/report/generate  run 5 sections + assemble PDF
GET  /api/projects/{id}/events           SSE stream of agent events
GET  /api/projects/{id}/report           {pdf_base64, summary}

GET  /health                             liveness
GET  /api/projects/{id}/state            debug
```

## Run it

```powershell
# from this_repo/backend
.\venv\Scripts\python.exe -m uvicorn main:app --port 8000
```

Then in another terminal, run the fake P3 client end-to-end smoke test:

```powershell
.\venv\Scripts\python.exe fake_p3_client.py
# writes outputs/<project_id>.pdf
```

## Modes (set in `this_repo/.env`)

| Variable | Effect |
|---|---|
| `MOCK_AGENTS=true` | Skip Gemini entirely. Deterministic stub responses. Useful for testing wiring. |
| `USE_MANAGED_AGENTS=true` | Use Antigravity for the report assembler. Set `false` to skip even trying. |
| `GEMINI_MODEL=gemini-3.5-flash` | Required. Hackathon track mandates 3.5 Flash. |

## File map

```
backend/
├── main.py                  # FastAPI app, lifespan, endpoints, SSE
├── orchestrator.py          # per-project pipeline driver
├── gemini_client.py         # google-genai client + agent registration
├── agent_runtime.py         # invoke_agent() — routes to mock / Flash / Antigravity
├── pdf_builder.py           # deterministic ReportLab + matplotlib fallback
├── models.py                # Pydantic schemas
├── cache_loader.py          # one-time agent provisioning
├── fake_p3_client.py        # end-to-end smoke test
├── agents/
│   ├── intake.py            # BOM -> DeviceProfile
│   ├── jurisdiction.py      # 5 parallel jurisdiction analysts
│   ├── test_plan.py         # cert matrix -> structured test plan
│   └── report.py            # 5 parallel sections + assembler+ fallback
└── skills/
    ├── fcc.md  eu.md  ca.md  jp.md  br.md  # regulatory reference docs
```

## SSE event schema

Frontend left panel reads these from `/events`:

```
agent_start    {agent, message}
agent_complete {agent, output}
phase_complete {phase, summary}
report_ready   {download_url}
```

`agent` values match `LABPILOT_V4`: `intake`, `jurisdiction_{fcc|eu|ca|jp|br}`,
`test_plan`, `report_{setup|measurement|citer|narrator|compliance}`,
`report_assembler`.
