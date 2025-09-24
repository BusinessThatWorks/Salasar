import frappe
import ast
import json
from frappe.utils import getdate, cstr, flt, cint
from frappe import _
from policy_reader.policy_reader.services.common_service import CommonService
from policy_reader.policy_reader.services.field_mapping_service import FieldMappingService

class PolicyCreationService:
    def __init__(self):
        self._last_used_prompt = None
    
    def create_policy_record(self, policy_document_name, policy_type):
        """
        Create a policy record (Motor/Health) from Policy Document using dynamic field mapping
        """
        # Input validation using common service
        CommonService.validate_required_fields({"policy_document_name": policy_document_name}, ["policy_document_name"])
        if not isinstance(policy_document_name, str):
            frappe.throw(f"Invalid input: policy document name must be a string, got {type(policy_document_name).__name__}: {policy_document_name}")
        
        policy_type = CommonService.validate_policy_type(policy_type)
        
        try:
            # Get Policy Document
            policy_doc = frappe.get_doc("Policy Document", policy_document_name)
            
            if not policy_doc.extracted_fields:
                frappe.throw("No extracted fields found. Please extract fields first.")
            
            # Get field mapping from Policy Reader Settings
            field_mapping = CommonService.get_field_mapping_for_policy_type(policy_type)
            
            frappe.logger().info(f"=== POLICY CREATION DEBUG for {policy_type} ===")
            frappe.logger().info(f"Field mapping retrieved: {len(field_mapping) if field_mapping else 0} entries")
            
            if not field_mapping:
                frappe.logger().error(f"No field mapping found for {policy_type}")
                frappe.throw(f"No field mapping found for {policy_type}. Please refresh field mappings in Policy Reader Settings.")
            
            # Parse extracted data with validation using common service
            extracted_data = CommonService.safe_parse_json(policy_doc.extracted_fields)
            if not isinstance(extracted_data, dict):
                frappe.throw("Invalid input: extracted fields must be a valid JSON object")
            
            frappe.logger().info(f"Raw extracted fields: {extracted_data}")
            frappe.logger().info(f"Extracted fields type: {type(extracted_data)}")
            
            # Use extracted data directly (already parsed by Claude Vision Service)
            parsed_data = extracted_data if isinstance(extracted_data, dict) else {}
            frappe.logger().info(f"Parsed data keys: {list(parsed_data.keys()) if parsed_data else 'No parsed data'}")
            frappe.logger().info(f"Parsed data sample: {dict(list(parsed_data.items())[:5]) if parsed_data else 'No data'}")
            
            # Create policy document
            if policy_type.lower() == "motor":
                policy_record = frappe.new_doc("Motor Policy")
            elif policy_type.lower() == "health":
                policy_record = frappe.new_doc("Health Policy")
            else:
                frappe.throw(f"Unsupported policy type: {policy_type}")
            
            # Set document link
            policy_record.policy_document = policy_doc.name
            policy_record.policy_file = policy_doc.policy_file
            
            # Dynamic field mapping
            field_mapping_service = FieldMappingService()
            mapping_results = field_mapping_service.map_fields_dynamically(
                parsed_data, field_mapping, policy_record, policy_type
            )
            
            # Validate and save
            policy_record.validate()
            policy_record.insert()
            
            # Update Policy Document with link
            if policy_type.lower() == "motor":
                policy_doc.motor_policy = policy_record.name
            elif policy_type.lower() == "health":
                policy_doc.health_policy = policy_record.name
            
            policy_doc.save()
            frappe.db.commit()
            
            return {
                "success": True,
                "policy_name": policy_record.name,
                "policy_type": policy_type,
                "mapped_fields": mapping_results["mapped_count"],
                "unmapped_fields": mapping_results["unmapped_fields"],
                "message": f"{policy_type} Policy {policy_record.name} created successfully with {mapping_results['mapped_count']} fields"
            }
            
        except Exception as e:
            frappe.db.rollback()
            CommonService.handle_processing_exception("creating policy record", e)
    
    
    def _normalize_key(self, text):
        """Normalize keys for robust alias matching (lowercase, alnum+space)"""
        try:
            if not text:
                return ""
            value = cstr(text).strip().lower()
            import re
            value = re.sub(r"[^a-z0-9]+", " ", value)
            value = " ".join(part for part in value.split() if part)
            return value
        except Exception:
            return cstr(text or "").strip().lower()

    def _build_normalized_mapping(self, field_mapping):
        """Build normalized mapping including normalized keys for matching"""
        normalized = {}
        for k, v in (field_mapping or {}).items():
            normalized[k] = v
            nk = self._normalize_key(k)
            if nk not in normalized:
                normalized[nk] = v
        return normalized

    def _find_best_match(self, key, mapping_keys):
        """Find a fuzzy best match candidate for an unmapped key"""
        try:
            from difflib import get_close_matches
            candidates = get_close_matches(key, mapping_keys, n=3, cutoff=0.75)
            return candidates
        except Exception:
            return []

    def map_fields_dynamically(self, parsed_data, field_mapping, policy_record, policy_type):
        """
        Dynamically map fields using the field mapping from Policy Reader Settings
        """
        mapped_count = 0
        unmapped_fields = []
        suggestions = {}
        
        frappe.logger().info(f"=== FIELD MAPPING DEBUG ===")
        frappe.logger().info(f"Parsed data keys: {list(parsed_data.keys())}")
        frappe.logger().info(f"Field mapping keys: {list(field_mapping.keys())}")
        frappe.logger().info(f"Policy record doctype: {policy_record.doctype}")
        
        # Build normalized mapping for robust matching
        normalized_mapping = self._build_normalized_mapping(field_mapping)
        
        # First pass: direct and normalized-key matching over parsed_data keys
        for raw_key, raw_value in parsed_data.items():
            if raw_value is None or str(raw_value).strip() == "":
                continue
            
            # Try direct match
            policy_field_name = normalized_mapping.get(raw_key)
            
            # Try normalized key match
            if not policy_field_name:
                nk = self._normalize_key(raw_key)
                policy_field_name = normalized_mapping.get(nk)
            
            if policy_field_name:
                try:
                    converted_value = self.convert_field_value(policy_field_name, raw_value, policy_record.doctype)
                    if converted_value is not None:
                        setattr(policy_record, policy_field_name, converted_value)
                        mapped_count += 1
                        frappe.logger().info(f"✓ Mapped {raw_key} -> {policy_field_name}: {converted_value}")
                    else:
                        unmapped_fields.append(raw_key)
                except Exception as e:
                    frappe.logger().error(f"✗ Error mapping {raw_key}: {str(e)}")
                    unmapped_fields.append(raw_key)
            else:
                unmapped_fields.append(raw_key)
                # Collect suggestions to guide alias additions
                nk = self._normalize_key(raw_key)
                cands = self._find_best_match(nk, list(normalized_mapping.keys()))
                if cands:
                    suggestions[raw_key] = cands
        
        # Log summary
        frappe.logger().info(f"=== FIELD MAPPING SUMMARY ===")
        frappe.logger().info(f"Mapped: {mapped_count}, Unmapped: {len(unmapped_fields)}")
        frappe.logger().info(f"Unmapped fields: {unmapped_fields}")
        if suggestions:
            frappe.logger().info(f"Suggestions for unmapped: {frappe.as_json(suggestions)}")
        
        return {
            "mapped_count": mapped_count,
            "unmapped_fields": unmapped_fields,
            "suggestions": suggestions
        }
    
    def convert_field_value(self, field_name, value, doctype):
        """
        Convert field value to appropriate type based on DocType field definition
        """
        try:
            # Handle null/empty/NA values first
            if not value or str(value).strip().upper() in ['NA', 'N/A', 'NULL', 'NONE', '']:
                return None
            
            # Get field metadata
            meta = frappe.get_meta(doctype)
            field = meta.get_field(field_name)
            
            if not field:
                return value
            
            # Convert based on field type
            if field.fieldtype == "Date":
                return self.convert_date_value(value)
            elif field.fieldtype == "Datetime":
                return self.convert_datetime_value(value)
            elif field.fieldtype == "Float":
                return flt(value)
            elif field.fieldtype == "Int":
                return cint(value)
            elif field.fieldtype == "Check":
                return bool(value)
            elif field.fieldtype == "Select":
                return self.normalize_select_value(value, field.options)
            else:
                return cstr(value)
                
        except Exception as e:
            frappe.logger().error(f"Error converting field {field_name}: {str(e)}")
            return None
    
    def convert_date_value(self, value):
        """
        Convert date value from DD/MM/YYYY format to proper date object
        """
        try:
            if not value or str(value).strip().upper() in ['NA', 'N/A', 'NULL', 'NONE', '']:
                return None
            
            # Handle DD/MM/YYYY format specifically
            date_str = str(value).strip()
            if '/' in date_str and len(date_str.split('/')) == 3:
                parts = date_str.split('/')
                if len(parts[0]) <= 2 and len(parts[1]) <= 2 and len(parts[2]) == 4:
                    # DD/MM/YYYY format
                    day, month, year = parts
                    formatted_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    return getdate(formatted_date)
            
            # Fall back to getdate for other formats
            return getdate(value)
        except Exception as e:
            frappe.logger().error(f"Error converting date value {value}: {str(e)}")
            return None
    
    def convert_datetime_value(self, value):
        """
        Convert datetime value from DD/MM/YYYY format to proper datetime object
        """
        try:
            if not value or str(value).strip().upper() in ['NA', 'N/A', 'NULL', 'NONE', '']:
                return None
            
            # Handle DD/MM/YYYY format specifically
            date_str = str(value).strip()
            if '/' in date_str and len(date_str.split('/')) == 3:
                parts = date_str.split('/')
                if len(parts[0]) <= 2 and len(parts[1]) <= 2 and len(parts[2]) == 4:
                    # DD/MM/YYYY format - convert to YYYY-MM-DD HH:MM:SS
                    day, month, year = parts
                    formatted_datetime = f"{year}-{month.zfill(2)}-{day.zfill(2)} 00:00:00"
                    from frappe.utils import get_datetime
                    return get_datetime(formatted_datetime)
            
            # Fall back to get_datetime for other formats
            from frappe.utils import get_datetime
            return get_datetime(value)
        except Exception as e:
            frappe.logger().error(f"Error converting datetime value {value}: {str(e)}")
            return None
    
    def normalize_select_value(self, value, options):
        """
        Normalize select field value to match available options
        """
        if not value or not options:
            return None
        
        # Handle NA values
        if str(value).strip().upper() in ['NA', 'N/A', 'NULL', 'NONE', '']:
            return None
        
        # Split options by newline
        available_options = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        # Try exact match first
        if value in available_options:
            return value
        
        # Try case-insensitive match
        for option in available_options:
            if option.lower() == value.lower():
                return option
        
        # Try partial match
        for option in available_options:
            if value.lower() in option.lower() or option.lower() in value.lower():
                return option
        
        # If no match found, return None to avoid validation errors
        return None
    
    
    def get_available_policy_types(self):
        """
        Get list of available policy types from Policy Reader Settings
        """
        try:
            settings = frappe.get_single("Policy Reader Settings")
            policy_types = []
            
            if settings.motor_policy_fields:
                policy_types.append("Motor")
            if settings.health_policy_fields:
                policy_types.append("Health")
            
            return policy_types
        except Exception as e:
            frappe.log_error(f"Error getting available policy types: {str(e)}")
            return []
    
    def validate_policy_creation_prerequisites(self, policy_document_name):
        """
        Validate that all prerequisites are met for policy creation
        """
        try:
            # Ensure policy_document_name is a string
            policy_document_name = str(policy_document_name)
            policy_doc = frappe.get_doc("Policy Document", policy_document_name)
            
            # Check if fields are extracted
            if not policy_doc.extracted_fields:
                return {
                    "valid": False,
                    "error": "No extracted fields found. Please extract fields first."
                }
            
            # Check if policy type is set
            if not policy_doc.policy_type:
                return {
                    "valid": False,
                    "error": "Policy type is not set. Please set the policy type first."
                }
            
            # Check if policy already exists
            if policy_doc.policy_type.lower() == "motor" and policy_doc.motor_policy:
                return {
                    "valid": False,
                    "error": "Motor policy already exists for this document."
                }
            elif policy_doc.policy_type.lower() == "health" and policy_doc.health_policy:
                return {
                    "valid": False,
                    "error": "Health policy already exists for this document."
                }
            
            return {"valid": True}
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }
