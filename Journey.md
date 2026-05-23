# LabPilot — Build Journey

A chronological log of how LabPilot went from "what should I build?" to a
working Phase 1 + Phase 2 pipeline running on four mock devices. Written
during a Google I/O hackathon prep cycle (Gemini 3.5 Flash track).

---

## 1. The "build for what you know" pivot

I'm a graduating college senior heading to the Google I/O Hackathon at
Shack15 SF. Prizes: $7.5k / $5k / $2.5k, plus a $5k bonus for "best use of
managed agents." Six hours to build, three minutes to pitch, must use
**Gemini 3.5 Flash**, can't be a wrapper or land on the banned-projects
list (no AI medical advice, no chatbots, no basic RAG).

Early ideas got killed for being saturated or unfit:

- AI recruiting tools — done to death
- Real estate financial modeling — niche, hard to demo
- AI debt collections — regulated, slow
- Document analyzers — wrapper territory
- "Tools for college seniors" — too generic

Looking at past winners (Medkit, Wrench Board, Maieutic), the pattern was
consistent: **domain expertise + AI = winning combination**. Pure SF
hackathon engineers don't have niche industry knowledge. That's the moat.

So I went through what I actually know:

- BCG consulting (analytical, but generic)
- Real estate financial modeling (taught it 5x to mentees)
- **UL Solutions, sophomore summer — SAR (Specific Absorption Rate)
  testing of wireless devices in the compliance lab**

The third one is the wedge. Every phone, watch, earbud, and IoT gadget
that ships in the US needs FCC certification, and most of that work
happens in dark RF chambers where engineers run lab tests for weeks.
Almost no one at the hackathon will have walked into one.

---

## 2. Competitive research before committing

Before locking in, I checked who else was attacking the
Testing-Inspection-Certification (TIC) industry with AI:

- **Calibre** (London, ex-Palantir, $3.3M pre-seed May 2026):
  broad TIC, "AuditorOS" product. https://www.calibre.ac/
- **Scope** (London, $20M Series A May 2026, Index Ventures): inspection
  workflow software
- **Seamflow** ($4.5M seed Feb 2026): medical / industrial TIC

None of them focus on RF, wireless, or SAR. UL Solutions itself
($3.05B revenue, NYSE: ULS) has compliance-management software (ULTRUS)
but **no AI agent product for actual test execution or report drafting.**

That left a clean wedge: an AI agent for FCC / CE / IC wireless and SAR
certification report drafting.

---

## 3. Product design — LabPilot

The full wireless certification workflow, broken into phases:

| Phase | Stage | LabPilot? |
|---|---|---|
| 1 | Intake (client email + spec) | ✅ |
| 2 | Pre-test scoping + quoting | ✅ |
| 3 | Test plan generation | ⏳ planned |
| 4 | Test script generation | ❌ scrapped (vendor-proprietary R&S / SPEAG schemas) |
| 5 | Robotic test execution | ⛔ out of scope (physical) |
| 6 | Post-test ingestion + validation | ⏳ planned |
| 7 | Final report drafting (200 pages) | ⏳ planned |
| 8 | TCB negotiation | ⛔ out of scope |

Tagline: **"AI engineer that runs a wireless certification project
end-to-end except the robot and the TCB negotiation."**

### Team-of-3 split for hackathon day

- **Person A — The Brain**: Phases 2 / 3, all skill files
- **Person B — The Hands**: Phases 6 / 7, managed agents sandbox for
  PDF + chart generation
- **Person C — The Face**: Phase 1, frontend, demo polish

### Tech stack

- Python + `google-genai` SDK
- **Gemini 3.5 Flash** — 1M context, structured output, function calling,
  parallel sub-agents (verified via web research). Currently using
  `gemini-2.5-flash` on personal account; swap when hackathon credits
  arrive.
- **Managed Agents** sandbox for Phase 7 (matplotlib charts, ReportLab
  PDF assembly) — this is where the $5k bonus gets earned
- Pydantic for typed data shapes between phases

---

## 4. Phase 0 — sanity check on a real device

