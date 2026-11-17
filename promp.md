# DEV PROMPT: RO Design Web App (Vontron-compatible)

## 0. Your role and ground rules
You are a senior full-stack engineer. Build a web app that reproduces the calculations of
**Vontron RO Design Software Ver 6.1**, using the confirmed logic in this document.

Rules:
1. **Never invent constants.** Every constant lives in `backend/app/config/*.json`.
   Items marked **[PROVISIONAL]** must be config-driven and tagged `# TODO-CONFIRM`.
2. **Write the golden tests (Section 10) first.** The calculation code must pass them.
3. **All calculations run in the Python backend.** The React frontend only collects input,
   calls the API and displays results.
4. **No database.** No SQL, NoSQL or ORM. State lives in the browser (persisted to
   localStorage). Projects are saved and loaded as `.json` files the user downloads or uploads.
5. Store everything internally in **mg/L, °C, m³/h, bar**. Convert units only for display.
6. **Always recompute TDS from the ions.** Never store TDS separately. (Vontron has a bug
   where a stale TDS is reloaded from file; do not replicate it.)
7. Use simple, plain-English labels and messages in the UI.

---

## 1. Tech stack
| Layer | Choice |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Routing | React Router v6 |
| State | Zustand, with the `persist` middleware (localStorage) |
| UI | Tailwind CSS + shadcn/ui (or MUI) |
| Charts | Recharts |
| Backend | Python 3.11 + FastAPI + Pydantic v2 |
| Math | numpy, scipy (root finding for the design engine) |
| Reports | ReportLab (PDF), openpyxl (Excel) |
| Tests | pytest (backend), Vitest + React Testing Library (frontend) |
| Run | `docker-compose` with 2 services (frontend, backend); also runnable locally |

---

## 2. Pages (5 total)
Top navigation tabs, in this order. Toolbar actions: **New**, **Open project (.json)**,
**Save project (.json)**.

1. **Water Analysis**: Section 4
2. **Scaling**: Section 5
3. **Design System**: Section 6
4. **Dashboard**: Section 7
5. **Report**: Section 8

Every page has a **Messages** panel. Warnings are shown in red.

---

## 3. Project data model (single JSON object)
```json
{
  "version": "1.0",
  "project": { "name": "", "date": "YYYY-MM-DD", "designedBy": "Untitled", "company": "Untitled" },
  "water": {
    "inputUnit": "mg/L | ppmCaCO3 | meq/L",
    "specifyIndividualSolutes": true,
    "tdsInput": null,
    "temperatureC": 25, "pH": 7.5,
    "waterType": "RO Permeate SDI < 1",
    "ions": { "Na":0,"Ca":0,"Mg":0,"K":0,"Ba":0,"Sr":0,"NH4":0,"B":0,
              "Cl":0,"CO3":0,"HCO3":0,"F":0,"NO3":0,"SO4":0,"SiO2":0 }
  },
  "scaling": {
    "recoveryPct": 15, "temperatureC": 25,
    "option": "none | ph_adjust | softening | antiscalant",
    "phAdjust": { "chemical": "H2SO4", "targetPH": 7.5 },
    "softening": { "caLeakage": 0.1, "mgLeakage": 0.1 }
  },
  "design": {
    "unitSet": "gpd_psi | gpm_psi | m3h_bar | m3d_bar",
    "recoveryPct": 15, "permeateFlow": 5, "feedTempC": 25, "foulingFactor": 0.85,
    "passes": [ { "stages": [ { "vessels": 1, "elementsPerVessel": 1, "elementModel": "LP22-8040",
                                "backPressure": 0 } ],
                  "sameElementInPass": true, "sameBackPressure": true } ],
    "pumpEfficiencyEnabled": false, "pumpEfficiencyPct": 80,
    "intakeBothEnds": false, "frontEndPct": 50,
    "recycle": { "enabled": false, "flow": 0 }
  },
  "results": { "water": {}, "scaling": {}, "design": {} }
}
```
`results` is a cache. On load, always recalculate.

---

## 4. Page 1: Water Analysis (✅ CONFIRMED against Vontron)

