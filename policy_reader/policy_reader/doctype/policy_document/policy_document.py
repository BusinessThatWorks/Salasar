# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document
from frappe.utils import getdate, cstr, flt, cint
from policy_reader.policy_reader.services.common_service import CommonService
from policy_reader.policy_reader.services.claude_vision_service import ClaudeVisionService
from policy_reader.policy_reader.services.api_health_service import APIHealthService


class PolicyDocument(Document):
    def before_save(self):
        # Auto-update title when file is uploaded or changed
        if self.policy_file:
            # Check if this is a new document or if the file has changed
            if not self.title or (self.has_value_changed('policy_file') and self.policy_file):
                self.title = self.get_filename_from_attachment()

        # Auto-populate processor information
        self._populate_processor_info()

    def validate(self):
        if self.status == "Completed" and not self.extracted_fields:
            frappe.throw("Invalid input: extracted fields cannot be empty for completed documents")
        
        # Prevent changing policy type after extraction
        if self.extraction_policy_type and self.policy_type and self.extraction_policy_type != self.policy_type:
            frappe.throw(f"Invalid input: Cannot change policy type after extraction. Extracted fields were generated for '{self.extraction_policy_type}' policy type. Please reprocess the document if you need to change the policy type.")
    
    def get_filename_from_attachment(self):
        """Extract filename from file attachment and clean it up"""
        if self.policy_file:
            # Get just the filename without path
            filename = os.path.basename(self.policy_file)
            
            # Remove file extensions (case insensitive)
            filename_no_ext = os.path.splitext(filename)[0]
            
            # Clean up the filename: replace underscores/hyphens with spaces, title case
            cleaned_name = filename_no_ext.replace('_', ' ').replace('-', ' ')
            
            # Remove extra spaces and title case each word
            cleaned_name = ' '.join(word.capitalize() for word in cleaned_name.split() if word)
            
            return cleaned_name if cleaned_name else "Policy Document"
        return "New Policy Document"

    def _populate_processor_info(self):
        """Auto-populate processor information from logged-in user's Insurance Employee record"""
        try:
            # Skip if already populated or for system users
            current_user = frappe.session.user
            if current_user in ["Administrator", "Guest"]:
                return

            # Only populate on new documents or if not already set
            if self.processor_employee_code:
                return

            # Query Insurance Employee record for logged-in user
            employee = frappe.db.get_value(
                "Insurance Employee",
                {"user": current_user},
                ["employee_code", "employee_type", "employee_name", "branch_name"],
                as_dict=True
            )

            if employee:
                self.processor_employee_code = employee.get("employee_code")
                self.processor_employee_type = employee.get("employee_type")
                self.processor_employee_name = employee.get("employee_name")
                self.processor_branch_name = employee.get("branch_name")
                frappe.logger().info(f"Auto-populated processor info for Policy Document: {employee}")
            else:
                frappe.logger().info(f"No Insurance Employee record found for user {current_user}")

        except Exception as e:
            frappe.logger().error(f"Error populating processor info: {str(e)}")
            # Don't throw - this is a non-critical operation

    def get_policy_reader_settings(self):
        """Get Policy Reader Settings with fallback to defaults"""
        return CommonService.get_policy_reader_settings()
    
    @frappe.whitelist()
    def process_policy(self, background=True):
        """Process policy document with Claude AI - can run in background or synchronously"""
        if not self.policy_file:
            frappe.throw("Invalid input: no file attached")
        
        if not self.policy_type:
            frappe.throw("Invalid input: policy type is required for processing")
        
        # File validation removed - proceeding directly with processing
        
        # Update status to Processing immediately
        self.status = "Processing"
        self.processing_method = "claude_vision"
        # Store the policy type used for extraction
        self.extraction_policy_type = self.policy_type
        self.save()
        frappe.db.commit()
        
        if background:
            # Enqueue background job
            settings = self.get_policy_reader_settings()
            timestamp = int(time.time())
            
            frappe.enqueue(
                method="policy_reader.policy_reader.doctype.policy_document.policy_document.process_policy_background",
                queue=settings.queue_type or 'short',
                timeout=settings.timeout or 180,
                is_async=True,
                job_name=f"policy_reader_{self.name}_{timestamp}",
                doc_name=self.name
            )
            
            return {
                "success": True,
                "message": "Policy processing started in background. You will be notified when complete.",
                "status": "Processing"
            }
        else:
            # Process directly
            try:
                result = self.process_policy_internal()
                
                return {
                    "success": result.get("success", False),
                    "message": "AI processing completed successfully" if result.get("success") else result.get("error", "Unknown error"),
                    "extracted_fields": result.get("extracted_fields", {}),
                    "processing_time": result.get("processing_time", 0)
                }
                
            except Exception as e:
                self.status = "Failed"
                self.error_message = str(e)
                self.save()
                frappe.db.commit()
                
                frappe.log_error(f"Unexpected error while processing policy document {self.name}: {str(e)}", frappe.get_traceback())
                
                # Notify user of failure
                frappe.publish_realtime(
                    event="policy_processing_complete",
                    message={
                        "doc_name": self.name,
                        "status": "Failed",
                        "message": f"AI processing failed: {str(e)}",
                        "processing_time": 0
                    },
                    user=self.owner
                )
                
                frappe.throw("Unexpected error occurred while processing with AI. Please contact support.")
    
    def process_policy_internal(self):
        """Internal method for actual policy processing (runs in background) - uses Claude Vision"""
        try:
            # Validate prerequisites
            if not self._validate_processing_prerequisites():
                frappe.throw("Processing prerequisites not met")
            
            # Execute AI processing
            result, processing_time = self._execute_ai_processing()
            
            # Update document status
            self._update_document_status(result, processing_time)
            
            # Notify completion
            self._notify_processing_completion(result, processing_time)
            
            return result
            
        except Exception as e:
            CommonService.log_processing_error("processing policy document", e, self.name)
            return self._handle_processing_error(e)
    
    def _validate_processing_prerequisites(self):
        """Validate prerequisites for processing"""
        # Check for timeout before starting processing
        if self.check_processing_timeout():
            return False
            
        # File validation removed - proceeding directly with processing
        
        return True
    
    def _execute_ai_processing(self):
        """Execute AI processing and return result with timing"""
        file_path = self.get_full_file_path()
        settings = self.get_policy_reader_settings()
        
        # Get API key using common service
        api_key = CommonService.get_api_key(settings)
        
        # Process with Claude Vision API using static method
        start_time = time.time()
        result = ClaudeVisionService.process_pdf(file_path, api_key, settings, self.policy_type)
        end_time = time.time()
        processing_time = round(end_time - start_time, 2)
        
        return result, processing_time
    
    def _update_document_status(self, result, processing_time):
        """Update document with processing results"""
        if result.get("success"):
            self.status = "Completed"
            self.extracted_fields = frappe.as_json(result.get("extracted_fields", {}))
            self.processing_time = processing_time
            self.processing_method = "claude_vision"
            self.tokens_used = result.get("tokens_used", 0)
            self.error_message = ""
            
            frappe.logger().info(f"Claude Vision processing completed for {self.name}")
        else:
            self.status = "Failed"
            self.error_message = result.get("error", "Unknown error occurred")
            
            frappe.log_error(f"Claude Vision processing failed for {self.name}: {self.error_message}", frappe.get_traceback())
            
        self.save()
        frappe.db.commit()
            
    def _notify_processing_completion(self, result, processing_time):
        """Notify user via real-time updates"""
        notification_message = "Claude Vision processing completed successfully" if result.get("success") else self.error_message
        
        frappe.publish_realtime(
            event="policy_processing_complete",
            message={
                "doc_name": self.name,
                "status": self.status,
                "message": notification_message,
                "processing_time": processing_time,
                "processing_method": "claude_vision",
                "tokens_used": self.tokens_used if hasattr(self, 'tokens_used') else 0
            },
            user=self.owner
        )
            
    def _handle_processing_error(self, error):
        """Handle processing errors"""
        self.status = "Failed"
        self.error_message = str(error)
        self.save()
        frappe.db.commit()
        
        CommonService.log_processing_error("processing policy document", error, self.name)
        
        # Notify user of failure
        frappe.publish_realtime(
            event="policy_processing_complete",
            message={
                "doc_name": self.name,
                "status": "Failed",
                "message": f"Processing failed: {str(error)}",
                "processing_time": 0
            },
            user=self.owner
        )
    
    def validate_file_access(self):
        """Validate that the file is accessible for processing - DISABLED"""
        return True  # Always return True to skip validation
    
    
    def get_full_file_path(self):
        """Get absolute path to the uploaded file - SIMPLIFIED VERSION"""
        if not self.policy_file:
            frappe.throw("No file attached")
        
        # Simple approach: just try to get the file and return its path
        try:
            file_doc = frappe.get_doc("File", {"file_url": self.policy_file})
            return file_doc.get_full_path()
        except:
            # If that fails, try to construct a simple path
            site_path = frappe.get_site_path()
            if self.policy_file.startswith('./'):
                clean_path = self.policy_file.lstrip('./')
                return os.path.join(site_path, clean_path)
            else:
                # Just use the filename
                filename = os.path.basename(self.policy_file)
                return os.path.join(site_path, 'private', 'files', filename)
    
    def get_extracted_fields_display(self):
        """Get extracted fields in a readable format using Frappe JSON utility"""
        if not self.extracted_fields:
            return {}
        
        try:
            return frappe.parse_json(self.extracted_fields)
        except Exception as e:
            frappe.log_error(f"Error parsing extracted fields for {self.name}: {str(e)}", "Policy OCR JSON Error")
            return {}
    
    
    
    
    
    
    
    @frappe.whitelist()
    def reset_processing_status(self):
        """Reset processing status for stuck documents using Frappe patterns"""
        try:
            if self.status == "Processing":
                self.status = "Draft"
                self.error_message = "Processing was reset by user"
                self.save()
                
                # Use Frappe's message system for user feedback
                frappe.msgprint("Processing status has been reset. You can now retry processing.", 
                              title="Status Reset", indicator="blue")
                
                return {"success": True, "message": "Status reset successfully"}
            else:
                # Use Frappe's throw for validation errors
                frappe.throw(f"Cannot reset status. Current status is '{self.status}', only 'Processing' status can be reset.")
                
        except Exception as e:
            # Use Frappe error logging
            frappe.log_error(f"Failed to reset processing status for {self.name}: {str(e)}", "Status Reset Error")
            frappe.throw(f"Failed to reset status: {str(e)}")
    
    def check_processing_timeout(self):
        """Check if document has been stuck in processing for too long"""
        if self.status == "Processing" and self.modified:
            # Use Frappe's time utilities for proper date handling
            from frappe.utils import time_diff, now_datetime
            
            # time_diff returns difference in seconds, convert to minutes
            seconds_elapsed = time_diff(now_datetime(), self.modified).total_seconds()
            minutes_elapsed = int(seconds_elapsed / 60)
            
            # If processing for more than 10 minutes, consider it stuck
            if minutes_elapsed > 10:
                self.status = "Failed"
                self.error_message = f"Processing timed out after {minutes_elapsed} minutes. Please try again or check if the API is accessible."
                self.save()
                
                # Use Frappe's logging for timeout events
                frappe.log_error(f"Document {self.name} processing timed out after {minutes_elapsed} minutes", "Processing Timeout")
                
                return True
        return False
    
    
    

