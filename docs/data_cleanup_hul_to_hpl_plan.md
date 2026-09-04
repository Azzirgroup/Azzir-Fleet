# Habili ERP — Data Cleanup & HUL → HPL Opening Migration Plan

- **Site:** habili.nvi.frappe.cloud (LIVE)
- **Prepared:** 2026-09-03
- **Status:** DRAFT — awaiting sign-off. **Nothing has been changed on the server.** All figures below come from read-only inspection.

---

## 1. Objective (target end state)

1. **Delete all test data** the users created while testing (invoices, quotations, payments, POs/PRs/PIs, stock entries, draft/cancelled recons) across **all three** companies.
2. **Keep the real opening balances** already entered:
   - **HPL** — keep its imported opening JEs **and** its opening stock (~16,924 ledger lines) exactly as-is.
   - **HCL** (Habili and Company Ltd) — keep its opening balances; delete only its test data.
3. **Move HUL's misfiled openings into HPL** (they were entered under HUL by mistake): HUL's opening stock (852 lines, 5,415,473,508) + its equity-offset JE → re-created under **HPL**. HUL then keeps operating but starts with no openings.

---

## 2. What is on the server today (read-only findings)

### 2.1 Three companies have data (not two)

| Company | Opening Journal Entries (keep) | Opening Stock (keep) | Test vouchers (delete) |
|---|---|---|---|
| **HABILI PARTS LIMITED (HPL)** | 2 submitted (`ACC-JV-2026-00050` = 28,095,256,247; `ACC-JV-2026-00047-1` = 79,629,600) + 2 cancelled | 2 submitted recons (`10000000009`, `10000000008`, ~16,924 SLE) | see §2.2 |
| **HABILI AND COMPANY LIMITED (HCL)** | 2 submitted (incl. `ACC-JV-2026-00046` = 276,458,739) | — | see §2.2 |
| **HABILI UNDERCARRIAGE LIMITED (HUL)** | 1 submitted (`ACC-JV-2026-00051` = 5,415,473,508) → **MOVE to HPL** | 1 submitted recon (`10000000010`, 852 lines) → **MOVE to HPL** | see §2.2 |

> **Note:** HUL's opening JE is only 2 lines — `Temporary Opening - HUL` Dr / `Opening Balance Equity - HUL` Cr — i.e. the equity counter-entry for its opening stock. So "HUL's openings" = the 852 stock lines plus that offset. Both accounts exist in HPL.

### 2.2 Test data to delete (non-opening), by doctype

| Doctype | HPL | HCL | HUL |
|---|---|---|---|
| Quotation | 11 (1 draft, 9 sub, 1 canc) | 17 (3 draft, 13 sub, 1 canc) | 1 draft |
| Sales Invoice | 29 (20 draft, 9 sub) | 17 (11 draft, 4 sub, 2 canc) | 2 sub |
| Delivery Note | 5 (2 draft, 3 sub) | — | 2 sub |
| Purchase Order | 1 draft | 5 (3 sub, 2 canc) | — |
| Purchase Receipt | — | 3 (2 draft, 1 sub) | — |
| Purchase Invoice | — | 10 (1 draft, 7 sub, 2 canc) | — |
| Payment Entry | 1 sub | 2 sub | — |
| Stock Entry | — | — | 2 sub |
| Stock Reconciliation (test only) | 3 draft + 3 cancelled | — | (wiped with HUL) |

All Journal Entries on the system are opening entries — there are **no test JEs**. The only JE cleanup is dropping HPL's 2 **cancelled** opening JEs.

### 2.3 Data Import trail (for reference / re-import files)

Every opening was traceable via the **Data Import** records. The opening **Journal Entries** were done via Data Import and the **original spreadsheets are still attached and downloadable**. The opening **stock** was entered as Stock Reconciliation documents directly (no import file) — which is why HPL's opening stock must be **preserved**, not re-imported.

---

## 3. Guiding principles (safety)

- **Full backup first**, downloaded off-site, before any change. This is irreversible.
- **ORM only** — all changes via Frappe/bench (`frappe.get_doc`, `cancel`, `delete_doc`), never direct SQL.
- **Openings are sacred** — the delete steps explicitly exclude `is_opening = Yes` JEs and the submitted Opening-Stock recons.
- **Move before delete** — HUL's openings are re-created in HPL and verified **before** HUL is cleared.
- **Verify** trial balance + stock balance per company after each phase.

---

## 4. The one decision needed — where HUL's `HUL1 - *` stock lands in HPL

HUL's 852 opening-stock lines split as:

| Target in HPL | Lines | Value |
|---|---:|---:|
| HPL warehouse **already exists** (MWANZA, MBEYA, ARUSHA, KAHAMA, DODOMA, SONGEA, NZEGA, WH1/WH2/WH4/RB) | **525** | 2,132,201,000 |
| **No HPL equivalent** — all `HUL1 - *` head-office bins (171 distinct) | **327** | 3,283,272,508 |

