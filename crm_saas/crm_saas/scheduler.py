# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import today
from crm_saas.crm_saas.services.subscription_service import SubscriptionService

def daily_expire_subscriptions():
	"""
	Scheduled daily job to automatically expire subscriptions that have passed their end_date.
	Logs updates and sends email notifications.
	"""
	expired_subs = frappe.get_all(
		"CRM Subscription",
		filters={
			"status": ["in", ["Active", "Trial"]],
			"end_date": ["<", today()]
		},
		fields=["name", "user", "plan", "is_trial"]
	)

	for sub in expired_subs:
		# Update status to Expired via SubscriptionService
		SubscriptionService.expire_subscription(sub.name)
		
		# Build renewal notifications
		subject = _("Your CRM Trial has Expired") if sub.is_trial else _("Your CRM Subscription has Expired")
		message = _("Your subscription/trial to plan '{0}' has expired on {1}. Please renew or choose a plan to restore access.").format(
			sub.plan, today()
		)
		
		# Log the event
		frappe.log_error(
			title=subject,
			message=f"User: {sub.user}\nSubscription: {sub.name}\n{message}"
		)
		
		# Send email
		if frappe.db.exists("User", sub.user):
			try:
				frappe.sendmail(
					recipients=sub.user,
					subject=subject,
					message=message,
					delayed=False
				)
			except Exception as mail_err:
				frappe.log_error(
					title="Failed to send subscription expiration email",
					message=f"Failed to send email to {sub.user}: {str(mail_err)}"
				)
