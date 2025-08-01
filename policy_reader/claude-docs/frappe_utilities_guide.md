# Frappe Framework Utilities Guide

**For AI Assistants & Developers**: Frappe is a batteries-included framework. Avoid reinventing the wheel by using these built-in utilities instead of writing custom code.

## Core Principle
**If you're writing more than 5-10 lines for a common operation, there's probably a Frappe utility for it!**

---

## Date & Time Operations
❌ **Don't write custom date parsing/formatting**  
✅ **Use Frappe's built-in utilities:**

```python
# Date operations
frappe.utils.getdate(date_string)          # Parse date safely
frappe.utils.get_datetime(datetime_string) # Parse datetime safely
frappe.utils.nowdate()                     # Current date
frappe.utils.nowtime()                     # Current time
frappe.utils.now_datetime()                # Current datetime

# Date arithmetic
frappe.utils.add_days(date, days)
frappe.utils.add_months(date, months)
frappe.utils.date_diff(end_date, start_date)
frappe.utils.time_diff(end_time, start_time)

# Date ranges
frappe.utils.get_first_day(date)
frappe.utils.get_last_day(date)
frappe.utils.get_quarter_start(date)
frappe.utils.get_year_start(date)

# Formatting
frappe.utils.format_date(date, format_string)
frappe.utils.format_time(time)
frappe.utils.format_datetime(datetime)
frappe.utils.pretty_date(date)             # "2 days ago" style
```

---

## Data Validation & Type Conversion
❌ **Don't write custom validators or type converters**  
✅ **Use Frappe's validation utilities:**

```python
# Type conversion (safe)
frappe.utils.cint(value, default=0)        # Clean integer
frappe.utils.flt(value, precision=None)    # Clean float
frappe.utils.cstr(value)                   # Clean string
frappe.utils.sbool(value)                  # String to boolean

# Validation
frappe.utils.validate_email_address(email)
frappe.utils.validate_phone_number(phone, country=None)
frappe.utils.validate_url(url)

# Data sanitization
frappe.utils.strip_html_tags(text)
frappe.utils.escape_html(text)
frappe.utils.sanitize_html(html_content)
```

---

## Database Operations
❌ **Don't write raw SQL for common operations**  
✅ **Use Frappe ORM:**

```python
# Reading data
frappe.get_doc(doctype, name)              # Single document
frappe.get_all(doctype, filters={}, fields=[], order_by="")
frappe.get_list(doctype, filters={})       # With permissions
frappe.db.get_value(doctype, name, fieldname)
frappe.db.get_values(doctype, filters, fieldnames)
frappe.db.exists(doctype, name)
frappe.db.count(doctype, filters={})

# Checking existence
if frappe.db.exists("User", email):
    # User exists

# Getting single values
value = frappe.db.get_single_value("System Settings", "country")
```

---

## File Operations
❌ **Don't manually handle file uploads/downloads**  
✅ **Use Frappe's file system:**

```python
# File handling
file_doc = frappe.get_doc("File", file_name)
file_content = frappe.get_doc("File", file_name).get_content()

# File utilities
from frappe.utils.file_manager import save_file, get_file
save_file(fname, content, dt, dn, folder=None, decode=False, is_private=0)

# File paths
frappe.utils.get_site_path()
frappe.get_site_path()
frappe.utils.get_files_path()
```

---

## Email & Communications
❌ **Don't build custom email systems**  
✅ **Use Frappe's communication:**

```python
# Send email
frappe.sendmail(
    recipients=["user@example.com"],
    subject="Subject",
    message="Message",
    attachments=[],
    reference_doctype="",
    reference_name=""
)

# Bulk operations
frappe.enqueue_doc(doctype, name, method, **kwargs)

# Real-time notifications
frappe.publish_realtime(event, message, user=None, doctype=None, docname=None)

# Show messages to user
frappe.msgprint("Message to user")
frappe.throw("Error message")  # Stops execution
```

---

## Permissions & Access Control
❌ **Don't write custom permission logic**  
✅ **Use Frappe's permission system:**

```python
# Check permissions
frappe.has_permission(doctype, ptype="read", doc=None, user=None)
frappe.only_for(roles, message=None)       # Decorator/function

# User and role management
frappe.get_roles(user=None)
frappe.session.user                        # Current user
frappe.session.user_type                   # User type

# Sharing
frappe.share.add(doctype, name, uid, read=1, write=0, share=0)
```

---

## Background Jobs & Queuing
❌ **Don't use external job queues**  
✅ **Use Frappe's built-in queuing:**

