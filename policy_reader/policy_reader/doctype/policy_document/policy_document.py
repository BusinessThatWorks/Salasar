# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
import os
import time
from frappe.model.document import Document
from frappe.utils import getdate, cstr, flt, cint
from policy_reader.policy_reader.services.processing_service import ProcessingService
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
                claude_model = "claude-sonnet-4-20250514"
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
        """Internal method for actual policy processing (runs in background) - uses Claude Vision"""
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
            
            # Get API key
            api_key = (settings.anthropic_api_key or 
                      frappe.conf.get('anthropic_api_key') or 
                      os.environ.get('ANTHROPIC_API_KEY'))
            
            if not api_key:
                frappe.throw("ANTHROPIC_API_KEY not configured. Please set it in Policy Reader Settings")
            
            # Process with Claude Vision API
            start_time = time.time()
            result = self.process_with_claude_vision(file_path, api_key, settings)
            end_time = time.time()
            processing_time = round(end_time - start_time, 2)
            
            # Update document with results
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
                
                frappe.log_error(f"Claude Vision processing failed for {self.name}: {self.error_message}", "Claude Vision Processing Error")
            
            self.save()
            frappe.db.commit()
            
            # Notify user via real-time updates
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
            
        except Exception as e:
            self.status = "Failed"
            self.error_message = str(e)
            self.save()
            frappe.db.commit()
            
            frappe.log_error(f"Claude Vision processing system error for {self.name}: {str(e)}", "Claude Vision System Error")
            
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
    
    @frappe.whitelist()
    def process_with_ai(self):
        """
        Process the policy document directly with Claude AI (no OCR step)
        Sends PDF directly to Claude with vision capabilities
        """
        if not self.policy_file:
            frappe.throw("No file attached")
        
        if not self.policy_type:
            frappe.throw("Policy type is required")
        
        try:
            # Update status
            self.status = "Processing"
            self.processing_method = "claude_vision"
            self.save()
            frappe.db.commit()
            
            # Get settings for API access
            settings = self.get_policy_reader_settings()
            
            # Get API key
            api_key = (settings.anthropic_api_key or 
                      frappe.conf.get('anthropic_api_key') or 
                      os.environ.get('ANTHROPIC_API_KEY'))
            
            if not api_key:
                frappe.throw("ANTHROPIC_API_KEY not configured. Please set it in Policy Reader Settings or add 'anthropic_api_key' to site_config.json or set ANTHROPIC_API_KEY environment variable")
            
            # Get file path and encode as base64
            file_path = self.get_full_file_path()
            
            # Process with Claude Vision API
            start_time = time.time()
            result = self.process_with_claude_vision(file_path, api_key, settings)
            end_time = time.time()
            processing_time = round(end_time - start_time, 2)
            
            # Update document with results
            if result.get("success"):
                self.status = "Completed"
                self.extracted_fields = frappe.as_json(result.get("extracted_fields", {}))
                self.processing_time = processing_time
                self.error_message = ""
                
                # Log success
                frappe.logger().info(f"Direct Claude AI processing completed successfully for {self.name}")
            else:
                self.status = "Failed"
                self.error_message = result.get("error", "Unknown error occurred")
                
                # Log error
                frappe.log_error(f"Direct Claude AI processing failed for {self.name}: {self.error_message}", "Claude AI Processing Error")
            
            self.save()
            frappe.db.commit()
            
            # Notify user via real-time updates
            notification_message = "Direct AI processing completed successfully" if result.get("success") else self.error_message
            
            frappe.publish_realtime(
                event="policy_processing_complete",
                message={
                    "doc_name": self.name,
                    "status": self.status,
                    "message": notification_message,
                    "processing_time": processing_time,
                    "processing_method": "claude_vision"
                },
                user=self.owner
            )
            
            return {
                "success": result.get("success", False),
                "message": "Direct AI processing completed successfully" if result.get("success") else self.error_message,
                "extracted_fields": result.get("extracted_fields", {}),
                "processing_time": processing_time
            }
            
        except Exception as e:
            self.status = "Failed"
            self.error_message = str(e)
            self.save()
            frappe.db.commit()
            
            frappe.log_error(f"Direct Claude AI processing system error for {self.name}: {str(e)}", "Claude AI System Error")
            
            # Notify user of failure
            frappe.publish_realtime(
                event="policy_processing_complete",
                message={
                    "doc_name": self.name,
                    "status": "Failed",
                    "message": f"Direct AI processing failed: {str(e)}",
                    "processing_time": 0
                },
                user=self.owner
            )
            
            frappe.throw(f"Failed to process with AI: {str(e)}")
    
    def process_with_claude_vision(self, file_path, api_key, settings):
        """
        Process PDF directly with Claude API using native PDF support
        """
        try:
            import base64
            import requests
            
            # Read and encode PDF file directly
            with open(file_path, 'rb') as pdf_file:
                pdf_data = base64.standard_b64encode(pdf_file.read()).decode('utf-8')
            
            # Get extraction prompt from settings
            prompt_text = self.get_vision_extraction_prompt(self.policy_type, settings)
            
            # Prepare Claude API request with direct PDF support
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': api_key,
                'anthropic-version': '2023-06-01'
            }
            
            # Build content array with PDF document and text prompt
            content = [
                {
                    'type': 'document',
                    'source': {
                        'type': 'base64',
                        'media_type': 'application/pdf',
                        'data': pdf_data
                    }
                },
                {
                    'type': 'text',
                    'text': prompt_text
                }
            ]
            
            payload = {
                'model': getattr(settings, 'claude_model', 'claude-sonnet-4-20250514'),
                'max_tokens': 4000,
                'messages': [
                    {
                        'role': 'user',
                        'content': content
                    }
                ]
            }
            
            # Make API call
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=payload,
                timeout=settings.timeout or 180
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Log the full response for debugging
                frappe.logger().info(f"Claude API Response: {response_data}")
                
                content = response_data.get('content', [{}])[0].get('text', '')
                
                # Extract JSON from Claude's response
                extracted_fields = self.extract_json_from_claude_response(content)
                
                # Get token usage from response
                usage = response_data.get('usage', {})
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                tokens_used = input_tokens + output_tokens
                
                frappe.logger().info(f"Token Usage - Input: {input_tokens}, Output: {output_tokens}, Total: {tokens_used}")
                
                return {
                    "success": True,
                    "extracted_fields": extracted_fields,
                    "tokens_used": tokens_used,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }
            elif response.status_code == 429:
                # Rate limit or insufficient balance
                error_data = response.json() if response.text else {}
                error_message = error_data.get('error', {}).get('message', response.text)
                return {
                    "success": False,
                    "error": f"API Rate Limit or Insufficient Balance: {error_message}",
                    "error_type": "rate_limit"
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "API Authentication Failed - Check your API key",
                    "error_type": "auth_error"
                }
            else:
                error_data = response.json() if response.text else {}
                error_message = error_data.get('error', {}).get('message', response.text[:200])
                return {
                    "success": False,
                    "error": f"Claude API error: HTTP {response.status_code} - {error_message}",
                    "error_type": "api_error"
                }
                
        except Exception as e:
            frappe.log_error(f"Claude vision processing error: {str(e)}", "Claude Vision Error")
            return {
                "success": False,
                "error": f"Claude vision processing failed: {str(e)}"
            }
    
    def convert_pdf_to_images(self, file_path):
        """
        Convert PDF to images for Claude Vision API
        """
        try:
            import base64
            
            # Try using pdf2image (requires poppler-utils)
            try:
                from pdf2image import convert_from_path
                
                # Convert PDF pages to images
                pages = convert_from_path(file_path, dpi=200, first_page=1, last_page=12)
                
                images = []
                for page in pages:
                    # Convert PIL image to base64
                    import io
                    img_byte_arr = io.BytesIO()
                    page.save(img_byte_arr, format='PNG')
                    img_byte_arr = img_byte_arr.getvalue()
                    img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')
                    images.append(img_base64)
                
                frappe.logger().info(f"Converted PDF to {len(images)} images for Claude Vision")
                return images
                
            except ImportError:
                frappe.logger().warning("pdf2image not available, trying alternative method")
                
                # Fallback: Try using PyMuPDF (fitz)
                try:
                    import fitz  # PyMuPDF
                    import base64
                    import io
                    from PIL import Image
                    
                    doc = fitz.open(file_path)
                    images = []
                    
                    # Convert first 12 pages to images
                    for page_num in range(min(len(doc), 12)):
                        page = doc.load_page(page_num)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
                        img_data = pix.tobytes("png")
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        images.append(img_base64)
                    
                    doc.close()
                    frappe.logger().info(f"Converted PDF to {len(images)} images using PyMuPDF")
                    return images
                    
                except ImportError:
                    frappe.logger().error("Neither pdf2image nor PyMuPDF available for PDF conversion")
                    return []
                    
        except Exception as e:
            frappe.log_error(f"PDF to image conversion failed: {str(e)}", "PDF Conversion Error")
            return []
    
    def get_vision_extraction_prompt(self, policy_type, settings):
        """
        Get extraction prompt optimized for Claude Vision API
        """
        try:
            # Get field mapping from settings
            policy_reader_settings = frappe.get_single("Policy Reader Settings")
            mapping = policy_reader_settings.get_cached_field_mapping(policy_type.lower()) or {}
            
            # Get canonical fields (fields that map to themselves)
            canonical_fields = [k for k, v in mapping.items() if k == v]
            canonical_fields = sorted(set(canonical_fields))
            
            if canonical_fields:
                fields_list = "\n".join([f"- {field}" for field in canonical_fields])
                
                prompt = f"""Analyze this {policy_type.lower()} insurance policy PDF and extract the following information as a flat JSON object:

Required fields to extract:
{fields_list}

Extraction rules:
- Dates: Convert to DD/MM/YYYY format only (e.g., "From 12-JUL-2022" → "12/07/2022")
- Currency/Amounts: Extract digits only, remove currency symbols, commas, dashes
- Numbers: Extract digits only, remove descriptive text
- Text fields: Extract clean core values, remove prefixes/labels
- Missing fields: Use null
- Return ONLY a flat JSON object with the exact field names listed above

Example output format:
{{
  "policy_no": "ABC123456",
  "vehicle_no": "DL-01-AA-1234",
  "make": "Maruti",
  "model": "Swift",
  ...
}}

Return only valid JSON, no explanations or markdown formatting."""
            else:
                # Fallback prompt if no mapping available
                if policy_type.lower() == "motor":
                    prompt = f"""Analyze this motor insurance policy PDF and extract the following information as a flat JSON object:

Required fields to extract:
- policy_no (Policy Number)
- policy_type (Type of Policy)
- policy_issuance_date (Policy Issuance Date)
- policy_start_date (Policy Start Date, From Date)
- policy_expiry_date (Policy Expiry Date, To Date)
- vehicle_no (Vehicle Number, Registration Number, Registration No.)
- make (Vehicle Make)
- model (Vehicle Model)
- variant (Vehicle Variant)
- year_of_man (Year of Manufacture)
- chasis_no (Chassis Number, Chasis Number)
- engine_no (Engine Number)
- cc (Engine Capacity, Cubic Capacity)
- fuel (Fuel Type)
- sum_insured (Sum Insured, IDV, Insured Declared Value)
- net_od_premium (Net OD Premium, OD Premium)
- tp_premium (TP Premium, Third Party Premium)
- gst (GST, Tax, Service Tax)
- ncb (NCB, No Claim Bonus)
- rto_code (RTO Code)
- vehicle_category (Vehicle Category, Vehicle Class)
- customer_name (Customer Name, Insured Name)
- customer_code (Customer Code)
- mobile_no (Mobile Number, Mobile No)
- email_id (Email ID, Email)
- payment_mode (Payment Mode)
- bank_name (Bank Name)

Extraction rules:
- Dates: Convert to DD/MM/YYYY format only (e.g., "From 12-JUL-2022" → "12/07/2022")
- Currency/Amounts: Extract the exact numeric value including decimals, remove currency symbols and commas only
  * "₹4,156,250.00" → "4156250.00"
  * "Rs. 13,502/-" → "13502"
  * "3,747.50" → "3747.50"
  * Preserve decimal points (.00, .50, etc.) when present
- Numbers: Extract digits and decimals only, remove descriptive text but keep decimal places
- Text fields: Extract clean core values, remove prefixes/labels
- Missing fields: Use null
- IMPORTANT: For sum_insured, net_od_premium, tp_premium, gst - be very careful with decimal places and large numbers
- Return ONLY a flat JSON object with the exact field names listed above

Example output format:
{{
  "policy_no": "ABC123456",
  "vehicle_no": "DL-01-AA-1234",
  "make": "Maruti",
  "model": "Swift",
  "year_of_man": "2019",
  "sum_insured": "500000.00",
  "net_od_premium": "13502.00",
  "tp_premium": "7317.00",
  "gst": "3747.50",
  ...
}}

Return only valid JSON, no explanations or markdown formatting."""
                else:
                    # Health policy fallback - using Saiba field specifications
                    prompt = f"""Analyze this health insurance policy PDF and extract the following information as a flat JSON object:

Required fields to extract:
- customer_code (Customer Code)
- pos_policy (Pos Policy, POS Policy)
- policy_biz_type (PolicyBiz Type, Policy Biz Type)
- insurer_branch_code (Insurer Branch Code)
- policy_issuance_date (PolicyIssuanceDate, Policy Issuance Date)
- policy_start_date (PolicyStartDate, Policy Start Date, Start Date, From Date)
- policy_expiry_date (PolicyExpiryDate, Policy Expiry Date, Expiry Date, To Date)
- policy_type (Policy Type)
- policy_no (PolicyNo, Policy No, Policy Number)
- plan_name (Plan Name)
- is_renewable (IsRenewable, Is Renewable, Renewable)
- prev_policy (PrevPolicy, Previous Policy)
- insured1name (INSURED1NAME, Insured Name, Insured 1 Name)
- insured1gender (INSURED1GENDER, Insured Gender, Gender)
- insured1dob (INSURED1DOB, Insured DOB, Date of Birth, DOB)
- insured1relation (INSURED1RELATION, Insured Relation, Relationship)
- sum_insured (Sum Insured, Insured Amount, Coverage Amount)
- net_od_premium (Net/OD Premium, Net Premium, Premium Amount)
- gst (GST, Tax, Service Tax)
- stamp_duty (StampDuty, Stamp Duty)
- payment_mode (Payment Mode)
- bank_name (Bank Name)
- payment_transaction_no (Payment TransactionNo, Transaction No)
- remarks (Remarks, Comments, Notes)
- policy_status (Policy Status, Status)

Extraction rules:
- Dates: Convert to DD/MM/YYYY format only (e.g., "12-JUL-2022" → "12/07/2022")
- Currency/Amounts: Extract the exact numeric value including decimals, remove currency symbols and commas only
  * "₹10,000,000.00" → "10000000.00"
  * "Rs. 1,50,000/-" → "150000"
  * "25,000.50" → "25000.50"
  * Preserve decimal points (.00, .50, etc.) when present
- Numbers: Extract digits and decimals only, remove descriptive text but keep decimal places
- Text fields: Extract clean core values, remove prefixes/labels
- Missing fields: Use null
- IMPORTANT: For sum_insured, net_od_premium, gst - be very careful with decimal places and large numbers
- Return ONLY a flat JSON object with the exact field names listed above

Example output format:
{{
  "customer_code": "12345",
  "policy_no": "HEALTH123456",
  "insured1name": "John Doe",
  "policy_start_date": "01/01/2024",
  "policy_expiry_date": "31/12/2024",
  "sum_insured": "10000000.00",
  "net_od_premium": "15000.00",
  "gst": "2700.50",
  "insured1gender": "Male",
  "insured1relation": "Self",
  ...
}}

Return only valid JSON, no explanations or markdown formatting."""
            
            return prompt
            
        except Exception as e:
            frappe.log_error(f"Error building vision prompt: {str(e)}", "Vision Prompt Error")
            return f"Extract key information from this {policy_type.lower()} insurance policy as JSON."
    
    def extract_json_from_claude_response(self, content):
        """
        Extract JSON from Claude's response text
        """
        import re
        
        try:
            # First try to parse as direct JSON
            return frappe.parse_json(content)
        except:
            pass
        
        # Look for JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_match:
            try:
                return frappe.parse_json(json_match.group(1))
            except:
                pass
        
        # Look for JSON object in text
        json_match = re.search(r'(\{.*\})', content, re.DOTALL)
        if json_match:
            try:
                return frappe.parse_json(json_match.group(1))
            except:
                pass
        
        # If all parsing fails, return empty dict
        frappe.logger().warning(f"Could not extract JSON from Claude response: {content[:500]}...")
        return {}

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