# API Key status checking method
@frappe.whitelist()
def check_api_key_status():
    """Check if Anthropic API key is configured and return status"""
    return APIHealthService.get_api_status()

@frappe.whitelist()
def test_claude_api_health():
    """Test Claude API connectivity with a simple health check"""
    return APIHealthService.test_claude_api_health()

@frappe.whitelist()
def get_current_user_employee_info():
    """Get Insurance Employee info for the current logged-in user"""
    try:
        current_user = frappe.session.user

        frappe.logger().info(f"=== GET CURRENT USER EMPLOYEE INFO DEBUG ===")
        frappe.logger().info(f"Current logged-in user: {current_user}")
        frappe.logger().info(f"Session user email: {frappe.session.user}")

        # Skip for Guest only (allow Administrator for now for testing)
        if current_user == "Guest":
            frappe.logger().info(f"Skipping for Guest user")
            return {"employee": None}

        # Query Insurance Employee record
        frappe.logger().info(f"Querying Insurance Employee with user={current_user}")

        employee = frappe.db.get_value(
            "Insurance Employee",
            {"user": current_user},
            ["employee_code", "employee_type", "employee_name", "branch_name"],
            as_dict=True
        )

        if employee:
            frappe.logger().info(f"Found Insurance Employee: {employee}")
        else:
            frappe.logger().warning(f"No Insurance Employee found for user: {current_user}")

        return {"employee": employee}
    except Exception as e:
        frappe.logger().error(f"Error fetching current user employee info: {str(e)}")
        frappe.log_error(f"Error in get_current_user_employee_info: {str(e)}", frappe.get_traceback())
        return {"employee": None}

