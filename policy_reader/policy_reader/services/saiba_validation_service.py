# Copyright (c) 2026, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, flt, getdate


class SaibaValidationService:
    """Service for validating policies before SAIBA sync"""

    # Category display order for consistent UI
    CATEGORY_ORDER = [
        "Policy Information",
        "Customer & Insurer",
        "Vehicle Information",
        "Insured Persons",
        "Financial",
        "Dates"
    ]

    def __init__(self):
        self._settings = None

    @property
    def settings(self):
        """Lazy load settings"""
        if self._settings is None:
            self._settings = frappe.get_single("SAIBA Validation Settings")
        return self._settings

    def is_enabled(self):
        """Check if validation feature is enabled"""
        try:
            return bool(self.settings.enabled)
        except Exception:
            return False

    def get_validation_rules(self, policy_type):
        """Fetch rules from motor_validation_rules or health_validation_rules table"""
        if not self.is_enabled():
            return []

        policy_type_lower = (policy_type or "").lower()

        if policy_type_lower == "motor":
            return self.settings.motor_validation_rules or []
        elif policy_type_lower == "health":
            return self.settings.health_validation_rules or []
        else:
            frappe.log_error(f"Unknown policy type: {policy_type}", "SAIBA Validation Error")
            return []

    def validate_field(self, value, validation_type):
        """
        Validate a single field value against the specified validation type.

        Returns tuple: (is_valid, error_message)
        """
        if validation_type == "string":
            # Non-empty string required
            if value is None or str(value).strip() == "":
                return False, "Required"
            return True, None

        elif validation_type == "integer":
            # Any integer (including 0) is valid, but must be set
            if value is None or value == "":
                return False, "Required"
            try:
                cint(value)
                return True, None
            except (ValueError, TypeError):
                return False, "Must be a number"

        elif validation_type == "integer_nonzero":
            # Non-zero integer required
            if value is None or value == "":
                return False, "Required"
            try:
                int_val = cint(value)
                if int_val == 0:
                    return False, "Must be non-zero"
                return True, None
            except (ValueError, TypeError):
                return False, "Must be a number"

        elif validation_type == "integer_positive":
            # Positive integer required (> 0)
            if value is None or value == "":
                return False, "Required"
            try:
                int_val = cint(value)
                if int_val <= 0:
                    return False, "Must be greater than 0"
                return True, None
            except (ValueError, TypeError):
                return False, "Must be a number"

        elif validation_type == "date":
            # Valid date required
            if value is None or value == "":
                return False, "Required"
            try:
                getdate(value)
                return True, None
            except Exception:
                return False, "Invalid date"

        elif validation_type == "yes_no":
            # Must be Yes or No
            if value is None or str(value).strip() == "":
                return False, "Required"
            if str(value).upper() not in ["YES", "NO"]:
                return False, "Must be Yes or No"
            return True, None

        elif validation_type == "new_renew":
            # Must be New or Renew
            if value is None or str(value).strip() == "":
                return False, "Required"
            if str(value).lower() not in ["new", "renew"]:
                return False, "Must be New or Renew"
            return True, None

        elif validation_type == "gcv_pcv_misc":
            # Must be GCV, PCV, or Misc
            if value is None or str(value).strip() == "":
                return False, "Required"
            if str(value).upper() not in ["GCV", "PCV", "MISC", "MISC.", "GSV"]:
                return False, "Must be GCV, PCV, or Misc"
            return True, None

        # Unknown validation type - treat as valid
        return True, None

    def format_display_value(self, value, validation_type):
        """Format a value for display in the validation modal"""
        if value is None or value == "":
            return "Not Set"

        if validation_type == "date":
            try:
                date_val = getdate(value)
                return date_val.strftime("%d-%m-%Y")
            except Exception:
                return str(value)

        if validation_type in ["integer", "integer_nonzero", "integer_positive"]:
            try:
                return str(cint(value))
            except Exception:
                return str(value)

        return str(value)

    def validate_policy(self, policy_doc, policy_type):
        """
        Validate all fields for a policy document.

        Returns dict with categorized results for frontend display.
        """
        rules = self.get_validation_rules(policy_type)

        if not rules:
            return {
                "success": False,
                "error": f"No validation rules found for {policy_type} policy"
            }

        # Group fields by category
        categories = {}
        valid_count = 0
        invalid_count = 0

        for rule in rules:
            # Skip non-required fields for validation count
            if not rule.is_required:
                continue

            # Get field value from policy document
            value = getattr(policy_doc, rule.doctype_field, None)

            # Validate field
            is_valid, error_message = self.validate_field(value, rule.validation_type)

            # Format display value
            display_value = self.format_display_value(value, rule.validation_type)

            # Add to category
            category_name = rule.category
            if category_name not in categories:
                categories[category_name] = []

            categories[category_name].append({
                "label": rule.label,
                "saiba_field": rule.saiba_field,
                "doctype_field": rule.doctype_field,
                "value": display_value,
                "is_valid": is_valid,
                "error": error_message
            })

            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1

        # Convert categories dict to ordered list
        categories_list = []
        for cat_name in self.CATEGORY_ORDER:
            if cat_name in categories:
                categories_list.append({
                    "name": cat_name,
                    "fields": categories[cat_name]
                })

        # Add any categories not in the predefined order
        for cat_name, fields in categories.items():
            if cat_name not in self.CATEGORY_ORDER:
                categories_list.append({
                    "name": cat_name,
                    "fields": fields
                })

        total_required = valid_count + invalid_count

        return {
            "success": True,
            "policy_type": policy_type,
            "policy_name": policy_doc.name,
            "summary": {
                "total_required": total_required,
                "valid": valid_count,
                "invalid": invalid_count,
                "ready_to_sync": invalid_count == 0
            },
            "categories": categories_list
        }

    def validate_motor_policy(self, policy_name):
        """Validate a Motor Policy for SAIBA sync readiness"""
        try:
            if not self.is_enabled():
                return {
                    "success": False,
                    "error": "SAIBA validation is not enabled"
                }

            if not frappe.db.exists("Motor Policy", policy_name):
                return {
                    "success": False,
                    "error": f"Motor Policy '{policy_name}' not found"
                }

            policy_doc = frappe.get_doc("Motor Policy", policy_name)
            return self.validate_policy(policy_doc, "Motor")

        except Exception as e:
            frappe.log_error(f"Motor Policy validation error: {str(e)}", "SAIBA Validation Error")
            return {
                "success": False,
                "error": str(e)
            }

    def validate_health_policy(self, policy_name):
        """Validate a Health Policy for SAIBA sync readiness"""
        try:
            if not self.is_enabled():
                return {
                    "success": False,
                    "error": "SAIBA validation is not enabled"
                }

            if not frappe.db.exists("Health Policy", policy_name):
                return {
                    "success": False,
                    "error": f"Health Policy '{policy_name}' not found"
                }

            policy_doc = frappe.get_doc("Health Policy", policy_name)
            return self.validate_policy(policy_doc, "Health")

        except Exception as e:
            frappe.log_error(f"Health Policy validation error: {str(e)}", "SAIBA Validation Error")
            return {
                "success": False,
                "error": str(e)
            }


# Whitelisted API methods
@frappe.whitelist()
def validate_motor_policy(policy_name):
    """Whitelisted endpoint for Motor Policy validation"""
    service = SaibaValidationService()
    return service.validate_motor_policy(policy_name)


@frappe.whitelist()
def validate_health_policy(policy_name):
    """Whitelisted endpoint for Health Policy validation"""
    service = SaibaValidationService()
    return service.validate_health_policy(policy_name)


@frappe.whitelist()
def is_validation_enabled():
    """Check if SAIBA validation feature is enabled"""
    service = SaibaValidationService()
    return {"enabled": service.is_enabled()}
