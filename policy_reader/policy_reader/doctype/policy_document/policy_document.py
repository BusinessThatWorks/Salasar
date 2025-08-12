# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document
from frappe.utils import getdate, cstr, flt, cint


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
            
            from document_reader import OCRReader
            
            # Get settings for processing configuration
            settings = self.get_policy_reader_settings()
            
            start_time = time.time()
            
            # Step 1: Extract text using OCR
            ocr_reader = OCRReader(
                language='en',
                confidence_threshold=float(settings.confidence_threshold or 0.3),
                image_resolution_scale=2.0,
                image_quality=80
            )
            
            # Limit pages if configured
            page_range = None
            if hasattr(settings, 'max_pages') and settings.max_pages:
                page_range = (1, int(settings.max_pages))
            
            extracted_text = ocr_reader.process_pdf(file_path, page_range=page_range)
            
            # Step 2: Extract structured fields using Claude API
            result = self.extract_fields_with_claude(extracted_text, self.policy_type.lower(), settings)
            
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
    
    def extract_fields_with_claude(self, extracted_text, policy_type, settings):
        """Extract structured fields from text using Claude API"""
        try:
            # Get API key with priority: Settings → site_config → environment
            api_key = (settings.anthropic_api_key or 
                      frappe.conf.get('anthropic_api_key') or 
                      os.environ.get('ANTHROPIC_API_KEY'))
            
            if not api_key:
                raise Exception("Anthropic API key not configured. Please set it in Policy Reader Settings or add 'anthropic_api_key' to site_config.json")
            
            # Get field mapping for the policy type
            from policy_reader.utils import get_field_mapping_for_policy_type
            field_mapping = get_field_mapping_for_policy_type(policy_type)
            
            # Build prompt for Claude
            fields_list = list(field_mapping.keys())
            prompt = self.build_extraction_prompt(extracted_text, policy_type, fields_list)
            
            # Call Claude API using Frappe HTTP utilities
            from frappe.integrations.utils import make_post_request
            
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': api_key,
                'anthropic-version': '2023-06-01'
            }
            
            payload = {
                'model': 'claude-3-haiku-20240307' if settings.fast_mode else 'claude-3-sonnet-20240229',
                'max_tokens': 4000,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }
            
            # Log the request for debugging
            frappe.logger().info(f"Sending Claude API request: {payload}")
            
            response = make_post_request(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                data=frappe.as_json(payload)
            )
            
            # Log the response for debugging
            frappe.logger().info(f"Claude API response type: {type(response)}")
            frappe.logger().info(f"Claude API response: {response}")
            
            # Handle different response formats from make_post_request
            if response:
                # Check if response is a dict with content
                if isinstance(response, dict) and response.get('content'):
                    content = response['content'][0]['text']
                    frappe.logger().info(f"Extracted content from response: {content[:200]}...")
                    
                    # Parse the JSON response from Claude using Frappe utilities
                    try:
                        extracted_fields = frappe.parse_json(content)
                        frappe.logger().info(f"Successfully parsed extracted fields: {extracted_fields}")
                        return {
                            "success": True,
                            "extracted_fields": extracted_fields
                        }
                    except (ValueError, TypeError) as e:
                        frappe.logger().error(f"JSON parsing error: {str(e)}")
                        return {
                            "success": False,
                            "error": f"Failed to parse Claude response as JSON: {str(e)}"
                        }
                
                # Check if response has error information
                elif isinstance(response, dict) and response.get('error'):
                    error_msg = f"Claude API error: {response.get('error', 'Unknown error')}"
                    frappe.logger().error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }
                
                # Check if response is a string (might be direct content)
                elif isinstance(response, str):
                    frappe.logger().info(f"Received string response: {response[:200]}...")
                    try:
                        extracted_fields = frappe.parse_json(response)
                        return {
                            "success": True,
                            "extracted_fields": extracted_fields
                        }
                    except (ValueError, TypeError) as e:
                        return {
                            "success": False,
                            "error": f"Failed to parse string response as JSON: {str(e)}"
                        }
                
                else:
                    error_msg = f"Unexpected Claude API response format: {type(response)}"
                    frappe.logger().error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg
                    }
            else:
                error_msg = "Claude API request returned no response"
                frappe.logger().error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Field extraction failed: {str(e)}"
            }
    
    def build_extraction_prompt(self, text, policy_type, fields_list):
        """Build prompt for Claude to extract specific fields"""
        prompt = f"""You are an expert at extracting information from {policy_type} insurance policy documents.

Extract the following fields from the policy document text below. Return ONLY a JSON object with the field names as keys and extracted values as values. If a field is not found, use null as the value.

Fields to extract:
{', '.join(fields_list)}

Document text:
{text[:8000]}  # Limit text length for token efficiency

Return your response as a valid JSON object only, no additional text or explanation."""
        
        return prompt
    
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
        """Create Motor or Health Policy record with extracted data"""
        if not extracted_data or not self.policy_type:
            frappe.logger().warning(f"Cannot create policy record - extracted_data: {bool(extracted_data)}, policy_type: {self.policy_type}")
            return
        
        frappe.logger().info(f"Creating {self.policy_type} policy record from extracted data for document {self.name}")
        
        policy_created = False
        if self.policy_type.lower() == "motor":
            policy_created = self.create_motor_policy_record(extracted_data)
        elif self.policy_type.lower() == "health":
            policy_created = self.create_health_policy_record(extracted_data)
        
        if policy_created:
            frappe.logger().info(f"Successfully created {self.policy_type} policy record for document {self.name}")
        else:
            frappe.logger().error(f"Failed to create {self.policy_type} policy record for document {self.name}")
    
    def create_motor_policy_record(self, extracted_data):
        """Create Motor Policy record with extracted data"""
        # Get field mapping from cache (with fallback to hardcoded)
        from policy_reader.utils import get_field_mapping_for_policy_type
        field_mapping = get_field_mapping_for_policy_type("motor")
        
        frappe.logger().info(f"Starting Motor Policy creation for {self.name} with {len(extracted_data)} extracted fields")
        frappe.logger().info(f"Field mapping: {field_mapping}")
        
        try:
            # Create Motor Policy record
            motor_policy = frappe.new_doc("Motor Policy")
            frappe.logger().info(f"Created new Motor Policy document")
            
            # Set bidirectional link and copy PDF file
            motor_policy.policy_document = self.name
            motor_policy.policy_file = self.policy_file
            frappe.logger().info(f"Set policy_document link to {self.name} and copied policy_file")
            
            # Track successful field mappings
            mapped_fields = 0
            
            # Populate fields with extracted data using Frappe utilities
            for extracted_field, motor_field in field_mapping.items():
                value = extracted_data.get(extracted_field)
                if value:
                    # Use Frappe utilities for safe type conversion
                    converted_value = self._convert_field_value(motor_field, value, "Motor Policy")
                    if converted_value is not None:
                        setattr(motor_policy, motor_field, converted_value)
                        mapped_fields += 1
                        frappe.logger().info(f"Mapped {extracted_field} -> {motor_field}: {converted_value}")
                    else:
                        frappe.logger().warning(f"Field conversion failed for {extracted_field} -> {motor_field}: {value}")
                else:
                    frappe.logger().info(f"No value found for {extracted_field}")
            
            frappe.logger().info(f"Successfully mapped {mapped_fields} fields to Motor Policy")
            
            # Pre-check field values before validation
            self._pre_validate_policy_fields(motor_policy, "Motor Policy")
            
            # Validate the Motor Policy before saving (only if custom validate method exists)
            try:
                if hasattr(motor_policy, 'validate') and callable(getattr(motor_policy, 'validate')):
                    motor_policy.validate()
                    frappe.logger().info(f"Motor Policy validation successful for document {self.name}")
                else:
                    frappe.logger().info(f"Motor Policy has no custom validate method, will validate during insert() for document {self.name}")
            except Exception as validation_error:
                frappe.logger().error(f"Motor Policy validation failed: {str(validation_error)}")
                # Log field values for debugging
                for field_name in ['fuel', 'relationship_to_policyholder']:  # Common validation fields
                    if hasattr(motor_policy, field_name):
                        field_value = getattr(motor_policy, field_name)
                        frappe.logger().info(f"Field {field_name} = '{field_value}'")
                raise validation_error
            
            # Save the Motor Policy record
            motor_policy.insert()
            frappe.logger().info(f"Motor Policy record created successfully with name: {motor_policy.name}")
            
            # Link to Policy Document
            self.motor_policy = motor_policy.name
            frappe.logger().info(f"Linked Motor Policy {motor_policy.name} to Policy Document {self.name}")
            
            return True
            
        except Exception as e:
            # Use Frappe error handling - log but don't fail entire processing
            error_msg = f"Failed to create Motor Policy record for {self.name}: {str(e)}"
            frappe.log_error(error_msg, "Motor Policy Creation Error")
            frappe.logger().error(error_msg)
            
            # Still save extracted fields JSON even if policy record creation fails
            frappe.msgprint(f"Policy extracted successfully but failed to create Motor Policy record: {str(e)}", 
                          title="Partial Processing Error", indicator="orange")
            return False
    
    def create_health_policy_record(self, extracted_data):
        """Create Health Policy record with extracted data"""
        # Get field mapping from cache (with fallback to hardcoded)
        from policy_reader.utils import get_field_mapping_for_policy_type
        field_mapping = get_field_mapping_for_policy_type("health")
        
        frappe.logger().info(f"Starting Health Policy creation for {self.name} with {len(extracted_data)} extracted fields")
        frappe.logger().info(f"Field mapping: {field_mapping}")
        
        try:
            # Create Health Policy record
            health_policy = frappe.new_doc("Health Policy")
            frappe.logger().info(f"Created new Health Policy document")
            
            # Set bidirectional link and copy PDF file
            health_policy.policy_document = self.name
            health_policy.policy_file = self.policy_file
            frappe.logger().info(f"Set policy_document link to {self.name} and copied policy_file")
            
            # Track successful field mappings
            mapped_fields = 0
            
            # Populate fields with extracted data using Frappe utilities
            for extracted_field, health_field in field_mapping.items():
                value = extracted_data.get(extracted_field)
                if value:
                    # Use Frappe utilities for safe type conversion
                    converted_value = self._convert_field_value(health_field, value, "Health Policy")
                    if converted_value is not None:
                        setattr(health_policy, health_field, converted_value)
                        mapped_fields += 1
                        frappe.logger().info(f"Mapped {extracted_field} -> {health_field}: {converted_value}")
                    else:
                        frappe.logger().warning(f"Field conversion failed for {extracted_field} -> {health_field}: {value}")
                else:
                    frappe.logger().info(f"No value found for {extracted_field}")
            
            frappe.logger().info(f"Successfully mapped {mapped_fields} fields to Health Policy")
            
            # Pre-check field values before validation
            self._pre_validate_policy_fields(health_policy, "Health Policy")
            
            # Validate the Health Policy before saving (only if custom validate method exists)
            try:
                if hasattr(health_policy, 'validate') and callable(getattr(health_policy, 'validate')):
                    health_policy.validate()
                    frappe.logger().info(f"Health Policy validation successful for document {self.name}")
                else:
                    frappe.logger().info(f"Health Policy has no custom validate method, will validate during insert() for document {self.name}")
            except Exception as validation_error:
                frappe.logger().error(f"Health Policy validation failed: {str(validation_error)}")
                # Log field values for debugging
                for field_name in ['relationship_to_policyholder']:  # Common validation fields
                    if hasattr(health_policy, field_name):
                        field_value = getattr(health_policy, field_name)
                        frappe.logger().info(f"Field {field_name} = '{field_value}'")
                raise validation_error
            
            # Save the Health Policy record
            health_policy.insert()
            frappe.logger().info(f"Health Policy record created successfully with name: {health_policy.name}")
            
            # Link to Policy Document
            self.health_policy = health_policy.name
            frappe.logger().info(f"Linked Health Policy {health_policy.name} to Policy Document {self.name}")
            
            return True
            
        except Exception as e:
            # Use Frappe error handling - log but don't fail entire processing
            error_msg = f"Failed to create Health Policy record for {self.name}: {str(e)}"
            frappe.log_error(error_msg, "Health Policy Creation Error")
            frappe.logger().error(error_msg)
            
            # Still save extracted fields JSON even if policy record creation fails
            frappe.msgprint(f"Policy extracted successfully but failed to create Health Policy record: {str(e)}", 
                          title="Partial Processing Error", indicator="orange")
            return False
    
    def _convert_field_value(self, fieldname, value, doctype_name):
        """Convert extracted field value to appropriate type using Frappe utilities"""
        try:
            # Get field metadata to determine proper conversion
            meta = frappe.get_meta(doctype_name)
            field = meta.get_field(fieldname)
            
            if not field:
                frappe.log_error(f"Field {fieldname} not found in {doctype_name}", "Field Conversion Warning")
                return cstr(value)  # Default to string
            
            fieldtype = field.fieldtype
            
            # Use Frappe utilities for type conversion
            if fieldtype == "Date":
                # Use Frappe's safe date parsing
                try:
                    return getdate(value)
                except Exception as e:
                    frappe.log_error(f"Date conversion failed for {fieldname}: {value} - {str(e)}", "Date Conversion Error")
                    return None  # Skip this field
                    
            elif fieldtype in ["Currency", "Float"]:
                # Use Frappe's safe float conversion
                return flt(value)
                
            elif fieldtype == "Int":
                # Use Frappe's safe integer conversion
                return cint(value)
                
            elif fieldtype == "Select":
                # Handle Select fields with case normalization
                return self._normalize_select_value(fieldname, value, field.options, doctype_name)
                
            elif fieldtype in ["Data", "Text", "Long Text"]:
                # Use Frappe's safe string conversion
                return cstr(value)
                
            else:
                # Default to string conversion
                return cstr(value)
                
        except Exception as e:
            frappe.log_error(f"Field conversion error for {fieldname} in {doctype_name}: {str(e)}", "Field Conversion Error")
            return None  # Skip problematic fields instead of failing
    
    def _normalize_select_value(self, fieldname, value, options, doctype_name):
        """Normalize select field values to match DocType options exactly"""
        if not value or not options:
            return cstr(value)
        
        # Get the list of valid options
        valid_options = [option.strip() for option in options.split('\n') if option.strip()]
        value_str = cstr(value).strip()
        
        # First try exact match
        if value_str in valid_options:
            return value_str
        
        # Try case-insensitive match
        for option in valid_options:
            if value_str.lower() == option.lower():
                frappe.logger().info(f"Normalized {fieldname} value '{value_str}' to '{option}' for {doctype_name}")
                return option
        
        # Log unmatched values for debugging
        frappe.logger().warning(f"Select field {fieldname} value '{value_str}' doesn't match any options: {valid_options}")
        
        # Return original value for now (will trigger validation error with clear message)
        return value_str
    
    def _pre_validate_policy_fields(self, policy_doc, doctype_name):
        """Pre-check field values before policy validation"""
        meta = frappe.get_meta(doctype_name)
        
        for field in meta.fields:
            if field.fieldtype == "Select" and field.options:
                field_value = getattr(policy_doc, field.fieldname, None)
                if field_value:
                    valid_options = [option.strip() for option in field.options.split('\n') if option.strip()]
                    if field_value not in valid_options:
                        frappe.logger().warning(f"Pre-validation: {field.fieldname} value '{field_value}' not in valid options: {valid_options}")
                    else:
                        frappe.logger().info(f"Pre-validation: {field.fieldname} value '{field_value}' is valid")
    
    @frappe.whitelist()
    def create_policy_record(self):
        """Create Motor/Health Policy record manually from extracted fields"""
        try:
            # Validation checks
            if not self.policy_type:
                frappe.throw("Policy type is required to create policy record")
            
            if self.status != "Completed":
                frappe.throw("Policy must be processed and completed before creating policy record")
            
            if not self.extracted_fields:
                frappe.throw("No extracted fields found. Please process the policy first.")
            
            # Check if policy record already exists
            if self.policy_type.lower() == "motor":
                if self.motor_policy:
                    frappe.throw(f"Motor Policy record already exists: {self.motor_policy}")
            elif self.policy_type.lower() == "health":
                if self.health_policy:
                    frappe.throw(f"Health Policy record already exists: {self.health_policy}")
            else:
                frappe.throw(f"Unsupported policy type: {self.policy_type}")
            
            # Parse extracted fields
            try:
                extracted_data = frappe.parse_json(self.extracted_fields)
            except Exception as e:
                frappe.throw(f"Failed to parse extracted fields: {str(e)}")
            
            if not extracted_data:
                frappe.throw("No data found in extracted fields")
            
            # Create the appropriate policy record
            policy_created = False
            if self.policy_type.lower() == "motor":
                policy_created = self.create_motor_policy_record(extracted_data)
                policy_type_display = "Motor Policy"
            elif self.policy_type.lower() == "health":
                policy_created = self.create_health_policy_record(extracted_data)
                policy_type_display = "Health Policy"
            
            if policy_created:
                # Save the updated Policy Document with the new policy link
                self.save()
                frappe.db.commit()
                
                # Get the policy name for user feedback
                policy_name = self.motor_policy if self.policy_type.lower() == "motor" else self.health_policy
                
                frappe.msgprint(
                    f"{policy_type_display} record created successfully: {policy_name}",
                    title="Policy Record Created",
                    indicator="green"
                )
                
                return {
                    "success": True,
                    "message": f"{policy_type_display} record created successfully",
                    "policy_name": policy_name
                }
            else:
                frappe.throw(f"Failed to create {policy_type_display} record. Please check the error logs.")
        
        except Exception as e:
            error_msg = str(e)
            frappe.log_error(f"Manual policy record creation failed for {self.name}: {error_msg}", 
                           "Manual Policy Creation Error")
            frappe.throw(error_msg)
    
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