Before building anything, I needed to confirm Gemini could actually read
a wireless test report and pull structured data from it. Steps:

1. Got an API key at https://aistudio.google.com/apikey
2. Pulled a real Apple iPhone SAR test report from the public FCC EAS
   database: https://apps.fcc.gov/oetcf/eas/reports/GenericSearch.cfm
   (FCC ID `BCG-E3996A`, ~4.3 MB PDF)
3. `python -m venv venv`, installed `google-genai` and `python-dotenv`
4. Wrote `test.py` — single Gemini call, structured-output schema, dump
   the result

It worked first try. Returned device name, FCC ID, applicant, full
frequency band list (GSM through 5G NR), modulation modes, lab name —
all clean JSON.

Setup gotchas worth remembering:
- Windows username has a space ("Mr. Paul"), so PowerShell paths need
  quotes
- Two `.env` files existed; the labpilot one had a typo
  (`GEMIN_API_KEY` with spaces around `=`)
- I pasted my API key into PowerShell once. Rotated it.

---

## 5. Phase 1 + Phase 2 — the working pipeline

Built the real thing. Files:

- `models.py` — Pydantic shapes: `Project`, `DeviceClassification`,
  `TestRequirement`, `CertificationMatrix`, `QuoteLine`, `Quote`
- `gemini.py` — shared client wrapper with **429 retry-with-backoff**
  that parses the server's suggested `retryDelay`
- `config.py` — model name, lab pricing constants, paths
- `phase1_intake.py` — reads email + spec, structured extraction →
  `Project` with ID like `PRJ-XXXXXXXX`
- `phase2_scoping.py` — three steps:
  1. `classify_device` reads spec + classification skill
  2. `run_jurisdictions_parallel` fans out FCC + ISED sub-agents via
     `ThreadPoolExecutor`, each loading its own skill files
  3. `build_quote` is **deterministic Python** (lab hours × rate +
     admin fee) — no LLM for the math
- `skills/` — 5 markdown skill files (device-classification,
  fcc-part-15, fcc-kdb-447498-sar, ised-rss-247, ised-rss-102-sar)
- `run.py` — single end-to-end runner

First successful run on the Apple SAR report:

| Field | Value |
|---|---|
| Project | PRJ-AF4FDA79 |
| Device | Apple iPhone (smartphone) |
| Tests | 41 across FCC + ISED |
| Quote | $147,600 |
| Timeline | 9 weeks |

Real regulatory citations in the matrix. Looked legit.

---

## 6. The bias check — switching from SAR reports to BOMs

Then I caught myself. Using a finished **SAR report** as the input spec
is cheating: the FCC ID is already labeled, the equipment class is
stated, the SAR test results are even there. Of course the agent can
"figure out" the scope — the answers are in the input.

Real life: a client emails you a **BOM (bill of materials)** at design
freeze, weeks before any test happens. No FCC ID, no test data, just
hardware.

So I built four mock BOMs in markdown (Gemini reads MD natively):

| Device | Why it's there |
|---|---|
| **FitTrack Mini** | Wrist-worn BLE-only fitness band — simplest case, tests body-worn SAR detection |
| **EchoNote Speaker** | Wi-Fi 6 + BLE smart speaker, NOT body-worn — tests the "MPE not SAR" branch |
| **MeshNode Gateway** | Sub-GHz LoRa industrial fixed install — tests jurisdiction differences |
| **PulsePro Watch** | LTE + Wi-Fi 6 + BLE + UWB + NFC smartwatch — kitchen-sink stress test |

Updated `phase1_intake.py` and `phase2_scoping.py` to accept either
PDF or markdown via a `_spec_part()` helper. Built `run_all_boms.py`
to run all four sequentially with 70-second cooldowns to stay under
the free-tier 5 RPM limit.

### Results — pipeline survives the honesty check

