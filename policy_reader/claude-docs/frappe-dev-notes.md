# Frappe Development Notes

*Quick reference for Frappe Framework development patterns and best practices*

## 🎯 Form JavaScript Patterns

### Event Handlers
```javascript
frappe.ui.form.on('DocType Name', {
    refresh: function(frm) {
        // Form initialization logic
    },
    
    field_name: function(frm) {
        // Field change handlers
    }
});
```

### Method Calling
```javascript
// ✅ CORRECT - Use trigger for custom methods
frm.trigger('custom_method_name');

// ❌ WRONG - Don't call methods directly
frm.custom_method_name(); // Will cause "not a function" errors
```

### Form Layout Properties
```javascript
// ✅ CORRECT
frm.layout.main.hide();
frm.layout.main.show();

// ❌ WRONG
frm.layout_main.hide(); // Property doesn't exist
```

### Field Access
```javascript
// Access field wrapper
frm.fields_dict[fieldname].wrapper

// Set field properties
frm.set_df_property(fieldname, 'hidden', 1);
frm.refresh_field(fieldname);
```

## 🔄 Background Jobs

### Module Path Format
```javascript
// ✅ CORRECT - Full path required
frappe.enqueue(
    method="app_name.app_name.doctype.doctype_name.method_name",
    // ...
);

// ❌ WRONG - Incomplete path will fail
method="app_name.doctype.doctype_name.method_name"
```

### User Context for Private Files
```python
@frappe.whitelist()
def background_method(doc_name):
    doc = frappe.get_doc("DocType", doc_name)
    frappe.set_user(doc.owner)  # Essential for private file access
    # ... processing logic
```

### Queue Configuration
```python
frappe.enqueue(
    method="...",
    queue='short',     # <5 min jobs
    timeout=180,       # 3 minutes
    is_async=True,
    job_name="unique_job_name"
)
```

## ⚙️ Settings & Configuration

### Single DocType Settings
```python
# Get settings with fallback
try:
    settings = frappe.get_single("Settings DocType")
except:
    # Use defaults
    pass
```

### API Key Priority Chain
```python
# Priority: Settings → site_config → environment
api_key = (settings.api_key or 
          frappe.conf.get('api_key') or 
          os.environ.get('API_KEY'))
```

### Empty String Handling
```python
def is_valid_key(key):
    return key and key.strip()  # Handles None and empty strings
```

## 📁 File Handling

### Private File Access Issues
```python
# Problem: Background jobs can't access private files
# Solution: Set user context
frappe.set_user(document_owner)

# Validate file accessibility
def validate_file_access(self):
    file_doc = frappe.get_doc("File", {"file_url": self.file_url})
    file_path = file_doc.get_full_path()
    return os.path.exists(file_path) and os.access(file_path, os.R_OK)
```

## 🎨 Frontend Development

### Split View Implementation
```css
.split-container {
    display: flex;
    height: calc(100vh - 150px);
}

.split-left {
    flex: 0 0 60%;
}

.split-right {
    flex: 1;
}

/* Mobile responsive */
@media (max-width: 768px) {
    .split-container {
        flex-direction: column;
    }
}
```

### User Preferences
```javascript
// Store preferences
localStorage.setItem('preference_key', value);

// Retrieve with fallback
let preference = localStorage.getItem('preference_key') || 'default';
```

### Real-time Updates
```javascript
// Listen for events
frappe.realtime.on('event_name', function(message) {
    // Handle real-time updates
});

// Publish events (Python)
frappe.publish_realtime(
    event="event_name",
    message={"data": "value"},
    user=user_name
)
```

### Modal Dialogs
```javascript
// Create modal with dynamic content
let modal = new frappe.ui.Dialog({
    title: __('Modal Title'),
    size: 'large', // or 'small', 'extra-large'
    fields: [
        {
            fieldtype: 'HTML',
            fieldname: 'content',
            options: '<div id="dynamic-content">Loading...</div>'
        }
    ],
    primary_action_label: __('Action'),
    primary_action: function() {
        // Handle action
        modal.hide();
    }
});

modal.show();

// Style modal after creation
modal.$wrapper.find('.modal-dialog').addClass('modal-xl');

// Populate dynamic content after modal is shown
setTimeout(() => {
    $('#dynamic-content').html('Actual content here');
}, 100);
```

### Modal Content Population
```javascript
// ❌ WRONG - frm.trigger() doesn't return values
let content = frm.trigger('generate_content');
$('#container').html(content); // Will be undefined

// ✅ CORRECT - Generate content directly in the method
populate_content: function(frm) {
    let content = `<div>Generated HTML content</div>`;
    $('#container').html(content);
}
```

## ⚠️ Common Pitfalls

### JavaScript Errors
1. **Method not found**: Use `frm.trigger()` not direct calls
2. **Layout undefined**: Use `frm.layout.main` not `frm.layout_main`
3. **Import errors**: Use complete module paths in background jobs
4. **Complex layouts**: Use modals instead of DOM manipulation for better reliability
5. **Empty modal content**: `frm.trigger()` doesn't return values, generate content directly

### Background Job Failures
1. **Private files**: Set proper user context with `frappe.set_user()`
2. **Module imports**: Ensure complete path format
3. **Empty configs**: Handle empty strings in configuration

### File Access Issues
1. **Permission errors**: Background jobs need user context
2. **Path resolution**: Use `frappe.get_doc("File")` methods
3. **Validation**: Always validate file exists before processing

## 🔧 Development Workflow

### After Code Changes
```bash
# JavaScript changes
bench restart

# DocType schema changes  
bench --site sitename reload-doctype "DocType Name"

# New DocType creation
# Use Frappe UI - bench commands limited
```

### Git Workflow
```bash
# Feature branches
git checkout -b feature-name

# Check app-specific changes
cd apps/app_name && git status

# Clean commits for app changes only
```

### Debugging Tips
1. **Console errors**: Check browser dev tools first
2. **Background jobs**: Check logs and Redis queues
3. **File issues**: Validate paths and permissions
4. **Settings**: Verify DocType reload after schema changes

## 🎯 Key Success Patterns

1. **Follow Frappe Conventions**: Use established patterns from framework
2. **Error Handling**: Always handle exceptions gracefully
3. **User Context**: Critical for private file access in background jobs
4. **Responsive Design**: Use Bootstrap classes and mobile-first approach
5. **Real-time Updates**: Provide immediate user feedback
6. **Settings Management**: Create Single DocTypes for configuration
7. **Clean JavaScript**: Use trigger pattern for method calls
8. **Modal Over Complex DOM**: Prefer modals for complex UI over DOM manipulation
9. **Direct Content Generation**: Generate HTML content directly, don't rely on trigger return values

---

*Last updated: Policy Reader Modal PDF Viewer Implementation*