# Policy Reader — Context Summary (Feb 13, 2026)

## What It Does
Insurance policy document processor on Frappe Framework.
Pipeline: **PDF Upload → Claude Vision AI Extraction → Motor/Health Policy Record → SAIBA ERP Sync**

## Key Components

| Layer | Components |
|-------|-----------|
| **DocTypes** | Policy Document (entry point), Motor Policy, Health Policy, Policy Reader Settings, SAIBA Validation Settings, plus master data (Insurance Customer, Company, Employee, etc.) |
| **Services (9)** | Claude Vision, Policy Creation, Field Mapping, Prompt, SAIBA Sync, SAIBA Validation, Common, API Health |
| **UI** | Split-pane Policy File View (PDF + editable form), Dashboard page |
| **Background** | Stuck-job monitor every 3 min, retries or fails stuck docs |

## Key Paths

| Purpose | Path |
|---------|------|
| Services | `policy_reader/policy_reader/services/` |
| Core DocTypes | `policy_reader/policy_reader/doctype/` |
| Policy DocTypes (active) | `policy_reader/policies/doctype/` |
| Background tasks | `policy_reader/tasks.py` |
| Hooks | `policy_reader/hooks.py` |
| Patches | `policy_reader/patches/` |
| SAIBA validation JS | `policy_reader/public/js/saiba_validation.js` |

## Architecture Notes
- **Two copies** of Motor/Health Policy DocTypes — `policies/doctype/` (active) and `policy_reader/doctype/` (older/alternate)
- Services are stateless, live in `policy_reader/policy_reader/services/`
- Field mapping uses alias system with fuzzy matching; protected fields never overwritten by AI
- SAIBA integration has auth token caching (23h validity) and pre-sync validation

## Latest Changes (as of commit 83a7d94, Feb 12 2026)

### `83a7d94` — Updated health and motor API sync
- Rewrote all SAIBA validation rules per Feb 2026 API spec (29 mandatory Motor, 25 Health)
- Sync button now always shows; warning-styled with confirmation if validation fails
- Added blue "S" badges on form fields required for SAIBA sync (`mark_required_fields()`)

### `43c9c57` — Changes in policy service files
- Added `_copy_checklist_fields()` — copies 14 checklist fields from Policy Document to policy record
- These fields are now protected (won't be overwritten by AI extraction)
- Added `get_required_fields()` whitelisted endpoint for the "S" badge UI

### `04774b7` — Fixed motor policy and policy document checklist
- Motor Policy JS: auto-extract RTO code from vehicle number (first 4 chars), manual override detection
- Policy Document JSON: minor checklist field changes

### Recent Focus
SAIBA ERP integration hardening — validation rules aligned to real API spec, better sync UX, ensuring checklist/business fields flow correctly without AI clobbering them.
