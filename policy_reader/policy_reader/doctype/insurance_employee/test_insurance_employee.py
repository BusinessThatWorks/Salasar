# Copyright (c) 2025, Clapgrow Software and Contributors
# See license.txt
import frappe
from frappe.tests.utils import FrappeTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestInsuranceEmployee(FrappeTestCase):
	"""
	Integration tests for InsuranceEmployee.
	Use this class for testing interactions between multiple components.
	"""

	def setUp(self):
		frappe.db.delete("Insurance Employee")
		if not frappe.db.exists("User", "test_insurance_employee@example.com"):
			frappe.get_doc({
				"doctype": "User",
				"first_name": "Example",
				"email": "test_insurance_employee@example.com"
			}).insert(ignore_permissions=True)


	def create_broker_branch(self):
		if frappe.db.exists("Broker Branch", {"branch_name": "BRANCH EXAMPLE"}):
			return frappe.get_doc("Broker Branch", {"branch_name": "BRANCH EXAMPLE"})

		return frappe.get_doc({
			"doctype": "Broker Branch",
			"branch_code": 11,
			"branch_name": "BRANCH EXAMPLE"
		}).insert(ignore_permissions=True)

	def create_first_insurance_employee(self):
		branch = self.create_broker_branch()

		return frappe.get_doc({
			"doctype": "Insurance Employee",
			"employee_name": "Testing Insurance Employee",
			"user": "test_insurance_employee@example.com",
			"branch": branch.name,
			"branch_name": branch.branch_name,
			"branch_code": branch.branch_code,
			"employee_type": "CSC",
			"employee_code": "EMP-002",
		}).insert(ignore_permissions=True)

	def test_allow_without_user(self):
		branch = self.create_broker_branch()

		doc = frappe.get_doc({
			"doctype": "Insurance Employee",
			"employee_name": "Testing Insurance Employee2",
			"branch": branch.name,
			"branch_name": branch.branch_name,
			"branch_code": branch.branch_code,
			"employee_type": "CSC",
			"employee_code": "EMP-003",
		})
		doc.insert(ignore_permissions=True)

	def test_allow_unique_user(self):
		self.create_first_insurance_employee()

	def test_block_duplicate_user(self):
		self.create_first_insurance_employee()

		branch = self.create_broker_branch()

		second = frappe.get_doc({
			"doctype": "Insurance Employee",
			"employee_name": "Testing Insurance Employee3",
			"user": "test_insurance_employee@example.com",
			"branch": branch.name,
			"branch_name": branch.branch_name,
			"branch_code": branch.branch_code,
			"employee_type": "CSC",
			"employee_code": "EMP-004",
		})

		with self.assertRaises(frappe.ValidationError) as error:
			second.insert(ignore_permissions=True)

