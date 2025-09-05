# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import os
import json


class FieldMappingService:
    """Service class for handling field extraction and mapping operations"""
    
    def __init__(self):
        """Initialize the field mapping service"""
        pass
    
    def get_field_mapping_for_policy_type(self, policy_type):
        """Get field mapping for a policy type with fallback to hardcoded mappings"""
        try:
            # Try to get cached mapping from Policy Reader Settings
            settings = frappe.get_single("Policy Reader Settings")
            if settings:
                cached_mapping = settings.get_cached_field_mapping(policy_type)
                if cached_mapping:
                    return cached_mapping
            
            # Fallback to hardcoded mappings if cache is empty
            frappe.logger().warning(f"Using fallback hardcoded field mapping for {policy_type} policy")
            
            if policy_type.lower() == "motor":
                return self.get_hardcoded_motor_mapping()
            elif policy_type.lower() == "health":
                return self.get_hardcoded_health_mapping()
            
            return {}
            
        except Exception as e:
            frappe.log_error(f"Error getting field mapping for {policy_type}: {str(e)}", 
                            "Field Mapping Retrieval Error")
            # Return hardcoded mapping as last resort
            if policy_type.lower() == "motor":
                return self.get_hardcoded_motor_mapping()
            elif policy_type.lower() == "health":
                return self.get_hardcoded_health_mapping()
            return {}
    
    def get_hardcoded_motor_mapping(self):
        """Fallback hardcoded motor policy field mapping for SAIBA ERP compatibility"""
        return {
            # OCR Extractable fields - mapped to new SAIBA ERP structure
            "PolicyNumber": "policy_no",
            "PolicyNo": "policy_no", 
            "PolicyType": "policy_type",
            "PolicyIssuanceDate": "policy_issuance_date",
            "PolicyStartDate": "policy_start_date", 
            "PolicyExpiryDate": "policy_expiry_date",
            
            # Financial fields
            "SumInsured": "sum_insured",
            "NetODPremium": "net_od_premium",
            "NetPremium": "net_od_premium",  # Alternative mapping
            "TPPremium": "tp_premium",
            "GST": "gst",
            "NCB": "ncb",
            
            # Vehicle information
            "VehicleNumber": "vehicle_no",
            "VehicleNo": "vehicle_no",
            "Make": "make",
            "Model": "model", 
            "Variant": "variant",
            "YearOfManufacture": "year_of_man",
            "ManufacturingYear": "year_of_man",
            "ChassisNumber": "chasis_no",
            "ChasisNo": "chasis_no",
            "EngineNumber": "engine_no",
            "EngineNo": "engine_no",
            "CC": "cc",
            "EngineCapacity": "cc",
            "Fuel": "fuel",
            "FuelType": "fuel",
            "RTOCode": "rto_code",
            "RTO": "rto_code",
            "VehicleCategory": "vehicle_category",
            "VehicleClass": "vehicle_category",  # Alternative mapping
            "PassengerGVW": "passenger_gvw",
            "GVW": "passenger_gvw"
            
            # NOTE: Manual entry fields (customer_code, policy_biz_type, etc.) 
            # are not included here as they won't be OCR extracted
        }
    
    def get_hardcoded_health_mapping(self):
        """Fallback hardcoded health policy field mapping"""
        return {
            # Match the exact field names that Claude extracts
            "PolicyNumber": "policy_number",
            "InsuredName": "insured_name",
            "SumInsured": "sum_insured", 
            "PolicyStartDate": "policy_start_date",
            "PolicyEndDate": "policy_end_date",
            "CustomerCode": "customer_code",
            "NetPremium": "net_premium",
            "PolicyPeriod": "policy_period",
            "IssuingOffice": "issuing_office",
            "RelationshipToPolicyholder": "relationship_to_policyholder",
            "DateOfBirth": "date_of_birth",
            "InsuredName2": "insured_name_2",
            "NomineeName": "nominee_name",
            "InsuredCode": "insured_code"
        }
    
    def get_field_format_specification(self, field_label, fieldname, field_meta):
        """Get format specification for a specific field based on its type"""
        if not field_meta:
            return f"- {field_label}: Text format"
        
        fieldtype = field_meta.fieldtype
        
        # Date fields
        if fieldtype in ["Date", "Datetime"]:
            return f"- {field_label}: Date in DD/MM/YYYY format only (remove 'FROM', 'UNTIL', 'VALID TILL', times, extra text)"
        
        # Currency fields  
        elif fieldtype in ["Currency", "Float"]:
            return f"- {field_label}: Numeric value only (remove currency symbols like '₹', 'Rs.', commas, '/-')"
        
        # Integer fields
        elif fieldtype == "Int":
            return f"- {field_label}: Integer number only (remove descriptive text like 'seater', 'capacity')"
        
        # Select fields
        elif fieldtype == "Select" and field_meta.options:
            options_list = [opt.strip() for opt in field_meta.options.split('\n') if opt.strip()]
            return f"- {field_label}: Exact match from [{', '.join(options_list)}] (case-insensitive matching)"
        
        # Data fields with special cases
        elif fieldtype == "Data":
            # Special handling for known date-like fields that should be Data type
            if any(date_keyword in fieldname.lower() for date_keyword in ['from', 'to', 'date', 'period']):
                if 'from' in fieldname.lower() or 'to' in fieldname.lower():
                    return f"- {field_label}: Date in DD/MM/YYYY format (clean from 'FROM 15/03/2024' to '15/03/2024')"
                else:
                    return f"- {field_label}: Clean text format (remove unnecessary prefixes/suffixes)"
            # Vehicle/Registration numbers
            elif any(vehicle_keyword in fieldname.lower() for vehicle_keyword in ['vehicle', 'registration', 'chassis', 'engine']):
                return f"- {field_label}: Alphanumeric format (clean registration/ID format)"
            else:
                return f"- {field_label}: Clean text format (core information only)"
        
        # Default fallback
        else:
            return f"- {field_label}: Text format"
    
    def build_field_format_specifications(self, policy_type, field_mapping):
        """Build complete field format specifications string for the prompt"""
        try:
            # Get DocType metadata
            if policy_type.lower() == "motor":
                doctype_name = "Motor Policy"
            elif policy_type.lower() == "health":  
                doctype_name = "Health Policy"
            else:
                return "- All fields: Clean text format"
            
            meta = frappe.get_meta(doctype_name)
            format_specs = []
            
            # Build format specification for each field
            for field_label, fieldname in field_mapping.items():
                field_meta = meta.get_field(fieldname)
                spec = self.get_field_format_specification(field_label, fieldname, field_meta)
                format_specs.append(spec)
            
            return '\n'.join(format_specs)
            
        except Exception as e:
            frappe.logger().warning(f"Could not build field format specifications: {str(e)}")
            return "- All fields: Extract clean, core information only"
    
    def build_extraction_prompt(self, text, policy_type, fields_list):
        """Build enhanced prompt for Claude to extract specific fields with format specifications"""
        try:
            # Get field mapping to build format specifications
            field_mapping = self.get_field_mapping_for_policy_type(policy_type)
            
            # Build format specifications
            format_specs = self.build_field_format_specifications(policy_type, field_mapping)
            
            # Create enhanced prompt with specific format requirements
            prompt = f"""You are an expert at extracting information from {policy_type} insurance policy documents.

Extract the following fields with EXACT formats as specified below:

FIELD FORMATS:
{format_specs}

EXTRACTION RULES:
- Extract ONLY the core data, remove prefixes/suffixes like "UNTIL", "FROM", "VALID TILL", "Rs.", "₹"
- For dates: Use DD/MM/YYYY or DD/MM/YY format only, remove time and extra text
- For currency: Extract numbers only, no currency symbols or formatting
- For select fields: Use exact option matches (case-insensitive)
- For numbers: Extract digits only, remove descriptive text
- If field not found, use null

EXTRACTION EXAMPLES:
- "FROM 15/03/2024" → "15/03/2024"
- "UNTIL MIDNIGHT 30/07/24" → "30/07/24" 
- "VALID TILL 31/12/2024" → "31/12/2024"
- "Rs. 25,000/-" → "25000"
- "₹50,000.00" → "50000"
- "5 seater capacity" → "5"
- "DIESEL fuel type" → "Diesel"
- "DL-01-AA-1234 (Vehicle)" → "DL-01-AA-1234"

Fields to extract:
{', '.join(fields_list)}

Document text:
{text[:8000]}

Return your response as a valid JSON object only, no additional text or explanation."""
            
            return prompt
            
        except Exception as e:
            # Fallback to simpler prompt if enhanced version fails
            frappe.logger().error(f"Enhanced prompt building failed: {str(e)}, using fallback")
            return f"""You are an expert at extracting information from {policy_type} insurance policy documents.

Extract the following fields from the document text. Return clean, formatted data:
- For dates: Use DD/MM/YYYY format only (remove extra text like "UNTIL MIDNIGHT")
- For numbers: Extract digits only (remove currency symbols, extra text)
- Return ONLY a JSON object with field names as keys and extracted values as values.

Fields to extract: {', '.join(fields_list)}

Document text: {text[:8000]}

Return valid JSON only, no additional text."""
    
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
            field_mapping = self.get_field_mapping_for_policy_type(policy_type)
            
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
            
            try:
                response = make_post_request(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    data=frappe.as_json(payload)
                )
            except Exception as e:
                frappe.log_error(f"Claude API make_post_request error: {str(e)}", "Claude API Request Error")
                return {
                    "success": False,
                    "error": f"Claude API request failed: {str(e)}"
                }
            
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