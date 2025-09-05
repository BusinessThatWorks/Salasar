# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import os
import time


class ProcessingService:
    """Service class for handling document processing operations"""
    
    def __init__(self, policy_document=None):
        """Initialize with optional policy document reference"""
        self.policy_document = policy_document
    
    def choose_processing_method(self, settings):
        """Choose between RunPod and local processing based on health and configuration"""
        try:
            # Check if RunPod is configured and healthy
            if (settings.runpod_pod_id and 
                settings.runpod_port and 
                settings.runpod_api_secret and
                settings.runpod_health_status == "healthy"):
                
                # Check if response time is acceptable (<5 seconds)
                if settings.runpod_response_time < 5:
                    frappe.logger().info(f"Using RunPod API for processing (response time: {settings.runpod_response_time:.2f}s)")
                    return "runpod"
                else:
                    frappe.logger().warning(f"RunPod responding slowly ({settings.runpod_response_time:.2f}s), using local processing")
                    return "local"
            
            # Fallback to local processing
            frappe.logger().info("RunPod unavailable, using local processing")
            return "local"
            
        except Exception as e:
            frappe.log_error(f"Error choosing processing method: {str(e)}", "Processing Method Selection Error")
            return "local"  # Default to local on error
    
    def get_recommended_processing_method(self, settings):
        """Get the recommended processing method for display purposes (doesn't actually process)"""
        try:
            # Check if RunPod is configured and healthy
            if (settings.runpod_pod_id and 
                settings.runpod_port and 
                settings.runpod_api_secret and
                settings.runpod_health_status == "healthy" and
                settings.runpod_response_time < 5):
                return "runpod"
            else:
                return "local"
        except Exception as e:
            return "local"
    
    def extract_text_with_runpod(self, file_path, policy_type, settings):
        """Extract OCR text using RunPod API (OCR only, field extraction happens locally)"""
        try:
            # Use RunPodService for OCR-only extraction
            from policy_reader.policy_reader.services.runpod_service import RunPodService
            runpod_service = RunPodService(settings)
            result = runpod_service.extract_document_text(file_path, policy_type)
            
            frappe.logger().info(f"RunPod OCR result: {result.get('success')}, text length: {len(result.get('text', ''))}")
            
            return result
                
        except Exception as e:
            frappe.log_error(f"RunPod OCR extraction error: {str(e)}", "RunPod OCR Error")
            return {"success": False, "error": f"RunPod OCR error: {str(e)}"}
    
    def extract_text_with_local(self, file_path, settings):
        """Extract text using local document_reader library (fallback method)"""
        try:
            from document_reader import extract_text_with_confidence
            
            # Use enhanced extraction with confidence scoring
            result = extract_text_with_confidence(
                file_path,
                language='en',
                enable_enhancement=True,
                enhancement_method="auto"
            )
            
            # Add processing method info
            if 'confidence_data' in result:
                result['confidence_data']['processing_method'] = 'local'
            
            return result
            
        except ImportError:
            return {"success": False, "error": "Local document_reader library not available"}
        except Exception as e:
            frappe.log_error(f"Local OCR processing error: {str(e)}", "Local OCR Error")
            return {"success": False, "error": f"Local OCR error: {str(e)}"}
    
    def validate_file_access(self, policy_file):
        """Validate that the file is accessible for processing"""
        try:
            if not policy_file:
                return False
            
            # Try to get the file document
            file_doc = frappe.get_doc("File", {"file_url": policy_file})
            
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
            frappe.logger().error(f"File validation failed for {policy_file}: {str(e)}")
            return False
    
    def process_document_text(self, file_path, policy_type, settings):
        """Main method to extract text using the best available method"""
        try:
            # Choose processing method
            processing_method = self.choose_processing_method(settings)
            
            # Process with chosen method
            if processing_method == "runpod":
                result = self.extract_text_with_runpod(file_path, policy_type, settings)
                if not result.get("success"):
                    # Fallback to local processing
                    frappe.logger().warning("RunPod processing failed, falling back to local")
                    result = self.extract_text_with_local(file_path, settings)
                    processing_method = "local"
            else:
                result = self.extract_text_with_local(file_path, settings)
            
            # Add processing method to result
            if result.get("success"):
                result["processing_method"] = processing_method
            
            return result
            
        except Exception as e:
            frappe.log_error(f"Document text processing error: {str(e)}", "Document Processing Error")
            return {"success": False, "error": f"Processing error: {str(e)}"}