# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from crm_saas.api.signup import signup as signup_api
from crm_saas.crm_saas.services.subscription_service import SubscriptionService

@frappe.whitelist(allow_guest=True)
def signup(company_name=None, email=None, password=None, companyName=None, **kwargs):
	"""
	Wrapper endpoint for signup that routes to signup_api.
	"""
	return signup_api(
		company_name=company_name or companyName,
		email=email,
		password=password,
		**kwargs
	)

@frappe.whitelist()
def check_subscription_status() -> dict:
	"""
	Whitelisted API endpoint to check the subscription status of the current user.
	"""
	user = frappe.session.user
	if user in ["Administrator", "Guest"]:
		return {
			"status": "Active",
			"is_trial": 0,
			"plan": "System",
			"end_date": None
		}

	sub = SubscriptionService.get_active_subscription(user)
	if not sub:
		return {
			"status": "Expired",
			"message": _("No active subscription found. Please subscribe to a plan to continue.")
		}

	# Run a validation check to automatically handle expirations
	try:
		SubscriptionService.validate_subscription(user)
	except Exception:
		# Subscription validation expired it in database, re-fetch status
		sub = SubscriptionService.get_active_subscription(user)
		if not sub:
			return {
				"status": "Expired",
				"message": _("Your subscription or trial has expired.")
			}

	return sub

@frappe.whitelist()
def activate_subscription(plan_name: str) -> dict:
	"""
	Whitelisted endpoint to mock successful payment and activate a paid plan.
	Delegates subscription update and activation logic to SubscriptionService.
	"""
	user = frappe.session.user
	if user in ["Administrator", "Guest"]:
		frappe.throw(_("Administrator or Guest cannot activate commercial plans."))

	sub = SubscriptionService.activate_subscription(user, plan_name)

	return {
		"status": "success",
		"message": _("Subscription to plan '{0}' activated successfully.").format(plan_name),
		"subscription": sub.name,
		"end_date": sub.end_date
	}