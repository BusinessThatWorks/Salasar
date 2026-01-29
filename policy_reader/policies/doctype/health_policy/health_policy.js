// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Health Policy", {
	refresh(frm) {
		// Add "View Policy Document" button if policy_document is linked
		if (frm.doc.policy_document) {
			frm.add_custom_button(__('View Policy Document'), function() {
				// Open the policy viewer with both IDs
				const url = `/app/policy-file-view?policy_document=${frm.doc.policy_document}&health_policy=${frm.doc.name}`;
				window.open(url, '_blank');
			}, __('Actions'));
		}

		// Add "Populate Fields" button if policy_document is linked
		if (frm.doc.policy_document && !frm.doc.__islocal) {
			frm.add_custom_button(__('Populate Fields'), function() {
				populate_health_policy_fields(frm);
			}, __('Actions'));
		}

		// Add SAIBA buttons (sync + validation)
		if (!frm.doc.__islocal) {
			add_saiba_sync_button_health(frm);
			// Add SAIBA validation button (uses shared function from saiba_validation.js)
			if (typeof policy_reader !== 'undefined' && policy_reader.saiba) {
				policy_reader.saiba.add_validate_button(frm, 'Health');
			}
		}
	}
});

function populate_health_policy_fields(frm) {
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
			console.log('=== POPULATE HEALTH POLICY FIELDS DEBUG ===');
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
			console.error('Error populating health policy fields:', error);
		}
	});
}

function add_saiba_sync_button_health(frm) {
	// Check if SAIBA sync is enabled in settings
	frappe.db.get_single_value('Policy Reader Settings', 'saiba_enabled').then(enabled => {
		if (!enabled) {
			return;
		}

		// Add sync button
		frm.add_custom_button(__('Sync to SAIBA'), function() {
			sync_health_policy_to_saiba(frm);
		}, __('Actions'));

		// Update button color based on sync status
		update_saiba_button_indicator_health(frm);
	});
}

function update_saiba_button_indicator_health(frm) {
	// Add visual indicator based on sync status
	const status = frm.doc.saiba_sync_status;
	let indicator = '';

	switch(status) {
		case 'Synced':
			indicator = 'green';
			break;
		case 'Failed':
			indicator = 'red';
			break;
		case 'Pending':
			indicator = 'orange';
			break;
		default:
			indicator = 'gray';
	}

	// Update the page indicator
	if (status && status !== 'Not Synced') {
		frm.page.set_indicator(status, indicator);
	}
}

function sync_health_policy_to_saiba(frm) {
	// Confirm before syncing
	frappe.confirm(
		__('Are you sure you want to sync this Health Policy to SAIBA?'),
		function() {
			// Yes - proceed with sync
			frappe.show_alert({
				message: __('Syncing to SAIBA...'),
				indicator: 'blue'
			});

			frappe.call({
				method: 'policy_reader.policy_reader.services.saiba_sync_service.sync_health_policy',
				args: {
					policy_name: frm.doc.name
				},
				callback: function(response) {
					if (response.message && response.message.success) {
						frappe.show_alert({
							message: __('Successfully synced to SAIBA. Control Number: {0}', [response.message.control_number || 'N/A']),
							indicator: 'green'
						});
						frm.reload_doc();
					} else {
						frappe.show_alert({
							message: __('Sync failed: {0}', [response.message.error || 'Unknown error']),
							indicator: 'red'
						});
						frm.reload_doc();
					}
				},
				error: function(error) {
					frappe.show_alert({
						message: __('Error syncing to SAIBA. Please try again.'),
						indicator: 'red'
					});
					console.error('SAIBA sync error:', error);
					frm.reload_doc();
				}
			});
		}
	);
}
