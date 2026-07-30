# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import frappe

def execute():
	"""
	Idempotent migration patch to safely delete obsolete DocTypes from the database:
	- CRM Tenant
	- Provisioning Job
	- Bench Cluster
	"""
	doctypes_to_remove = ["CRM Tenant", "Provisioning Job", "Bench Cluster"]
	
	for doctype in doctypes_to_remove:
		if frappe.db.exists("DocType", doctype):
			try:
				# Force delete the DocType document and its nested fields/permissions
				frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True, ignore_missing=True)
				print(f"SUCCESS: Deleted DocType metadata for '{doctype}'")
			except Exception as e:
				frappe.log_error(
					title=f"Failed to delete DocType metadata for {doctype} in migration patch",
					message=frappe.get_traceback()
				)

			# Safely drop the associated database table
			table_name = f"tab{doctype}"
			try:
				frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{table_name}`")
				print(f"SUCCESS: Dropped database table '{table_name}'")
			except Exception as e:
				frappe.log_error(
					title=f"Failed to drop table {table_name} in migration patch",
					message=frappe.get_traceback()
				)

	# Clean up leftover references across metadata tables
	for doctype in doctypes_to_remove:
		# Delete custom fields created on or pointing to the DocType
		frappe.db.delete("Custom Field", {"dt": doctype})
		frappe.db.delete("Custom Field", {"options": doctype})
		
		# Delete property setters
		frappe.db.delete("Property Setter", {"doc_type": doctype})
		
		# Delete Custom DocPerms
		frappe.db.delete("Custom DocPerm", {"parent": doctype})
		
		# Delete User Permissions
		frappe.db.delete("User Permission", {"allow": doctype})

	frappe.db.commit()
	frappe.clear_cache()
