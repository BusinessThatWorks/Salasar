# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Add SAIBA sync fields to Motor Policy and Health Policy DocTypes"""

    # Define SAIBA sync fields for both policy types
    saiba_sync_fields = [
        {
            "fieldname": "saiba_sync_tab",
            "fieldtype": "Tab Break",
            "label": "SAIBA Sync",
            "insert_after": "mandate"
        },
        {
            "fieldname": "saiba_sync_section",
            "fieldtype": "Section Break",
            "label": "Sync Status",
            "insert_after": "saiba_sync_tab"
        },
        {
            "fieldname": "saiba_sync_status",
            "fieldtype": "Select",
            "label": "SAIBA Sync Status",
            "options": "Not Synced\nSynced\nFailed\nPending",
            "default": "Not Synced",
            "read_only": 1,
            "in_list_view": 1,
            "description": "Current sync status with SAIBA ERP",
            "insert_after": "saiba_sync_section"
        },
        {
            "fieldname": "saiba_sync_datetime",
            "fieldtype": "Datetime",
            "label": "Sync Datetime",
            "read_only": 1,
            "description": "Last sync timestamp",
            "insert_after": "saiba_sync_status"
        },
        {
            "fieldname": "column_break_saiba_sync",
            "fieldtype": "Column Break",
            "insert_after": "saiba_sync_datetime"
        },
        {
            "fieldname": "saiba_control_number",
            "fieldtype": "Data",
            "label": "SAIBA Control Number",
            "read_only": 1,
            "length": 50,
            "description": "Control number returned by SAIBA after successful sync",
            "insert_after": "column_break_saiba_sync"
        },
        {
            "fieldname": "saiba_sync_error",
            "fieldtype": "Long Text",
            "label": "Sync Error",
            "read_only": 1,
            "depends_on": "eval:doc.saiba_sync_status === 'Failed'",
            "description": "Error message if sync failed",
            "insert_after": "saiba_control_number"
        },
        {
            "fieldname": "saiba_sync_response",
            "fieldtype": "JSON",
            "label": "Sync Request/Response (Debug)",
            "read_only": 1,
            "depends_on": "eval:doc.saiba_sync_status === 'Failed' || doc.saiba_sync_status === 'Synced'",
            "description": "Full API request/response from SAIBA (for debugging)",
            "insert_after": "saiba_sync_error"
        }
    ]

    # Add fields to Motor Policy
    motor_fields = []
    for field in saiba_sync_fields:
        motor_field = field.copy()
        if motor_field["fieldname"] == "saiba_sync_tab":
            motor_field["insert_after"] = "mandate"
        motor_fields.append(motor_field)

    # Add fields to Health Policy
    health_fields = []
    for field in saiba_sync_fields:
        health_field = field.copy()
        if health_field["fieldname"] == "saiba_sync_tab":
            health_field["insert_after"] = "tp_reward"
        health_fields.append(health_field)

    # Check if fields already exist before adding
    # For Motor Policy
    if not frappe.db.exists("Custom Field", {"dt": "Motor Policy", "fieldname": "saiba_sync_status"}):
        create_custom_fields({
            "Motor Policy": motor_fields
        })
        frappe.logger().info("Added SAIBA sync fields to Motor Policy")

    # For Health Policy
    if not frappe.db.exists("Custom Field", {"dt": "Health Policy", "fieldname": "saiba_sync_status"}):
        create_custom_fields({
            "Health Policy": health_fields
        })
        frappe.logger().info("Added SAIBA sync fields to Health Policy")

    # Add SAIBA integration fields to Policy Reader Settings
    settings_fields = [
        {
            "fieldname": "saiba_integration_section",
            "fieldtype": "Section Break",
            "label": "SAIBA Integration",
            "insert_after": "claude_model"
        },
        {
            "fieldname": "saiba_enabled",
            "fieldtype": "Check",
            "label": "Enable SAIBA Sync",
            "default": "0",
            "description": "Enable/disable SAIBA sync functionality",
            "insert_after": "saiba_integration_section"
        },
        {
            "fieldname": "saiba_base_url",
            "fieldtype": "Data",
            "label": "SAIBA Base URL",
            "default": "http://3.108.100.243:8085",
            "depends_on": "eval:doc.saiba_enabled",
            "description": "SAIBA API base URL",
            "insert_after": "saiba_enabled"
        },
        {
            "fieldname": "column_break_saiba",
            "fieldtype": "Column Break",
            "insert_after": "saiba_base_url"
        },
        {
            "fieldname": "saiba_username",
            "fieldtype": "Data",
            "label": "SAIBA Username",
            "depends_on": "eval:doc.saiba_enabled",
            "description": "SAIBA API authentication username",
            "insert_after": "column_break_saiba"
        },
        {
            "fieldname": "saiba_password",
            "fieldtype": "Password",
            "label": "SAIBA Password",
            "depends_on": "eval:doc.saiba_enabled",
            "description": "SAIBA API authentication password",
            "insert_after": "saiba_username"
        },
        {
            "fieldname": "saiba_token_section",
            "fieldtype": "Section Break",
            "label": "SAIBA Token (Auto-managed)",
            "collapsible": 1,
            "depends_on": "eval:doc.saiba_enabled",
            "insert_after": "saiba_password"
        },
        {
            "fieldname": "saiba_token",
            "fieldtype": "Long Text",
            "label": "SAIBA Token",
            "read_only": 1,
            "hidden": 1,
            "description": "Cached authentication token (auto-managed)",
            "insert_after": "saiba_token_section"
        },
        {
            "fieldname": "saiba_token_expiry",
            "fieldtype": "Datetime",
            "label": "Token Expiry",
            "read_only": 1,
            "description": "Token expiry timestamp",
            "insert_after": "saiba_token"
        },
        {
            "fieldname": "test_saiba_connection",
            "fieldtype": "Button",
            "label": "Test Connection",
            "depends_on": "eval:doc.saiba_enabled",
            "description": "Test SAIBA API connectivity",
            "insert_after": "saiba_token_expiry"
        }
    ]

    # Check if fields already exist before adding to Policy Reader Settings
    if not frappe.db.exists("Custom Field", {"dt": "Policy Reader Settings", "fieldname": "saiba_enabled"}):
        create_custom_fields({
            "Policy Reader Settings": settings_fields
        })
        frappe.logger().info("Added SAIBA integration fields to Policy Reader Settings")

    frappe.db.commit()
