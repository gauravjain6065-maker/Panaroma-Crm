import frappe

def create_trial_plan():
    """
    Creates the 'Trial' CRM Plan if it doesn't already exist.
    """
    if not frappe.db.exists("CRM Plan", "Trial"):
        plan = frappe.get_doc({
            "doctype": "CRM Plan",
            "plan_name": "Trial",
            "monthly_price_per_user": 0.0,
            "billing_interval": "Monthly",
            "is_active": 1
        })
        plan.insert(ignore_permissions=True)
        frappe.db.commit()
        print("SUCCESS: Created 'Trial' CRM Plan.")
    else:
        plan = frappe.get_doc("CRM Plan", "Trial")
        if not plan.is_active:
            plan.is_active = 1
            plan.save(ignore_permissions=True)
            frappe.db.commit()
            print("SUCCESS: Activated existing 'Trial' CRM Plan.")
        else:
            print("INFO: 'Trial' CRM Plan already exists and is active.")

    doc = frappe.get_doc("CRM Plan", "Trial")
    print(f"PLAN_STATUS: name={doc.name}, is_active={doc.is_active}, monthly_price_per_user={doc.monthly_price_per_user}")
    return doc.as_dict()

def execute():
    create_trial_plan()
