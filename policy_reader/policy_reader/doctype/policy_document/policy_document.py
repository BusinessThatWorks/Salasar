# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document
from frappe.utils import getdate, cstr, flt, cint
from policy_reader.policy_reader.services.processing_service import ProcessingService
from policy_reader.policy_reader.services.runpod_service import RunPodService  
from policy_reader.policy_reader.services.extraction_service import ExtractionService
from policy_reader.policy_reader.services.policy_creation_service import PolicyCreationService


class PolicyDocument(Document):
    def before_save(self):
        # Auto-update title when file is uploaded or changed
        if self.policy_file:
            # Check if this is a new document or if the file has changed
            if not self.title or (self.has_value_changed('policy_file') and self.policy_file):
                self.title = self.get_filename_from_attachment()
    
    def validate(self):
        if self.status == "Completed" and not self.extracted_fields:
            frappe.throw("Extracted fields cannot be empty for completed documents")
    
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
    
    def get_policy_reader_settings(self):
        """Get Policy Reader Settings with fallback to defaults"""
        try:
            settings = frappe.get_single("Policy Reader Settings")
            return settings
        except:
            # Return object with default values if settings don't exist
            class DefaultSettings:
                anthropic_api_key = None
                fast_mode = True
                max_pages = 3
                confidence_threshold = 0.3
                enable_logging = True
                timeout = 180
                queue_type = "short"
            return DefaultSettings()
    
    @frappe.whitelist()
    def process_policy(self):
        """Enqueue policy processing as background job"""
        if not self.policy_file:
            frappe.throw("No file attached")
        
        if not self.policy_type:
            frappe.throw("Policy type is required")
        
        # Validate file access before enqueueing job
        if not self.validate_file_access():
            frappe.throw("File is not accessible for processing. Please check that the file is properly uploaded and accessible.")
        
        # Get settings for background job configuration
        settings = self.get_policy_reader_settings()
        
        # Update status to Processing immediately
        self.status = "Processing"
        self.save()
        frappe.db.commit()
        
        # Enqueue background job using settings configuration
        import time
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
    
    def process_policy_internal(self):
        """Internal method for actual policy processing (runs in background)"""
        try:
            # Check for timeout before starting processing
            if self.check_processing_timeout():
                return  # Document was timed out, exit early
                
            # Validate file accessibility before processing
            if not self.validate_file_access():
                raise Exception("File is not accessible for processing. Please ensure the file is uploaded and accessible.")
            
            file_path = self.get_full_file_path()
            
            # Get settings for processing configuration
            settings = self.get_policy_reader_settings()
            
            start_time = time.time()
            
            # Choose processing method: RunPod or Local
            processing_method = self.choose_processing_method(settings)
            
            # Step 1: Extract text using chosen method
            if processing_method == "runpod":
                # Use RunPod API for text extraction
                result = self.extract_text_with_runpod(file_path, settings)
                if not result.get("success"):
                    frappe.logger().warning(f"RunPod processing failed, falling back to local: {result.get('error')}")
                    # Fallback to local processing
                    result = self.extract_text_with_local(file_path, settings)
            else:
                # Use local document_reader library
                result = self.extract_text_with_local(file_path, settings)
            
            extracted_text = result.get('text', '')
            confidence_data = result.get('confidence_data', {})
            runpod_endpoint = result.get('runpod_endpoint', '')
            
            # Store RunPod endpoint immediately after RunPod call (before Claude extraction)
            self.runpod_endpoint = runpod_endpoint
            
            # Step 2: Extract structured fields using Claude API
            claude_result = self.extract_fields_with_claude(extracted_text, self.policy_type.lower(), settings)
            
            end_time = time.time()
            processing_time = round(end_time - start_time, 2)
            
            if claude_result.get("success"):
                # Extract confidence metrics with error handling
                try:
                    avg_confidence = confidence_data.get('average_confidence', 0.0)
                    enhancement_applied = any(
                        m.get('enhancement_applied', False) 
                        for m in confidence_data.get('enhancement_metrics', [])
                    )
                    
                    # Determine if manual review is recommended (confidence < 70%)
                    manual_review_recommended = avg_confidence < 0.7
                except Exception as confidence_error:
                    frappe.logger().warning(f"Error extracting confidence metrics: {str(confidence_error)}")
                    # Fallback values
                    avg_confidence = 0.0
                    enhancement_applied = False
                    manual_review_recommended = True  # Default to recommending review if we can't determine confidence
                
                self.status = "Completed"
                self.extracted_fields = frappe.as_json(claude_result.get("extracted_fields", {}))
                self.raw_ocr_text = extracted_text  # Store raw OCR text for re-extraction
                self.processing_time = processing_time
                self.error_message = ""
                
                # Store processing method used
                self.processing_method = processing_method
                
                # Store confidence metrics
                # The document reader returns confidence as decimal (0.72 = 72%)
                # Frappe Percent field expects percentage value (72 for 72%)
                self.ocr_confidence = float(avg_confidence) * 100
                self.manual_review_recommended = 1 if manual_review_recommended else 0
                self.enhancement_applied = 1 if enhancement_applied else 0
                self.confidence_data = frappe.as_json(confidence_data)
                
                # Field extraction completed successfully
            else:
                self.status = "Failed"
                self.error_message = claude_result.get("error", "Unknown error occurred")
                
                frappe.log_error(f"Policy OCR processing failed for {self.name}: {self.error_message}", "Policy OCR Processing Error")
            
            self.save()
            frappe.db.commit()
            
            # Notify user via real-time updates
            notification_message = "Processing completed successfully"
            if self.status == "Completed" and hasattr(self, 'ocr_confidence'):
                confidence_pct = int(self.ocr_confidence)  # Already stored as percentage
                method_text = "RunPod API" if processing_method == "runpod" else "Local OCR"
                notification_message = f"Processing completed successfully via {method_text} (OCR confidence: {confidence_pct}%)"
                if self.manual_review_recommended:
                    notification_message += " - Manual review recommended"
            elif self.status != "Completed":
                notification_message = self.error_message
                
            frappe.publish_realtime(
                event="policy_processing_complete",
                message={
                    "doc_name": self.name,
                    "status": self.status,
                    "message": notification_message,
                    "processing_time": processing_time if hasattr(self, 'processing_time') else 0,
                    "ocr_confidence": getattr(self, 'ocr_confidence', 0),  # Already stored as percentage
                    "manual_review_recommended": getattr(self, 'manual_review_recommended', 0),
                    "processing_method": processing_method
                },
                user=self.owner
            )
            
        except Exception as e:
            self.status = "Failed"
            self.error_message = str(e)
            self.save()
            frappe.db.commit()
            
            frappe.log_error(f"Policy processing system error for {self.name}: {str(e)}", "Policy OCR System Error")
            
            # Notify user of failure
            frappe.publish_realtime(
                event="policy_processing_complete",
                message={
                    "doc_name": self.name,
                    "status": "Failed",
                    "message": f"Processing failed: {str(e)}",
                    "processing_time": 0
                },
                user=self.owner
            )
    
    def choose_processing_method(self, settings):
        """Choose between RunPod and local processing based on health and configuration"""
        processing_service = ProcessingService(self)
        return processing_service.choose_processing_method(settings)
    
    def get_recommended_processing_method(self, settings):
        """Get the recommended processing method for display purposes (doesn't actually process)"""
        processing_service = ProcessingService(self)
        return processing_service.get_recommended_processing_method(settings)
    
    def set_initial_processing_method(self, settings):
        """Set the initial processing method based on RunPod health"""
        try:
            recommended = self.get_recommended_processing_method(settings)
            self.processing_method = recommended
            return recommended
        except Exception as e:
            self.processing_method = "local"
            return "local"
    
    def extract_text_with_runpod(self, file_path, settings):
        """Extract text using RunPod API"""
        processing_service = ProcessingService(self)
        return processing_service.extract_text_with_runpod(file_path, self.policy_type, settings)
    
    def extract_text_with_local(self, file_path, settings):
        """Extract text using local document_reader library (fallback method)"""
        processing_service = ProcessingService(self)
        return processing_service.extract_text_with_local(file_path, settings)
    
    def validate_file_access(self):
        """Validate that the file is accessible for processing"""
        processing_service = ProcessingService(self)
        return processing_service.validate_file_access(self.policy_file)
    
    def extract_fields_with_claude(self, extracted_text, policy_type, settings):
        """Extract structured fields from text using Claude API"""
        extraction_service = ExtractionService()
        
        # Log extraction details
        frappe.logger().info(f"=== FIELD EXTRACTION DEBUG ===")
        frappe.logger().info(f"Policy type: {policy_type}")
        frappe.logger().info(f"Text length: {len(extracted_text)} characters")
        
        # Perform extraction using the new service
        result = extraction_service.extract_fields_from_text(extracted_text, policy_type, settings)
        
        # Store the prompt used for debugging (if available)
        if hasattr(extraction_service, '_last_used_prompt'):
            self.used_prompt = extraction_service._last_used_prompt
            frappe.logger().info(f"Used prompt length: {len(self.used_prompt)} characters")
        
        return result
    
    @frappe.whitelist()
    def ai_extract_fields_from_ocr(self):
        """Rerun AI extraction on the stored OCR text using current template settings"""
        try:
            # Check if we have raw OCR text to work with
            if not self.raw_ocr_text:
                return {
                    "success": False,
                    "message": "No raw OCR text found. Please process the document first."
                }
            
            # Get settings
            settings = self.get_policy_reader_settings()
            
            # Rerun AI extraction with current template settings (including insurer-specific templates)
            claude_result = self.extract_fields_with_claude(self.raw_ocr_text, self.policy_type.lower(), settings)
            
            if claude_result.get("success"):
                # Update the extracted fields
                self.extracted_fields = frappe.as_json(claude_result.get("extracted_fields", {}))
                self.save()
                frappe.db.commit()
                
                return {
                    "success": True,
                    "message": "AI extraction completed successfully!",
                    "extracted_fields": claude_result.get("extracted_fields", {})
                }
            else:
                return {
                    "success": False,
                    "message": claude_result.get("message", "AI extraction failed")
                }
                
        except Exception as e:
            frappe.log_error(f"AI extraction error for {self.name}: {str(e)}", "AI Extraction Error")
            return {
                "success": False,
                "message": f"Error during AI extraction: {str(e)}"
            }
    
    
    
    def get_full_file_path(self):
        """Get absolute path to the uploaded file using Frappe's file management"""
        if not self.policy_file:
            frappe.throw("No file attached")
        
        try:
            # Try to get file by URL first (handles both private and public files)
            file_doc = frappe.get_doc("File", {"file_url": self.policy_file})
            file_path = file_doc.get_full_path()
            
            return file_path
            
        except frappe.DoesNotExistError:
            try:
                # Fallback: try to find by filename
                file_name = self.policy_file.split('/')[-1]
                file_doc = frappe.get_doc("File", {"file_name": file_name})
                file_path = file_doc.get_full_path()
                
                return file_path
                
            except frappe.DoesNotExistError:
                frappe.log_error(f"File not found in database: {self.policy_file}", "Policy OCR File Not Found")
                frappe.throw(f"File not found in system: {self.policy_file}")
                
        except Exception as e:
            frappe.log_error(f"File access error for {self.policy_file}: {str(e)}", "Policy OCR File Access Error")
            frappe.throw(f"Could not access file: {self.policy_file}. Error: {str(e)}")
    
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
    
    @frappe.whitelist()
    def create_policy_entry(self):
        """
        Create a policy record (Motor/Health) from the extracted fields
        """
        try:
            # Validate prerequisites
            policy_creation_service = PolicyCreationService()
            validation = policy_creation_service.validate_policy_creation_prerequisites(self.name)
            
            if not validation["valid"]:
                frappe.msgprint(validation["error"], alert=True)
                return {"success": False, "error": validation["error"]}
            
            # Create policy record
            result = policy_creation_service.create_policy_record(self.name, self.policy_type)
            
            if result["success"]:
                frappe.msgprint(
                    f"✅ {result['message']}\n"
                    f"📊 Mapped {result['mapped_fields']} fields\n"
                    f"🔗 Policy: {result['policy_name']}",
                    alert=True
                )
                
                # Refresh the form to show the new policy link
                frappe.publish_realtime('policy_created', {
                    'policy_document': self.name,
                    'policy_name': result['policy_name'],
                    'policy_type': result['policy_type']
                })
            else:
                frappe.msgprint(f"❌ {result['error']}", alert=True)
            
            return result
            
        except Exception as e:
            frappe.log_error(f"Policy creation failed: {str(e)}")
            frappe.msgprint(f"❌ Policy creation failed: {str(e)}", alert=True)
            return {"success": False, "error": str(e)}
    
    @frappe.whitelist()
    def get_policy_creation_status(self):
        """
        Get the status of policy creation for this document
        """
        try:
            policy_creation_service = PolicyCreationService()
            validation = policy_creation_service.validate_policy_creation_prerequisites(self.name)
            
            return {
                "can_create": validation["valid"],
                "error": validation.get("error"),
                "policy_type": self.policy_type,
                "has_extracted_fields": bool(self.extracted_fields),
                "existing_policy": self.motor_policy or self.health_policy
            }
            
        except Exception as e:
            return {
                "can_create": False,
                "error": str(e)
            }

