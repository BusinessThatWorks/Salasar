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
	try:
		# Try to get cached mapping from Policy Reader Settings
		settings = frappe.get_single("Policy Reader Settings")
		if settings:
			cached_mapping = settings.get_cached_field_mapping(policy_type)
			if cached_mapping:
				return cached_mapping
		
		# Fallback to hardcoded mappings if cache is empty
		frappe.logger().warning(f"Using fallback hardcoded field mapping for {policy_type} policy")
		
		if policy_type.lower() == "motor":
			return get_hardcoded_motor_mapping()
		elif policy_type.lower() == "health":
			return get_hardcoded_health_mapping()
		
		return {}
		
	except Exception as e:
		frappe.log_error(f"Error getting field mapping for {policy_type}: {str(e)}", 
						"Field Mapping Retrieval Error")
		# Return hardcoded mapping as last resort
		if policy_type.lower() == "motor":
			return get_hardcoded_motor_mapping()
		elif policy_type.lower() == "health":
			return get_hardcoded_health_mapping()
		return {}


def get_hardcoded_motor_mapping():
	"""Fallback hardcoded motor policy field mapping"""
	return {
		"Policy Number": "policy_number",
		"Insured Name": "insured_name", 
		"Vehicle Number": "vehicle_number",
		"Chassis Number": "chassis_number",
		"Engine Number": "engine_number",
		"From": "policy_from",
		"To": "policy_to",
		"Premium Amount": "premium_amount",
		"Sum Insured": "sum_insured",
		"Make / Model": "make_model",
		"Variant": "variant",
		"Vehicle Class": "vehicle_class",
		"Registration Number": "registration_number",
		"Fuel": "fuel",
		"Seat Capacity": "seat_capacity"
	}


def get_hardcoded_health_mapping():
	"""Fallback hardcoded health policy field mapping"""
	return {
		"Policy Number": "policy_number",
		"Insured Name": "insured_name",
		"Sum Insured": "sum_insured", 
		"Policy Start Date": "policy_start_date",
		"Policy End Date": "policy_end_date",
		"Customer Code": "customer_code",
		"Net Premium": "net_premium",
		"Policy Period": "policy_period",
		"Issuing Office": "issuing_office",
		"Relationship to Policyholder": "relationship_to_policyholder",
		"Date of Birth": "date_of_birth",
		"Insured Name 2": "insured_name_2",
		"Nominee Name": "nominee_name",
		"Insured Code": "insured_code"
	}


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