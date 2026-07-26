# Copyright (c) 2026, Interns and contributors
# For license information, please see license.txt

import re
import frappe

def validate_email(email: str) -> bool:
	"""
	Validates the format of an email address.
	"""
	if not email:
		return False
	# Standard email regex pattern
	regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
	return bool(re.match(regex, email))

def validate_slug(slug: str) -> bool:
	"""
	Validates the slug format.
	Allows only lowercase letters, numbers, and single hyphens.
	Must start and end with a letter or number.
	"""
	if not slug:
		return False
	# Regex for slug (lowercase, numbers, single hyphens, no double hyphens or leading/trailing hyphens)
	regex = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
	return bool(re.match(regex, slug))

def normalize_company_name(name: str) -> str:
	"""
	Normalizes the company name by removing leading and trailing whitespaces.
	"""
	if not name:
		return ""
	return name.strip()

def generate_site_name(slug: str) -> str:
	"""
	Generates the target site name for the tenant.
	Uses the base domain if configured in site_config, otherwise defaults to local.
	"""
	if not slug:
		return ""
	base_domain = frappe.conf.get("base_domain") or "local"
	return f"{slug}.{base_domain}"
