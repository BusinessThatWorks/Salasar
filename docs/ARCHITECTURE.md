# Policy Reader

Insurance policy document processor built on Frappe Framework. Extracts data from PDFs using Claude AI, creates Motor/Health Policy records.

> **Architecture docs:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Frappe Framework Conventions

### Use Frappe Built-ins (Don't Reinvent)

```python
# Database operations
frappe.get_doc("DocType", name)              # Fetch full document
frappe.db.get_value("DocType", name, "field") # Fetch single field
frappe.db.get_all("DocType", filters, fields) # Query multiple records
frappe.db.exists("DocType", name)            # Check existence
frappe.db.set_value("DocType", name, "field", value)  # Update field

# NEVER use raw SQL unless absolutely necessary
# Bad:  frappe.db.sql("SELECT * FROM `tabCustomer` WHERE ...")
# Good: frappe.db.get_all("Customer", filters={...}, fields=[...])
```

```python
# Document operations
doc = frappe.new_doc("DocType")              # Create new
doc.insert()                                  # Insert (triggers validate)
doc.save()                                    # Save existing
doc.submit()                                  # Submit (if submittable)
doc.db_set("field", value)                   # Update without triggers
```

```python
# Utilities - always prefer these
from frappe.utils import now, getdate, add_days, cint, flt, cstr
getdate("2024-01-15")                        # Parse date
add_days(getdate(), 30)                      # Date arithmetic
cint(value)                                  # Safe int conversion
flt(value, precision=2)                      # Safe float conversion
```

```python
# Background jobs - NEVER use threading
frappe.enqueue(
    method="path.to.function",
    queue="short",                           # short/default/long
    timeout=300,
    kwarg1=value1
)
```

```python
# Caching
frappe.cache().get_value("key")
frappe.cache().set_value("key", value)
frappe.cache().hget("hash", "key")
```

### Error Handling

```python
# User-facing errors (shows dialog in UI)
frappe.throw("Customer not found")
frappe.throw(_("Customer not found"))        # Translatable

# Validation errors in DocType
if not self.customer:
    frappe.throw(_("Customer is required"))

# Log errors for debugging (doesn't stop execution)
frappe.log_error(frappe.get_traceback(), "Descriptive Title")

# Informational logging
frappe.logger().info(f"Processing {doc.name}")
frappe.logger().warning(f"Fallback used for {doc.name}")
```

### API Endpoints

```python
@frappe.whitelist()                          # Expose to JS/API
def get_policy_details(policy_no):
    if not policy_no:
        frappe.throw("Policy number required")
    return frappe.db.get_value("Motor Policy", policy_no, ["customer", "vehicle_no"], as_dict=True)

@frappe.whitelist(allow_guest=True)          # Public endpoint (rare)
def public_endpoint():
    pass
```

### Client Scripts (JS)

```javascript
frappe.ui.form.on("Motor Policy", {
  refresh(frm) {
    // Add custom button
    if (!frm.is_new()) {
      frm.add_custom_button(__("Process"), () => {
        frm.call("process_policy");
      });
    }
  },

  customer_code(frm) {
    // Field change handler - fetch related data
    if (frm.doc.customer_code) {
      frappe.db
        .get_value("Insurance Customer", frm.doc.customer_code, "customer_name")
        .then((r) => {
          frm.set_value("customer_name", r.message.customer_name);
        });
    }
  },
});

// Call backend method
frappe.call({
  method: "policy_reader.api.get_policy_details",
  args: { policy_no: "POL-001" },
  callback: function (r) {
    if (r.message) {
      console.log(r.message);
    }
  },
});
```

### DocType Controller Pattern

```python
class MotorPolicy(Document):
    def validate(self):
        # Light validation only - no heavy logic
        self.validate_dates()

    def before_save(self):
        # Set computed fields
        self.full_name = f"{self.first_name} {self.last_name}"

    def on_submit(self):
        # Trigger downstream actions (keep minimal)
        self.update_related_records()

    # Heavy logic goes in services, called via custom methods
    @frappe.whitelist()
    def process_policy(self):
        from policy_reader.services.processing_service import ProcessingService
        return ProcessingService().process(self.name)
```

---

## Policy Reader Patterns

### Service Architecture

All business logic lives in `policy_reader/policy_reader/services/`. Services are stateless.

```python
# Correct: Use services
from policy_reader.policy_reader.services.policy_creation_service import PolicyCreationService
result = PolicyCreationService().create_policy_record(doc_name, "Motor")

# Wrong: Business logic in DocType controller
```

### Settings Access

```python
from policy_reader.policy_reader.services.common_service import CommonService
settings = CommonService.get_policy_reader_settings()
api_key = CommonService.get_api_key(settings)
```

### Protected Fields

These are set from master data selection, never from AI extraction:

- `customer_code`, `customer_name`, `customer_group`
- `insurance_company_branch`, `insurer_name`, `insurer_city`
- `processor_employee_*` fields

### Field Mapping

Don't hardcode field names. Use the alias system:

```python
from policy_reader.policy_reader.services.field_mapping_service import FieldMappingService
FieldMappingService().map_fields_dynamically(extracted_data, policy_type, policy_doc)
```

### Real-time Notifications

```python
frappe.publish_realtime(
    event="policy_processing_complete",
    message={"doc_name": self.name, "status": "Completed"},
    user=self.owner
)
```

---

## Don't

- **Don't** use raw SQL — use `frappe.db.get_all()`, `frappe.db.get_value()`
- **Don't** use Python threading — use `frappe.enqueue()`
- **Don't** put business logic in `validate()` — use services
- **Don't** bypass field mapping with direct assignments
- **Don't** catch exceptions silently — always log or re-raise
- **Don't** modify protected fields from AI extraction results

---

## Adding Features

### New Policy Type

1. Create DocType in `policies/doctype/`
2. Add aliases in `FieldMappingService.get_default_aliases()`
3. Add prompt builder in `PromptService`
4. Add option to `policy_type` Select in Policy Document
5. Register in hooks for field mapping refresh

### New Service

1. Create in `policy_reader/policy_reader/services/`
2. Follow stateless pattern — no instance state
3. Use `CommonService` for shared utilities
4. Add comprehensive docstrings

---

## Commands

```bash
# Development
bench start
bench --site dev.localhost clear-cache

# Testing
bench --site dev.localhost run-tests --app policy_reader
bench --site dev.localhost run-tests --module policy_reader.policy_reader.doctype.policy_document.test_policy_document
bench --site dev.localhost run-tests --app policy_reader --coverage

# Migrations
bench --site dev.localhost migrate

# Console
bench --site dev.localhost console
bench --site dev.localhost mariadb
```

## Key Paths

| Purpose          | Path                                    |
| ---------------- | --------------------------------------- |
| Services         | `policy_reader/policy_reader/services/` |
| Core DocTypes    | `policy_reader/policy_reader/doctype/`  |
| Policy DocTypes  | `policy_reader/policies/doctype/`       |
| Background tasks | `policy_reader/tasks.py`                |
| Hooks            | `policy_reader/hooks.py`                |
| Patches          | `policy_reader/patches/`                |
