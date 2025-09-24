# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import os
import json
import re
from frappe.utils import getdate, cstr, flt, cint


class CommonService:
    """Common service for shared functionality across the Policy Reader app"""
    
    @staticmethod
    def get_policy_reader_settings():
        """Get Policy Reader Settings with fallback to defaults"""
        try:
            settings = frappe.get_single("Policy Reader Settings")
            return settings
        except frappe.DoesNotExistError:
            frappe.logger().warning("Policy Reader Settings not found")
            return CommonService._get_default_settings()
        except Exception as e:
            frappe.log_error(f"Error loading Policy Reader Settings: {str(e)}", frappe.get_traceback())
            return CommonService._get_default_settings()
    
    @staticmethod
    def _get_default_settings():
        """Get default settings object"""
        class DefaultSettings:
            anthropic_api_key = None
            claude_model = "claude-sonnet-4-20250514"
            timeout = 180
            queue_type = "short"
        return DefaultSettings()
    
    @staticmethod
    def get_api_key(settings=None):
        """Get API key with proper priority: Settings → site_config → environment"""
        if not settings:
            settings = CommonService.get_policy_reader_settings()
        
        api_key = (settings.anthropic_api_key or 
                  frappe.conf.get('anthropic_api_key') or 
                  os.environ.get('ANTHROPIC_API_KEY'))
        
        if not api_key:
            frappe.throw("Invalid input: ANTHROPIC_API_KEY not configured. Please set it in Policy Reader Settings")
        
        return api_key
    
    @staticmethod
    def safe_parse_json(json_string, default=None):
        """Safely parse JSON string with fallback"""
        if default is None:
            default = {}
        
        try:
            return frappe.parse_json(json_string)
        except (ValueError, TypeError):
            frappe.logger().warning(f"Failed to parse JSON: {str(json_string)[:100]}...")
            return default
    
    @staticmethod
    def extract_json_from_text(text):
        """Extract JSON from text with multiple parsing strategies"""
        if not text or not isinstance(text, str):
            return {}
        
        # Strategy 1: Try direct JSON parsing
        try:
            return frappe.parse_json(text)
        except (ValueError, TypeError):
            pass
        
        # Strategy 2: Look for JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return frappe.parse_json(json_match.group(1))
            except (ValueError, TypeError):
                pass
        
        # Strategy 3: Look for JSON object in text
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            try:
                return frappe.parse_json(json_match.group(1))
            except (ValueError, TypeError):
                pass
        
        # If all parsing fails, return empty dict
        frappe.logger().warning(f"Could not extract JSON from text: {text[:500]}...")
        return {}
    
    @staticmethod
    def validate_required_fields(data, required_fields, field_type="input"):
        """Validate that required fields are present in data"""
        missing_fields = []
        
        for field in required_fields:
            if not data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            frappe.throw(f"Invalid {field_type}: missing required fields: {', '.join(missing_fields)}")
        
        return True
    
    @staticmethod
    def validate_policy_type(policy_type):
        """Validate policy type is supported"""
        if not policy_type or not isinstance(policy_type, str):
            frappe.throw("Invalid input: policy type is required and must be a string")
        
        if policy_type.lower() not in ["motor", "health"]:
            frappe.throw("Invalid input: policy type must be either 'motor' or 'health'")
        
        return policy_type.lower()
    
    @staticmethod
    def validate_file_access(file_path):
        """Validate that file is accessible"""
        if not file_path:
            frappe.throw("Invalid input: file path is required")
        
        if not os.path.exists(file_path):
            frappe.throw("Invalid input: file does not exist")
        
        if not os.access(file_path, os.R_OK):
            frappe.throw("Invalid input: file is not readable")
        
        return True
    
    @staticmethod
    def log_processing_error(operation, error, context=None):
        """Standardized error logging for processing operations"""
        error_context = f" for {context}" if context else ""
        frappe.log_error(f"Unexpected error while {operation}{error_context}: {str(error)}", frappe.get_traceback())
    
    @staticmethod
    def handle_processing_exception(operation, error, context=None):
        """Standardized exception handling for processing operations"""
        CommonService.log_processing_error(operation, error, context)
        frappe.throw(f"Unexpected error occurred while {operation}. Please contact support.")
    
    @staticmethod
    def get_field_mapping_for_policy_type(policy_type):
        """Get field mapping for a policy type from settings"""
        try:
            settings = CommonService.get_policy_reader_settings()
            return settings.get_cached_field_mapping(policy_type)
        except Exception as e:
            frappe.log_error(f"Error getting field mapping for {policy_type}: {str(e)}", frappe.get_traceback())
            return {}
    
    @staticmethod
    def normalize_string(value):
        """Normalize string value for consistent processing"""
        if not value:
            return ""
        
        if not isinstance(value, str):
            value = str(value)
        
        return value.strip()
    
    @staticmethod
    def safe_get_attribute(obj, attr, default=None):
        """Safely get attribute from object with fallback"""
        try:
            return getattr(obj, attr, default)
        except (AttributeError, TypeError):
            return default
    
    @staticmethod
    def truncate_text(text, max_length=200):
        """Truncate text to specified length with ellipsis"""
        if not text or not isinstance(text, str):
            return ""
        
        if len(text) <= max_length:
            return text
        
        return text[:max_length] + "..."
    
    @staticmethod
    def format_error_message(operation, error_type="error", details=None):
        """Format standardized error messages"""
        base_message = f"Unexpected {error_type} occurred while {operation}"
        
        if details:
            base_message += f": {details}"
        else:
            base_message += ". Please contact support."
        
        return base_message
    
    @staticmethod
    def validate_file_access(policy_file):
        """Validate that the file is accessible for processing - DISABLED"""
        # Always return True to skip all file validation
        return True