```python
# Enqueue jobs
frappe.enqueue(
    method,                    # Function to call
    timeout=300,               # Timeout in seconds
    is_async=True,            # Run in background
    job_name=None,            # Custom job name
    **kwargs                  # Arguments to pass
)

# Enqueue document methods
frappe.enqueue_doc(doctype, name, method, **kwargs)

# Example
frappe.enqueue("myapp.utils.heavy_function", user_id=user.name, timeout=600)
```

---

## Caching
❌ **Don't implement custom caching**  
✅ **Use Frappe's cache system:**

```python
# Cache operations
frappe.cache().get_value(key)
frappe.cache().set_value(key, value, expires_in_sec=None)
frappe.cache().delete_value(key)

# Local cache (request-scoped)
frappe.local.cache.get(key)
frappe.local.cache[key] = value

# Document caching
frappe.get_cached_doc(doctype, name)
```

---

## Configuration Management
❌ **Don't create custom config files**  
✅ **Use Frappe's settings:**

```python
# Site configuration
frappe.conf.get("setting_name")
frappe.conf.db_name                        # Database name
frappe.conf.host_name                      # Host

# Single DocTypes (Settings)
frappe.get_single("System Settings")
frappe.db.get_single_value("System Settings", "country")

# Set single values
frappe.db.set_single_value("System Settings", "country", "India")
```

---

## Logging & Error Handling
❌ **Don't use print statements or custom loggers**  
✅ **Use Frappe's logging:**

```python
# Error handling
frappe.throw("User-facing error message")   # Stops execution
frappe.log_error("Error details", "Error Title")  # Logs to Error Log

# Development logging
frappe.errprint("Debug message")            # Development only
frappe.logger().info("Info message")
frappe.logger().error("Error message")

# Message types
frappe.msgprint("Info message", indicator="blue")
frappe.msgprint("Success message", indicator="green")
frappe.msgprint("Warning message", indicator="orange")
frappe.msgprint("Error message", indicator="red")
```

---

## JSON & Data Parsing
❌ **Don't use json.loads/dumps directly**  
✅ **Use Frappe's JSON utilities:**

```python
# JSON operations
frappe.parse_json(json_string)             # Safe JSON parsing
frappe.as_json(python_object)              # Convert to JSON string

# Form data
frappe.form_dict                           # Request form data
frappe.form_dict.get("field_name")
```

---

## Translation & Formatting
❌ **Don't build custom translation systems**  
✅ **Use Frappe's i18n:**

```python
# Translation
frappe._("Text to translate")
frappe._("Hello {0}").format(name)

# Number formatting
frappe.format(value, options={"fieldtype": "Currency"})
frappe.format_value(value, fieldtype="Float", precision=2)

# Currency formatting
frappe.utils.fmt_money(amount, currency=None)
```

---

## Web Forms & APIs
❌ **Don't build custom form handlers**  
✅ **Use Frappe's web infrastructure:**

```python
# API endpoints
@frappe.whitelist()
def my_api_method():
    return {"status": "success"}

@frappe.whitelist(allow_guest=True)
def public_api():
    return frappe.form_dict

# Method calls from frontend
frappe.call({
    method: "myapp.api.my_method",
    args: {param1: "value1"},
    callback: function(r) {
        console.log(r.message);
    }
});
```

---

## Frontend Utilities (JavaScript)
❌ **Don't write custom dialog/UI code**  
✅ **Use Frappe's UI components:**

```javascript
// Dialogs
let dialog = new frappe.ui.Dialog({
    title: "Dialog Title",
    fields: [{
        fieldname: "field1",
        fieldtype: "Data",
        label: "Field Label"
    }]
});

// Messages
frappe.msgprint("Message");
frappe.show_alert("Alert message");
frappe.confirm("Are you sure?", () => {
    // Confirmed
});

// Loading
frappe.show_progress("Loading...", 50, 100);
frappe.hide_progress();
```

---

## Common Anti-Patterns to Avoid

1. **❌ Custom pagination** → ✅ Use `limit_start`, `limit_page_length` in `frappe.get_list()`
2. **❌ Manual database connections** → ✅ Use `frappe.db`
3. **❌ Custom authentication** → ✅ Use Frappe's session management
4. **❌ Custom templating** → ✅ Use Jinja2 in Print Formats
5. **❌ Manual form validation** → ✅ Use DocType validation hooks
6. **❌ Custom REST API framework** → ✅ Use `@frappe.whitelist()`
7. **❌ Manual websocket handling** → ✅ Use `frappe.publish_realtime()`
8. **❌ Custom search implementations** → ✅ Use `frappe.db.sql()` with `MATCH AGAINST`

