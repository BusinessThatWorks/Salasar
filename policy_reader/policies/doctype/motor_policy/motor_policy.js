// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Motor Policy", {
	refresh(frm) {
		// Add "View Policy Document" button if policy_document is linked
		if (frm.doc.policy_document) {
			frm.add_custom_button(__('View Policy Document'), function() {
				// Open the policy viewer with both IDs
				const url = `/app/policy-file-view?policy_document=${frm.doc.policy_document}&motor_policy=${frm.doc.name}`;
				window.open(url, '_blank');
			}, __('Actions'));
		}
	}
});
