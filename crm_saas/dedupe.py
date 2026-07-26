import frappe
try:
    from crm_saas.crm_saas.utils import get_domain
except ImportError:
    from crm_saas.utils import get_domain

@frappe.whitelist()
def find_candidates(doctype="CRM Lead"):
    if not frappe.has_permission(doctype, "read"):
        frappe.throw("Not permitted", frappe.PermissionError)

    records = frappe.get_all(doctype, fields=["name", "email", "phone"])

    candidates = []
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            a, b = records[i], records[j]
            score = 0
            matched_on = []

            email_a = (a.email or "").strip().lower()
            email_b = (b.email or "").strip().lower()
            phone_a = (a.phone or "").strip()
            phone_b = (b.phone or "").strip()

            if email_a and email_a == email_b:
                score += 0.5
                matched_on.append("email")

            if phone_a and phone_a == phone_b:
                score += 0.4
                matched_on.append("phone")

            domain_a, domain_b = get_domain(email_a), get_domain(email_b)
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
            "reference_doctype": doctype,
            "record_1": c["record_1"],
            "record_2": c["record_2"],
            "match_score": c["match_score"],
            "matched_on": c["matched_on"],
            "status": "Pending"
        }).insert(ignore_permissions=True)

    return candidates