# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import os
import sys
import json
import traceback
import subprocess
import frappe
from frappe import _

# Function to retrieve logger dynamically to avoid import-time path issues
def get_logger():
	return frappe.logger("crm_saas")

def get_sites_path() -> str:
	"""
	Get the absolute path to the sites directory relative to the bench path.
	"""
	return os.path.join(frappe.utils.get_bench_path(), "sites")

def run_bench_command(args: list) -> str:
	"""
	Helper function to run bench subcommands dynamically.
	Uses the active virtualenv python executable and sets the working directory
	to the sites folder to ensure apps.txt and configuration are found.
	"""
	logger = get_logger()
	sites_path = get_sites_path()
	python_bin = sys.executable
	
	# Execute bench command using bench_helper entry point
	cmd = [python_bin, "-m", "frappe.utils.bench_helper", "frappe"] + args
	
	logger.info(f"Executing: {' '.join(cmd)}")
	
	result = subprocess.run(
		cmd,
		cwd=sites_path,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		text=True
	)
	
	if result.returncode != 0:
		error_msg = (
			f"Command execution failed: {' '.join(cmd)}\n"
			f"Exit Code: {result.returncode}\n"
			f"Stdout: {result.stdout}\n"
			f"Stderr: {result.stderr}"
		)
		logger.error(error_msg)
		raise subprocess.SubprocessError(error_msg)
		
	return result.stdout

def provision_tenant(provisioning_job_name: str):
	"""
	Internal background worker task to provision a new tenant site.
	"""
	logger = get_logger()
	if not frappe.db.exists("Provisioning Job", provisioning_job_name):
		logger.error(f"Provisioning Job '{provisioning_job_name}' does not exist in the database.")
		return

	job = frappe.get_doc("Provisioning Job", provisioning_job_name)
	job.status = "Running"
	job.started_on = frappe.utils.now_datetime()
	job.save(ignore_permissions=True)
	frappe.db.commit()

	tenant = frappe.get_doc("CRM Tenant", job.tenant)
	site_name = tenant.site_name

	logger.info(f"Starting provisioning for site '{site_name}' under job '{provisioning_job_name}'.")

	try:
		# 1. Fetch DB Root Password dynamically
		db_root_password = frappe.conf.get("db_root_password")
		if not db_root_password:
			sites_path = get_sites_path()
			common_config_path = os.path.join(sites_path, "common_site_config.json")
			if os.path.exists(common_config_path):
				with open(common_config_path, "r") as f:
					common_config = json.load(f)
					db_root_password = common_config.get("db_root_password")
		
		if not db_root_password:
			raise ValueError("db_root_password is not configured in common_site_config.json.")

		admin_password = "admin" # Default admin password for trials

		# 2. Create the site (using --force to allow retrying clean site builds)
		run_bench_command([
			"new-site", site_name,
			"--db-root-username", "root",
			"--db-root-password", db_root_password,
			"--admin-password", admin_password,
			"--force"
		])

		# Extract database name dynamically from the newly created site's config
		site_config_path = os.path.join(get_sites_path(), site_name, "site_config.json")
		db_name = ""
		if os.path.exists(site_config_path):
			with open(site_config_path, "r") as f:
				config_data = json.load(f)
				db_name = config_data.get("db_name", "")

		# Save database name to Master Tenant record
		tenant.db_name = db_name
		tenant.save(ignore_permissions=True)
		frappe.db.commit()

		# 3. Install crm_saas app on the tenant site
		run_bench_command(["--site", site_name, "install-app", "crm_saas"])

		# 4. Migrate the tenant site
		run_bench_command(["--site", site_name, "migrate"])

		# 5. Initialize administrator profile and seed welcome data safely via kwargs
		init_kwargs = repr({
			"email": tenant.email,
			"company_name": tenant.company_name
		})
		run_bench_command([
			"--site", site_name,
			"execute", "crm_saas.api.provisioning.initialize_tenant_site",
			"--kwargs", init_kwargs
		])

		# 6. Mark Job and Tenant as successful
		job.status = "Success"
		job.completed_on = frappe.utils.now_datetime()
		job.save(ignore_permissions=True)

		tenant.status = "Active"
		tenant.save(ignore_permissions=True)
		
		frappe.db.commit()
		logger.info(f"Successfully provisioned site '{site_name}' for tenant '{tenant.name}'.")

	except Exception as e:
		frappe.db.rollback()
		tb = traceback.format_exc()
		
		job.status = "Failed"
		job.completed_on = frappe.utils.now_datetime()
		job.traceback = tb
		job.save(ignore_permissions=True)

		tenant.status = "Requested" # Revert to allow retry
		tenant.save(ignore_permissions=True)
		
		frappe.db.commit()
		
		logger.error(f"Provisioning failed for site '{site_name}' in job '{provisioning_job_name}': {tb}")

def initialize_tenant_site(email: str, company_name: str):
	"""
	Safe initialization method executed in the context of the tenant site.
	Saves user details and seeds initial welcome data.
	"""
	# 1. Update the default Administrator User info
	if frappe.db.exists("User", "Administrator"):
		admin = frappe.get_doc("User", "Administrator")
		admin.email = email
		admin.first_name = company_name
		admin.save(ignore_permissions=True)
		
	# 2. Seed a welcome Lead if the Lead DocType exists
	if frappe.db.exists("DocType", "Lead"):
		lead = frappe.new_doc("Lead")
		lead.lead_name = "Welcome Lead"
		lead.company_name = company_name
		lead.email_id = email
		lead.status = "Lead"
		lead.insert(ignore_permissions=True)
		
	frappe.db.commit()

@frappe.whitelist()
def retry_provisioning(job_name: str) -> dict:
	"""
	Whitelisted API endpoint to retry a failed provisioning job.
	Resets the status of the job and tenant, then re-enqueues the worker.
	"""
	if not frappe.db.exists("Provisioning Job", job_name):
		frappe.throw(
			_("Provisioning Job '{0}' does not exist.").format(job_name),
			frappe.DoesNotExistError
		)

	job = frappe.get_doc("Provisioning Job", job_name)
	
	# Only failed jobs should be retried
	if job.status != "Failed":
		frappe.throw(
			_("Only failed provisioning jobs can be retried. Current job status: {0}").format(job.status),
			frappe.ValidationError
		)

	# Reset Job document fields
	job.status = "Requested"
	job.traceback = None
	job.started_on = None
	job.completed_on = None
	job.save(ignore_permissions=True)

	# Ensure the Tenant status is reset to Requested
	tenant = frappe.get_doc("CRM Tenant", job.tenant)
	tenant.status = "Requested"
	tenant.save(ignore_permissions=True)

	frappe.db.commit()

	# Re-enqueue the provisioning background worker
	frappe.enqueue(
		"crm_saas.api.provisioning.provision_tenant",
		queue="default",
		timeout=600,
		is_async=True,
		provisioning_job_name=job.name
	)

	return {
		"status": "success",
		"message": _("Provisioning job '{0}' has been reset and re-enqueued.").format(job_name),
		"job": job.name
	}

