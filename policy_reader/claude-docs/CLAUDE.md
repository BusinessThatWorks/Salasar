# Context Package for Claude Code - Frappe Bench Implementation

## 📋 **Files to Provide to Claude Code**

When working with Claude Code in your Frappe bench environment, provide these files in **this exact order** for optimal context:

### **ESSENTIAL FILES (Must Provide)**

#### 1. **claude-salasar-bench-1.md** ⭐ **HIGHEST PRIORITY**

- **Location**: `simple-ocr/claude-salasar-bench-1.md`
- **Purpose**: Step-by-step implementation guide for minimal MVP
- **Why Essential**: This is the immediate action plan with complete code examples

#### 2. **frappe_utilities_guide.md** ⭐ **CRITICAL REFERENCE**

- **Location**: `simple-ocr/docs/frappe_utilities_guide.md`
- **Purpose**: Comprehensive Frappe framework utilities reference
- **Why Essential**: Prevents reinventing Frappe functionality, shows proper patterns

#### 3. **policy-ocr-lib/CLAUDE.md** ⭐ **CRITICAL**

- **Location**: `simple-ocr/policy-ocr-lib/CLAUDE.md`
- **Purpose**: Complete library documentation and usage patterns
- **Why Essential**: Claude Code needs to understand how to use the policy-ocr library

#### 4. **policy-fields.json** ⭐ **REQUIRED**

- **Location**: `simple-ocr/config/fields.json`
- **Purpose**: Field definitions for Motor and Health policies
- **Why Essential**: Shows what fields to extract for each policy type

### **IMPORTANT FILES (Highly Recommended)**

#### 5. **frappe_implementation.md**

- **Location**: `simple-ocr/docs/frappe_implementation.md`
- **Purpose**: Complete future implementation reference
- **Why Important**: Provides full context for future iterations

## 🎯 **Context Instructions to Give Claude Code**

### **Project Context**

```
You are working in a Frappe bench environment with:
- Existing Frappe app called "policy_reader"
- Need to integrate the policy-ocr library for document processing
- This is Phase 1 (minimal MVP) of a larger project
- Goal: Upload 1 PDF, process it, display extracted fields
```

### **Technical Context**

```

- Policy OCR Library is installed in the frappe env
- Claude API key needs configuration (environment variable or site_config.json)
- Use synchronous processing initially (no background jobs)
- Focus on Motor and Health policy types

CRITICAL: Use Frappe framework functions - DO NOT reinvent:
- File handling: Use frappe.get_doc("File"), Frappe file management
- Database operations: Use Frappe ORM methods
- Configuration: Use frappe.conf, frappe.get_single()
- Error handling: Use frappe.throw(), frappe.log_error()
- Always research Frappe documentation before writing custom utilities
```

### **Implementation Approach**

```
- Follow claude-salasar-bench-1.md for step-by-step implementation
- Create single DocType: Policy Document
- Use hardcoded field definitions initially
- Reference frappe_implementation.md for future enhancements
- Maintain compatibility for future expansion
```

### **Success Criteria**

```
Working system where user can:
1. Log into Frappe site
2. Upload a PDF file
3. Click "Process Now"
4. See extracted fields displayed
5. View processing status and errors
```

## 📁 **How to Provide Files**

### **Option 1: Direct File Share**

Copy the content of each file in the priority order listed above.

### **Option 2: Context Message Template**

```
I need to implement Policy OCR integration in Frappe. Here's the context:

PROJECT: Minimal Policy OCR integration - upload PDF, extract fields, display results

FILES PROVIDED:
1. claude-salasar-bench-1.md (implementation guide)
2. frappe_utilities_guide.md (Frappe framework utilities reference) ⭐ CRITICAL
3. CLAUDE.md (library documentation)
4. fields.json (field definitions)
5. frappe_implementation.md (future reference)
6. README.md (project overview)

ENVIRONMENT: Frappe bench with "policy-reader" app
GOAL: Working MVP today, expandable to full system later

CRITICAL: Use Frappe framework utilities - see frappe_utilities_guide.md
- File handling: Use frappe.get_doc("File") and Frappe's file management
- Configuration: Use frappe.conf.get() for settings
- Error handling: Use frappe.throw(), frappe.log_error()
- JSON operations: Use frappe.parse_json(), frappe.as_json()
- DO NOT reinvent functionality that Frappe already provides
```

## ⚠️ **Critical Context Points**

### **Phase 1 Constraints**

- **No background processing** - synchronous only
- **Hardcoded policy types** - Motor and Health only
- **Local processing only** - no RunPod yet
- **No analytics** - just basic processing

### **Future Compatibility**

- Same DocType structure as full implementation
- Same field names and database schema
- Same library integration patterns
- Progressive enhancement approach

### **Library Integration**

- Uses existing policy-ocr library from simple-ocr directory
- Requires Claude API key configuration
- Processes Motor and Health policies
- Returns structured JSON with extracted fields

## 🔄 **Iteration Strategy**

### **Phase 1 (Today)**

- Minimal working implementation per claude-salasar-bench-1.md
- Single file upload and processing
- Basic field display

### **Phase 2 (Future)**

- Background processing
- Configurable field definitions (Policy Type Config DocType)
- Enhanced error handling

### **Phase 3 (Future)**

- Analytics dashboard
- RunPod integration
- Advanced features per frappe_implementation.md

## 📊 **Context Validation**

**Claude Code should understand:**

- ✅ This is a Frappe environment
- ✅ There's an existing policy-reader app
- ✅ The policy-ocr library needs integration
- ✅ This is Phase 1 of a larger project
- ✅ The goal is a working MVP today
- ✅ Future iterations will expand functionality

**If Claude Code asks for:**

- **More Frappe-specific help**: It has adequate context
- **Library usage details**: Refer to CLAUDE.md
- **Field definitions**: Refer to fields.json
- **Implementation patterns**: Refer to test files
- **Future roadmap**: Refer to frappe_implementation.md

---

**Result**: Claude Code will have complete context to implement the minimal Policy OCR integration and understand how to iterate forward systematically! 🚀
