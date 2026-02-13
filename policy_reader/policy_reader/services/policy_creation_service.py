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

            # Populate customer data from Policy Document if available
            self._populate_customer_fields(policy_record, policy_doc)

            # Copy documents from Policy Document
            self._copy_document_fields(policy_record, policy_doc)

            # Copy business information from Policy Document
            self._copy_business_info_fields(policy_record, policy_doc)

            # Copy checklist fields from Policy Document
            self._copy_checklist_fields(policy_record, policy_doc)

            # Define fields that should not be overwritten by AI extraction
            protected_fields = self._get_protected_fields()

            # Dynamic field mapping
            field_mapping_service = FieldMappingService()
            mapping_results = field_mapping_service.map_fields_dynamically(
                parsed_data, field_mapping, policy_record, policy_type, protected_fields
            )

            # Auto-populate processor information based on logged-in user
            self._populate_processor_fields(policy_record)

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

    def _get_protected_fields(self):
        """
        Get list of fields that should not be overwritten by AI extraction

        These are fields that were manually selected in Policy Document and should
        always take precedence over AI-extracted values
        """
        return [
            # Customer fields from Policy Document
            'customer_code',
            'customer_name',
            'customer_group',

            # Insurer fields from Policy Document
            'insurance_company_branch',
            'insurer_name',
            'insurer_city',
            'insurer_branch',
            'insurer_branch_code',

            # Checklist fields from Policy Document
            'department',
            'policy_type',
            'coverage_type',
            'old_control_number',
            'branch_code',
            'biz_type',
            'customer_vertical',
            'rm_code',
            'csc_code',
            'tc_code',
            'ref_code',
            'customer_pan',
            'customer_gst',
            'category',
            'portability',
        ]

    def _get_current_user_employee_info(self):
        """Get Insurance Employee record for the logged-in user"""
        try:
            current_user = frappe.session.user

            frappe.logger().info(f"Checking employee info for user: {current_user}")

            # Skip for Guest only (Administrator might have an employee record)
            if current_user == "Guest":
                frappe.logger().info("Skipping Guest user")
                return None

            # Query Insurance Employee where user matches
            employee = frappe.db.get_value(
                "Insurance Employee",
                {"user": current_user},
                ["name", "employee_name", "employee_code", "employee_type"],
                as_dict=True
            )

            if employee:
                frappe.logger().info(f"Found employee info for user {current_user}: {employee}")
                return employee
            else:
                frappe.logger().warning(f"No Insurance Employee record found for user {current_user}")
                return None

        except Exception as e:
            frappe.logger().error(f"Error fetching employee info for user {frappe.session.user}: {str(e)}")
            return None

    def _populate_processor_fields(self, policy_record):
        """Auto-populate processor fields via Insurance Employee link"""
        try:
            employee_info = self._get_current_user_employee_info()

            if not employee_info:
                frappe.logger().info("No employee info found, skipping processor field population")
                return

            # Set the link field directly - Frappe will auto-fetch all related fields
            # (employee_name, employee_code, employee_type, branch_name)
            policy_record.insurance_employee = employee_info.get("name")
            frappe.logger().info(f"Auto-populated insurance_employee link: {employee_info.get('name')}")
            frappe.logger().info(f"Frappe will auto-fetch: name, code, type, branch name")
            frappe.logger().info(f"Successfully set processor link field for {policy_record.doctype}")

        except Exception as e:
            frappe.logger().error(f"Error populating processor fields: {str(e)}")
            frappe.log_error(f"Failed to populate processor fields: {str(e)}", "Processor Field Population")
            # Don't throw - this is a non-critical operation

    def _populate_customer_fields(self, policy_record, policy_doc):
        """Populate customer information from Policy Document to policy record"""
        try:
            if not policy_doc.customer_code:
                frappe.logger().info("No customer selected in Policy Document, skipping customer field population")
                return

            # Copy customer code (just the text value in Motor/Health Policy)
            policy_record.customer_code = policy_doc.customer_code
            frappe.logger().info(f"Copied customer_code: {policy_doc.customer_code}")

            # Copy customer name from Policy Document's auto-fetched field
            if policy_doc.customer_name:
                policy_record.customer_name = policy_doc.customer_name
                frappe.logger().info(f"Copied customer_name: {policy_doc.customer_name}")

            # Copy customer group from Policy Document's auto-fetched field
            # Note: Policy Document uses 'customer_group_name', Motor/Health Policy uses 'customer_group'
            if policy_doc.customer_group_name:
                policy_record.customer_group = policy_doc.customer_group_name
                frappe.logger().info(f"Copied customer_group: {policy_doc.customer_group_name}")

            frappe.logger().info(f"Successfully copied customer fields from Policy Document for {policy_record.doctype}")

        except Exception as e:
            frappe.logger().error(f"Error populating customer fields: {str(e)}")
            frappe.log_error(f"Failed to populate customer fields: {str(e)}", "Customer Field Population")
            # Don't throw - this is a non-critical operation

    def _copy_document_fields(self, policy_record, policy_doc):
        """Copy document attachment fields from Policy Document to policy record"""
        try:
            document_fields = [
                'final_quote_renewal_notice',
                'quote_comparison',
                'mandate_doc',
                'kyc_doc',
                'proposal_form',
                'portability_form',
                'policy_copy_doc',
                'rc_copy',
                'passport_copy',
                'payment_details_doc'
            ]

            copied_count = 0
            for field in document_fields:
                if hasattr(policy_doc, field) and getattr(policy_doc, field):
                    setattr(policy_record, field, getattr(policy_doc, field))
                    copied_count += 1
                    frappe.logger().info(f"Copied document field: {field}")

            frappe.logger().info(f"Successfully copied {copied_count} document fields from Policy Document")

        except Exception as e:
            frappe.logger().error(f"Error copying document fields: {str(e)}")
            frappe.log_error(f"Failed to copy document fields: {str(e)}", "Document Field Copy")
            # Don't throw - this is a non-critical operation

    def _copy_checklist_fields(self, policy_record, policy_doc):
        """Copy checklist fields from Policy Document to policy record"""
        try:
            checklist_mapping = {
                "checklist_department": "department",
                "checklist_policy_type": "policy_type",
                "checklist_coverage_type": "coverage_type",
                "checklist_old_control_number": "old_control_number",
                "checklist_branch_code": "branch_code",
                "checklist_biz_type": "biz_type",
                "checklist_customer_vertical": "customer_vertical",
                "checklist_rm_code": "rm_code",
                "checklist_csc_code": "csc_code",
                "checklist_tc_code": "tc_code",
                "checklist_ref_code": "ref_code",
                "checklist_customer_pan": "customer_pan",
                "checklist_customer_gst": "customer_gst",
                "checklist_category": "category",
                "checklist_portability": "portability",
            }

            copied_count = 0
            for source_field, target_field in checklist_mapping.items():
                value = getattr(policy_doc, source_field, None)
                if value:
                    setattr(policy_record, target_field, value)
                    copied_count += 1
                    frappe.logger().info(f"Copied checklist field: {source_field} -> {target_field} = {value}")

            frappe.logger().info(f"Successfully copied {copied_count} checklist fields from Policy Document")

        except Exception as e:
            frappe.logger().error(f"Error copying checklist fields: {str(e)}")
            frappe.log_error(f"Failed to copy checklist fields: {str(e)}", "Checklist Field Copy")
            # Don't throw - this is a non-critical operation

    def _copy_business_info_fields(self, policy_record, policy_doc):
        """Copy business information fields from Policy Document to policy record"""
        try:
            if not policy_doc.insurance_company_branch:
                frappe.logger().info("No insurance company branch selected in Policy Document, skipping business info population")
                return

            # Copy the insurance company branch link field
            policy_record.insurance_company_branch = policy_doc.insurance_company_branch
            frappe.logger().info(f"Copied insurance_company_branch: {policy_doc.insurance_company_branch}")

            # Copy auto-fetched insurer fields from Policy Document
            if policy_doc.insurer_name:
                policy_record.insurer_name = policy_doc.insurer_name
                frappe.logger().info(f"Copied insurer_name: {policy_doc.insurer_name}")

            if policy_doc.insurer_city:
                policy_record.insurer_city = policy_doc.insurer_city
                frappe.logger().info(f"Copied insurer_city: {policy_doc.insurer_city}")

            if policy_doc.insurer_branch:
                policy_record.insurer_branch = policy_doc.insurer_branch
                frappe.logger().info(f"Copied insurer_branch: {policy_doc.insurer_branch}")

            if policy_doc.insurer_branch_code:
                policy_record.insurer_branch_code = policy_doc.insurer_branch_code
                frappe.logger().info(f"Copied insurer_branch_code: {policy_doc.insurer_branch_code}")

            frappe.logger().info(f"Successfully copied business info fields from Policy Document for {policy_record.doctype}")

        except Exception as e:
            frappe.logger().error(f"Error copying business info fields: {str(e)}")
            frappe.log_error(f"Failed to copy business info fields: {str(e)}", "Business Info Copy")
            # Don't throw - this is a non-critical operation

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
                return self.normalize_select_value(value, field.options, field_name=field_name, field_label=field.label)
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
    
    def _get_select_field_default(self, field_name, field_label):
        """
        Get default value for select fields when extracted value doesn't match options

        Returns None if no default should be applied (field will be left empty)
        Returns a string value if a default should be used
        """
        # Define defaults for specific fields
        # Key can be fieldname or label (lowercase)
        defaults = {
            # Customer Title defaults to "Mr." for unrecognized values
            'customer_title': 'Mr.',
            'title': 'Mr.',

            # Add more field defaults here as needed
            # 'field_name': 'default_value',
        }

        # Check by fieldname first, then by label
        field_key = field_name.lower() if field_name else None
        label_key = field_label.lower() if field_label else None

        if field_key and field_key in defaults:
            return defaults[field_key]
        if label_key and label_key in defaults:
            return defaults[label_key]

        return None

    def normalize_select_value(self, value, options, field_name=None, field_label=None):
        """
        Normalize select field value to match available options
        If no match found, apply field-specific defaults
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

        # No match found - check if we should apply a default
        default_value = self._get_select_field_default(field_name, field_label)
        if default_value:
            frappe.logger().warning(f"Select field '{field_name or field_label}' value '{value}' not found in options. Using default: '{default_value}'")
            return default_value

        # If no default defined, return None to leave field empty
        frappe.logger().warning(f"Select field '{field_name or field_label}' value '{value}' not found in options. Leaving empty.")
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