### 4.1 Ion constants (config `ions.json`)
| Ion | Charge | Eq. wt (for meq) | Factor to ppm CaCO3 | Mol. wt (for molarity) |
|---|---|---|---|---|
| Na | +1 | **23.00** | 2.18 | 22.990 |
| Ca | +2 | 20.04 | 2.50 | 40.078 |
| Mg | +2 | 12.15 | 4.12 | 24.305 |
| K | +1 | 39.10 | 1.28 | 39.098 |
| Ba | +2 | 68.67 | 0.73 | 137.327 |
| Sr | +2 | 43.81 | 1.14 | 87.62 |
| NH4 | +1 | 18.04 | 2.78 | 18.04 |
| B | 0 | n.a | n.a | 10.81 |
| Cl | −1 | 35.45 | 1.41 | 35.453 |
| CO3 | −2 | 30.00 | 1.67 | 60.008 |
| HCO3 | −1 | 61.02 | 0.82 | 61.017 |
| F | −1 | 19.00 | **2.66** | 18.998 |
| NO3 | −1 | 62.00 | 0.81 | 62.004 |
| SO4 | −2 | 48.03 | 1.04 | 96.06 |
| SiO2 | 0 | n.a | n.a | 60.08 |

### 4.2 Formulas
- `meq = mg/L ÷ EqWt`
- `ppmCaCO3 = mg/L × Factor`
- Reverse: `mg/L = meq × EqWt`, `mg/L = ppmCaCO3 ÷ Factor`
- Only the column of the selected input unit is editable. B and SiO2 show "n.a" in the
  other two columns.
- **TDS = Σ mg/L of all ions including SiO2, with Boron counted as boric acid:**
  `TDS = Σ(all ions except B) + B × 5.72`
- `Cations = Σ meq(Na, Ca, Mg, K, Ba, Sr, NH4)`, `Anions = Σ meq(Cl, CO3, HCO3, F, NO3, SO4)`
- `Balance = Cations − Anions`
- Imbalance warning text: `Warning:Ions out of Balance.`
  **[PROVISIONAL]** Show it when |Balance| ÷ max(Cations, Anions) > 5% (config).
  Observed: 10% warns; 0.1% does not.

### 4.3 Auto Balance
- If Anions > Cations: `Na += round(|Balance|, 1) × 23.00` ✅ confirmed (Vontron rounds the
  balance to 1 decimal before correcting).
- If Cations > Anions: `Cl += round(|Balance|, 1) × 35.45` **[PROVISIONAL]**
- Config flag `autoBalanceRoundTo1Decimal: true` (default true, to match Vontron).

### 4.4 "Specify Individual Solutes" unticked (TDS-only mode) ✅
- The TDS field becomes editable; all ion inputs are locked and set to 0, except:
- `Na = TDS × 0.393236`, `Cl = TDS × 0.606764`

### 4.5 Display
- mg/L, ppm CaCO3, meq: 2 decimals. Cations, Anions, Balance: 1 decimal.
- Temperature (1–45 °C) and pH (1–13) are validated.
- Water Type dropdown (exact list): RO Permeate SDI < 1; Well Water SDI < 3; Tap Water SDI < 3;
  Surface Supply SDI < 3; Surface Supply SDI < 5; Wastewater (MF/UF) SDI<3;
  Wastewater (Conventional) SDI<5; Seawater (MF/UF) SDI<3; Seawater (Conventional) SDI<5.

---

## 5. Page 2: Scaling

### 5.1 Inputs and layout
Recovery (%) and Temp (°C), option radio buttons (4), option-specific panel, and a
**Scale Calculation** button.
Result table: rows = pH, TDS, HCO3, CO3, CO2, LSI, Stiff & Davis Stability Index (S&DSI),
CaSO4 / BaSO4 / SrSO4 / CaF2 / SiO2 Saturation %. Columns = Feed | Adjusted Feed | Concentrate.
All values to 2 decimals.

### 5.2 Core formulas (✅ CONFIRMED)
- `CF = 1 ÷ (1 − Recovery/100)`
- Concentrate ion = AdjustedFeed ion × CF (all ions); `TDS_conc = TDS_adj × CF`
- `pH_conc = pH_adj + log10(CF)`
- `CO2 (mg/L) = HCO3 (mg/L) × 10^(6.3 − pH)`. No temperature dependence.
- `CO2_conc = CO2_adj` (CO2 passes through the membrane)
- CO3 is not calculated; show the entered value (× CF in the concentrate).

