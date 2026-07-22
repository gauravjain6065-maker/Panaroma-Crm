# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, today
from crm_saas.utils.helpers import (
	validate_email,
	validate_slug,
	normalize_company_name,
	generate_site_name,
)

@frappe.whitelist(allow_guest=True)
def request_trial(company_name: str, email: str, plan: str, slug: str) -> dict:
	"""
	Whitelisted API endpoint to request a trial tenant.
	Creates CRM Tenant, CRM Subscription, and Provisioning Job,
	then enqueues the provisioning background worker.
	"""
	# 1. Validate required fields presence
	if not all([company_name, email, plan, slug]):
		frappe.throw(
			_("All fields (company_name, email, plan, slug) are required."),
			frappe.ValidationError
		)

	# Normalize fields
	company_name = normalize_company_name(company_name)
	email = email.strip().lower()
	slug = slug.strip().lower()
	plan = plan.strip()

	# Re-check empty after normalization
	if not all([company_name, email, plan, slug]):
		frappe.throw(
			_("All fields (company_name, email, plan, slug) must contain non-empty data."),
			frappe.ValidationError
		)

	# 2. Validate email format
	if not validate_email(email):
		frappe.throw(_("Invalid email format."), frappe.ValidationError)

	# 3. Validate slug format
	if not validate_slug(slug):
		frappe.throw(
			_("Invalid slug format. Slugs can only contain lowercase alphanumeric characters and single hyphens (no leading or trailing hyphens)."),
			frappe.ValidationError
		)

	# 4. Check duplicate slug in CRM Tenant
	if frappe.db.exists("CRM Tenant", {"slug": slug}):
		frappe.throw(
			_("Slug '{0}' is already taken. Please choose another slug.").format(slug),
			frappe.ValidationError
		)

	# 5. Fetch and validate CRM Plan
	if not frappe.db.exists("CRM Plan", plan):
		frappe.throw(_("The requested CRM Plan '{0}' does not exist.").format(plan), frappe.ValidationError)

	plan_doc = frappe.get_doc("CRM Plan", plan)
	if not plan_doc.is_active:
		frappe.throw(_("The CRM Plan '{0}' is not active.").format(plan), frappe.ValidationError)

	# Create documents inside a try-except block for transaction safety
	try:
		# 6. Create CRM Tenant
		tenant = frappe.new_doc("CRM Tenant")
		tenant.company_name = company_name
		tenant.email = email
		tenant.slug = slug
		tenant.site_name = generate_site_name(slug)
		tenant.status = "Requested"
		tenant.insert(ignore_permissions=True)

		# 7. Create CRM Subscription
		subscription = frappe.new_doc("CRM Subscription")
		subscription.tenant = tenant.name
		subscription.plan = plan
		subscription.status = "Trial"
		subscription.start_date = today()
		subscription.end_date = add_days(today(), 14) # Default 14-day trial
		subscription.insert(ignore_permissions=True)

		# 8. Create Provisioning Job
		job = frappe.new_doc("Provisioning Job")
		job.tenant = tenant.name
		job.status = "Requested"
		job.insert(ignore_permissions=True)

		# 9. Commit database transaction to persist records
		frappe.db.commit()

		# 10. Enqueue background worker for provisioning
		frappe.enqueue(
			"crm_saas.api.provisioning.provision_tenant",
			queue="default",
			timeout=600,
			is_async=True,
			job_name=job.name
		)

		# 11. Return proper JSON success response
		return {
			"status": "success",
			"message": _("Trial request received successfully. Site provisioning started."),
			"tenant": tenant.name,
			"subscription": subscription.name,
			"job": job.name
		}

	except Exception as e:
		# Rollback transaction on failure
		frappe.db.rollback()
		frappe.log_error(message=frappe.get_traceback(), title="request_trial_failed")
		frappe.throw(
			_("An error occurred while processing your trial request: {0}").format(str(e)),
			frappe.ValidationError
		)

@frappe.whitelist(allow_guest=True)
def check_slug(slug: str) -> dict:
	"""
	Whitelisted API endpoint to check if a slug is available for site creation.
	Returns {"available": True} if vacant, else {"available": False}.
	"""
	if not slug:
		return {
			"available": False,
			"message": _("Slug cannot be empty.")
		}

	slug = slug.strip().lower()

	# Validate format
	if not validate_slug(slug):
		return {
			"available": False,
			"message": _("Invalid slug format. Slugs can only contain lowercase alphanumeric characters and single hyphens.")
		}

	# Check existence in database
	if frappe.db.exists("CRM Tenant", {"slug": slug}):
		return {
			"available": False,
			"message": _("Slug is already taken.")
		}

	return {
		"available": True
	}

