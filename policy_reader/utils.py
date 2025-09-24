# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now


def refresh_field_mappings_if_policy_doctype(doc, method):
	"""Refresh field mappings when Motor Policy or Health Policy DocTypes are updated"""
	try:
		# Only trigger for Motor Policy and Health Policy DocTypes
		if doc.name not in ["Motor Policy", "Health Policy"]:
			return
		
		# Get Policy Reader Settings
		settings = frappe.get_single("Policy Reader Settings")
		if not settings:
			return
		
		# Refresh field mappings
		if doc.name == "Motor Policy":
			motor_mapping = settings.build_field_mapping_from_doctype("Motor Policy")
			settings.motor_policy_fields = frappe.as_json(motor_mapping)
			settings.last_field_sync = now()
			settings.save()
			
			frappe.logger().info(f"Auto-refreshed Motor Policy field mappings: {len(motor_mapping)} fields")
			
		elif doc.name == "Health Policy":
			health_mapping = settings.build_field_mapping_from_doctype("Health Policy")
			settings.health_policy_fields = frappe.as_json(health_mapping)
			settings.last_field_sync = now()
			settings.save()
			
			frappe.logger().info(f"Auto-refreshed Health Policy field mappings: {len(health_mapping)} fields")
		
	except Exception as e:
		# Log error but don't break DocType save operation
		frappe.log_error(f"Failed to auto-refresh field mappings for {doc.name}: {str(e)}", 
						"Field Mapping Auto-Refresh Error")


def get_field_mapping_for_policy_type(policy_type):
	"""Get field mapping for a policy type with fallback to hardcoded mappings"""
	from policy_reader.policy_reader.services.common_service import CommonService
	return CommonService.get_field_mapping_for_policy_type(policy_type)






def initialize_field_mappings():
	"""Initialize field mappings in Policy Reader Settings (run once)"""
	try:
		# Get or create Policy Reader Settings
		settings = frappe.get_single("Policy Reader Settings")
		
		# Check if mappings are already initialized
		if settings.motor_policy_fields and settings.health_policy_fields:
			frappe.logger().info("Field mappings already initialized")
			return
		
		# Refresh field mappings
		settings.refresh_field_mappings()
		
		frappe.logger().info("Field mappings initialized successfully")
		return "Field mappings initialized successfully"
		
	except Exception as e:
		frappe.log_error(f"Failed to initialize field mappings: {str(e)}", "Field Mapping Initialization Error")
		raise