---

## Framework-Specific Patterns

### DocType Hooks (Use instead of custom event systems)
```python
# In doctype.py
def validate(self):
    # Validation logic

def before_save(self):
    # Pre-save logic

def after_insert(self):
    # Post-creation logic

def on_update(self):
    # Update logic

def on_cancel(self):
    # Cancellation logic
```

### Custom Fields (Don't modify core)
```python
# Use Custom Field DocType instead of altering core doctypes
frappe.get_meta("DocType Name").get_field("field_name")
```

### Workflow (Don't build custom state machines)
```python
# Use built-in Workflow DocType
frappe.workflow.get_workflow_name(doctype)
frappe.workflow.get_transitions(doc)
```

---

## Performance Best Practices

1. **Use `frappe.get_all()` instead of `frappe.get_list()`** when you don't need permission filtering
2. **Use `frappe.db.get_value()` for single field lookups** instead of `frappe.get_doc()`
3. **Use `frappe.only_for()` for role-based access** instead of manual role checking
4. **Use `frappe.enqueue()` for heavy operations** instead of blocking requests
5. **Use `frappe.cache()` for expensive computations** instead of recalculating

---

## Advanced Utilities

### Batch Operations
❌ **Don't loop through large datasets**  
✅ **Use Frappe's batch processing:**

```python
# Bulk operations
frappe.db.bulk_insert(doctype, fields, values)
frappe.db.bulk_update(doctype, update_dict, condition)

# Batch processing
from frappe.utils import get_batch_interval
for start, end in get_batch_interval(total_count, batch_size=1000):
    # Process batch
    pass

# Queue bulk operations
frappe.enqueue("method", queue="long", **kwargs)
```

### String & Text Utilities
❌ **Don't write custom string manipulation**  
✅ **Use Frappe's text utilities:**

```python
# String operations
frappe.utils.random_string(length)
frappe.utils.encode(text)
frappe.utils.decode(encoded_text)
frappe.utils.md5(text)
frappe.utils.sha256_hash(text)

# Text formatting
frappe.utils.strip(text)
frappe.utils.comma_and(items_list)           # "A, B and C"
frappe.utils.comma_or(items_list)            # "A, B or C"
frappe.utils.get_formatted_email(email)      # "Name <email@domain.com>"

# Name formatting
frappe.utils.get_fullname(user)
frappe.utils.get_abbr(name)                  # Get abbreviation
```

### Document Operations
❌ **Don't write custom document manipulation**  
✅ **Use Frappe's document utilities:**

```python
# Document operations
frappe.copy_doc(doc, ignore_no_copy=True)
frappe.rename_doc(doctype, old_name, new_name, merge=False)
frappe.delete_doc(doctype, name, force=False)

# Document status
frappe.db.set_value(doctype, name, field, value)
doc.reload()                                 # Refresh from database
doc.run_method("method_name")               # Call document method

# Child table operations
doc.append("child_table_field", {
    "field1": "value1",
    "field2": "value2"
})
```

### System & Site Utilities
❌ **Don't access system info manually**  
✅ **Use Frappe's system utilities:**

```python
# Site information
frappe.local.site                           # Current site
frappe.local.site_path                      # Site directory path
frappe.utils.get_site_base_path()

# System information
frappe.utils.get_bench_path()
frappe.utils.get_site_config()
frappe.get_system_timezone()

# Request information
frappe.local.request                        # Request object
frappe.local.response                       # Response object
frappe.get_request_header("header_name")
```

### Number & Math Utilities
❌ **Don't write custom math functions**  
✅ **Use Frappe's math utilities:**

```python
# Math operations
frappe.utils.rounded(number, precision=0)
frappe.utils.floor(number)
frappe.utils.ceil(number)

# Currency and financial
frappe.utils.money_in_words(amount, currency="INR")
frappe.utils.in_words(number)               # Number to words

# Percentage calculations
frappe.utils.percentage(part, whole)
frappe.utils.add_percentage(amount, percentage)
```

### Report & Print Utilities
❌ **Don't build custom reporting systems**  
✅ **Use Frappe's reporting framework:**

