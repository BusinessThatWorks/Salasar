# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document


class PolicyDocument(Document):
    def before_save(self):
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
        self.clear_individual_fields()
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
            # Validate file accessibility before processing
            if not self.validate_file_access():
                raise Exception("File is not accessible for processing. Please ensure the file is uploaded and accessible.")
            
            file_path = self.get_full_file_path()
            
            from policy_ocr import PolicyProcessor, OCRConfig
            
            # Get settings for processing configuration
            settings = self.get_policy_reader_settings()
            
            # Get API key with priority: Settings → site_config → environment
            api_key = (settings.anthropic_api_key or 
                      frappe.conf.get('anthropic_api_key') or 
                      os.environ.get('ANTHROPIC_API_KEY'))
            
            if not api_key:
                raise Exception("Anthropic API key not configured. Please set it in Policy Reader Settings or add 'anthropic_api_key' to site_config.json")
            
            config = OCRConfig(
                claude_api_key=api_key,
                fast_mode=bool(settings.fast_mode),
                max_pages=int(settings.max_pages or 3),
                confidence_threshold=float(settings.confidence_threshold or 0.3),
                enable_logging=bool(settings.enable_logging)
            )
            
            processor = PolicyProcessor(config)
            
            start_time = time.time()
            
            result = processor.process_policy(
                file_path=file_path,
                policy_type=self.policy_type.lower()
            )
            
            end_time = time.time()
            processing_time = round(end_time - start_time, 2)
            
            if result.get("success"):
                self.status = "Completed"
                self.extracted_fields = frappe.as_json(result.get("extracted_fields", {}))
                self.processing_time = processing_time
                self.error_message = ""
                
                # Populate individual fields based on policy type
                self.populate_individual_fields(result.get("extracted_fields", {}))
            else:
                self.status = "Failed"
                self.error_message = result.get("error", "Unknown error occurred")
                
                frappe.log_error(f"Policy OCR processing failed for {self.name}: {self.error_message}", "Policy OCR Processing Error")
            
            self.save()
            frappe.db.commit()
            
            # Notify user via real-time updates
            frappe.publish_realtime(
                event="policy_processing_complete",
                message={
                    "doc_name": self.name,
                    "status": self.status,
                    "message": "Processing completed successfully" if self.status == "Completed" else self.error_message,
                    "processing_time": processing_time if hasattr(self, 'processing_time') else 0
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
    
    def validate_file_access(self):
        """Validate that the file is accessible for processing"""
        try:
            if not self.policy_file:
                return False
            
            # Try to get the file document
            file_doc = frappe.get_doc("File", {"file_url": self.policy_file})
            
            # Check if file exists on disk
            file_path = file_doc.get_full_path()
            if not os.path.exists(file_path):
                frappe.logger().error(f"File does not exist on disk: {file_path}")
                return False
            
            # Check if file is readable
            if not os.access(file_path, os.R_OK):
                frappe.logger().error(f"File is not readable: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            frappe.logger().error(f"File validation failed for {self.policy_file}: {str(e)}")
            return False
    
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
    
    def populate_individual_fields(self, extracted_data):
        """Populate individual fields based on policy type and extracted data"""
        if not extracted_data or not self.policy_type:
            return
        
        # Clear all individual fields first
        self.clear_individual_fields()
        
        if self.policy_type.lower() == "motor":
            # Map Motor policy fields
            field_mapping = {
                "Policy Number": "policy_number_motor",
                "Insured Name": "insured_name_motor", 
                "Vehicle Number": "vehicle_number_motor",
                "Chassis Number": "chassis_number_motor",
                "Engine Number": "engine_number_motor",
                "From": "policy_from_motor",
                "To": "policy_to_motor",
                "Premium Amount": "premium_amount_motor",
                "Sum Insured": "sum_insured_motor",
                "Make / Model": "make_model_motor",
                "Variant": "variant_motor",
                "Vehicle Class": "vehicle_class_motor",
                "Registration Number": "registration_number_motor",
                "Fuel": "fuel_motor",
                "Seat Capacity": "seat_capacity_motor"
            }
        elif self.policy_type.lower() == "health":
            # Map Health policy fields
            field_mapping = {
                "Policy Number": "policy_number_health",
                "Insured Name": "insured_name_health",
                "Sum Insured": "sum_insured_health", 
                "Policy Start Date": "policy_start_date_health",
                "Policy End Date": "policy_end_date_health",
                "Customer Code": "customer_code_health",
                "Net Premium": "net_premium_health",
                "Policy Period": "policy_period_health",
                "Issuing Office": "issuing_office_health",
                "Relationship to Policyholder": "relationship_to_policyholder_health",
                "Date of Birth": "date_of_birth_health"
            }
        else:
            return
        
        # Populate fields with extracted data
        for extracted_field, doctype_field in field_mapping.items():
            value = extracted_data.get(extracted_field)
            if value:
                setattr(self, doctype_field, value)
    
    def clear_individual_fields(self):
        """Clear all individual policy fields"""
        # Motor fields
        motor_fields = [
            "policy_number_motor", "insured_name_motor", "vehicle_number_motor",
            "chassis_number_motor", "engine_number_motor", "policy_from_motor",
            "policy_to_motor", "premium_amount_motor", "sum_insured_motor",
            "make_model_motor", "variant_motor", "vehicle_class_motor",
            "registration_number_motor", "fuel_motor", "seat_capacity_motor"
        ]
        
        # Health fields  
        health_fields = [
            "policy_number_health", "insured_name_health", "sum_insured_health",
            "policy_start_date_health", "policy_end_date_health", "customer_code_health",
            "net_premium_health", "policy_period_health", "issuing_office_health",
            "relationship_to_policyholder_health", "date_of_birth_health"
        ]
        
        # Clear all fields
        for field in motor_fields + health_fields:
            setattr(self, field, None)

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
