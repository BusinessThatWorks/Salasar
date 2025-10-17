# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from policy_reader.policy_reader.services.common_service import CommonService


class FieldMappingService:
    """Service for dynamic field mapping between extracted data and policy records"""
    
    def __init__(self):
        self._last_used_prompt = None
    
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
                    converted_value = self._convert_field_value(policy_field_name, raw_value, policy_record.doctype)
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
        frappe.logger().info(f"Total fields processed: {len(parsed_data)}")
        frappe.logger().info(f"Successfully mapped: {mapped_count}")
        frappe.logger().info(f"Unmapped fields: {len(unmapped_fields)}")
        frappe.logger().info(f"Unmapped: {unmapped_fields}")
        
        return {
            "mapped_count": mapped_count,
            "unmapped_fields": unmapped_fields,
            "suggestions": suggestions
        }
    
    def _build_normalized_mapping(self, field_mapping):
        """Build normalized mapping for robust key matching"""
        normalized = {}
        
        for alias, canonical in field_mapping.items():
            # Add original key
            normalized[alias] = canonical
            
            # Add normalized key
            normalized_key = self._normalize_key(alias)
            if normalized_key != alias:
                normalized[normalized_key] = canonical
        
        return normalized
    
    def _normalize_key(self, text):
        """Normalize key for consistent matching"""
        if not text:
            return ""
        
        # Convert to lowercase and replace common separators
        normalized = str(text).lower().strip()
        normalized = normalized.replace(' ', '_').replace('-', '_').replace('.', '_')
        normalized = normalized.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
        
        return normalized
    
    def _convert_field_value(self, field_name, value, doctype):
        """Convert field value based on Frappe field metadata"""
        try:
            # Get field metadata
            field_meta = frappe.get_meta(doctype).get_field(field_name)
            if not field_meta:
                return value
            
            # Handle different field types
            if field_meta.fieldtype == "Date":
                return self._convert_to_date(value)
            elif field_meta.fieldtype == "Datetime":
                return self._convert_to_datetime(value)
            elif field_meta.fieldtype == "Float":
                return self._convert_to_float(value)
            elif field_meta.fieldtype == "Int":
                return self._convert_to_int(value)
            elif field_meta.fieldtype == "Check":
                return self._convert_to_check(value)
            elif field_meta.fieldtype == "Select":
                return self._convert_to_select(value, field_meta.options, field_name=field_name)
            else:
                # Default: return as string
                return str(value).strip() if value else None
                
        except Exception as e:
            frappe.logger().error(f"Error converting field {field_name}: {str(e)}")
            return str(value).strip() if value else None
    
    def _convert_to_date(self, value):
        """Convert value to date format"""
        if not value:
            return None
        
        try:
            from frappe.utils import getdate
            from datetime import datetime
            
            # Handle DD/MM/YYYY format (common in Indian documents)
            if isinstance(value, str) and '/' in value:
                # Try to parse DD/MM/YYYY format
                try:
                    # Split by / and check if it's DD/MM/YYYY
                    parts = value.split('/')
                    if len(parts) == 3:
                        day, month, year = parts
                        # If day > 12, it's likely DD/MM/YYYY
                        if int(day) > 12:
                            # Convert DD/MM/YYYY to YYYY-MM-DD
                            date_obj = datetime(int(year), int(month), int(day))
                            return date_obj.date()
                        else:
                            # Could be MM/DD/YYYY, try both formats
                            try:
                                date_obj = datetime(int(year), int(month), int(day))
                                return date_obj.date()
                            except ValueError:
                                # Try MM/DD/YYYY
                                date_obj = datetime(int(year), int(day), int(month))
                                return date_obj.date()
                except (ValueError, IndexError):
                    pass
            
            # Fallback to Frappe's getdate
            return getdate(value)
        except (ValueError, TypeError, AttributeError):
            return None
    
    def _convert_to_datetime(self, value):
        """Convert value to datetime format"""
        if not value:
            return None
        
        try:
            from frappe.utils import get_datetime
            from datetime import datetime
            
            # Handle DD/MM/YYYY format (common in Indian documents)
            if isinstance(value, str) and '/' in value:
                # Try to parse DD/MM/YYYY format
                try:
                    parts = value.split('/')
                    if len(parts) == 3:
                        day, month, year = parts
                        # Convert DD/MM/YYYY to YYYY-MM-DD HH:MM:SS
                        datetime_str = f"{year}-{month.zfill(2)}-{day.zfill(2)} 00:00:00"
                        return get_datetime(datetime_str)
                except (ValueError, IndexError):
                    pass
            
            # Fallback to Frappe's get_datetime
            return get_datetime(value)
        except (ValueError, TypeError, AttributeError):
            return None
    
    def _convert_to_float(self, value):
        """Convert value to float"""
        if not value:
            return None
        
        try:
            # Remove currency symbols and commas
            cleaned = str(value).replace(',', '').replace('₹', '').replace('$', '').replace('€', '').strip()
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    def _convert_to_int(self, value):
        """Convert value to integer"""
        if not value:
            return None
        
        try:
            # Remove non-numeric characters
            cleaned = ''.join(filter(str.isdigit, str(value)))
            return int(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None
    
    def _convert_to_check(self, value):
        """Convert value to checkbox (0 or 1)"""
        if not value:
            return 0
        
        value_str = str(value).lower().strip()
        if value_str in ['yes', 'true', '1', 'y']:
            return 1
        elif value_str in ['no', 'false', '0', 'n']:
            return 0
        else:
            return 0
    
    def _convert_to_select(self, value, options, field_name=None):
        """Convert value to select option with default value handling"""
        if not value or not options:
            return None

        value_str = str(value).strip()
        options_list = [opt.strip() for opt in options.split('\n') if opt.strip()]

        # Try exact match first
        if value_str in options_list:
            return value_str

        # Try case-insensitive match
        for option in options_list:
            if option.lower() == value_str.lower():
                return option

        # Try partial match
        for option in options_list:
            if value_str.lower() in option.lower() or option.lower() in value_str.lower():
                return option

        # No match found - check for field-specific defaults
        default_value = self._get_select_field_default(field_name)
        if default_value:
            frappe.logger().warning(f"Select field '{field_name}' value '{value_str}' not found in options. Using default: '{default_value}'")
            return default_value

        # If no default defined, return None to leave field empty
        frappe.logger().warning(f"Select field '{field_name}' value '{value_str}' not found in options. Leaving empty.")
        return None

    def _get_select_field_default(self, field_name):
        """
        Get default value for select fields when extracted value doesn't match options

        Returns None if no default should be applied (field will be left empty)
        Returns a string value if a default should be used
        """
        if not field_name:
            return None

        # Define defaults for specific fields (case-insensitive)
        defaults = {
            'customer_title': 'Mr.',
            'title': 'Mr.',
            # Add more field defaults here as needed
        }

        # Check by fieldname (case-insensitive)
        field_key = field_name.lower() if field_name else None
        if field_key and field_key in defaults:
            return defaults[field_key]

        return None
    
    def _find_best_match(self, key, candidates):
        """Find best matching candidates for a key"""
        if not key or not candidates:
            return []
        
        matches = []
        key_lower = key.lower()
        
        for candidate in candidates:
            candidate_lower = candidate.lower()
            
            # Exact match
            if key_lower == candidate_lower:
                matches.append((candidate, 100))
            # Contains match
            elif key_lower in candidate_lower or candidate_lower in key_lower:
                matches.append((candidate, 80))
            # Similar characters
            elif self._calculate_similarity(key_lower, candidate_lower) > 0.6:
                matches.append((candidate, 60))
        
        # Sort by score and return top 3
        matches.sort(key=lambda x: x[1], reverse=True)
        return [match[0] for match in matches[:3]]
    
    def _calculate_similarity(self, str1, str2):
        """Calculate similarity between two strings"""
        if not str1 or not str2:
            return 0
        
        # Simple character-based similarity
        common_chars = set(str1) & set(str2)
        total_chars = set(str1) | set(str2)
        
        if not total_chars:
            return 0
        
        return len(common_chars) / len(total_chars)