# Background job method - must be module level for frappe.enqueue
@frappe.whitelist()
def process_policy_background(doc_name):
    """Background job for policy processing"""
    doc = None
    try:
        # Initialize Frappe context for background job
        if not frappe.db:
            frappe.init_site()
        
        # Get document and set user context for file access
        doc = frappe.get_doc("Policy Document", doc_name)
        frappe.set_user(doc.owner)
        
        # Process the policy
        doc.process_policy_internal()
        
    except Exception as e:
        error_msg = f"Background job failed for Policy Document {doc_name}: {str(e)}"
        frappe.log_error(error_msg, "Policy OCR Background Job Error")
        
        # Update document status to failed
        try:
            if not doc:
                doc = frappe.get_doc("Policy Document", doc_name)
            
            # Set user context to update the document
            frappe.set_user(doc.owner)
            
            doc.status = "Failed"
            doc.error_message = f"Background job failed: {str(e)}"
            doc.save()
            frappe.db.commit()
            
            # Notify user of failure
            frappe.publish_realtime(
                event="policy_processing_complete",
                message={
                    "doc_name": doc_name,
                    "status": "Failed", 
                    "message": f"Processing failed: {str(e)}",
                    "processing_time": 0
                },
                user=doc.owner
            )
            
        except Exception as save_error:
            frappe.log_error(f"Failed to update document status for {doc_name}: {str(save_error)}", "Policy OCR Status Update Error")
            # Don't re-raise to avoid recursive errors
    