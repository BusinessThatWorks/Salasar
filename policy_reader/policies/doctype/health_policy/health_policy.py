# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, cstr
from policy_reader.policy_reader.services.policy_creation_service import PolicyCreationService


class HealthPolicy(Document):
	def before_save(self):
		"""Auto-populate RM/CE1 Code with current user's Insurance Employee"""
		self._populate_rm_ce1_code()

	def validate(self):
		"""Basic validation for Health Policy"""
		self.validate_policy_dates()
		self.validate_required_fields()
		self.validate_renewable_policy()
	
	def validate_policy_dates(self):
		"""Validate policy date logic"""
		if self.policy_start_date and self.policy_expiry_date:
			start_date = getdate(self.policy_start_date)
			expiry_date = getdate(self.policy_expiry_date)
			
			if start_date >= expiry_date:
				frappe.throw("Policy start date must be before expiry date")
	
	def validate_required_fields(self):
		"""Validate critical Health Policy fields"""
		# Allow document creation without all fields for flexibility
		pass

	def validate_renewable_policy(self):
		"""Validate that renewable policies have Old Control Number"""
		if self.is_renewable == "Yes" and not self.old_control_number:
			frappe.throw("Old Control Number is required when policy is marked as Renewable")

	def _populate_rm_ce1_code(self):
		"""Auto-set RM/CE1 Code to current user's Insurance Employee if not already set"""
		try:
			# Only auto-populate if empty (allows manual override)
			if not self.rm_ce1_code:
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
					self.rm_ce1_code = employee
					frappe.logger().info(f"Auto-populated rm_ce1_code with Insurance Employee: {employee}")
				else:
					frappe.logger().info(f"No Insurance Employee record found for user {current_user}")

		except Exception as e:
			frappe.logger().error(f"Error auto-populating rm_ce1_code: {str(e)}")
			# Don't throw - this is a non-critical operation
	
	@frappe.whitelist()
	def populate_fields_from_policy_document(self, policy_document_name):
		"""
		Populate Health Policy fields from the linked Policy Document's extracted fields
		Uses the existing PolicyCreationService to avoid code duplication

		IMPORTANT: Customer and Insurer information from Policy Document takes precedence
		over AI-extracted values and will not be overwritten.
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

			# STEP 1: Copy customer and insurer information from Policy Document FIRST
			# These should match the Policy Document's manually selected values
			self._copy_customer_info_from_policy_doc(policy_doc)
			self._copy_insurer_info_from_policy_doc(policy_doc)

			# Use extracted data directly (already parsed by Claude Vision Service)
			extracted_data = frappe.parse_json(policy_doc.extracted_fields)
			parsed_data = extracted_data if isinstance(extracted_data, dict) else {}

			# Refresh field mappings to include latest aliases
			try:
				settings = frappe.get_single("Policy Reader Settings")
				settings.refresh_field_mappings()
				frappe.db.commit()
				frappe.logger().info("Health Policy field mappings refreshed successfully")
			except Exception as e:
				frappe.logger().warning(f"Could not refresh health policy field mappings: {str(e)}")

			# Get field mapping for Health policy type
			field_mapping = policy_service.get_field_mapping_for_policy_type("Health")

			if not field_mapping:
				return {
					"success": False,
					"error": "No field mapping found for Health policy. Please check Policy Reader Settings."
				}

			# STEP 2: Define protected fields that should not be overwritten by AI extraction
			protected_fields = policy_service._get_protected_fields()

			# STEP 3: Map fields using existing service method with field protection
			mapping_results = policy_service.map_fields_dynamically(
				parsed_data, field_mapping, self, "Health", protected_fields
			)

			# Save the Health Policy with populated fields
			self.save()

			return {
				"success": True,
				"populated_fields": mapping_results["mapped_count"],
				"protected_fields": mapping_results.get("protected_count", 0),
				"unmapped_fields": mapping_results["unmapped_fields"],
				"message": f"Successfully populated {mapping_results['mapped_count']} fields from Policy Document. {mapping_results.get('protected_count', 0)} fields protected from overwriting.",
				"debug_matches": mapping_results.get("suggestions", {}),
				"debug_parsed_keys": list(parsed_data.keys())[:10],
				"debug_unmapped": mapping_results["unmapped_fields"]
			}

		except Exception as e:
			frappe.log_error(f"Error populating Health Policy fields: {str(e)}", "Health Policy Population Error")
			return {
				"success": False,
				"error": str(e)
			}

	def _copy_customer_info_from_policy_doc(self, policy_doc):
		"""Copy customer information from Policy Document to Health Policy"""
		try:
			if policy_doc.customer_code:
				self.customer_code = policy_doc.customer_code
				frappe.logger().info(f"Copied customer_code from Policy Document: {policy_doc.customer_code}")

			if policy_doc.customer_name:
				self.customer_name = policy_doc.customer_name
				frappe.logger().info(f"Copied customer_name from Policy Document: {policy_doc.customer_name}")

			if policy_doc.customer_group_name:
				self.customer_group = policy_doc.customer_group_name
				frappe.logger().info(f"Copied customer_group from Policy Document: {policy_doc.customer_group_name}")

		except Exception as e:
			frappe.logger().error(f"Error copying customer info from Policy Document: {str(e)}")

	def _copy_insurer_info_from_policy_doc(self, policy_doc):
		"""Copy insurer information from Policy Document to Health Policy"""
		try:
			if policy_doc.insurance_company_branch:
				self.insurance_company_branch = policy_doc.insurance_company_branch
				frappe.logger().info(f"Copied insurance_company_branch from Policy Document: {policy_doc.insurance_company_branch}")

			if policy_doc.insurer_name:
				self.insurer_name = policy_doc.insurer_name
				frappe.logger().info(f"Copied insurer_name from Policy Document: {policy_doc.insurer_name}")

			if policy_doc.insurer_city:
				self.insurer_city = policy_doc.insurer_city
				frappe.logger().info(f"Copied insurer_city from Policy Document: {policy_doc.insurer_city}")

			if policy_doc.insurer_branch:
				self.insurer_branch = policy_doc.insurer_branch
				frappe.logger().info(f"Copied insurer_branch from Policy Document: {policy_doc.insurer_branch}")

			if policy_doc.insurer_branch_code:
				self.insurer_branch_code = policy_doc.insurer_branch_code
				frappe.logger().info(f"Copied insurer_branch_code from Policy Document: {policy_doc.insurer_branch_code}")

		except Exception as e:
			frappe.logger().error(f"Error copying insurer info from Policy Document: {str(e)}")
