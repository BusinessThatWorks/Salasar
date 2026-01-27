# Copyright (c) 2026, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe


def execute():
    """Update Motor Policy validation rules to include all 40 mandatory SAIBA fields"""

    # Check if SAIBA Validation Settings exists
    if not frappe.db.exists("SAIBA Validation Settings", "SAIBA Validation Settings"):
        frappe.logger().info("SAIBA Validation Settings not found, skipping motor rules update")
        return

    settings = frappe.get_single("SAIBA Validation Settings")

    # Clear existing motor validation rules
    settings.motor_validation_rules = []

    # Define all 40 Motor Policy mandatory validation rules
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

        # Dates (5 fields)
        {
            "saiba_field": "issuenceDate",
            "doctype_field": "policy_issuance_date",
            "label": "Policy Issuance Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },
        {
            "saiba_field": "busBrokDate",
            "doctype_field": "bus_brok_date",
            "label": "Business/Brokerage Date",
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
            "saiba_field": "policyReceivedDate",
            "doctype_field": "receive_date",
            "label": "Policy Received Date",
            "category": "Dates",
            "validation_type": "date",
            "is_required": 1
        },

        # Policy Information (8 fields)
        {
            "saiba_field": "posPolicy",
            "doctype_field": "pos_misp_ref",
            "label": "POS Policy",
            "category": "Policy Information",
            "validation_type": "yes_no",
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
            "saiba_field": "department",
            "doctype_field": "department",
            "label": "Department",
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
        {
            "saiba_field": "prevPolicy",
            "doctype_field": "prev_policy_no",
            "label": "Previous Policy",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "remarks",
            "doctype_field": "policy_enquiry_remarks",
            "label": "Remarks",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },
        {
            "saiba_field": "policyStatus",
            "doctype_field": "policy_status_na",
            "label": "Policy Status",
            "category": "Policy Information",
            "validation_type": "string",
            "is_required": 1
        },

        # Vehicle Information (14 fields)
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
            "saiba_field": "registrationDate",
            "doctype_field": "registration_date",
            "label": "Registration Date",
            "category": "Vehicle Information",
            "validation_type": "date",
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
        {
            "saiba_field": "vehicleCategory",
            "doctype_field": "category",
            "label": "Vehicle Category",
            "category": "Vehicle Information",
            "validation_type": "gcv_pcv_misc",
            "is_required": 1
        },
        {
            "saiba_field": "passengerGVW",
            "doctype_field": "passenger_gvw",
            "label": "Passenger GVW",
            "category": "Vehicle Information",
            "validation_type": "string",
            "is_required": 1
        },

        # Financial (11 fields)
        {
            "saiba_field": "ncb",
            "doctype_field": "ncb",
            "label": "NCB",
            "category": "Financial",
            "validation_type": "integer",
            "is_required": 1
        },
        {
            "saiba_field": "odd",
            "doctype_field": "odd",
            "label": "Own Damage Deductible",
            "category": "Financial",
            "validation_type": "integer",
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
            "saiba_field": "lpodPremium",
            "doctype_field": "lpod_premium",
            "label": "LPOD Premium",
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
            "saiba_field": "stampDuty",
            "doctype_field": "stamp_duty",
            "label": "Stamp Duty",
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
        {
            "saiba_field": "paymentTranNo",
            "doctype_field": "payment_tran_no",
            "label": "Payment Transaction No",
            "category": "Financial",
            "validation_type": "string",
            "is_required": 1
        }
    ]

    # Add all motor rules
    for rule_data in motor_rules:
        settings.append("motor_validation_rules", rule_data)

    # Save settings
    settings.save()
    frappe.db.commit()

    frappe.logger().info(
        f"Updated SAIBA Validation Settings with {len(motor_rules)} Motor Policy validation rules"
    )