@frappe.whitelist()
def test_claude_api_health():
    """Test Claude API connectivity with a simple health check"""
    import time
    import requests
    
    try:
        settings = frappe.get_single("Policy Reader Settings")
        api_key = (settings.anthropic_api_key or 
                  frappe.conf.get('anthropic_api_key') or 
                  os.environ.get('ANTHROPIC_API_KEY'))
        
        if not api_key:
            return {
                "success": False,
                "error": "API key not configured"
            }
        
        # Simple test request to Claude API
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
            'anthropic-version': '2023-06-01'
        }
        
        payload = {
            'model': getattr(settings, 'claude_model', 'claude-sonnet-4-20250514'),
            'max_tokens': 10,
            'messages': [
                {
                    'role': 'user',
                    'content': 'Hi'
                }
            ]
        }
        
        start_time = time.time()
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=payload,
            timeout=10
        )
        response_time = int((time.time() - start_time) * 1000)  # Convert to ms
        
        if response.status_code == 200:
            # Check token usage from response
            response_data = response.json()
            usage = response_data.get('usage', {})
            tokens_used = usage.get('input_tokens', 0) + usage.get('output_tokens', 0)
            
            return {
                "success": True,
                "response_time": response_time,
                "message": "API is healthy",
                "tokens_used": tokens_used
            }
        elif response.status_code == 429:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', 'Rate limit exceeded or insufficient credits')
            return {
                "success": False,
                "error": f"Rate Limit/Insufficient Balance: {error_msg}"
            }
        elif response.status_code == 401:
            return {
                "success": False,
                "error": "Authentication Failed - Invalid API Key"
            }
        else:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', response.text[:100])
            return {
                "success": False,
                "error": f"HTTP {response.status_code}: {error_msg}"
            }
            
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "Request timeout - API took too long to respond"
        }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Connection failed - cannot reach Claude API"
        }
    except Exception as e:
        frappe.log_error(f"Claude API health check error: {str(e)}", "API Health Check Error")
        return {
            "success": False,
            "error": str(e)
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
    