# API Key status checking method
@frappe.whitelist()
def check_api_key_status():
    """Check if Anthropic API key is configured and return status"""
    try:
        # Try to get a dummy PolicyDocument instance to use its settings method
        class DummyDoc:
            def get_policy_reader_settings(self):
                try:
                    settings = frappe.get_single("Policy Reader Settings")
                    return settings
                except:
                    class DefaultSettings:
                        anthropic_api_key = None
                    return DefaultSettings()
        
        dummy = DummyDoc()
        settings = dummy.get_policy_reader_settings()
        
        # Get API key with priority: Settings → site_config → environment
        api_key = (settings.anthropic_api_key or 
                  frappe.conf.get('anthropic_api_key') or 
                  os.environ.get('ANTHROPIC_API_KEY'))
        
        if not api_key:
            return {
                "configured": False,
                "message": "Not configured - Please set in Policy Reader Settings"
            }
        
        # Check if API key looks valid (starts with expected format)
        if api_key.startswith('sk-ant-'):
            key_preview = api_key[:10] + "..." + api_key[-4:]
            return {
                "configured": True,
                "message": f"Configured ({key_preview})"
            }
        else:
            return {
                "configured": False,
                "message": "Invalid format - API key should start with 'sk-ant-'"
            }
            
    except Exception as e:
        return {
            "configured": False,
            "message": f"Error checking API key: {str(e)}"
        }

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
    