# Copyright (c) 2025, Clapgrow Software and Contributors
# See license.txt
import frappe
import os
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, add_to_date
from unittest.mock import patch


EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []

class IntegrationTestPolicyDocument(FrappeTestCase):
	"""
	Integration tests for PolicyDocument.
	Use this class for testing interactions between multiple components.
	"""

	def make_test_image_file(self, private=False):
		base = frappe.get_app_path("policy_reader", "policy_reader/test/data")
		file_path = os.path.join(base, "MOTOR_POLICIES_CAR.pdf")

		with open(file_path, "rb") as f:
			file_content = f.read()

		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "MOTOR_POLICIES_CAR.pdf",
				"content": file_content,
				"is_private": private,
			}
		).insert(ignore_permissions=True)

		return test_file

	def create_policy_document(self):
		test_file = self.make_test_image_file()
		doc = frappe.get_doc({
			"doctype": "Policy Document",
			"policy_file": test_file.file_url,
		}).insert(ignore_permissions=True)

		return doc

	def setUp(self):
		if not frappe.db.exists("User", "test@example.com"):
			frappe.get_doc({
				"doctype": "User",
				"email": "test@example.com",
				"first_name": "Test",
				"enabled": 1,
			}).insert(ignore_permissions=True)

		frappe.set_user("test@example.com")
		self.create_insurance_employee()



	def create_broker_branch(self):
		if frappe.db.exists("Broker Branch", {"branch_name": "EXAMPLE"}):
			return frappe.get_doc("Broker Branch", {"branch_name": "EXAMPLE"})

		broker_branch_doc = frappe.get_doc({
			"doctype": "Broker Branch",
			"branch_code": 10,
			"branch_name": "EXAMPLE"
		}).insert(ignore_permissions=True)

		return broker_branch_doc

	def create_insurance_employee(self):
		existing = frappe.db.get_value(
			"Insurance Employee",
			{"user": "test@example.com"},
			"name"
		)

		if existing:
			return frappe.get_doc("Insurance Employee", existing)

		branch = self.create_broker_branch()

		return frappe.get_doc({
			"doctype": "Insurance Employee",
			"employee_name": "Testing Employee",
			"user": "test@example.com",
			"branch": branch.name,
			"branch_name": branch.branch_name,
			"branch_code": branch.branch_code,
			"employee_type": "CSC",
			"employee_code": "EMP-001",
		}).insert(ignore_permissions=True)



	def test_before_save_sets_title_from_file(self):
		doc = self.create_policy_document()
		doc.save()

		self.assertEqual(doc.title, "Motor Policies Car")


	def test_before_save_populates_processor_info(self):
		doc = self.create_policy_document()
		doc.save()

		self.assertEqual(doc.processor_employee_code, "EMP-001")
		self.assertEqual(doc.processor_employee_name, "Testing Employee")
		self.assertEqual(doc.processor_employee_type, "CSC")
		self.assertEqual(doc.processor_branch_name, "EXAMPLE")


# validate 


	def test_completed_status_without_extracted_fields_throws(self):
		doc = frappe.get_doc({
			"doctype": "Policy Document",
			"policy_file": self.make_test_image_file().file_url,
			"status": "Completed",
			"extracted_fields": None,
		})

		with self.assertRaises(frappe.ValidationError) as error:
			doc.insert(ignore_permissions=True)

		self.assertIn(f"Invalid input: extracted fields cannot be empty for completed documents", str(error.exception))



	def test_cannot_change_policy_type_after_extraction(self):
		doc = frappe.get_doc({
			"doctype": "Policy Document",
			"policy_file": self.make_test_image_file().file_url,
			"status": "Completed",
			"policy_type": "Motor",
			"extraction_policy_type": "Motor",
			"extracted_fields": '{"Motor": "Policy"}', 
		})
		doc.policy_type="Health"

		with self.assertRaises(frappe.ValidationError) as error:
			doc.insert(ignore_permissions=True)

		self.assertIn(f"Invalid input: Cannot change policy type after extraction. Extracted fields were generated for '{doc.extraction_policy_type}' policy type. Please reprocess the document if you need to change the policy type.", str(error.exception))


    # background -> true
	def test_process_policy_enqueues_background_job(self):
		doc = self.create_policy_document()
		doc.policy_type = "Motor"
		doc.save()

		with patch("frappe.enqueue") as mock_enqueue:
			result = doc.process_policy(background=True)
			doc.reload()

			self.assertEqual(doc.status, "Processing")
			self.assertEqual(doc.extraction_policy_type, "Motor")
			mock_enqueue.assert_called_once()
			self.assertTrue(result["success"])
			self.assertEqual(result["status"], "Processing")

	 # background -> false	-> success
	def test_process_policy_sync_success(self):
		doc = self.create_policy_document()
		doc.policy_type = "Motor"
		doc.save()

		fake_ai_result = {
			"success": True,
			"extracted_fields": {"policy_no": "EXAMPLE-123"}
		}

		with patch.object(doc, "_execute_ai_processing") as mock_exec, \
			patch("frappe.publish_realtime"):
			mock_exec.return_value = (fake_ai_result, 1.2)
			result = doc.process_policy(background=False)
			doc.reload()
			self.assertEqual(doc.status, "Completed")
			self.assertEqual(doc.get_extracted_fields_display(), {"policy_no": "EXAMPLE-123"})
			self.assertTrue(result["success"])
			self.assertEqual(result["extracted_fields"], {"policy_no": "EXAMPLE-123"})

    # background -> false -> failure 
	# def test_process_policy_sync_failure(self):
	# 	doc = self.create_policy_document()
	# 	doc.policy_type = "Motor"
	# 	doc.save()

	# 	fake_ai_result = {
	# 		"success": False,
	# 		"error": "Invalid PDF format"
	# 	}

	# 	with patch.object(doc, "_execute_ai_processing") as mock_exec, \
	# 		patch("frappe.publish_realtime"):

	# 		# Pretend AI failed
	# 		mock_exec.return_value = (fake_ai_result, 0.8)

	# 		result = doc.process_policy(background=False)
	# 		doc.reload()

	# 		# Document should now be Failed
	# 		self.assertEqual(doc.status, "Failed")
	# 		self.assertEqual(doc.error_message, "Invalid PDF format")

	# 		# API response should reflect failure
	# 		self.assertFalse(result["success"])
	# 		self.assertIn("Invalid PDF format", result["message"])
	def test_reset_processing_status_from_processing(self):
		doc = self.create_policy_document()
		doc.status = "Processing"
		doc.save()

		result = doc.reset_processing_status()
		doc.reload()

		self.assertEqual(doc.status, "Draft")
		self.assertEqual(doc.error_message, "Processing was reset by user")
		self.assertTrue(result["success"])
    
	def test_reset_processing_status_invalid_state(self):
		doc = self.create_policy_document()
		# check for completed also later 
		doc.status = "Failed"
		doc.save()

		with self.assertRaises(frappe.ValidationError):
			doc.reset_processing_status()
  