### 5.3 Ionic strength
`I = ½ × Σ (mg/L ÷ (MolWt × 1000)) × z²` over all charged ions (exclude B, SiO2 and CO2).
Concentrate: `I_conc = I_adj × CF`.
Molarity for ion products: `[X] = mg/L ÷ (MolWt × 1000)`.

### 5.4 S&DSI (✅ CONFIRMED, brackish range I = 0.02–0.13)
```
S&DSI = pH − pCa − pAlk − K
pCa  = −log10(Ca / 40078)
pAlk = −log10(HCO3 / 61017)
K    = 2.031 + 5.497·I − 9.12·I² − 0.024·(T − 25)
```
**[PROVISIONAL]** for I > 0.13 (seawater). Keep the coefficients in config.

### 5.5 LSI (standard formula, "behaviour B"; ✅ CONFIRMED at 25 °C)
```
pHs = 9.3 + A + B − C − D
A = (log10(TDS) − 1) / 10
B = −13.12 · log10(T + 273.15) + 34.55
C = log10(Ca × 2.50) − 0.4
D = log10(HCO3 mg/L)        # Vontron uses HCO3 directly, NOT converted to CaCO3
LSI = pH − pHs
```
If Ca ≤ 0 or HCO3 ≤ 0, display "N/A" (no CaCO3 scaling risk).
**[PROVISIONAL]** Vontron sometimes reports a lower LSI ("behaviour A", depending on edit
order). The temperature effect is not yet fully confirmed. Add a config flag
`lsiMode: "standard"` for a future alternative.

### 5.6 Saturation % (✅ CONFIRMED for this water; [PROVISIONAL] general form)
```
Ksp(I, T) = K · I^n · exp( E · (1/298.15 − 1/(T + 273.15)) )
Sat% = IonProduct / Ksp × 100
```
| Salt | Ion product | K | n | E |
|---|---|---|---|---|
| CaSO4 | [Ca][SO4] | 7.09e-4 | 0.4544 | 2150 |
| BaSO4 | [Ba][SO4] | 7.60e-9 | 0.8339 | 3146 |
| SrSO4 (TDS_conc ≤ 4000) | [Sr][SO4] | 6.52e-6 | 0.5715 | 634 |
| SrSO4 (TDS_conc > 4000) | [Sr][SO4] | 6.55e-7 | 0.4416 | 634 |
| CaF2 | [Ca][F]² | 4.31e-10 | 0.4785 | 1312 |

Config flag `replicateVontronSrSO4Jump: true` [PROVISIONAL, awaiting client decision].
For the Feed column, use the feed TDS to choose the SrSO4 branch.

### 5.7 Silica (✅ CONFIRMED)
```
Limit(pH, T) = Table(pH) × (T + 35.8) / 60.8
SiO2 Sat% = SiO2 / Limit × 100      # uses the column's own pH (feed or concentrate)
```
Table at 25 °C (pH → mg/L), with linear interpolation; clamp outside the range:
5.0→156.9, 5.3→152.6, 5.5→149.7, 5.8→145.4, 6.0→142.6, 6.3→138.3, 6.5→135.4, 6.8→131.1,
7.0→126.1, 7.3→126.7, 7.6→126.1, 7.8→127.4, 7.9→131.7, 8.0→138.2, 8.2→153.2, 8.3→162.2,
8.42→175.4, 8.5→184.5, 8.8→225.5, 9.0→258.1, 9.3→315.2, 9.5→358.4, 9.8→432.0,
10.0→486.6, 10.3→576.4

### 5.8 Options
| Option | Adjusted Feed | Status |
|---|---|---|
| No chemicals added | = Feed | ✅ |
| Dosing Antiscalants | = Feed (no chemistry change; warnings identical in tests so far) | ✅ / limits [PROVISIONAL] |
| User adjusted pH | Acid (H2SO4/HCl) converts HCO3→CO2 to reach the target pH; add SO4 (×48.03) or Cl (×35.45) per meq of acid; recompute everything | [PROVISIONAL] |
| Ion exchange softening | Ca→Ca leakage, Mg→Mg leakage; `Na += [(Ca−CaLeak)/20.04 + (Mg−MgLeak)/12.15] × 23.00` | [PROVISIONAL] |

For the pH-adjust option, use: total carbonate is conserved, `HCO3/CO2 = 10^(pH − 6.3)` (molar
basis, consistent with 5.2); acid meq = drop in HCO3 in mmol; also show the acid dose
(H2SO4: meq × 49.04 mg/L; HCl: meq × 36.46 mg/L).

