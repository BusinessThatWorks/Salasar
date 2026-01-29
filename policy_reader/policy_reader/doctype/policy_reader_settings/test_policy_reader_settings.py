# Copyright (c) 2025, Clapgrow Software and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestPolicyReaderSettings(FrappeTestCase):
	"""
	Integration tests for PolicyReaderSettings.
	Use this class for testing interactions between multiple components.
	"""

	def setUp(self):
		self.doc = frappe.get_single("Policy Reader Settings")

	def test_valid_anthropic_key(self):
		"""Valid API key should save successfully"""
		self.doc.anthropic_api_key = "sk-ant-123456"
		self.doc.timeout = 120
		self.doc.save()  

	def test_invalid_anthropic_key(self):
		"""Invalid API key format should throw error"""
		self.doc.anthropic_api_key = "SK-ANT-123"
		self.doc.timeout = 120

		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_empty_anthropic_key(self):
		"""Empty API key is allowed"""
		self.doc.anthropic_api_key = None
		self.doc.timeout = 120
		self.doc.save()  # should not throw

	def test_timeout_too_small(self):
		"""Timeout below 60 should fail"""
		self.doc.anthropic_api_key = "sk-ant-valid"
		self.doc.timeout = 30

		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_timeout_too_large(self):
		"""Timeout above 600 should fail"""
		self.doc.anthropic_api_key = "sk-ant-valid"
		self.doc.timeout = 700

		with self.assertRaises(frappe.ValidationError):
			self.doc.save()

	def test_timeout_boundary_values(self):
		"""Timeout at boundary values should pass"""

		# Lower bound
		self.doc.anthropic_api_key = "sk-ant-valid"
		self.doc.timeout = 60
		self.doc.save()  # should pass

		# Upper bound
		self.doc.anthropic_api_key = "sk-ant-valid"
		self.doc.timeout = 600
		self.doc.save()  # should pass


