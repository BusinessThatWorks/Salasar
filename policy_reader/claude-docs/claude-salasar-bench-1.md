# Claude Code Implementation Guide - Policy OCR Minimal Integration

## 🎯 **Objective**
Create a minimal working Policy OCR integration in the existing `policy-reader` Frappe app. Goal: Upload 1 PDF file, process it with the policy-ocr library, and display extracted fields.

## 📋 **Context**
- You are working in a Frappe bench environment
- There is an existing Frappe app called `policy-reader`
- The policy-ocr library is available (needs installation)
- This is **Phase 1** of a larger implementation (see `docs/frappe_implementation.md` for full plan)
- Today's goal: Working MVP that can be extended later

## ⚠️ **CRITICAL: Use Frappe Framework Functions**

**DO NOT reinvent functionality that Frappe already provides.** Always use Frappe's built-in functions for:
- **File handling**: Use `frappe.get_doc("File", file_name)` and Frappe's file management
- **File paths**: Use `frappe.utils.get_files_path()`, `frappe.get_site_path()` 
- **Database operations**: Use Frappe ORM methods (`frappe.get_doc`, `frappe.get_all`)
- **Configuration**: Use `frappe.conf.get()`, `frappe.get_single()` for settings
- **Error handling**: Use `frappe.throw()`, `frappe.log_error()`
- **Validation**: Use Frappe's built-in validation patterns
- **JSON operations**: Use `frappe.parse_json()`, `frappe.as_json()`
- **Background jobs**: Use `frappe.enqueue()` for heavy operations

**📚 REFERENCE: See `docs/frappe_utilities_guide.md` for comprehensive utility reference.**

**Research Frappe documentation first** before writing custom utility functions.

## 🔧 **Prerequisites**

### 1. Install Policy OCR Library
```bash
# From the bench directory
cd /path/to/simple-ocr/policy-ocr-lib
pip install -e .

# Or if you have the wheel file
pip install /path/to/policy_ocr-0.1.0-py3-none-any.whl

# Verify installation
python3 -c "from policy_ocr import PolicyProcessor; print('Policy OCR library installed successfully')"
```

### 2. Set Claude API Key
```bash
# Option 1: Environment variable (recommended)
export ANTHROPIC_API_KEY="your-anthropic-api-key"

# Option 2: Add to site_config.json
# In sites/your-site/site_config.json add:
# "anthropic_api_key": "your-anthropic-api-key"
```

## 📁 **Implementation Steps**

### Step 1: Create Policy Document DocType

#### Create DocType via Frappe UI:
1. Go to **Desk → DocType List → New**
2. Create DocType with these settings:

**Basic Details:**
- **DocType Name**: `Policy Document`
- **Module**: `Policy Reader`
- **Is Single**: No
- **Is Submittable**: No
- **Track Changes**: Yes

**Fields to Add:**

| Field Name | Label | Field Type | Options/Default | Required | Read Only |
|------------|-------|------------|-----------------|----------|-----------|
| `title` | Title | Data | | Yes | No |
| `policy_file` | Policy File | Attach | file_types:pdf | Yes | No |
| `policy_type` | Policy Type | Select | Motor\nHealth | Yes | No |
| `status` | Status | Select | Draft\nProcessing\nCompleted\nFailed | Yes | Yes |
| `section_break_1` | | Section Break | Processing Results | | |
| `extracted_fields` | Extracted Fields | JSON | | No | Yes |
| `processing_time` | Processing Time (seconds) | Float | precision: 2 | No | Yes |
| `error_message` | Error Message | Long Text | | No | Yes |

**Permissions:**
- Give **All** permissions to **System Manager** role
- Give **Read, Write, Create** permissions to **All** role (for testing)

### Step 2: Create Python Controller

Create file: `apps/policy_reader/policy_reader/doctype/policy_document/policy_document.py`