The 525 map cleanly by name (swap `- HUL` → `- HPL`). The 327 in the `HUL1 - *` bins need a landing choice:

- **Option A — Replicate the bins (recommended).** Auto-create the 171 missing `HUL1 - … - HPL` leaf warehouses under HPL and map 1:1. Preserves exact locations; pickup slips / stock reports stay meaningful.
- **Option B — Consolidate.** Land all 327 lines into a single new HPL warehouse (e.g. `HUL1 Received Stock - HPL`). Simpler warehouse list, but loses the per-bin location.

**Recommendation: Option A** — it keeps the stock exactly where it physically is and matches how the branch warehouses already map.

> **CONFIRMED (2026-09-03): Option A — replicate the 171 `HUL1 - *` bins under HPL and map 1:1.**

---

## 5. Execution phases

### Phase 0 — Backup
- Take a full Frappe Cloud backup (with files) and download it. Confirm it's downloaded before proceeding.

### Phase 1 — Move HUL openings → HPL
1. Read HUL's opening-stock recon `10000000010` (852 lines: item, qty, valuation_rate, warehouse).
2. Build the warehouse map (525 existing + 171 created per Option A).
3. Create **one** new HPL Stock Reconciliation, purpose **Opening Stock**, posting on the same opening date, with all 852 lines remapped to HPL warehouses. Submit.
   - This auto-posts Dr Stock / Cr `Temporary Opening - HPL`.
4. Create the HPL equity-offset JE (Opening): Dr `Temporary Opening - HPL` / Cr `Opening Balance Equity - HPL`, 5,415,473,508, mirroring `ACC-JV-2026-00051`. Submit.
5. **Verify** HPL stock value increased by 5,415,473,508 and HPL trial balance still balances.

### Phase 2 — Clear HUL
- With HUL's openings now safely in HPL, run ERPNext **"Delete Company Transactions"** on **HUL** (Company master → Delete Company Transactions). This wipes HUL's test data **and** its now-duplicated openings in one supported, atomic step. Masters and setup (users, permissions, roles, modules) are untouched.

### Phase 3 — Surgical delete of test data on HPL & HCL (keep openings)
Cancel + delete, in dependency order, **excluding** opening JEs and the submitted Opening-Stock recons:
1. Payment Entries
2. Sales Invoices / Purchase Invoices
3. Delivery Notes / Purchase Receipts
4. Sales Orders / Purchase Orders
5. Quotations
6. Stock Entries
7. Test Stock Reconciliations (HPL's 3 draft + 3 cancelled)
8. HPL's 2 cancelled opening JEs (cleanup)

GL Entries and Stock Ledger Entries are removed automatically on cancel + delete.

### Phase 4 — Verify
- **Trial balance** per company balances (Dr = Cr).
- **Stock balance** totals: HPL = original HPL opening + 5,415,473,508 (HUL moved in); HUL = 0; HCL unchanged.
- Opening JEs intact: HPL (`00050`, `00047-1`), HCL (`00046` + 1), plus the new HPL offset JE.
- User permissions / roles / workspaces unchanged (spot check kabogo).

---

## 6. Rollback
If anything looks wrong at any checkpoint: **stop** and restore the Phase-0 backup. Because HUL is only cleared in Phase 2 *after* Phase 1 is verified, and HPL/HCL openings are never deleted, the blast radius is contained even without a restore.

---

## 7. Open items to confirm before running
1. ~~Warehouse landing choice~~ — **RESOLVED: Option A (replicate 1:1).** Create group `HUL1 - HPL` + 171 leaf bins under HPL.
2. Confirmation that a **backup has been taken and downloaded** — *pending*.
3. Go-ahead to execute (scripts prepared per Option A, run with your approval, phase by phase).

### Phase-1 dry-run (2026-09-03, read-only) — PASSED
- 852 lines; **all items exist and are stock items** (0 missing / 0 non-stock).
- 248 distinct warehouses: 77 exist in HPL, **171 to create** (all under one parent `HUL1 - HUL` → create `HUL1 - HPL` group + 171 leaves).
- Offset accounts exist.
- **Verification baseline:** HPL stock value = 28,013,786,647 → expect **33,429,260,155** after the move.

---

## Appendix — key figures
- HUL opening stock to move: **852 lines, 5,415,473,508** (525 map / 327 need bins).
- HUL offset JE: `ACC-JV-2026-00051` = 5,415,473,508 (`Temporary Opening - HUL` → `Opening Balance Equity - HUL`).
- HPL openings kept: `ACC-JV-2026-00050` (28,095,256,247), `ACC-JV-2026-00047-1` (79,629,600), recons `10000000009` + `10000000008`.
- HCL openings kept: `ACC-JV-2026-00046` (276,458,739) + 1 more.