```python
# Report execution
frappe.get_print(doctype, name, print_format=None, as_pdf=False)
frappe.attach_print(doctype, name, file_name=None, print_format=None)

# PDF generation
from frappe.utils.pdf import get_pdf
html_content = "<html>...</html>"
pdf = get_pdf(html_content)

# Excel export
from frappe.utils.xlsxutils import make_xlsx
make_xlsx(data, "Sheet Name", wb=None)
```

### Search & Filter Utilities
❌ **Don't implement custom search**  
✅ **Use Frappe's search utilities:**

```python
# Advanced search
frappe.db.sql("""
    SELECT * FROM `tabDocType` 
    WHERE MATCH(field1, field2) AGAINST (%s IN BOOLEAN MODE)
""", (search_term,))

# Filter utilities
from frappe.model.utils import get_fetch_values
get_fetch_values(doctype, fieldname, value)

# Link field searches
frappe.get_list(doctype, 
    filters=[
        ["field", "like", "%value%"],
        ["date_field", "between", [start_date, end_date]]
    ]
)
```

### Workflow & State Management
❌ **Don't create custom state machines**  
✅ **Use Frappe's workflow system:**

```python
# Workflow operations
from frappe.workflow.doctype.workflow.workflow import get_workflow_name
workflow = get_workflow_name(doctype)

# State transitions
from frappe.workflow.doctype.workflow.workflow import apply_workflow
apply_workflow(doc, action)

# Workflow states
frappe.get_all("Workflow Document State", 
    filters={"parent": workflow_name})
```

### Integration & External APIs
❌ **Don't use requests library directly**  
✅ **Use Frappe's HTTP utilities:**

```python
# HTTP requests
from frappe.utils import get_request_session
session = get_request_session()
response = session.get(url, headers=headers)

# OAuth and authentication
from frappe.integrations.utils import make_get_request, make_post_request
response = make_get_request(url, headers=headers)
response = make_post_request(url, data=data, headers=headers)
```

### Backup & Data Management
❌ **Don't write custom backup systems**  
✅ **Use Frappe's data management:**

```python
# Backup operations (via bench commands)
# frappe.utils.backups - for programmatic access

# Data export/import
from frappe.core.doctype.data_import.data_import import export_json
export_json(doctype, path, filters=None)

# Fixture management
frappe.get_fixtures_path()
```

### Security Utilities
❌ **Don't implement custom security**  
✅ **Use Frappe's security utilities:**

```python
# Password utilities
from frappe.utils.password import get_decrypted_password
password = get_decrypted_password(doctype, name, fieldname)

# Encryption
from frappe.utils.password import encrypt, decrypt
encrypted = encrypt(password)
decrypted = decrypt(encrypted_password)

# Session management
frappe.session.user                         # Current user
frappe.local.login_manager.login_as(user)   # Switch user context
frappe.local.login_manager.logout()         # Logout
```

### Custom Scripts & Client-side
❌ **Don't write vanilla JavaScript**  
✅ **Use Frappe's client-side framework:**

```javascript
// Form customization
frappe.ui.form.on("DocType", {
    refresh: function(frm) {
        // Form refresh logic
    },
    field_name: function(frm) {
        // Field change logic
    }
});

// Custom buttons
frm.add_custom_button("Button Label", function() {
    // Button click logic
}, "Button Group");

// Queries and filters
frm.set_query("link_field", function() {
    return {
        filters: {
            "status": "Active"
        }
    };
});

// Field formatting
frappe.form.link_formatters["DocType"] = function(value, doc) {
    return value ? `${value} (${doc.field})` : value;
};
```

### Testing Utilities
❌ **Don't write custom test frameworks**  
✅ **Use Frappe's testing utilities:**

```python
# Test framework
import frappe
from frappe.tests.utils import FrappeTestCase

class TestMyDocType(FrappeTestCase):
    def test_creation(self):
        doc = frappe.get_doc({
            "doctype": "My DocType",
            "field": "value"
        })
        doc.insert()
        self.assertEqual(doc.field, "value")

# Test data
frappe.get_test_records("DocType")
```

### Custom Field & Meta Programming
❌ **Don't modify core DocTypes**  
✅ **Use Frappe's customization framework:**

```python
# Meta programming
meta = frappe.get_meta("DocType")
field = meta.get_field("fieldname")
options = field.options

# Custom field creation (programmatically)
custom_field = frappe.get_doc({
    "doctype": "Custom Field",
    "dt": "DocType Name",
    "label": "Custom Field",
    "fieldname": "custom_field",
    "fieldtype": "Data"
})
custom_field.insert()

# Property setter
frappe.make_property_setter("DocType", "field", "property", "value")
```

