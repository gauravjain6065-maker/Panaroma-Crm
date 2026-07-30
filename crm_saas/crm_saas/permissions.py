# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from crm_saas.crm_saas.services.subscription_service import SubscriptionService

def get_permission_query_conditions(user, doctype=None):
	"""
	Native Frappe hook to inject custom row-level security SQL query.
	Restricts normal users to only see records they created (owner = user).
	"""
	if not user:
		user = frappe.session.user

	if "Administrator" in frappe.get_roles(user) or "System Manager" in frappe.get_roles(user):
		return ""

	# Check subscription/trial validity (raises CRMSubscriptionExpiredError if inactive)
	SubscriptionService.validate_subscription(user)

	# Restrict to records owned by the user
	return f"`tab{doctype}`.owner = {frappe.db.escape(user)}"

def has_permission(doc, ptype=None, user=None):
	"""
	Native Frappe hook to validate individual document permissions.
	Restricts normal users to only perform CRUD on records they created.
	"""
	if not user:
		user = frappe.session.user

	if "Administrator" in frappe.get_roles(user) or "System Manager" in frappe.get_roles(user):
		return True

	# Validate subscription
	SubscriptionService.validate_subscription(user)

	# Row-level check: User must own the record
	return doc.owner == user

def before_request():
	"""
	Hook executed before every request to validate subscription.
	Only validates protected routes (CRM REST APIs or whitelisted CRM endpoints).
	"""
	user = frappe.session.user
	if user in ["Administrator", "Guest"]:
		return

	# Determine if this is a protected CRM resource/endpoint
	is_protected = False

	# 1. Check REST resource requests
	if frappe.request and frappe.request.path.startswith("/api/resource/"):
		parts = frappe.request.path.split("/")
		if len(parts) >= 4:
			doctype = parts[3]
			if doctype in ["CRM Lead", "CRM Contact", "CRM Organization", "CRM Activity", "CRM Subscription", "CRM Plan"]:
				is_protected = True

	# 2. Check whitelisted custom endpoints (except subscription status, activation, and auth/signup)
	cmd = frappe.form_dict.get("cmd")
	if cmd:
		crm_exemptions = [
			"crm_saas.api.auth.check_subscription_status",
			"crm_saas.api.auth.activate_subscription",
			"crm_saas.api.auth.signup",
			"crm_saas.api.signup.signup"
		]
		if cmd.startswith("crm_saas.") and cmd not in crm_exemptions:
			is_protected = True

	if is_protected:
		SubscriptionService.validate_subscription(user)
