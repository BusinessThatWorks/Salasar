import frappe
def execute():
    ie = frappe.get_all("Insurance Employee", pluck = "name")
    for row in ie:
        if row.strip('""') != row:
            frappe.rename_doc("Insurance Employee", row, row.strip('""'))