### Monitoring & Health Checks
❌ **Don't build custom monitoring**  
✅ **Use Frappe's monitoring utilities:**

```python
# System health
from frappe.utils.doctor import get_system_info
system_info = get_system_info()

# Performance monitoring
from frappe.utils import get_execution_time
with get_execution_time() as timer:
    # Code to measure
    pass
print(f"Execution time: {timer.elapsed}")

# Memory usage
import frappe.monitor
frappe.monitor.start()
# Code to monitor
frappe.monitor.stop()
```

---

## ERPNext-Specific Utilities (If using ERPNext)

### Accounting Utilities
```python
# ERPNext accounting functions
from erpnext.accounts.utils import get_balance_on
balance = get_balance_on(account, date)

from erpnext.accounts.utils import get_fiscal_year
fiscal_year = get_fiscal_year(date)
```

### Stock & Inventory
```python
# Stock utilities
from erpnext.stock.utils import get_stock_balance
stock_qty = get_stock_balance(item_code, warehouse, posting_date)

from erpnext.stock.get_item_details import get_item_details
item_details = get_item_details(args)
```

### Manufacturing
```python
# Manufacturing utilities
from erpnext.manufacturing.utils import get_bom_items
bom_items = get_bom_items(bom_no)
```

---

## Migration & Upgrade Utilities
❌ **Don't write custom migration scripts**  
✅ **Use Frappe's migration framework:**

```python
# In patches/v1_0/patch_name.py
import frappe

def execute():
    # Migration logic
    frappe.reload_doctype("DocType Name")
    
    # Data migration
    frappe.db.sql("""UPDATE `tabDocType` SET field = %s WHERE condition = %s""", 
                  (new_value, condition_value))
    
    # Commit changes
    frappe.db.commit()
```

---

## Best Practices Summary

### Do's ✅
1. **Always use Frappe utilities first** - Check `frappe.utils` before writing custom code
2. **Use `frappe.db` for database operations** - It handles connections and transactions
3. **Use `@frappe.whitelist()` for API endpoints** - Built-in authentication and error handling
4. **Use Frappe's validation patterns** - `frappe.throw()`, `frappe.msgprint()`
5. **Use built-in caching** - `frappe.cache()` for performance
6. **Use `frappe.enqueue()` for heavy operations** - Don't block user requests
7. **Use DocType hooks** - `validate()`, `before_save()`, etc.
8. **Use Custom Fields** - Don't modify core DocTypes
9. **Use Print Formats** - Don't build custom PDF generators
10. **Use Workflow DocType** - Don't build custom approval systems

### Don'ts ❌
1. **Don't use `print()` statements** - Use `frappe.errprint()` or `frappe.log_error()`
2. **Don't use `json.loads()`** - Use `frappe.parse_json()`
3. **Don't use `requests` directly** - Use Frappe's HTTP utilities
4. **Don't write custom authentication** - Use Frappe's session management
5. **Don't write custom email systems** - Use `frappe.sendmail()`
6. **Don't write custom caching** - Use `frappe.cache()`
7. **Don't write raw SQL for common operations** - Use Frappe ORM
8. **Don't modify core files** - Use hooks and customizations
9. **Don't write custom pagination** - Use `limit_start`, `limit_page_length`
10. **Don't ignore error handling** - Use `frappe.throw()` and `frappe.log_error()`

---

## Quick Reference Checklist

Before writing custom code, ask:
- [ ] Does `frappe.utils` have this functionality?
- [ ] Can I use `frappe.db` instead of raw SQL?
- [ ] Should this be in a DocType hook instead?
- [ ] Can I use `frappe.enqueue()` for this heavy operation?
- [ ] Is there a built-in validation I can use?
- [ ] Can I use Custom Fields instead of modifying core?
- [ ] Should this be a Print Format instead of custom PDF?
- [ ] Can I use the Workflow DocType instead?
- [ ] Am I properly using `@frappe.whitelist()`?
- [ ] Am I using proper error handling with `frappe.throw()`?

**Remember**: Frappe is designed to handle 80% of common web application needs out of the box. Always check the framework documentation and source code before implementing custom solutions.

---

## Additional Resources

- **Official Documentation**: https://frappeframework.com/docs
- **Source Code**: https://github.com/frappe/frappe
- **Utils Source**: `frappe/utils/` directory for all utility functions
- **ERPNext Utils**: `erpnext/utilities/` for ERPNext-specific functions
- **Community**: https://discuss.frappe.io for questions and best practices