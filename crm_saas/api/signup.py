# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.password import update_password
from crm_saas.utils.helpers import validate_email, normalize_company_name
from crm_saas.crm_saas.services.subscription_service import SubscriptionService

@frappe.whitelist(allow_guest=True)
def signup(company_name: str, email: str, password: str, **kwargs) -> dict:
	"""
	Whitelisted API endpoint to register a new user on a single master site.
	Creates User and automatically activates a 5-day Free Trial subscription.
	"""
	# 1. Validate required fields
	if not all([company_name, email, password]):
		frappe.throw(
			_("All fields (company_name, email, password) are required."),
			frappe.ValidationError
		)

	# Normalize fields
	company_name = normalize_company_name(company_name)
	email = email.strip().lower()

	if not all([company_name, email, password]):
		frappe.throw(
			_("All fields must contain non-empty data."),
			frappe.ValidationError
		)

	# 2. Validate email format
	if not validate_email(email):
		frappe.throw(_("Invalid email format."), frappe.ValidationError)

	# 3. Validate password length
	if len(password) < 8:
		frappe.throw(_("Password must be at least 8 characters long."), frappe.ValidationError)

	# 4. Check if User already exists
	if frappe.db.exists("User", email):
		frappe.throw(_("User with email '{0}' already exists.").format(email), frappe.ValidationError)

	try:
		# 5. Ensure CRM User role exists
		if not frappe.db.exists("Role", "CRM User"):
			role_doc = frappe.new_doc("Role")
			role_doc.role_name = "CRM User"
			role_doc.desk_access = 1
			role_doc.insert(ignore_permissions=True)

		# 6. Create User document
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = company_name
		user.send_welcome_email = 0
		user.enabled = 1
		user.user_type = "System User"
		user.append("roles", {"role": "CRM User"})
		user.insert(ignore_permissions=True)

		# Securely update password
		update_password(user.name, password)

		# 7. Create 5-day Trial Subscription via Service
		subscription = SubscriptionService.create_trial_subscription(user.name)

		return {
			"status": "success",
			"message": _("Registration successful. Your 5-day free trial has been activated."),
			"user": user.name,
			"subscription": subscription.name,
			"trial_end_date": subscription.end_date
		}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(message=frappe.get_traceback(), title="signup_failed")
		frappe.throw(
			_("An error occurred during registration: {0}").format(str(e)),
			frappe.ValidationError
		)
