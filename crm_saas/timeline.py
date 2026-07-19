import frappe
@frappe.whitelist()
def log_activity(reference_doctype, reference_name, activity_type,content,is_private=0):
    doc = frappe.get_doc({
        "doctype":"CRM Activity",
        "reference_doctype":reference_doctype,
        "reference_name":reference_name,
        "activity_type":activity_type,
        "content":content,
        "is_private":is_private
    })
    doc.insert()
    return doc.name
@frappe.whitelist()
def feed(reference_doctype,reference_name):
    filters = {
        "reference_doctype":reference_doctype,
        "reference_name":reference_name
    }
    if not frappe.has_permission("CRM Activity","read"):
        frappe.throw("Not Permitted",frappe.PermissionError)
    activities = frappe.get_all(
        "CRM Activity",
        filters=filters,
        fields=["name","activity_type","content","is_private","creation"]
    )
    return [
        a for a in activities
        if not a.is_private or a.owner == frappe.session.user
    ]