### 5.9 Warnings (on the Concentrate column)
Text format (exact): `{X} Saturation limits  exceeded ,Antiscalants may be required or change your system design.`
- X = `CaCO3` when LSI > 0 **[PROVISIONAL threshold]**
- X = `CaSO4`, `BaSO4`, `SrSO4`, `CaF2`, `SiO2` when Sat% > 100 ✅
- Antiscalant limits: config `antiscalantLimits` (default the same as above) [PROVISIONAL]

---

## 6. Page 3: Design System ([PROVISIONAL] engine; UI ✅)

### 6.1 UI fields
Unit Set (gpd/psi, gpm/psi, m³/h/bar, m³/d/bar); Recovery; Permeate Flow; Feed Flow (calculated);
System Flux (calculated); Feed Temp; Fouling Factor (0.5–1.0, default 0.85); Number of Passes
(1–2); Stages per pass (1–3); stage selector; Pressure Vessels; Elements per Vessel (1–8);
Total elements (calculated); Select Product (from `elements.json`); "Use the Same Element in
the Pass"; "Same Back Pressure for all stages"; Feed Pressure (calculated); Back Pressure;
Booster Pressure (calculated); Pump Efficiency (checkbox + %); Intake on both ends + Front-end %;
Recirculation (checkbox + recycle flow); a System Configuration diagram (SVG showing passes
and stages); and a **Calculation** button.

### 6.2 Confirmed formulas
- `Feed = Permeate ÷ (Recovery/100)`; `Concentrate = Feed − Permeate`
- `Flux (gfd) = Permeate (gpd) ÷ (TotalElements × Area ft²)`; `LMH = gfd × 1.698`
- Unit conversions: gpm × 0.2271 = m³/h; gpm × 1440 = gpd; m³/h × 24 = m³/d;
  bar × 14.504 = psi; ft² × 0.0929 = m²

### 6.3 Engine [PROVISIONAL]
Simulate element by element; the concentrate of one element is the feed of the next.
- From the datasheet: `A = Qtest / (Area × NDPtest)`; `B = Qtest × (1 − Rej) / (Rej × Area)`
- `TCF = exp(K × (1/298.15 − 1/(T + 273.15)))`, K = 2640 (T ≥ 25), 3020 (T < 25)
- `π (bar) = 0.08314 × (T + 273.15) × Σ molarity`
- `C_avg = C_f × ln(1/(1−r)) / r`; `CPF = exp(0.7·r)`; `ΔP = k × Q_avg^1.75`
- `NDP = P_f − ΔP/2 − P_p − (π_avg × CPF − π_p)`
- `Qp = A × Area × TCF × FF × NDP`; `Qs = B × Area × TCF × (C_avg × CPF − C_p)`
- Iterate inside each element until stable. Solve the feed pressure with `scipy.optimize.brentq`
  so that total permeate equals the target (tolerance 0.1%).
- Per-ion permeate uses config `ionPassageRatio` [PROVISIONAL].
- `Pump kW = Q(m³/h) × P(bar) / (36 × η)`; `SEC = kW / Qp(m³/h)`
- Recycle: mix the feed with the recycle stream; iterate until the result changes by less than 0.1%.
- Validate against the Water Type limits in `water_types.json` (avg flux range, max element
  recovery, max feed flow per vessel 75 gpm, min concentrate 12–16 gpm, max ΔP per vessel 60 psi),
  all [PROVISIONAL].

### 6.4 `elements.json`
```json
[{ "model": "LP22-8040", "areaFt2": 400, "testFlowGpd": null, "testRejectionPct": null,
   "testPressurePsi": null, "testNaClMgL": null, "testRecoveryPct": null, "testTempC": 25,
   "maxPressurePsi": null, "maxFeedGpm": null, "minConcGpm": null, "dpK": null }]
```
`null` = TODO: fill from the Vontron datasheets. If any `null` is used, the engine returns a
clear error.

---

## 7. Page 4: Dashboard
Read-only summary of the current project:
- **KPI cards:** Feed / Permeate / Concentrate flow, Recovery, Avg flux, Feed pressure,
  Permeate TDS, Specific energy, Feed TDS, Water type
