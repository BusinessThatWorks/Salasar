# Copyright (c) 2026, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """Update SAIBA validation rules per Feb 2026 SAIBA API specification.

    Motor Policy: 29 mandatory fields
    Health Policy: 25 mandatory fields
    """

    # Check if SAIBA Validation Settings exists
    if not frappe.db.exists("SAIBA Validation Settings", "SAIBA Validation Settings"):
        frappe.logger().info("SAIBA Validation Settings not found, skipping validation rules update")
        return

    settings = frappe.get_single("SAIBA Validation Settings")

    # Clear existing validation rules
    settings.motor_validation_rules = []
    settings.health_validation_rules = []

    # =========================================================================
    # Motor Policy - 29 Mandatory Fields (Feb 2026 SAIBA API Spec)
    # =========================================================================
    motor_rules = [
        # Customer & Insurer (2 fields)
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

        # Policy Information (6 fields)
        {
            "saiba_field": "posPolicy",
            "doctype_field": "pos_misp_ref",
            "label": "POS Policy",
            "category": "Policy Information",
            "validation_type": "yes_no",
            "is_required": 1
        },
        {
            "saiba_field": "bizType",
            "doctype_field": "biz_type",
            "label": "Business Type",
            "category": "Policy Information",
            "validation_type": "new_renew",
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
            "saiba_field": "policyNo",
            "doctype_field": "policy_no",
            "label": "Policy Number",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "isRenewable",
            "doctype_field": "is_renewable",
            "label": "Is Renewable",
            "category": "Policy Information",
            "validation_type": "yes_no",
            "is_required": 1
        },
        {
            "saiba_field": "newRenewal",
            "doctype_field": "new_renewal",
            "label": "New/Renewal",
            "category": "Policy Information",
            "validation_type": "new_renew",
            "is_required": 1
        },

        # Dates (3 fields)
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

        # Vehicle Information (10 fields)
        {
            "saiba_field": "vehicleNo",
            "doctype_field": "vehicle_no",
            "label": "Vehicle Number",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "make",
            "doctype_field": "make",
            "label": "Vehicle Make",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "model",
            "doctype_field": "model",
            "label": "Vehicle Model",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "variant",
            "doctype_field": "variant",
            "label": "Vehicle Variant",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "yearOfMan",
            "doctype_field": "year_of_man",
            "label": "Year of Manufacture",
            "category": "Vehicle Information",
            "validation_type": "integer_positive",
            "is_required": 1
        },
        {
            "saiba_field": "chasisNo",
            "doctype_field": "chasis_no",
            "label": "Chassis Number",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "engineNo",
            "doctype_field": "engine_no",
            "label": "Engine Number",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "cc",
            "doctype_field": "cc",
            "label": "Engine CC",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "fuel",
            "doctype_field": "fuel",
            "label": "Fuel Type",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "rtoCode",
            "doctype_field": "rto_code",
            "label": "RTO Code",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },

        # Financial (7 fields)
        {
            "saiba_field": "ncb",
            "doctype_field": "ncb",
            "label": "NCB",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "sumInsured",
            "doctype_field": "sum_insured",
            "label": "Sum Insured",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "netODPremium",
            "doctype_field": "net_od_premium",
            "label": "Net OD Premium",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "tpPremium",
            "doctype_field": "tp_premium",
            "label": "TP Premium",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "gst",
            "doctype_field": "gst",
            "label": "GST",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "paymentMode",
            "doctype_field": "payment_mode_1",
            "label": "Payment Mode",
            "category": "Financial",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "bankName",
            "doctype_field": "bank_name",
            "label": "Bank Name",
            "category": "Financial",
            "validation_type": "string",
            "is_required": 1
        },

        # Policy Information (continued - 1 field)
        {
            "saiba_field": "remarks",
            "doctype_field": "policy_enquiry_remarks",
            "label": "Remarks",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        }
    ]

    # =========================================================================
    # Health Policy - 25 Mandatory Fields (Feb 2026 SAIBA API Spec)
    # =========================================================================
    health_rules = [
        # Customer & Insurer (2 fields)
        {
            "saiba_field": "customerCode",
            "doctype_field": "customer_code",
            "label": "Customer Code",
            "category": "Customer & Insurer",
            "validation_type": "integer_nonzero",
            "is_required": 1
        },
        {
            "saiba_field": "insurerBranchCode",
            "doctype_field": "insurer_branch_code",
            "label": "Insurer Branch Code",
            "category": "Customer & Insurer",
            "validation_type": "integer",
            "is_required": 1
        },

        # Policy Information (6 fields)
        {
            "saiba_field": "posPolicy",
            "doctype_field": "pos_policy",
            "label": "POS Policy",
            "category": "Policy Information",
            "validation_type": "yes_no",
            "is_required": 1
        },
        {
            "saiba_field": "policyBizType",
            "doctype_field": "biz_type",
            "label": "Policy Business Type",
            "category": "Policy Information",
            "validation_type": "new_renew",
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
            "saiba_field": "policyNo",
            "doctype_field": "policy_no",
            "label": "Policy Number",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "planName",
            "doctype_field": "plan_name",
            "label": "Plan Name",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "isRenewable",
            "doctype_field": "is_renewable",
            "label": "Is Renewable",
            "category": "Policy Information",
            "validation_type": "yes_no",
            "is_required": 1
        },
        {
            "saiba_field": "prevPolicy",
            "doctype_field": "prev_policy",
            "label": "Previous Policy",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },

        # Dates (3 fields)
        {
            "saiba_field": "policyIssuanceDate",
            "doctype_field": "policy_issuance_date",
            "label": "Policy Issuance Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "policyStartDate",
            "doctype_field": "policy_start_date",
            "label": "Policy Start Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "policyExpiryDate",
            "doctype_field": "policy_expiry_date",
            "label": "Policy Expiry Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },

        # Insured Persons (4 fields)
        {
            "saiba_field": "insured1Name",
            "doctype_field": "insured_1_name",
            "label": "Insured 1 Name",
            "category": "Insured Persons",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "insured1DOB",
            "doctype_field": "insured_1_dob",
            "label": "Insured 1 DOB",
            "category": "Insured Persons",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "insured1Gender",
            "doctype_field": "insured_1_gender",
            "label": "Insured 1 Gender",
            "category": "Insured Persons",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "insured1Relation",
            "doctype_field": "insured_1_relation",
            "label": "Insured 1 Relation",
            "category": "Insured Persons",
            "validation_type": "string",
            "is_required": 1
        },

        # Financial (7 fields)
        {
            "saiba_field": "sumInsured",
            "doctype_field": "sum_insured",
            "label": "Sum Insured",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "netODPremium",
            "doctype_field": "net_od_premium",
            "label": "Net OD Premium",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "gst",
            "doctype_field": "gst_tax_percent",
            "label": "GST",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "stampDuty",
            "doctype_field": "stamp_duty",
            "label": "Stamp Duty",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "paymentMode",
            "doctype_field": "payment_mode",
            "label": "Payment Mode",
            "category": "Financial",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "bankName",
            "doctype_field": "bank_name",
            "label": "Bank Name",
            "category": "Financial",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "paymentTransactionNo",
            "doctype_field": "payment_transaction_no",
            "label": "Payment Transaction No",
            "category": "Financial",
            "validation_type": "string",
            "is_required": 1
        },

        # Policy Information (continued - 2 fields)
        {
            "saiba_field": "remarks",
            "doctype_field": "remarks",
            "label": "Remarks",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "policyStatus",
            "doctype_field": "policy_status",
            "label": "Policy Status",
            "category": "Policy Information",
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

    # Save settings
    settings.save()
    frappe.db.commit()

    frappe.logger().info(
        f"Updated SAIBA Validation Settings: {len(motor_rules)} Motor rules, {len(health_rules)} Health rules"
    )
