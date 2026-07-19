# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CRMActivity(Document):
    def validate(self):
        if not self.reference_doctype or not self.reference_name:
            frappe.throw("Reference Doctype and Reference are Required")

	
