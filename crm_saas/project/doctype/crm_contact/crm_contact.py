import frappe
from frappe.model.document import Document
from crm_saas.crm_saas.utils.normalize import normalize_email, normalize_phone


class CRMContact(Document):
    def validate(self):
        self.email_id = normalize_email(self.email_id)
        self.phone = normalize_phone(self.phone)
        self.mobile_no = normalize_phone(self.mobile_no)
        self.check_permissions_custom()

    def check_permissions_custom(self):
        if self.is_new():
            return
        if not frappe.has_permission(self.doctype, "write", self):
            frappe.throw("Not permitted to modify this record")