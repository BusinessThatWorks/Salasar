// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on('Policy Reader Settings', {
	test_saiba_connection: function(frm) {
		// Check if SAIBA is enabled
		if (!frm.doc.saiba_enabled) {
			frappe.msgprint({
				title: __('SAIBA Not Enabled'),
				message: __('Please enable SAIBA integration first.'),
				indicator: 'orange'
			});
			return;
		}

		// Check if credentials are filled
		if (!frm.doc.saiba_base_url || !frm.doc.saiba_username || !frm.doc.saiba_password) {
			frappe.msgprint({
				title: __('Missing Credentials'),
				message: __('Please fill in Base URL, Username, and Password before testing.'),
				indicator: 'orange'
			});
			return;
		}

		// Save the document first if it has unsaved changes
		if (frm.is_dirty()) {
			frappe.msgprint({
				title: __('Unsaved Changes'),
				message: __('Please save the document before testing the connection.'),
				indicator: 'orange'
			});
			return;
		}

		frappe.call({
			method: 'test_saiba_connection',
			doc: frm.doc,
			freeze: true,
			freeze_message: __('Testing SAIBA Connection...'),
			callback: function(r) {
				if (r.message) {
					if (r.message.success) {
						frappe.msgprint({
							title: __('Connection Successful'),
							message: r.message.message || __('Successfully connected to SAIBA API'),
							indicator: 'green'
						});
					} else {
						frappe.msgprint({
							title: __('Connection Failed'),
							message: r.message.error || __('Failed to connect to SAIBA API'),
							indicator: 'red'
						});
					}
				}
				frm.reload_doc();
			},
			error: function(r) {
				frappe.msgprint({
					title: __('Error'),
					message: __('An error occurred while testing the connection. Please check the console for details.'),
					indicator: 'red'
				});
				console.error('SAIBA connection test error:', r);
			}
		});
	},
	
	refresh_field_mappings: function(frm) {
		frappe.call({
			method: 'refresh_field_mappings',
			doc: frm.doc,
			freeze: true,
			freeze_message: __('Refreshing Field Mappings...'),
			callback: function(r) {
				frm.refresh();
			}
		});
	},
	
	refresh_extraction_prompts: function(frm) {
		frappe.call({
			method: 'refresh_extraction_prompts',
			doc: frm.doc,
			freeze: true,
			freeze_message: __('Refreshing Extraction Prompts...'),
			callback: function(r) {
				frm.refresh();
			}
		});
	}
});
