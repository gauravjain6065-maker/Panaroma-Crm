import frappe
from crm_saas.utils import get_domain

@frappe.whitelist()
def find_candidates(doctype="CRM Lead"):
    if not frappe.has_permission(doctype, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)

    records = frappe.get_all(doctype, fields=["name", "normalized_email", "normalized_phone"])

    candidates = []
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            a, b = records[i], records[j]
            score = 0
            matched_on = []

            if a.normalized_email and a.normalized_email == b.normalized_email:
                score += 0.5
                matched_on.append("email")

            if a.normalized_phone and a.normalized_phone == b.normalized_phone:
                score += 0.4
                matched_on.append("phone")

            domain_a, domain_b = get_domain(a.normalized_email), get_domain(b.normalized_email)
            if domain_a and domain_a == domain_b and "email" not in matched_on:
                score += 0.1
                matched_on.append("domain")

            if score > 0:
                candidates.append({
                    "record_1": a.name,
                    "record_2": b.name,
                    "match_score": score,
                    "matched_on": ",".join(matched_on)
                })

    for c in candidates:
        frappe.get_doc({
            "doctype": "CRM Duplicate Candidate",
            "doctype_reference": doctype,
            "record_1": c["record_1"],
            "record_2": c["record_2"],
            "match_score": c["match_score"],
            "matched_on": c["matched_on"],
            "status": "Pending"
        }).insert(ignore_permissions=True)

    return candidates