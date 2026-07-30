# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, today, add_days
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response
import json
from functools import wraps

class CRMSubscriptionExpiredError(HTTPException):
	"""
	Custom exception indicating that the user's CRM subscription or trial has expired.
	Sets the HTTP status code to 402 (Payment Required) and returns a structured JSON payload
	for the React frontend to reliably capture and handle redirects.
	"""
	code = 402
	description = "Subscription Expired"

	def get_response(self, environ=None):
		response = Response(
			json.dumps({
				"status": "subscription_expired",
				"message": "Your subscription has expired.",
				"subscription_required": True
			}),
			status=402,
			mimetype="application/json"
		)
		return response

class SubscriptionService:
	@staticmethod
	def get_active_subscription(user):
		"""
		Returns the active (Active or Trial) subscription for the user.
		"""
		if not user:
			return None
			
		sub = frappe.db.get_value(
			"CRM Subscription",
			{"user": user, "status": ["in", ["Active", "Trial"]]},
			["name", "plan", "status", "is_trial", "start_date", "end_date"],
			as_dict=True
		)
		return sub

	@staticmethod
	def is_trial_active(user):
		"""
		Checks if the user has an active Trial subscription.
		"""
		sub = SubscriptionService.get_active_subscription(user)
		if sub and sub.is_trial and sub.status == "Trial":
			if sub.end_date and getdate(sub.end_date) >= getdate(today()):
				return True
		return False

	@staticmethod
	def is_subscription_active(user):
		"""
		Checks if the user has any active (trial or paid) subscription.
		"""
		sub = SubscriptionService.get_active_subscription(user)
		if sub:
			if sub.end_date and getdate(sub.end_date) >= getdate(today()):
				return True
		return False

	@staticmethod
	def validate_subscription(user):
		"""
		Validates the user's subscription.
		If expired or inactive, raises CRMSubscriptionExpiredError (HTTP 402).
		"""
		if not user or user in ["Administrator", "Guest"]:
			return True

		# System Managers (internal administrators) have unrestricted access
		if "System Manager" in frappe.get_roles(user):
			return True

		# Only restrict users who have roles associated with the CRM
		if not ("CRM User" in frappe.get_roles(user) or "Sales User" in frappe.get_roles(user)):
			return True

		sub = SubscriptionService.get_active_subscription(user)
		if not sub:
			raise CRMSubscriptionExpiredError()

		# Check expiration date
		if sub.end_date and getdate(sub.end_date) < getdate(today()):
			SubscriptionService.expire_subscription(sub.name)
			raise CRMSubscriptionExpiredError()

		return True

	@staticmethod
	def expire_subscription(subscription_name):
		"""
		Marks a subscription as Expired.
		"""
		frappe.db.set_value("CRM Subscription", subscription_name, "status", "Expired")
		frappe.db.commit()

	@staticmethod
	def activate_subscription(user, plan_name):
		"""
		Activates a paid plan for the user, cancelling existing active ones.
		"""
		if not plan_name:
			frappe.throw(_("Plan name is required."))

		if not frappe.db.exists("CRM Plan", plan_name):
			frappe.throw(_("The requested CRM Plan '{0}' does not exist.").format(plan_name))

		# Cancel existing active/trial subscriptions
		existing_subs = frappe.get_all(
			"CRM Subscription",
			filters={"user": user, "status": ["in", ["Active", "Trial"]]},
			fields=["name"]
		)
		for es in existing_subs:
			frappe.db.set_value("CRM Subscription", es.name, "status", "Cancelled")

		# Create new subscription
		sub = frappe.new_doc("CRM Subscription")
		sub.user = user
		sub.plan = plan_name
		sub.status = "Active"
		sub.is_trial = 0
		sub.start_date = today()
		sub.end_date = add_days(today(), 30) # 30 days cycle
		sub.insert(ignore_permissions=True)
		frappe.db.commit()
		return sub

	@staticmethod
	def create_trial_subscription(user):
		"""
		Creates a 5-day trial subscription for the user.
		"""
		if not frappe.db.exists("CRM Plan", "Trial"):
			plan = frappe.new_doc("CRM Plan")
			plan.plan_name = "Trial"
			plan.monthly_price_per_user = 0.0
			plan.billing_interval = "Monthly"
			plan.is_active = 1
			plan.insert(ignore_permissions=True)
			frappe.db.commit()

		sub = frappe.new_doc("CRM Subscription")
		sub.user = user
		sub.plan = "Trial"
		sub.status = "Trial"
		sub.is_trial = 1
		sub.start_date = today()
		sub.end_date = add_days(today(), 5)
		sub.insert(ignore_permissions=True)
		frappe.db.commit()
		return sub

def require_subscription(func):
	"""
	Reusable decorator to validate subscription before executing an API endpoint.
	"""
	@wraps(func)
	def wrapper(*args, **kwargs):
		SubscriptionService.validate_subscription(frappe.session.user)
		return func(*args, **kwargs)
	return wrapper