- **Scaling status:** traffic light per index (green < 80% of limit, amber 80–100%, red > limit)
- **Charts (Recharts):**
  1. Saturation % bar chart, Feed vs Concentrate, with a 100% limit line
  2. Ion composition stacked bar (Feed / Concentrate / Permeate)
  3. Per-element flux and pressure profile (line chart)
  4. LSI and S&DSI, Feed vs Concentrate
- **All warnings** from every page, in one list
- An "Out of date" badge if inputs changed since the last calculation, with a **Recalculate all** button

---

## 8. Page 5: Report
- On-screen preview of the full report:
  1. Project info
  2. Water analysis table (3 units) + charge balance
  3. Scaling table + option used + warnings
  4. Design configuration + system results + per-stage and per-element tables
  5. Charts
  6. Notes and provisional-logic disclaimer
- Download buttons:
  - **PDF**: `POST /api/report/pdf` (ReportLab, A4, company and project header, page numbers)
  - **Excel**: `POST /api/report/xlsx` (one sheet per section, numbers stored as numbers)
  - **Project JSON** (client-side download)
- File name: `{ProjectName}_{YYYYMMDD}.pdf|xlsx|json`

---

## 9. Backend API (stateless, no DB)
| Method | Path | Body → Response |
|---|---|---|
| POST | `/api/water/analyze` | water → converted table, TDS, balance, messages |
| POST | `/api/water/auto-balance` | water → water (balanced) + analysis |
| POST | `/api/scaling/calculate` | water + scaling → 3-column table + messages |
| POST | `/api/design/calculate` | full project → system, stage and element results + messages |
| POST | `/api/calculate-all` | full project → all results |
| POST | `/api/report/pdf` | full project → PDF file |
| POST | `/api/report/xlsx` | full project → XLSX file |
| GET | `/api/elements` | element list |
| GET | `/api/water-types` | water types + limits |

Backend structure:
```
backend/app/
  main.py
  api/            # routers
  models/         # pydantic schemas
  calc/
    water.py      # conversions, TDS, balance, auto-balance
    scaling.py    # CF, CO2, LSI, S&DSI, Ksp, silica, options
    design.py     # engine
    units.py
  reports/ pdf.py xlsx.py
  config/ ions.json scaling.json silica_table.json elements.json water_types.json
tests/ test_water.py test_scaling.py test_design.py golden_cases.json
```
Frontend structure:
```
frontend/src/
  pages/ WaterAnalysis.tsx Scaling.tsx DesignSystem.tsx Dashboard.tsx Report.tsx
  components/ IonGrid.tsx ResultTable.tsx MessagesPanel.tsx ConfigDiagram.tsx charts/
  store/ projectStore.ts
  api/ client.ts
  utils/ units.ts format.ts
```

---

## 10. Golden tests (must pass; tolerance ±0.01 on displayed values unless noted)

### 10.1 NaCl-only sample (TDS-only mode, TDS = 2000)
Na 786.47 → ppm 1714.50; Cl 1213.53 → ppm 1711.08; TDS 2000.00.
Scaling at 15%: CF 1.1765; TDS_conc 2352.94; pH 7.50 → 7.57.
Design: permeate 5 gpm, recovery 15% → feed 33.33 gpm; 1 × LP22-8040 → flux 18.0 gfd.

### 10.2 TDS-only mode
- TDS 1500 → Na 589.85 (meq 25.65), Cl 910.15 (meq 25.67)
- TDS 5000 → Na 1966.18 (meq 85.49), Cl 3033.82 (meq 85.58), Balance −0.1

### 10.3 TC-Water A, before balancing
Na 150, Ca 80, Mg 25, K 8, Ba 0.05, Sr 1.0, NH4 0, B 0.1, Cl 220, CO3 0, HCO3 250, F 0.8,
NO3 10, SO4 180, SiO2 20; pH 7.6; 25 °C.
- ppm CaCO3: Na 327.00, Ca 200.00, Mg 103.00, K 10.24, Sr 1.14, Cl 310.20, HCO3 205.00,
  F 2.13, NO3 8.10, SO4 187.20
- meq: Na 6.52, Ca 3.99, Mg 2.06, K 0.20, Cl 6.21, HCO3 4.10, F 0.04, NO3 0.16, SO4 3.75
- TDS 945.42; Cations 12.8; Anions 14.3; Balance −1.5; imbalance warning shown

