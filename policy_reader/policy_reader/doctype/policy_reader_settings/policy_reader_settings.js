// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Policy Reader Settings", {
	refresh(frm) {
		// Add custom button handler for Test RunPod Connection
		frm.add_custom_button(__('Test RunPod Connection'), function() {
			frm.trigger('test_runpod_connection');
		}, __('Actions'));
	},
	
	test_runpod_connection(frm) {
		// Show loading state
		frm.dashboard.add_comment(__('Testing RunPod connection...'), 'blue', true);
		
		// Call the test method
		frm.call('test_runpod_connection').then(r => {
			if (r.message && r.message.status === 'healthy') {
				frm.dashboard.add_comment(__('✅ RunPod API is healthy!'), 'green', true);
			} else {
				frm.dashboard.add_comment(__('❌ RunPod API test failed'), 'red', true);
			}
			// Reload to show updated health status
			frm.reload_doc();
		}).catch(err => {
			frm.dashboard.add_comment(__('❌ RunPod test error: {0}', [err.message]), 'red', true);
		});
	}
});
