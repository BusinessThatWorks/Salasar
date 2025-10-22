# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, cstr
from policy_reader.policy_reader.services.policy_creation_service import PolicyCreationService


class MotorPolicy(Document):
	def before_save(self):
		"""Auto-populate RM/CSC/REF with current user's Insurance Employee"""
		self._populate_rm_csc_ref()

	def validate(self):
		"""Basic validation for SAIBA ERP compliance"""
		self.validate_policy_dates()
		self.validate_required_fields()
	
	def validate_policy_dates(self):
		"""Validate policy date logic"""
		if self.policy_start_date and self.policy_expiry_date:
			start_date = getdate(self.policy_start_date)
			expiry_date = getdate(self.policy_expiry_date)
			
			if start_date >= expiry_date:
				frappe.throw("Policy start date must be before expiry date")
	
	def validate_required_fields(self):
		"""Validate critical SAIBA fields with better error messages"""
		# Removed mandatory validation to allow document creation without all fields
		# Fields can be populated later through AI extraction or manual entry
		pass

	def _populate_rm_csc_ref(self):
		"""Auto-set RM/CSC/REF to current user's Insurance Employee if not already set"""
		try:
			# Only auto-populate if empty (allows manual override)
			if not self.rm_csc_ref:
				current_user = frappe.session.user

				# Skip for system users
				if current_user in ["Guest", "Administrator"]:
					return

				# Get Insurance Employee record for current user
				employee = frappe.db.get_value(
					"Insurance Employee",
					{"user": current_user},
					"name"
				)

				if employee:
					self.rm_csc_ref = employee
					frappe.logger().info(f"Auto-populated rm_csc_ref with Insurance Employee: {employee}")
				else:
					frappe.logger().info(f"No Insurance Employee record found for user {current_user}")

		except Exception as e:
			frappe.logger().error(f"Error auto-populating rm_csc_ref: {str(e)}")
			# Don't throw - this is a non-critical operation
	
	@frappe.whitelist()
	def populate_fields_from_policy_document(self, policy_document_name):
		"""
		Populate Motor Policy fields from the linked Policy Document's extracted fields
		Uses the existing PolicyCreationService to avoid code duplication
		"""
		try:
			# Get the Policy Document
			policy_doc = frappe.get_doc("Policy Document", policy_document_name)
			
			# Check if extracted fields exist
			if not policy_doc.extracted_fields:
				return {
					"success": False,
					"error": "No extracted fields found in Policy Document. Please process the document first."
				}
			
			# Use the existing PolicyCreationService
			policy_service = PolicyCreationService()
			
			# Use extracted data directly (already parsed by Claude Vision Service)
			extracted_data = frappe.parse_json(policy_doc.extracted_fields)
			parsed_data = extracted_data if isinstance(extracted_data, dict) else {}
			
			# Refresh field mappings to include latest aliases (including ChasisNo)
			try:
				settings = frappe.get_single("Policy Reader Settings")
				settings.refresh_field_mappings()
				frappe.db.commit()
				frappe.logger().info("Field mappings refreshed successfully - ChasisNo mapping updated")
			except Exception as e:
				frappe.logger().warning(f"Could not refresh field mappings: {str(e)}")
			
			# Get field mapping for Motor policy type
			field_mapping = policy_service.get_field_mapping_for_policy_type("Motor")
			
			if not field_mapping:
				return {
					"success": False,
					"error": "No field mapping found for Motor policy. Please check Policy Reader Settings."
				}
			
			# Debug: Log the specific fields we're trying to map
			chasis_related = [k for k in parsed_data.keys() if 'chasis' in k.lower() or 'chassis' in k.lower()]
			if chasis_related:
				frappe.logger().info(f"Found chassis-related fields in parsed data: {chasis_related}")
				for field in chasis_related:
					if field in field_mapping:
						frappe.logger().info(f"✓ Field '{field}' maps to: {field_mapping[field]}")
					else:
						frappe.logger().warning(f"✗ Field '{field}' NOT found in mapping")
			
			# Map fields using existing service method
			mapping_results = policy_service.map_fields_dynamically(
				parsed_data, field_mapping, self, "Motor"
			)
			
			# Save the Motor Policy with populated fields
			self.save()
			
			return {
				"success": True,
				"populated_fields": mapping_results["mapped_count"],
				"unmapped_fields": mapping_results["unmapped_fields"],
				"message": f"Successfully populated {mapping_results['mapped_count']} fields from Policy Document."
			}
			
		except Exception as e:
			frappe.log_error(f"Error populating Motor Policy fields: {str(e)}", "Motor Policy Population Error")
			return {
				"success": False,
				"error": str(e)
			}
