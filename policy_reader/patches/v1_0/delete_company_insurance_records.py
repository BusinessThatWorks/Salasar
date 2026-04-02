import frappe
# patch for deleteing all the documents in the doctype Insurance Company Branch
def execute():
    frappe.db.delete("Insurance Company Branch")