```python
import frappe
import json
import os
from frappe.model.document import Document
from frappe.utils import get_site_path, get_files_path

class PolicyDocument(Document):
    def before_save(self):
        # Auto-generate title from filename
        if not self.title and self.policy_file:
            self.title = self.get_filename_from_attachment()
    
    def validate(self):
        if self.status == "Completed" and not self.extracted_fields:
            frappe.throw("Extracted fields cannot be empty for completed documents")
    
    def get_filename_from_attachment(self):
        """Extract filename from file attachment"""
        if self.policy_file:
            return os.path.basename(self.policy_file).replace('.pdf', '').replace('.PDF', '')
        return "New Policy Document"
    
    @frappe.whitelist()
    def process_policy(self):
        """Process the policy document using policy-ocr library"""
        if not self.policy_file:
            frappe.throw("No file attached")
        
        if not self.policy_type:
            frappe.throw("Policy type is required")
        
        try:
            # Update status
            self.status = "Processing"
            self.save()
            frappe.db.commit()
            
            # Get file path
            file_path = self.get_full_file_path()
            
            # Import and configure policy-ocr library
            from policy_ocr import PolicyProcessor, OCRConfig
            
            # Get API key using proper Frappe config patterns (per frappe_utilities_guide.md)
            api_key = frappe.conf.get('anthropic_api_key') or os.environ.get('ANTHROPIC_API_KEY')
            if not api_key:
                frappe.throw("ANTHROPIC_API_KEY not configured. Add 'anthropic_api_key' to site_config.json or set ANTHROPIC_API_KEY environment variable")
            
            # Configure OCR with simple settings
            config = OCRConfig(
                claude_api_key=api_key,
                fast_mode=True,  # Process only first 3 pages
                max_pages=5,     # Limit pages for initial testing
                confidence_threshold=0.5,
                enable_logging=True
            )
            
            processor = PolicyProcessor(config)
            
            # Process the document
            import time
            start_time = time.time()
            
            result = processor.process_policy(
                file_path=file_path,
                policy_type=self.policy_type.lower()
            )
            
            end_time = time.time()
            processing_time = round(end_time - start_time, 2)
            
            # Update document with results
            if result.get("success"):
                self.status = "Completed"
                self.extracted_fields = frappe.as_json(result.get("extracted_fields", {}))  # Use Frappe JSON utility
                self.processing_time = processing_time
                self.error_message = ""
                
                # Log success for monitoring (optional)
                frappe.logger().info(f"Policy OCR completed successfully for {self.name}")
            else:
                self.status = "Failed"
                self.error_message = result.get("error", "Unknown error occurred")
                
                # Log business logic errors
                frappe.log_error(f"Policy OCR processing failed for {self.name}: {self.error_message}", "Policy OCR Processing Error")
            
            self.save()
            frappe.db.commit()
            
            return {
                "success": result.get("success", False),
                "message": "Processing completed successfully" if result.get("success") else self.error_message,
                "extracted_fields": result.get("extracted_fields", {}),
                "processing_time": processing_time
            }
            
        except Exception as e:
            # Handle system errors with proper Frappe error handling
            self.status = "Failed"
            self.error_message = str(e)
            self.save()
            frappe.db.commit()
            
            # Log detailed technical error for debugging
            frappe.log_error(f"Policy processing system error for {self.name}: {str(e)}", "Policy OCR System Error")
            
            # Throw user-friendly error message
            frappe.throw(f"Failed to process policy document: {str(e)}")
    
    def get_full_file_path(self):
        """Get absolute path to the uploaded file using Frappe's file management"""
        if not self.policy_file:
            frappe.throw("No file attached")
        
        # Use Frappe's built-in File DocType - proper way per frappe_utilities_guide.md
        try:
            # Method 1: Get File document by file_url
            file_doc = frappe.get_doc("File", {"file_url": self.policy_file})
            return file_doc.get_full_path()
        except frappe.DoesNotExistError:
            # Method 2: Try getting by file_name if URL lookup fails
            try:
                file_name = self.policy_file.split('/')[-1]  # Extract filename from URL
                file_doc = frappe.get_doc("File", {"file_name": file_name})
                return file_doc.get_full_path()
            except frappe.DoesNotExistError:
                frappe.throw(f"File not found in system: {self.policy_file}")
        except Exception as e:
            frappe.log_error(f"File access error: {str(e)}", "Policy OCR File Error")
            frappe.throw(f"Could not access file: {self.policy_file}")
    
    def get_extracted_fields_display(self):
        """Get extracted fields in a readable format using Frappe JSON utility"""
        if not self.extracted_fields:
            return {}
        
        try:
            return frappe.parse_json(self.extracted_fields)  # Use Frappe's safe JSON parsing
        except Exception as e:
            frappe.log_error(f"Error parsing extracted fields for {self.name}: {str(e)}", "Policy OCR JSON Error")
            return {}
```

### Step 3: Create JavaScript Controller

Create file: `apps/policy_reader/policy_reader/doctype/policy_document/policy_document.js`

