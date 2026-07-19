import frappe
@frappe.whitelist()
def find_candidates():
    leads = frappe.get_all("Leads",fields=["name","email_id","phone"])
    candidates = []
    return candidates
cd