### 10.4 TC-Water A, after Auto Balance
Na 184.50 (meq 8.02, ppm 402.21); TDS 979.92; Balance 0.0.
TDS with B = 0 → 979.35; B = 1.0 → 985.07; SiO2 = 0 → 959.92.

### 10.5 Scaling, TC-Water A balanced, 25 °C, no chemicals
Feed: pH 7.60, CO2 12.53, S&DSI 0.38, CaSO4 3.18, BaSO4 242.48, SrSO4 3.14, CaF2 5.44, SiO2 15.86

| Recovery | pH_c | TDS_c | S&DSI_c | CaSO4 | BaSO4 | SrSO4 | CaF2 | SiO2 |
|---|---|---|---|---|---|---|---|---|
| 25 | 7.72 | 1306.56 | 0.72 | 4.96 | 339.14 | 4.73 | 11.24 | 21.10 |
| 50 | 7.90 | 1959.84 | 1.19 | 9.28 | 544.14 | 8.45 | 31.25 | 30.38 |
| 65 | 8.06 | 2799.77 | 1.58 | 16.11 | 824.79 | 14.06 | 76.80 | 40.37 |
| 75 | 8.20 | 3919.68 | 1.92 | 27.10 | 1221.08 | 22.75 | 179.38 | 52.21 |
| 76 | 8.22 | 4083.00 | 1.96 | 28.86 | 1280.61 | 172.93 | 198.82 | 53.83 |
| 80 | 8.30 | 4899.60 | 2.14 | 38.26 | 1583.99 | 229.76 | 314.84 | 61.64 |
| 85 | 8.42 | 6532.80 | 2.40 | 59.68 | 2215.35 | 359.72 | 650.24 | 76.04 |

Warnings at 75%: CaCO3, BaSO4, CaF2. At 80%: CaCO3, BaSO4, SrSO4, CaF2.

### 10.6 Temperature (75% recovery)
- 10 °C: feed CaSO4 4.66, BaSO4 424.06, SrSO4 3.51, CaF2 6.87, SiO2 21.03;
  conc 39.71, 2135.47, 25.46, 226.48, 69.33
- 35 °C: feed 2.52, 172.18, 2.93, 4.72, 13.64; conc 21.44, 867.06, 21.23, 155.50, 44.84
- S&DSI at 50% recovery, pH 7.0: 10 °C −0.57 / 0.24; 35 °C 0.03 / 0.84

### 10.7 pH sweep (50% recovery, 25 °C)
- **S&DSI feed = pH − 7.22; conc = feed + 0.81** (check pH 5.0, 6.0, 7.6, 9.0, 10.0)
- **LSI (standard) feed / conc:** pH 5.0 −2.29 / −1.41; 6.0 −1.29 / −0.41; 8.0 0.71 / 1.59;
  9.0 1.71 / 2.59; 10.0 2.71 / 3.59
- **SiO2 feed %:** 5.0 12.75; 6.0 14.03; 6.5 14.77; 7.6 15.86; 8.0 14.47; 8.5 10.84;
  9.0 7.75; 9.5 5.58; 10.0 4.11

---

## 11. Open items (keep config-driven; do not hard-code)
1. LSI "behaviour A" and LSI temperature effect
2. CaCO3 (LSI) warning threshold
3. Antiscalant warning limits
4. Replicate the SrSO4 jump at TDS 4000? (client decision)
5. Validate the Ksp model on a second water (TC-Water B)
6. pH-adjust and softening logic (no Vontron data yet)
7. Element datasheets, pressure-drop constant k, per-ion passage ratios
8. Design limits per water type
9. "Intake on both ends" meaning
10. Imbalance warning threshold

## 12. Delivery phases
1. Backend `calc/water.py` + tests 10.1–10.4 → Water Analysis page
2. `calc/scaling.py` + tests 10.5–10.7 → Scaling page
3. Design engine skeleton + confirmed formulas (6.2) → Design page
4. Dashboard
5. Report (PDF/XLSX/JSON)
6. Docker, README, how to run the tests

## 13. Acceptance criteria
- All golden tests pass
- No database anywhere; save/load works via a JSON file; refreshing the browser keeps the
  current project
- Every PROVISIONAL constant lives in config and is listed in the README
- Reports download correctly and open in Acrobat and Excel
- Responsive layout (desktop first; usable on a tablet)