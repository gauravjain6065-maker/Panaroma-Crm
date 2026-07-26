<<<<<<< HEAD
<<<<<<< HEAD
# Copyright (c) 2026, Yash Dubey and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class CRMOrganization(Document):
	pass
=======
=======
>>>>>>> cbae17b2db5641c5d9d02e72f8f72044c1c68773
import frappe
from frappe.model.document import Document
from crm_saas.crm_saas.utils.normalize import normalize_email, normalize_phone


class CRMOrganization(Document):
	def validate(self):
		self.email = normalize_email(self.email)
		self.phone = normalize_phone(self.phone)
		self.check_permissions_custom()

	def check_permissions_custom(self):
		if self.is_new():
			return
		if not frappe.has_permission(self.doctype, "write", self):
			frappe.throw("Not permitted to modify this record")
<<<<<<< HEAD
>>>>>>> origin/develop
=======
>>>>>>> cbae17b2db5641c5d9d02e72f8f72044c1c68773
