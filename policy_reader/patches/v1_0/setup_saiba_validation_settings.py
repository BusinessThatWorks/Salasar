# Copyright (c) 2026, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """Setup SAIBA Validation Settings with default validation rules"""

    # Check if settings already exist with rules populated
    if frappe.db.exists("SAIBA Validation Settings", "SAIBA Validation Settings"):
        settings = frappe.get_single("SAIBA Validation Settings")
        if settings.motor_validation_rules or settings.health_validation_rules:
            frappe.logger().info("SAIBA Validation Settings already has rules, skipping setup")
            return

    # Get or create settings
    settings = frappe.get_single("SAIBA Validation Settings")

    # Define Motor Policy validation rules
    motor_rules = [
        {
            "saiba_field": "custCode",
            "doctype_field": "customer_code",
            "label": "Customer Code",
            "category": "Customer & Insurer",
            "validation_type": "integer_nonzero",
            "is_required": 1
        },
        {
            "saiba_field": "insBranchCode",
            "doctype_field": "insurer_branch_code",
            "label": "Insurer Branch Code",
            "category": "Customer & Insurer",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "policyNo",
            "doctype_field": "policy_no",
            "label": "Policy Number",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "policyType",
            "doctype_field": "policy_type",
            "label": "Policy Type",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "vehicleNo",
            "doctype_field": "vehicle_no",
            "label": "Vehicle Number",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "sumInsured",
            "doctype_field": "sum_insured",
            "label": "Sum Insured",
            "category": "Financial",
            "validation_type": "integer_positive",
            "is_required": 1
        },
        {
            "saiba_field": "issuenceDate",
            "doctype_field": "policy_issuance_date",
            "label": "Policy Issuance Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "startDate",
            "doctype_field": "policy_start_date",
            "label": "Policy Start Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "expiryDate",
            "doctype_field": "policy_expiry_date",
            "label": "Policy Expiry Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        }
    ]

    # Define Health Policy validation rules
    health_rules = [
        {
            "saiba_field": "custCode",
            "doctype_field": "customer_code",
            "label": "Customer Code",
            "category": "Customer & Insurer",
            "validation_type": "integer_nonzero",
            "is_required": 1
        },
        {
            "saiba_field": "policyNo",
            "doctype_field": "policy_no",
            "label": "Policy Number",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "policyType",
            "doctype_field": "policy_type",
            "label": "Policy Type",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "sumInsured",
            "doctype_field": "sum_insured",
            "label": "Sum Insured",
            "category": "Financial",
            "validation_type": "integer_positive",
            "is_required": 1
        },
        {
            "saiba_field": "issuenceDate",
            "doctype_field": "policy_issuance_date",
            "label": "Policy Issuance Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "startDate",
            "doctype_field": "policy_start_date",
            "label": "Policy Start Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "expiryDate",
            "doctype_field": "policy_expiry_date",
            "label": "Policy Expiry Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "insured1Name",
            "doctype_field": "insured_1_name",
            "label": "Primary Insured Name",
            "category": "Insured Persons",
            "validation_type": "string",
            "is_required": 1
        }
    ]

    # Add Motor rules
    for rule_data in motor_rules:
        settings.append("motor_validation_rules", rule_data)

    # Add Health rules
    for rule_data in health_rules:
        settings.append("health_validation_rules", rule_data)

    # Enable by default
    settings.enabled = 1

    # Save settings
    settings.save()
    frappe.db.commit()

    frappe.logger().info(
        f"SAIBA Validation Settings created with {len(motor_rules)} Motor rules and {len(health_rules)} Health rules"
    )
