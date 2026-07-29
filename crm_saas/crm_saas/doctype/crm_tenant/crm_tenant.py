# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from crm_saas.utils.helpers import generate_site_name

class CRMTenant(Document):
	def validate(self):
		# Sync legacy slug field with tenant_slug
		if not self.tenant_slug and self.slug:
			self.tenant_slug = self.slug
		elif not self.slug and self.tenant_slug:
			self.slug = self.tenant_slug

		if self.tenant_slug:
			site_name = generate_site_name(self.tenant_slug)
			self.site_name = site_name
			self.primary_domain = site_name
