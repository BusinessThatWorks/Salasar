# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InsuranceEmployee(Document):
	def validate(self):
		"""Validate Insurance Employee before save"""
		self.validate_unique_user()

	def validate_unique_user(self):
		"""Ensure one user is only linked to one employee record"""
		if not self.user:
			return

		# Check if another Insurance Employee record exists with this user
		existing = frappe.db.exists(
			"Insurance Employee",
			{
				"user": self.user,
				"name": ["!=", self.name]
			}
		)

		if existing:
			frappe.throw(f"User {self.user} is already linked to another Insurance Employee record: {existing}")
