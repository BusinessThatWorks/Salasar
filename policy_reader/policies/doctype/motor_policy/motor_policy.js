// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Motor Policy", {
	refresh(frm) {
		// Set type_of_vehicle based on policy_type on load
		set_type_of_vehicle(frm);
	},

	policy_type(frm) {
		// Auto-set type_of_vehicle when policy_type changes
		set_type_of_vehicle(frm);
	},

	onload(frm) {
		// Add "View Policy Document" button if policy_document is linked
		if (frm.doc.policy_document) {
			frm.add_custom_button(__('View Policy Document'), function() {
				// Open the policy viewer with both IDs
				const url = `/app/policy-file-view?policy_document=${frm.doc.policy_document}&motor_policy=${frm.doc.name}`;
				window.open(url, '_blank');
			}, __('Actions'));
		}

		// Add "Populate Fields" button if policy_document is linked
		if (frm.doc.policy_document && !frm.doc.__islocal) {
			frm.add_custom_button(__('Populate Fields'), function() {
				populate_motor_policy_fields(frm);
			}, __('Actions'));
		}
	}
});

function set_type_of_vehicle(frm) {
	// Auto-set type_of_vehicle based on policy_type
	// If "Motor Commercial Car" is selected → "COMMERCIAL"
	// Otherwise (Motor Private Car, Two Wheeler, etc.) → "PRIVATE"
	let policy_type = frm.doc.policy_type || '';

	if (policy_type.toLowerCase().includes('commercial')) {
		frm.set_value('type_of_vehicle', 'COMMERCIAL');
	} else if (policy_type) {
		// Only set to Private if a policy_type is actually selected
		frm.set_value('type_of_vehicle', 'PRIVATE');
	}
}

function populate_motor_policy_fields(frm) {
	// Show loading indicator
	frappe.show_alert({
		message: __('Populating fields from Policy Document...'),
		indicator: 'blue'
	});
	
	// Call server method to populate fields
	frappe.call({
		method: 'populate_fields_from_policy_document',
		doc: frm.doc,
		args: {
			policy_document_name: frm.doc.policy_document
		},
		callback: function(response) {
			// Debug: Output detailed information to browser console
			console.log('=== POPULATE FIELDS DEBUG ===');
			console.log('Full response:', response);
			
			if (response.message) {
				console.log('Response message:', response.message);
				console.log('Error message:', response.message.error);
				
				// Debug specific fields
				if (response.message.debug_matches) {
					console.log('Field matches found:', response.message.debug_matches);
				}
				if (response.message.debug_parsed_keys) {
					console.log('Parsed data keys:', response.message.debug_parsed_keys);
				}
				if (response.message.debug_unmapped) {
					console.log('Unmapped fields:', response.message.debug_unmapped);
				}
			}
			console.log('=== END DEBUG ===');
			
			if (response.message && response.message.success) {
				// Refresh the form to show populated fields
				frm.reload_doc();
				
				frappe.show_alert({
					message: __(`✅ Populated ${response.message.populated_fields} fields successfully!`),
					indicator: 'green'
				});
			} else {
				frappe.show_alert({
					message: __(`❌ Failed to populate fields: ${response.message.error || 'Unknown error'}`),
					indicator: 'red'
				});
			}
		},
		error: function(error) {
			frappe.show_alert({
				message: __('❌ Error populating fields. Please try again.'),
				indicator: 'red'
			});
			console.error('Error populating fields:', error);
		}
	});
}
