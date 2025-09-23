import frappe
import ast
import json
from frappe.utils import getdate, cstr, flt, cint
from frappe import _

class PolicyCreationService:
    def __init__(self):
        self._last_used_prompt = None
    
    def create_policy_record(self, policy_document_name, policy_type):
        """
        Create a policy record (Motor/Health) from Policy Document using dynamic field mapping
        """
        try:
            # Get Policy Document
            policy_doc = frappe.get_doc("Policy Document", policy_document_name)
            
            if not policy_doc.extracted_fields:
                return {
                    "success": False,
                    "error": "No extracted fields found. Please extract fields first."
                }
            
            # Get field mapping from Policy Reader Settings
            field_mapping = self.get_field_mapping_for_policy_type(policy_type)
            
            if not field_mapping:
                return {
                    "success": False,
                    "error": f"No field mapping found for {policy_type}. Please refresh field mappings in Policy Reader Settings."
                }
            
            # Parse extracted data
            extracted_data = frappe.parse_json(policy_doc.extracted_fields)
            parsed_data = self.parse_nested_extracted_data(extracted_data)
            
            # Create policy document
            if policy_type.lower() == "motor":
                policy_record = frappe.new_doc("Motor Policy")
            elif policy_type.lower() == "health":
                policy_record = frappe.new_doc("Health Policy")
            else:
                return {
                    "success": False,
                    "error": f"Unsupported policy type: {policy_type}"
                }
            
            # Set document link
            policy_record.policy_document = policy_doc.name
            policy_record.policy_file = policy_doc.policy_file
            
            # Dynamic field mapping
            mapping_results = self.map_fields_dynamically(
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
            frappe.log_error(f"Policy creation failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def parse_nested_extracted_data(self, extracted_data):
        """
        Parse the extracted JSON structure - handles both flat and nested formats
        """
        parsed_data = {}
        
        frappe.logger().info(f"Parsing extracted data structure: {type(extracted_data)}")
        frappe.logger().info(f"Sample data keys: {list(extracted_data.keys())[:10] if isinstance(extracted_data, dict) else 'Not a dict'}")
        
        # Handle flat JSON structure (direct field->value mapping)
        if self._is_flat_structure(extracted_data):
            frappe.logger().info("Detected flat JSON structure")
            for field_name, field_value in extracted_data.items():
                parsed_data[field_name] = field_value
                frappe.logger().info(f"Parsed flat field: {field_name} = {field_value}")
        else:
            # Handle nested JSON structure (category->fields mapping)
            frappe.logger().info("Detected nested JSON structure")
            for category_name, category_data in extracted_data.items():
                try:
                    category_dict = None
                    
                    # Multiple parsing strategies for robustness
                    if isinstance(category_data, str):
                        # Strategy 1: Try ast.literal_eval (handles {'key': 'value'} format)
                        try:
                            category_dict = ast.literal_eval(category_data)
                            frappe.logger().info(f"Parsed {category_name} using ast.literal_eval")
                        except:
                            # Strategy 2: Try json.loads (handles {"key": "value"} format)
                            try:
                                category_dict = frappe.parse_json(category_data)
                                frappe.logger().info(f"Parsed {category_name} using json.loads")
                            except:
                                # Strategy 3: Try cleaning and parsing again
                                try:
                                    cleaned = category_data.strip().strip("'\"")
                                    category_dict = ast.literal_eval(cleaned)
                                    frappe.logger().info(f"Parsed {category_name} after cleaning")
                                except:
                                    frappe.logger().error(f"Failed to parse {category_name}: {category_data[:100]}...")
                                    continue
                    elif isinstance(category_data, dict):
                        category_dict = category_data
                        frappe.logger().info(f"Category {category_name} already a dict")
                    else:
                        frappe.logger().warning(f"Unexpected data type for {category_name}: {type(category_data)}")
                        continue
                    
                    # Add all fields from this category to parsed_data
                    if category_dict:
                        for field_name, field_value in category_dict.items():
                            parsed_data[field_name] = field_value
                            frappe.logger().info(f"Parsed nested field: {field_name} = {field_value}")
                        frappe.logger().info(f"Successfully flattened {len(category_dict)} fields from {category_name}")
                        
                except Exception as e:
                    frappe.logger().error(f"Error parsing category {category_name}: {str(e)}")
                    continue
        
        frappe.logger().info(f"Parsed {len(parsed_data)} total fields")
        return parsed_data
    
    def _is_flat_structure(self, data):
        """
        Check if the extracted data is a flat structure (field->value) 
        vs nested structure (category->fields)
        """
        if not isinstance(data, dict):
            return False
        
        # Sample a few values to determine structure
        sample_values = list(data.values())[:5]
        
        # Check for string-encoded dictionaries (nested structure indicators)
        nested_indicators = 0
        for value in sample_values:
            if isinstance(value, str):
                # Check if it looks like a serialized dictionary
                stripped = value.strip()
                if (stripped.startswith('{') and stripped.endswith('}')) or \
                   (stripped.startswith("'{") and stripped.endswith("'}")) or \
                   (stripped.startswith('"{') and stripped.endswith('}"')):
                    nested_indicators += 1
        
        # If we have nested indicators, it's definitely nested
        if nested_indicators > 0:
            frappe.logger().info(f"Detected nested structure: {nested_indicators} string-encoded dictionaries found")
            return False
        
        # If most values are simple types, it's likely flat
        simple_types = (str, int, float, type(None), bool)
        simple_count = sum(1 for v in sample_values if isinstance(v, simple_types))
        
        # If 80% or more are simple types, consider it flat
        is_flat = simple_count >= len(sample_values) * 0.8
        frappe.logger().info(f"Structure detection: {simple_count}/{len(sample_values)} simple types, is_flat: {is_flat}")
        return is_flat
    
    def map_fields_dynamically(self, parsed_data, field_mapping, policy_record, policy_type):
        """
        Dynamically map fields using the field mapping from Policy Reader Settings
        """
        mapped_count = 0
        unmapped_fields = []
        
        frappe.logger().info(f"=== FIELD MAPPING DEBUG ===")
        frappe.logger().info(f"Parsed data keys: {list(parsed_data.keys())}")
        frappe.logger().info(f"Field mapping keys: {list(field_mapping.keys())}")
        frappe.logger().info(f"Policy record doctype: {policy_record.doctype}")
        
        for extracted_field_name, policy_field_name in field_mapping.items():
            value = parsed_data.get(extracted_field_name)
            frappe.logger().info(f"Checking field '{extracted_field_name}' -> '{policy_field_name}': value = {value}")
            
            if value is not None and str(value).strip():
                try:
                    # Convert value to appropriate type
                    converted_value = self.convert_field_value(policy_field_name, value, policy_record.doctype)
                    frappe.logger().info(f"Converted value for {policy_field_name}: {converted_value} (type: {type(converted_value)})")
                    
                    if converted_value is not None:
                        setattr(policy_record, policy_field_name, converted_value)
                        mapped_count += 1
                        frappe.logger().info(f"✓ Mapped {extracted_field_name} -> {policy_field_name}: {converted_value}")
                    else:
                        frappe.logger().warning(f"✗ Converted value is None for {extracted_field_name}")
                        unmapped_fields.append(extracted_field_name)
                except Exception as e:
                    frappe.logger().error(f"✗ Error mapping {extracted_field_name}: {str(e)}")
                    unmapped_fields.append(extracted_field_name)
            else:
                frappe.logger().info(f"✗ Field {extracted_field_name} has no value or empty value")
                unmapped_fields.append(extracted_field_name)
        
        # Check for extracted fields that don't have mappings
        unmapped_extracted_fields = [key for key in parsed_data.keys() if key not in field_mapping]
        if unmapped_extracted_fields:
            frappe.logger().info(f"Extracted fields without mappings: {unmapped_extracted_fields}")
        
        frappe.logger().info(f"=== FIELD MAPPING SUMMARY ===")
        frappe.logger().info(f"Mapped: {mapped_count}, Unmapped: {len(unmapped_fields)}")
        frappe.logger().info(f"Unmapped fields: {unmapped_fields}")
        
        return {
            "mapped_count": mapped_count,
            "unmapped_fields": unmapped_fields
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
                return getdate(value)
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
    
    def get_field_mapping_for_policy_type(self, policy_type):
        """
        Get field mapping from Policy Reader Settings cache
        """
        try:
            settings = frappe.get_single("Policy Reader Settings")
            return settings.get_cached_field_mapping(policy_type)
        except Exception as e:
            frappe.log_error(f"Error getting field mapping for {policy_type}: {str(e)}")
            return {}
    
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
