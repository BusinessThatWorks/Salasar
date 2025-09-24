# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import os


class ProcessingService:
    """Service class for handling document processing operations"""
    
    def __init__(self, policy_document=None):
        """Initialize with optional policy document reference"""
        self.policy_document = policy_document
    
    def extract_text_with_local(self, file_path, settings):
        """Extract text using local document_reader library"""
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