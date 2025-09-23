# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import os
import json
from frappe.integrations.utils import make_post_request


class ExtractionService:
    """Service for extracting structured fields from policy documents using AI"""
    
    def __init__(self):
        """Initialize the extraction service"""
        pass
    
    def extract_fields_from_text(self, extracted_text, policy_type, settings):
        """Extract structured fields from OCR text using Claude API"""
        try:
            # Get the appropriate prompt from Policy Reader Settings
            prompt = self._get_extraction_prompt(extracted_text, policy_type, settings)
            
            if not prompt:
                return {
                    "success": False,
                    "error": f"No extraction prompt found for policy type: {policy_type}"
                }
            
            # Call Claude API
            result = self._call_claude_api(prompt, settings)
            
            if result.get("success"):
                # Parse and validate the extracted fields
                extracted_fields = result.get("extracted_fields", {})
                validated_fields = self._validate_extracted_fields(extracted_fields, policy_type)
                
                return {
                    "success": True,
                    "extracted_fields": validated_fields
                }
            else:
                return result
                
        except Exception as e:
            frappe.log_error(f"Field extraction failed: {str(e)}", "Extraction Service Error")
            return {
                "success": False,
                "error": f"Field extraction failed: {str(e)}"
            }
    
    def _get_extraction_prompt(self, extracted_text, policy_type, settings):
        """Get the appropriate extraction prompt from Policy Reader Settings"""
        try:
            # Get Policy Reader Settings
            policy_reader_settings = frappe.get_single("Policy Reader Settings")
            
            # Try to get cached prompt first
            cached_prompt = policy_reader_settings.get_cached_extraction_prompt(policy_type, extracted_text)
            if cached_prompt:
                frappe.logger().info(f"Using cached extraction prompt for {policy_type}")
                self._last_used_prompt = cached_prompt
                return cached_prompt
            
            # Build dynamic prompt if not cached
            dynamic_prompt = policy_reader_settings.build_dynamic_extraction_prompt(policy_type, extracted_text)
            if dynamic_prompt:
                frappe.logger().info(f"Using dynamic extraction prompt for {policy_type}")
                self._last_used_prompt = dynamic_prompt
                return dynamic_prompt
            
            # Fallback to simple prompt
            frappe.logger().warning(f"No specific prompt found for {policy_type}, using fallback")
            fallback_prompt = self._build_fallback_prompt(extracted_text, policy_type, settings)
            self._last_used_prompt = fallback_prompt
            return fallback_prompt
            
        except Exception as e:
            frappe.log_error(f"Error getting extraction prompt: {str(e)}", "Prompt Retrieval Error")
            fallback_prompt = self._build_fallback_prompt(extracted_text, policy_type, settings)
            self._last_used_prompt = fallback_prompt
            return fallback_prompt
    
    def _call_claude_api(self, prompt, settings):
        """Call Claude API to extract fields from text"""
        try:
            # Get API key with priority: Settings → site_config → environment
            api_key = (settings.anthropic_api_key or 
                      frappe.conf.get('anthropic_api_key') or 
                      os.environ.get('ANTHROPIC_API_KEY'))
            
            if not api_key:
                raise Exception("Anthropic API key not configured. Please set it in Policy Reader Settings or add 'anthropic_api_key' to site_config.json")
            
            # Prepare API request
            headers = {
                'Content-Type': 'application/json',
                'X-API-Key': api_key,
                'anthropic-version': '2023-06-01'
            }
            
            payload = {
                'model': getattr(settings, 'claude_model', 'claude-sonnet-4-20250514'),
                'max_tokens': 4000,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }
            
            # Log the request for debugging
            frappe.logger().info(f"Sending Claude API request with model: {payload['model']}")
            
            # Make API call
            response = make_post_request(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                data=frappe.as_json(payload)
            )
            
            # Process response
            return self._process_claude_response(response)
            
        except Exception as e:
            frappe.log_error(f"Claude API call failed: {str(e)}", "Claude API Error")
            return {
                "success": False,
                "error": f"Claude API call failed: {str(e)}"
            }
    
    def _process_claude_response(self, response):
        """Process Claude API response and extract JSON"""
        try:
            frappe.logger().info(f"Claude API response type: {type(response)}")
            
            if not response:
                return {
                    "success": False,
                    "error": "Claude API request returned no response"
                }
            
            # Handle different response formats from make_post_request
            if isinstance(response, dict) and response.get('content'):
                content = response['content'][0]['text']
                frappe.logger().info(f"Extracted content from response: {content[:200]}...")
                
                # Parse the JSON response from Claude with improved extraction
                extracted_fields = self._extract_json_from_text(content)
                frappe.logger().info(f"Successfully parsed extracted fields: {len(extracted_fields)} fields")
                
                return {
                    "success": True,
                    "extracted_fields": extracted_fields
                }
            
            elif isinstance(response, dict) and response.get('error'):
                error_msg = f"Claude API error: {response.get('error', 'Unknown error')}"
                frappe.logger().error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
            
            elif isinstance(response, str):
                frappe.logger().info(f"Received string response: {response[:200]}...")
                extracted_fields = self._extract_json_from_text(response)
                return {
                    "success": True,
                    "extracted_fields": extracted_fields
                }
            
            else:
                error_msg = f"Unexpected Claude API response format: {type(response)}"
                frappe.logger().error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }
                
        except (ValueError, TypeError) as e:
            frappe.logger().error(f"JSON parsing error: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to parse Claude response as JSON: {str(e)}"
            }
        except Exception as e:
            frappe.log_error(f"Error processing Claude response: {str(e)}", "Claude Response Processing Error")
            return {
                "success": False,
                "error": f"Error processing Claude response: {str(e)}"
            }
    
    def _validate_extracted_fields(self, extracted_fields, policy_type):
        """Validate and clean extracted fields"""
        if not isinstance(extracted_fields, dict):
            frappe.logger().warning(f"Extracted fields is not a dictionary: {type(extracted_fields)}")
            return {}
        
        # Basic validation - ensure all values are strings, numbers, or null
        validated_fields = {}
        for field_name, field_value in extracted_fields.items():
            if field_value is None or field_value == "":
                validated_fields[field_name] = None
            elif isinstance(field_value, (str, int, float, bool)):
                validated_fields[field_name] = field_value
            else:
                # Convert other types to string
                validated_fields[field_name] = str(field_value)
        
        frappe.logger().info(f"Validated {len(validated_fields)} fields for {policy_type} policy")
        return validated_fields
    
    def _build_fallback_prompt(self, extracted_text, policy_type, settings):
        """Build a simple fallback prompt if no specific prompt is available"""
        try:
            truncation_limit = 200000  # Default text truncation limit (200k chars)
        except:
            truncation_limit = 200000
        
        if policy_type.lower() == "motor":
            return f"""Extract motor insurance policy information as FLAT JSON:
PolicyNumber, VehicleNumber, ChasisNo, EngineNo, Make, Model, PolicyStartDate, PolicyExpiryDate, SumInsured, NetODPremium, TPPremium, GST, NCB

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency: Extract digits only (remove currency symbols)
- Numbers: Digits only (remove descriptive text)
- Text: Clean format
- Missing fields: null
- Chassis/Engine: Extract from combined formats like "Chassis no./Engine no.: ABC123 DEF456"

EXAMPLES:
- "Chassis no./Engine no.: MATRC4GGA91 J57810/GG91.76864" → ChasisNo: "MATRC4GGA91", EngineNo: "J57810"

IMPORTANT: Return ONE FLAT JSON object with all fields at the same level.
DO NOT group fields by categories. DO NOT create nested structures.

Document: {extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
        
        elif policy_type.lower() == "health":
            return f"""Extract health insurance policy information as FLAT JSON:
PolicyNumber, InsuredName, PolicyStartDate, PolicyExpiryDate, SumInsured, NetPremium, CustomerCode, PolicyPeriod

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency: Extract digits only (remove currency symbols)
- Text: Clean format
- Missing fields: null

IMPORTANT: Return ONE FLAT JSON object with all fields at the same level.
DO NOT group fields by categories. DO NOT create nested structures.

Document: {extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
        
        else:
            return f"""Extract {policy_type} insurance policy information as FLAT JSON.
Return clean, structured data with dates in DD/MM/YYYY format and numbers as digits only.

IMPORTANT: Return ONE FLAT JSON object with all fields at the same level.
DO NOT group fields by categories. DO NOT create nested structures.

Document: {extracted_text[:truncation_limit]}

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""
    
    def get_field_mapping_for_policy_type(self, policy_type):
        """Get field mapping for a policy type (for backward compatibility)"""
        try:
            settings = frappe.get_single("Policy Reader Settings")
            return settings.get_cached_field_mapping(policy_type)
        except Exception as e:
            frappe.log_error(f"Error getting field mapping for {policy_type}: {str(e)}", "Field Mapping Error")
            return {}
    
    def _extract_json_from_text(self, text):
        """Extract JSON from Claude's response, handling various formats"""
        import re
        import json
        
        frappe.logger().info(f"Attempting to extract JSON from text: {text[:500]}...")
        
        # First, try to parse the text directly as JSON
        try:
            return frappe.parse_json(text)
        except:
            pass
        
        # Look for JSON wrapped in code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                json_text = json_match.group(1)
                frappe.logger().info(f"Found JSON in code block: {json_text[:200]}...")
                return frappe.parse_json(json_text)
            except Exception as e:
                frappe.logger().warning(f"Failed to parse JSON from code block: {str(e)}")
        
        # Look for JSON object starting with { and ending with }
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            try:
                json_text = json_match.group(1)
                frappe.logger().info(f"Found JSON object: {json_text[:200]}...")
                return frappe.parse_json(json_text)
            except Exception as e:
                frappe.logger().warning(f"Failed to parse extracted JSON object: {str(e)}")
        
        # If all else fails, try to clean the text and parse
        try:
            # Remove common non-JSON prefixes/suffixes
            cleaned_text = text.strip()
            
            # Remove any text before the first {
            start_idx = cleaned_text.find('{')
            if start_idx > 0:
                cleaned_text = cleaned_text[start_idx:]
            
            # Remove any text after the last }
            end_idx = cleaned_text.rfind('}')
            if end_idx >= 0:
                cleaned_text = cleaned_text[:end_idx + 1]
            
            frappe.logger().info(f"Cleaned text for JSON parsing: {cleaned_text[:200]}...")
            return frappe.parse_json(cleaned_text)
            
        except Exception as e:
            frappe.logger().error(f"All JSON extraction attempts failed: {str(e)}")
            # Return empty dict as fallback
            return {}
