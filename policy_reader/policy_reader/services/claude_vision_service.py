# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import base64
import requests
import os
from policy_reader.policy_reader.services.common_service import CommonService


class ClaudeVisionService:
    """Service for handling Claude Vision API interactions"""
    
    @staticmethod
    def process_pdf(file_path, api_key, settings, policy_type):
        """
        Process PDF directly with Claude API using native PDF support
        """
        try:
            # Read and encode PDF file directly
            pdf_data = ClaudeVisionService._encode_pdf_file(file_path)
            
            # Get extraction prompt from settings
            prompt_text = ClaudeVisionService._get_vision_extraction_prompt(settings, policy_type)
            
            # Prepare Claude API request with direct PDF support
            headers = ClaudeVisionService._prepare_headers(api_key)
            content = ClaudeVisionService._build_content_array(pdf_data, prompt_text)
            payload = ClaudeVisionService._build_payload(settings, content)
            
            # Make API call
            response = ClaudeVisionService._make_api_call(headers, payload, settings)
            
            # Process response
            return ClaudeVisionService._process_api_response(response)
                
        except Exception as e:
            frappe.log_error(f"Claude vision processing error: {str(e)}", frappe.get_traceback())
            return {
                "success": False,
                "error": f"Claude vision processing failed: {str(e)}"
            }
    
    @staticmethod
    def _encode_pdf_file(file_path):
        """Encode PDF file to base64"""
        CommonService.validate_file_access(file_path)
        
        with open(file_path, 'rb') as pdf_file:
            return base64.standard_b64encode(pdf_file.read()).decode('utf-8')
    
    @staticmethod
    def _get_vision_extraction_prompt(settings, policy_type):
        """Get extraction prompt optimized for Claude Vision API"""
        try:
            # Get field mapping from settings
            policy_reader_settings = CommonService.get_policy_reader_settings()
            mapping = policy_reader_settings.get_cached_field_mapping(policy_type.lower()) or {}
            
            # Get canonical fields (fields that map to themselves)
            canonical_fields = [k for k, v in mapping.items() if k == v]
            canonical_fields = sorted(set(canonical_fields))
            
            if canonical_fields:
                fields_list = "\n".join([f"- {field}" for field in canonical_fields])
                
                prompt = f"""Analyze this {policy_type.lower()} insurance policy PDF and extract the following information as a flat JSON object:

Required fields to extract:
{fields_list}

EXTRACTION RULES:
- Dates: DD/MM/YYYY format only
- Currency/Amounts: Extract exact numeric value including decimals, remove currency symbols and commas only
- Text: Extract exact text as it appears
- Numbers: Extract as strings unless specified otherwise
- If a field is not found, use null
- Return ONLY valid JSON, no explanations or markdown

RESPOND WITH VALID FLAT JSON ONLY - NO EXPLANATIONS, NO MARKDOWN, NO CODE BLOCKS."""

                # Add health-specific insured persons extraction instructions
                if policy_type.lower() == "health":
                    prompt += """

INSURED PERSONS TABLE EXTRACTION:
This policy may contain a table listing multiple insured members/dependents.
Look for tables with headers like: Name, Relation, DOB, Gender, Sum Insured, Employee Code, Member Code, etc.

For each row in the insured persons table:
- Row 1 (usually Self/Proposer) maps to: insured_1_name, insured_1_relation, insured_1_dob, insured_1_gender, insured_1_sum_insured, insured_1_emp_code
- Row 2 (usually Spouse) maps to: insured_2_name, insured_2_relation, insured_2_dob, insured_2_gender, insured_2_sum_insured, insured_2_emp_code
- Row 3 maps to insured_3_*, Row 4 to insured_4_*, and so on up to Row 8 (insured_8_*)

IMPORTANT:
- Extract each insured person's data into the numbered fields based on their row position
- The "Self" or "Proposer" is typically insured_1_*
- Relations like "Spouse", "Son", "Daughter", "Father", "Mother" indicate family members
- Dates of Birth should be in DD/MM/YYYY format
- Gender: Use "Male", "Female", or "Other"
- Relation: Use "Self", "Spouse", "Wife", "Husband", "Son", "Daughter", "Father", "Mother", or "Other"
"""

                return prompt
            else:
                # Fallback prompt if no mapping available
                return f"Extract key information from this {policy_type.lower()} insurance policy as JSON."
                
        except Exception as e:
            frappe.log_error(f"Error building vision prompt: {str(e)}", frappe.get_traceback())
            return f"Extract key information from this {policy_type.lower()} insurance policy as JSON."
    
    @staticmethod
    def _prepare_headers(api_key):
        """Prepare headers for Claude API request"""
        return {
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
            'anthropic-version': '2023-06-01'
        }
    
    @staticmethod
    def _build_content_array(pdf_data, prompt_text):
        """Build content array with PDF document and text prompt"""
        return [
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
    
    @staticmethod
    def _build_payload(settings, content):
        """Build payload for Claude API request"""
        return {
            'model': getattr(settings, 'claude_model', 'claude-sonnet-4-20250514'),
            'max_tokens': 4000,
            'messages': [
                {
                    'role': 'user',
                    'content': content
                }
            ]
        }
    
    @staticmethod
    def _make_api_call(headers, payload, settings):
        """Make API call to Claude"""
        return requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=payload,
            timeout=settings.timeout or 180
        )
    
    @staticmethod
    def _process_api_response(response):
        """Process Claude API response"""
        if response.status_code == 200:
            return ClaudeVisionService._handle_successful_response(response)
        elif response.status_code == 429:
            return ClaudeVisionService._handle_rate_limit_response(response)
        elif response.status_code == 401:
            return ClaudeVisionService._handle_auth_error_response()
        else:
            return ClaudeVisionService._handle_error_response(response)
    
    @staticmethod
    def _handle_successful_response(response):
        """Handle successful API response"""
        response_data = response.json()
        
        # Log the full response for debugging
        frappe.logger().info(f"Claude API Response: {response_data}")
        
        content = response_data.get('content', [{}])[0].get('text', '')
        
        # Extract JSON from Claude's response
        extracted_fields = CommonService.extract_json_from_text(content)
        
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
    
    @staticmethod
    def _handle_rate_limit_response(response):
        """Handle rate limit response"""
        error_data = response.json() if response.text else {}
        error_message = error_data.get('error', {}).get('message', response.text)
        return {
            "success": False,
            "error": f"API Rate Limit or Insufficient Balance: {error_message}",
            "error_type": "rate_limit"
        }
    
    @staticmethod
    def _handle_auth_error_response():
        """Handle authentication error response"""
        return {
            "success": False,
            "error": "API Authentication Failed - Check your API key",
            "error_type": "auth_error"
        }
    
    @staticmethod
    def _handle_error_response(response):
        """Handle general error response"""
        error_data = response.json() if response.text else {}
        error_message = error_data.get('error', {}).get('message', response.text[:200])
        return {
            "success": False,
            "error": f"Claude API error: HTTP {response.status_code} - {error_message}",
            "error_type": "api_error"
        }
    