| Case | Project | Tests | Jurisdictions | Quote | Weeks |
|---|---|---:|---:|---:|---:|
| FitTrack Mini | PRJ-A0A7B5E5 | 13 | 2 | $37,100 | 6 |
| EchoNote Speaker | PRJ-E22C2A67 | 33 | 2 | $70,800 | 6 |
| MeshNode Gateway | PRJ-257DC56E | 25 | 2 | $21,400 | 6 |
| PulsePro Watch | ❌ blocked | — | — | — | — |

Three of four ran cleanly. The agent correctly identified:
- FitTrack as portable + body-worn (full SAR scope)
- EchoNote as not portable (MPE only, no SAR), still includes DFS
  testing for 5 GHz Wi-Fi
- MeshNode as fixed install (simpler LoRa scope, lowest cost)

PulsePro hit `429 RESOURCE_EXHAUSTED` after 4 retries — the free tier's
**20 requests/day** ceiling for `gemini-2.5-flash`. Not a code bug.

### Resumable runner

Updated `run_all_boms.py` so it can be re-run safely:
- Fully cached cases (project + matrix + quote on disk) → skip
- Partial cases (only project on disk) → reuse Phase 1, run Phase 2
- New cases → run both phases

This means once billing is enabled or quota resets, finishing PulsePro
is one command.

---

## 7. Where it stands now

**Done**

- Phase 1 (intake) — working
- Phase 2 (scoping + quote) — working
- 3 mock BOMs through the full pipeline with diverse, sensible scopes
- 5 skill files covering FCC Part 15, FCC KDB 447498 SAR, ISED RSS-247,
  ISED RSS-102 SAR, device classification
- Resumable multi-case runner

**Still to build**

- **Phase 3** — test plan generation. Reads `_matrix.json`, fans out
  one parallel sub-agent per test (~30 sections), produces a
  structured test plan with frequencies, power levels, body positions,
  and citations.
- **Phase 6** — post-test validation. Ingests synthetic SPEAG DASY8 SAR
  measurement CSVs, validates measurement geometry and pass/fail.
- **Phase 7** — final report drafting. 200-page certification report
  via Managed Agents sandbox: matplotlib charts + ReportLab/WeasyPrint
  PDF. **Verifier swarm pattern** (independent re-read of every claim)
  is the load-bearing anti-hallucination feature. This is the
  highest-value Flash 3.5 use case — 400-700 sub-agent calls per
  report — the fan-out math that finally justifies the model spend.

**Open decisions**

- Free-tier quota → enable billing or wait for UTC midnight reset
- When to swap `gemini-2.5-flash` → `gemini-3.5-flash` (after credits
  arrive)

---

## 8. What I learned along the way

- **Build for what you know**. Three winners I studied all had this in
  common. The moat in a 6-hour hackathon isn't the code — it's the
  domain context that lets your demo land.
- **Search before pitching ideas**, not after. The first round of
  ideas was lazy because I hadn't checked the competitive landscape.
- **Catch your own biases.** The SAR-report-as-spec setup looked great
  until I realized the answers were already in the input. The pipeline
  passing on real BOMs is the actual proof point.
- **Cap the LLM, not the math.** Phase 2's quote calculation is
  deterministic Python. Pricing is not where you want hallucinations.
- **Failures during a run are usually rate limits, not bugs.** Read
  the error before "fixing" anything.

---

## File map

```
labpilot/
├── config.py              # model, paths, pricing
├── gemini.py              # shared client + 429 retry
├── models.py              # Pydantic shapes between phases
├── phase1_intake.py       # email + spec → Project
├── phase2_scoping.py      # classify → fan out → quote
├── run.py                 # single end-to-end runner
├── run_all_boms.py        # multi-case resumable runner
├── test.py                # Phase 0 sanity check
├── inputs/
│   ├── bom_*.md           # 4 mock BOMs
│   └── email_*.txt        # 4 mock client emails
├── skills/
│   ├── device-classification.md
│   ├── fcc-part-15.md
│   ├── fcc-kdb-447498-sar.md
│   ├── ised-rss-247.md
│   └── ised-rss-102-sar.md
├── outputs/               # generated PRJ-*_project / _matrix / _quote JSONs
└── sar_report.pdf         # public FCC filing used for Phase 0
```
