# Copyright (c) 2025, Clapgrow Software and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class InsuranceCustomer(Document):
    def before_insert(self):
        self.random_number_customer_code()

    def before_save(self):
        self.check_for_default_values()
        self.check_for_saiba_fields()
        
    def check_for_default_values(self):
        if self.city and not self.location:
            self.location=self.city
        if not self.short_name:
            self.short_name=0
        if not self.vertical:
            self.vertical="RETAIL"
        if not self.customer_category:
            self.customer_category="Small Account"
        if not self.industry_segment:
            self.industry_segment="NA"
        if not self.form_of_organization:
            self.form_of_organization="INDIVIDUAL"  

    def random_number_customer_code(self):
        if not self.customer_code:
            customer_code=frappe.generate_hash(length=5)
            self.customer_code = customer_code
           
        
    def check_for_saiba_fields(self):
        required_fields_for_saiba = {
            "Title": self.title,
            "Customer Name": self.customer_name,
            "Customer Group": self.customer_group,
            "Short Name": self.short_name,
            "Gender": self.gender,
            "DOB/DOI": self.dob_doi,
            "Address": self.address,
            "State": self.state,
            "City": self.city,
            "Country": self.country,
            "Location": self.location,
            "PIN Code": self.pin,
            "Phone No": self.phone_no,
            "Mobile No": self.mobile_no,
            "Email": self.email,
            "Customer PAN": self.customer_pan,
            "Vertical": self.vertical,
            "Industry Segment": self.industry_segment,
            "Form Of Organization": self.form_of_organization,
            "Customer Category": self.customer_category,
            "Branch Code": self.branch_code,
            "POS/REF/MISP Code": self.posrefmisp_code,
            "Customer Aadhaar No":self.customer_aadhaar_no
        }

        missing = [label for label, value in required_fields_for_saiba.items() if not value]

        if missing:
            frappe.throw("The following fields are mandatory to sync with saiba:\n" + "\n".join(f"• {f}" for f in missing))

 