```javascript
frappe.ui.form.on('Policy Document', {
    refresh: function(frm) {
        // Add Process Now button
        if (frm.doc.policy_file && frm.doc.policy_type && frm.doc.status !== 'Processing') {
            frm.add_custom_button(__('Process Now'), function() {
                frm.call('process_policy').then(r => {
                    if (r.message) {
                        if (r.message.success) {
                            frappe.show_alert({
                                message: __('Processing completed successfully'),
                                indicator: 'green'
                            });
                            frm.reload_doc();
                        } else {
                            frappe.msgprint({
                                title: __('Processing Failed'),
                                message: r.message.message,
                                indicator: 'red'
                            });
                        }
                    }
                });
            }, __('Actions'));
        }
        
        // Show processing status
        if (frm.doc.status === 'Processing') {
            frm.dashboard.add_comment(__('Processing in progress...'), 'blue', true);
        }
        
        // Display extracted fields in a better format
        if (frm.doc.status === 'Completed' && frm.doc.extracted_fields) {
            frm.trigger('display_extracted_fields');
        }
    },
    
    policy_file: function(frm) {
        // Auto-generate title from filename
        if (frm.doc.policy_file && !frm.doc.title) {
            let filename = frm.doc.policy_file.split('/').pop();
            let title = filename.replace('.pdf', '').replace('.PDF', '');
            frm.set_value('title', title);
        }
    },
    
    display_extracted_fields: function(frm) {
        if (!frm.doc.extracted_fields) return;
        
        try {
            let fields = JSON.parse(frm.doc.extracted_fields);
            let html = '<div class="extracted-fields-display" style="margin-top: 10px;">';
            html += '<h5>Extracted Fields:</h5>';
            html += '<div class="row">';
            
            Object.keys(fields).forEach(key => {
                let value = fields[key] || 'Not found';
                let status_color = fields[key] ? '#28a745' : '#dc3545';
                let status_icon = fields[key] ? '✓' : '✗';
                
                html += `
                    <div class="col-md-6 mb-2">
                        <div class="card" style="border-left: 3px solid ${status_color};">
                            <div class="card-body p-2">
                                <strong>${key}:</strong><br>
                                <span style="color: ${status_color};">
                                    ${status_icon} ${value}
                                </span>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += '</div></div>';
            
            // Add to form
            if (!frm.fields_dict.extracted_fields_html) {
                frm.add_custom_button(__(''), function() {}, __(''));
            }
            
            // Insert after extracted_fields
            $(frm.fields_dict.extracted_fields.wrapper).after(html);
            
        } catch (e) {
            console.error('Error displaying extracted fields:', e);
        }
    }
});
```

### Step 4: Apply Changes and Test

```bash
# In your bench directory
bench migrate

# Clear cache
bench clear-cache

# Restart (if needed)
bench restart
```

## 🧪 **Testing the Implementation**

### Test with Sample Data:

1. **Go to Policy Document List**
   - Navigate to: Desk → Policy Document → New

2. **Upload a PDF**
   - Click "Policy File" and upload a sample PDF
   - Select "Motor" or "Health" for Policy Type
   - Save the document

3. **Process the Document**
   - Click the "Process Now" button
   - Wait for processing to complete
   - View the extracted fields

### Expected Behavior:

- **Status changes**: Draft → Processing → Completed/Failed
- **Extracted fields appear**: Formatted display of found data
- **Processing time recorded**: Shows how long it took
- **Error handling**: Clear error messages if something fails

## 🔍 **Troubleshooting**

### Common Issues:

1. **"policy-ocr library not installed"**
   ```bash
   pip install -e /path/to/simple-ocr/policy-ocr-lib
   ```

2. **"ANTHROPIC_API_KEY not configured"**
   ```bash
   export ANTHROPIC_API_KEY="your-key"
   # Or add to site_config.json
   ```

3. **"File not found" error**
   - Check file permissions
   - Verify file upload worked correctly
   - Check `sites/your-site/public/files/` directory

4. **Import errors**
   ```bash
   # Test library installation
   python3 -c "from policy_ocr import PolicyProcessor; print('OK')"
   
   # Check Python path
   which python3
   pip list | grep policy-ocr
   ```

### Debug Commands:

```bash
# Check Frappe logs
bench logs

# Test in Frappe console
bench console
>>> from policy_ocr import PolicyProcessor
>>> print("Library available")

# Check site configuration
bench console
>>> import frappe
>>> print(frappe.conf.get('anthropic_api_key'))
```

## 🎯 **Success Criteria**

✅ **You'll know it's working when:**
- You can upload a PDF file
- Click "Process Now" button
- See status change to "Processing" then "Completed"
- View extracted fields in formatted display
- Processing time is recorded

## 🚀 **Next Steps** 

This minimal implementation provides the foundation for:
- **Background processing** (Phase 2)
- **Configurable field definitions** (Phase 2)
- **Analytics dashboard** (Phase 3)
- **RunPod integration** (Phase 3)

See `docs/frappe_implementation.md` for the complete implementation plan.

---

## 📚 **Context Files Referenced**

- `docs/frappe_implementation.md` - Full implementation reference
- `policy-ocr-lib/CLAUDE.md` - Library documentation  
- `config/fields.json` - Field definitions
- `tests/test_single_policy.py` - Working code example

**Happy coding! 🎉** You now have everything needed to create a working Policy OCR integration in Frappe.