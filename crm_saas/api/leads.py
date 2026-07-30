import frappe
from frappe import _
from crm_saas.crm_saas.utils.normalize import normalize_email, normalize_phone
from crm_saas.crm_saas.services.subscription_service import require_subscription


@frappe.whitelist()
@require_subscription
def quick_create(lead_name, organization_name=None, email=None, phone=None,
                  source="Website", next_followup_date=None, create_followup_task=False):

    if not lead_name:
        frappe.throw(_("Lead name is required"))

    norm_email = normalize_email(email)
    norm_phone = normalize_phone(phone)

    # Find duplicate candidates before saving
    candidates = []
    if norm_phone:
        matches = frappe.get_all("CRM Lead", filters={"phone": norm_phone}, fields=["name"])
        for m in matches:
            candidates.append({"doctype": "CRM Lead", "name": m.name, "reason": "phone", "score": 95})

    if norm_email:
        matches = frappe.get_all("CRM Lead", filters={"email": norm_email}, fields=["name"])
        for m in matches:
            if not any(c["name"] == m.name for c in candidates):
                candidates.append({"doctype": "CRM Lead", "name": m.name, "reason": "email", "score": 90})

    # Create the lead
    lead = frappe.new_doc("CRM Lead")
    lead.lead_name = lead_name
    lead.organization_name = organization_name
    lead.email = email
    lead.phone = phone
    lead.source = source
    lead.status = "New"
    lead.lead_owner = frappe.session.user
    lead.next_followup_date = next_followup_date
    lead.insert()

    # Optional follow-up task
    task = None
    if int(create_followup_task or 0):
        task = frappe.new_doc("ToDo")
        task.description = f"Follow up with {lead.lead_name}"
        task.reference_type = "CRM Lead"
        task.reference_name = lead.name
        task.date = next_followup_date or frappe.utils.add_days(frappe.utils.nowdate(), 1)
        task.allocated_to = frappe.session.user
        task.insert()

    return {
        "lead": lead.name,
        "duplicate_warning": len(candidates) > 0,
        "candidates": candidates,
        "task": task.name if task else None
    }