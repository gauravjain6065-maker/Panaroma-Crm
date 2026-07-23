import frappe
from frappe.model.document import Document
from panorama_crm.panorama_crm.utils.normalize import normalize_email, normalize_phone
class CRMLead(Document):
    def validate(self):
        self.email = normalize_email(self.email)
        self.phone = normalize_phone(self.phone)
        self.check_permissions_custom()

    def check_permissions_custom(self):
        if self.is_new():
            return
        if not frappe.has_permission(self.doctype, "write", self):
            frappe.throw("Not permitted to modify this record")