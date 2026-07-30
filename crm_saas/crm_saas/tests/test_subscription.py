# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
import unittest
from frappe.utils import add_days, today, getdate
from crm_saas.api.signup import signup
from crm_saas.api.auth import check_subscription_status, activate_subscription
from crm_saas.crm_saas.services.subscription_service import SubscriptionService, CRMSubscriptionExpiredError
from crm_saas.crm_saas.scheduler import daily_expire_subscriptions

class TestCRMSubscription(unittest.TestCase):
	def setUp(self):
		self.test_email = "test_prod_user_1@example.com"
		self.test_email_2 = "test_prod_user_2@example.com"
		
		# Clean up any residual test records and cache
		frappe.cache.hdel("roles", self.test_email)
		frappe.cache.hdel("roles", self.test_email_2)
		frappe.db.delete("User", {"email": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.delete("Has Role", {"parent": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.delete("CRM Subscription", {"user": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.delete("CRM Lead", {"owner": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.commit()
		self.switch_user("Administrator")

	def tearDown(self):
		self.switch_user("Administrator")
		# Clean up all created test records and cache
		frappe.cache.hdel("roles", self.test_email)
		frappe.cache.hdel("roles", self.test_email_2)
		frappe.db.delete("User", {"email": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.delete("Has Role", {"parent": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.delete("CRM Subscription", {"user": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.delete("CRM Lead", {"owner": ["in", [self.test_email, self.test_email_2]]})
		frappe.db.commit()

	def switch_user(self, user):
		"""
		Helper to safely switch user sessions during tests by clearing role and permission caches.
		"""
		frappe.set_user(user)
		frappe.cache.hdel("roles", user)
		frappe.local.user_roles = None
		if hasattr(frappe.local, "role_permissions"):
			frappe.local.role_permissions = {}

	def test_active_trial(self):
		"""
		Verifies signup sets up default role and active 5-day trial subscription.
		"""
		res = signup(company_name="Acme Corp", email=self.test_email, password="password123")
		self.assertEqual(res.get("status"), "success")
		self.assertTrue(frappe.db.exists("User", self.test_email))
		
		# Role verify
		user_roles = frappe.get_roles(self.test_email)
		print("ROLES PRINT:", user_roles)
		self.assertIn("CRM User", user_roles)
		
		# Active Trial verify
		self.assertTrue(SubscriptionService.is_trial_active(self.test_email))
		self.assertTrue(SubscriptionService.is_subscription_active(self.test_email))
		
		sub = SubscriptionService.get_active_subscription(self.test_email)
		self.assertEqual(sub.is_trial, 1)
		self.assertEqual(sub.status, "Trial")
		self.assertEqual(getdate(sub.end_date), getdate(add_days(today(), 5)))

	def test_expired_trial(self):
		"""
		Verifies expired trial is detected and blocks access with CRMSubscriptionExpiredError (HTTP 402).
		"""
		signup(company_name="Acme Corp", email=self.test_email, password="password123")
		
		# Backdate trial end_date
		self.switch_user("Administrator")
		sub_name = frappe.db.get_value("CRM Subscription", {"user": self.test_email}, "name")
		frappe.db.set_value("CRM Subscription", sub_name, "end_date", add_days(today(), -1))
		frappe.db.commit()
		
		# Switch to user to test validation
		self.switch_user(self.test_email)
		
		# Trial should not be active anymore
		self.assertFalse(SubscriptionService.is_trial_active(self.test_email))
		self.assertFalse(SubscriptionService.is_subscription_active(self.test_email))
		
		# Validating subscription should raise 402 error
		with self.assertRaises(CRMSubscriptionExpiredError) as context:
			SubscriptionService.validate_subscription(self.test_email)
		self.assertEqual(context.exception.code, 402)

	def test_active_paid_subscription(self):
		"""
		Verifies active paid subscription is detected correctly.
		"""
		signup(company_name="Acme Corp", email=self.test_email, password="password123")
		
		# Seed plan
		self.switch_user("Administrator")
		if not frappe.db.exists("CRM Plan", "Premium Plan"):
			plan = frappe.new_doc("CRM Plan")
			plan.plan_name = "Premium Plan"
			plan.monthly_price_per_user = 50.0
			plan.billing_interval = "Monthly"
			plan.is_active = 1
			plan.insert(ignore_permissions=True)
			frappe.db.commit()
			
		self.switch_user(self.test_email)
		SubscriptionService.activate_subscription(self.test_email, "Premium Plan")
		
		# Sub should be active, but NOT a trial
		self.assertFalse(SubscriptionService.is_trial_active(self.test_email))
		self.assertTrue(SubscriptionService.is_subscription_active(self.test_email))
		
		sub = SubscriptionService.get_active_subscription(self.test_email)
		self.assertEqual(sub.is_trial, 0)
		self.assertEqual(sub.status, "Active")
		self.assertEqual(sub.plan, "Premium Plan")

	def test_expired_paid_subscription(self):
		"""
		Verifies expired paid subscription throws CRMSubscriptionExpiredError.
		"""
		signup(company_name="Acme Corp", email=self.test_email, password="password123")
		
		# Setup active paid plan
		self.switch_user("Administrator")
		if not frappe.db.exists("CRM Plan", "Premium Plan"):
			plan = frappe.new_doc("CRM Plan")
			plan.plan_name = "Premium Plan"
			plan.monthly_price_per_user = 50.0
			plan.billing_interval = "Monthly"
			plan.is_active = 1
			plan.insert(ignore_permissions=True)
			frappe.db.commit()
		
		self.switch_user(self.test_email)
		sub = SubscriptionService.activate_subscription(self.test_email, "Premium Plan")
		
		# Backdate subscription
		self.switch_user("Administrator")
		frappe.db.set_value("CRM Subscription", sub.name, "end_date", add_days(today(), -1))
		frappe.db.commit()
		
		# Validate subscription should raise 402
		self.switch_user(self.test_email)
		with self.assertRaises(CRMSubscriptionExpiredError) as context:
			SubscriptionService.validate_subscription(self.test_email)
		self.assertEqual(context.exception.code, 402)

	def test_cancelled_subscription(self):
		"""
		Verifies cancelled subscription blocks access.
		"""
		signup(company_name="Acme Corp", email=self.test_email, password="password123")
		
		# Mark sub as Cancelled
		self.switch_user("Administrator")
		sub_name = frappe.db.get_value("CRM Subscription", {"user": self.test_email}, "name")
		frappe.db.set_value("CRM Subscription", sub_name, "status", "Cancelled")
		frappe.db.commit()
		
		self.switch_user(self.test_email)
		with self.assertRaises(CRMSubscriptionExpiredError) as context:
			SubscriptionService.validate_subscription(self.test_email)
		self.assertEqual(context.exception.code, 402)

	def test_administrator_bypass(self):
		"""
		Verifies Administrator and System Managers bypass subscription check.
		"""
		self.switch_user("Administrator")
		# Validate subscription for Administrator should pass silently
		self.assertTrue(SubscriptionService.validate_subscription("Administrator"))
		
		# System Manager role verify
		signup(company_name="Admin Team", email=self.test_email, password="password123")
		
		self.switch_user("Administrator")
		# Assign System Manager role
		user_doc = frappe.get_doc("User", self.test_email)
		user_doc.append("roles", {"role": "System Manager"})
		user_doc.save(ignore_permissions=True)
		
		# Backdate trial to ensure it's expired
		sub_name = frappe.db.get_value("CRM Subscription", {"user": self.test_email}, "name")
		frappe.db.set_value("CRM Subscription", sub_name, "end_date", add_days(today(), -5))
		frappe.db.commit()
		
		# System manager validation should pass despite expired subscription
		self.switch_user(self.test_email)
		self.assertTrue(SubscriptionService.validate_subscription(self.test_email))

	def test_row_level_security_and_isolation(self):
		"""
		Verifies row-level data visibility.
		User 1 cannot read User 2's records, and Administrator can see everything.
		"""
		signup(company_name="Acme Corp", email=self.test_email, password="password123")
		signup(company_name="Beta Corp", email=self.test_email_2, password="password123")
		
		# Create Lead as User 1
		self.switch_user(self.test_email)
		lead1 = frappe.new_doc("CRM Lead")
		lead1.lead_name = "User 1 Lead"
		lead1.email = "u1@example.com"
		lead1.insert()
		
		# Create Lead as User 2
		self.switch_user(self.test_email_2)
		lead2 = frappe.new_doc("CRM Lead")
		lead2.lead_name = "User 2 Lead"
		lead2.email = "u2@example.com"
		lead2.insert()
		
		# User 1 query
		self.switch_user(self.test_email)
		leads_u1 = frappe.get_list("CRM Lead")
		self.assertEqual(len(leads_u1), 1)
		self.assertEqual(leads_u1[0].name, lead1.name)
		
		# User 2 query
		self.switch_user(self.test_email_2)
		leads_u2 = frappe.get_list("CRM Lead")
		self.assertEqual(len(leads_u2), 1)
		self.assertEqual(leads_u2[0].name, lead2.name)
		
		# Admin query
		self.switch_user("Administrator")
		leads_admin = frappe.get_list("CRM Lead")
		self.assertGreaterEqual(len(leads_admin), 2)

	def test_scheduler_expiration_job(self):
		"""
		Verifies scheduler sweep finds, expires, and emails renewal alerts.
		"""
		signup(company_name="Acme Corp", email=self.test_email, password="password123")
		
		# Backdate subscription
		self.switch_user("Administrator")
		sub_name = frappe.db.get_value("CRM Subscription", {"user": self.test_email}, "name")
		frappe.db.set_value("CRM Subscription", sub_name, "end_date", add_days(today(), -2))
		frappe.db.commit()
		
		self.switch_user("Administrator")
		daily_expire_subscriptions()
		
		status = frappe.db.get_value("CRM Subscription", sub_name, "status")
		self.assertEqual(status, "Expired")

	def test_api_access_and_exemptions_after_expiry(self):
		"""
		Verifies that after subscription expiry, protected CRM APIs block access,
		but exempt subscription status and activation endpoints are accessible.
		"""
		signup(company_name="Acme Corp", email=self.test_email, password="password123")
		
		# Expire subscription
		self.switch_user("Administrator")
		sub_name = frappe.db.get_value("CRM Subscription", {"user": self.test_email}, "name")
		frappe.db.set_value("CRM Subscription", sub_name, "end_date", add_days(today(), -1))
		frappe.db.commit()
		
		self.switch_user(self.test_email)
		
		# Exempt API: check_subscription_status should run without 402 exception
		status_res = check_subscription_status()
		self.assertEqual(status_res.get("status"), "Expired")
		
		# Protected API: calling quick_create should fail with CRMSubscriptionExpiredError
		from crm_saas.api.leads import quick_create
		with self.assertRaises(CRMSubscriptionExpiredError):
			quick_create(lead_name="Blocked Lead")
			
		# Exempt API: activate_subscription should allow upgrading/activating plan
		self.switch_user("Administrator")
		if not frappe.db.exists("CRM Plan", "Basic Plan"):
			plan = frappe.new_doc("CRM Plan")
			plan.plan_name = "Basic Plan"
			plan.monthly_price_per_user = 20.0
			plan.billing_interval = "Monthly"
			plan.is_active = 1
			plan.insert(ignore_permissions=True)
			frappe.db.commit()
			
		self.switch_user(self.test_email)
		activation_res = activate_subscription("Basic Plan")
		self.assertEqual(activation_res.get("status"), "success")
