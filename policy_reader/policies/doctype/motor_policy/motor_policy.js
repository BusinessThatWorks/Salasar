// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt
/* global policy_reader */
frappe.ui.form.on("Motor Policy", {
	refresh(frm) {
		frm.refresh_field("vehicle_info_text");
		if (!frm.doc.payment_mode_1) {
			frm.set_value("payment_mode_1", "Bank Transfer");
		}
		if (!frm.doc.model) {
			frm.set_value("model", "NA");
		}
		if (!frm.doc.variant) {
			frm.set_value("variant", "NA");
		}
		if (!frm.doc.bank_name) {
			frm.set_value("bank_name", "NONE");
		}
		if (!frm.doc.gst) {
			frm.set_value("gst", 18);
		}
		frm.set_value("pos_misp_ref", "YES");
		frm.set_value("policy_enquiry_remarks", "NA");

		// Mark AI fields first so indicators are always visible regardless of status
		if (!frm.doc.__islocal && typeof policy_reader !== "undefined" && policy_reader.saiba) {
			policy_reader.saiba.mark_saiba_ai_fields(frm, "Motor");
		}
		// for enabling users to check ai_extracted_fields manually and then allow them to mark it as approved
		if (!frm.is_new() && frm.doc.approval_status !== "Approved") {
			frm.add_custom_button(
				__("Approve"),
				() => {
					frappe.confirm(
						__("Are you sure you want to approve this Motor Policy?"),
						() => {
							frappe.call({
								method: "sync_motor_policy",
								doc: frm.doc,
								freeze: true,
								callback() {
									frm.reload_doc();
								},
							});
						}
					);
				},
				__("Actions")
			);
		}
		if (frm.doc.vehicle_no && frm.doc.approval_status !== "Approved") {
			const raw = frm.doc.vehicle_no;
			const normalized = raw.toUpperCase().replace(/[\s\-]/g, "");

			if (normalized !== raw) {
				frm.set_value("vehicle_no", normalized);
			}

			if (normalized.length >= 4) {
				const derived_rto = normalized.slice(0, 4);
				if (frm.doc.rto_code !== derived_rto) {
					frm.set_value("rto_code", derived_rto);
				}
			}
		}

		if (frm.doc.vehicle_no && !frm.doc.rto_code) {
			frm.trigger("vehicle_no");
		}
		// Set type_of_vehicle based on policy_type on load
		set_type_of_vehicle(frm);
		frm._rto_code_manual = false;
		// Add SAIBA buttons (sync + validation)
		if (!frm.doc.__islocal && frm.doc.approval_status === "Approved") {
			add_saiba_sync_button(frm);
			// Add SAIBA validation button and field indicators (uses shared functions from saiba_validation.js)
			if (typeof policy_reader !== "undefined" && policy_reader.saiba) {
				policy_reader.saiba.add_validate_button(frm, "Motor");
				policy_reader.saiba.mark_required_fields(frm, "Motor");
			}
		}
	},
	policy_type(frm) {
		// Auto-set type_of_vehicle when policy_type changes
		set_type_of_vehicle(frm);
	},

	rto_code(frm) {
		// if user changed it (not during our scripted set_value), mark as manual
		if (!frm._setting_rto_code) {
			frm._rto_code_manual = true;
		}
	},
	vehicle_no(frm) {
		// debug alert
		console.log("vehicle_no fired ✅", frm.doc.vehicle_no);

		const v = (frm.doc.vehicle_no || "").toUpperCase().replace(/\s+/g, "");
		if (!v) return;

		const rto = v.slice(0, 4);

		if (
			!frm._rto_code_manual &&
			(!frm.doc.rto_code || frm.doc.rto_code === frm._last_auto_rto)
		) {
			frm._setting_rto_code = true;
			frm.set_value("rto_code", rto).then(() => {
				frm._setting_rto_code = false;
				frm._last_auto_rto = rto;
			});
		}
	},
	onload(frm) {
		frm._rto_code_manual = false;
		frm._last_auto_rto = null;
		// Add "View Policy Document" button if policy_document is linked
		if (frm.doc.policy_document) {
			frm.add_custom_button(
				__("View Policy Document"),
				function () {
					// Open the policy viewer with both IDs
					const url = `/app/policy-file-view?policy_document=${frm.doc.policy_document}&motor_policy=${frm.doc.name}`;
					window.open(url, "_blank");
				},
				__("Actions")
			);
		}

		// Add "Populate Fields" button if policy_document is linked
		if (frm.doc.policy_document && !frm.doc.__islocal) {
			frm.add_custom_button(
				__("Populate Fields"),
				function () {
					populate_motor_policy_fields(frm);
				},
				__("Actions")
			);
		}
	},
});

function set_rto_code(frm) {
	let source_value = frm.doc.vehicle_no;
	frappe.show_alert("source_value");
	if (source_value && source_value.length >= 4) {
		// Get the first four characters
		var first_four = source_value.substring(0, 4); // or source_value.slice(0, 4);

		// Set the value of the 'target_field_name'
		// Replace 'target_field_name' with the actual field name of the target field
		frm.set_value("rto_code", first_four);
	} else {
		// Optional: clear the target field if the source value is too short or empty
		frm.set_value("rto_code", "");
	}
}

function set_type_of_vehicle(frm) {
	// Auto-set type_of_vehicle based on policy_type
	// If "Motor Commercial Car" is selected → "COMMERCIAL"
	// Otherwise (Motor Private Car, Two Wheeler, etc.) → "PRIVATE"
	let policy_type = frm.doc.policy_type || "";

	if (policy_type.toLowerCase().includes("commercial")) {
		frm.set_value("type_of_vehicle", "COMMERCIAL");
	} else if (policy_type) {
		// Only set to Private if a policy_type is actually selected
		frm.set_value("type_of_vehicle", "PRIVATE");
	}
}

function populate_motor_policy_fields(frm) {
	// Show loading indicator
	frappe.show_alert({
		message: __("Populating fields from Policy Document..."),
		indicator: "blue",
	});

	// Call server method to populate fields
	frappe.call({
		method: "populate_fields_from_policy_document",
		doc: frm.doc,
		args: {
			policy_document_name: frm.doc.policy_document,
		},
		callback: function (response) {
			// Debug: Output detailed information to browser console
			console.log("=== POPULATE FIELDS DEBUG ===");
			console.log("Full response:", response);

			if (response.message) {
				console.log("Response message:", response.message);
				console.log("Error message:", response.message.error);

				// Debug specific fields
				if (response.message.debug_matches) {
					console.log("Field matches found:", response.message.debug_matches);
				}
				if (response.message.debug_parsed_keys) {
					console.log("Parsed data keys:", response.message.debug_parsed_keys);
				}
				if (response.message.debug_unmapped) {
					console.log("Unmapped fields:", response.message.debug_unmapped);
				}
			}
			console.log("=== END DEBUG ===");

			if (response.message && response.message.success) {
				// Refresh the form to show populated fields
				frm.reload_doc();

				frappe.show_alert({
					message: __(
						`✅ Populated ${response.message.populated_fields} fields successfully!`
					),
					indicator: "green",
				});
			} else {
				frappe.show_alert({
					message: __(
						`❌ Failed to populate fields: ${
							response.message.error || "Unknown error"
						}`
					),
					indicator: "red",
				});
			}
		},
		error: function (error) {
			frappe.show_alert({
				message: __("❌ Error populating fields. Please try again."),
				indicator: "red",
			});
			console.error("Error populating fields:", error);
		},
	});
}

function add_saiba_sync_button(frm) {
	// Check if SAIBA sync is enabled in settings
	frappe.db.get_single_value("Policy Reader Settings", "saiba_enabled").then((enabled) => {
		if (!enabled) {
			return;
		}

		// Add sync button
		frm.add_custom_button(
			__("Sync to SAIBA"),
			function () {
				sync_motor_policy_to_saiba(frm);
			},
			__("Actions")
		);

		// Update button color based on sync status
		update_saiba_button_indicator(frm);
	});
}

function update_saiba_button_indicator(frm) {
	// Add visual indicator based on sync status
	const status = frm.doc.saiba_sync_status;
	let indicator = "";

	switch (status) {
		case "Synced":
			indicator = "green";
			break;
		case "Failed":
			indicator = "red";
			break;
		case "Pending":
			indicator = "orange";
			break;
		default:
			indicator = "gray";
	}

	// Update the page indicator
	if (status && status !== "Not Synced") {
		frm.page.set_indicator(status, indicator);
	}
}

function sync_motor_policy_to_saiba(frm) {
	// Confirm before syncing
	frappe.confirm(__("Are you sure you want to sync this Motor Policy to SAIBA?"), function () {
		// Yes - proceed with sync
		frappe.show_alert({
			message: __("Syncing to SAIBA..."),
			indicator: "blue",
		});

		frappe.call({
			method: "policy_reader.policy_reader.services.saiba_sync_service.sync_motor_policy",
			args: {
				policy_name: frm.doc.name,
			},
			callback: function (response) {
				if (response.message && response.message.success) {
					frappe.show_alert({
						message: __("Successfully synced to SAIBA. Control Number: {0}", [
							response.message.control_number || "N/A",
						]),
						indicator: "green",
					});
					frm.reload_doc();
				} else {
					// frappe.show_alert({
					// 	message: __("Sync failed: {0}", [
					// 		response.message.error || "Unknown error",
					// 	]),
					// 	indicator: "red",
					// });
					// frm.reload_doc();
					// clear_saiba_highlights(frm)
					const error_fields = response.message?.error_fields || [];
					error_fields.forEach((fieldname) => highlight_saiba_field(frm, fieldname));

					const validations = response.message?.validations || [];
					frappe.msgprint({
						title: __("❌ SAIBA Sync Failed"),
						message: validations.length
							? validations.join("<br>")
							: response.message?.error || "Unknown error",
						indicator: "red",
					});
					frm.reload_doc();
				}
			},
			error: function (error) {
				frappe.show_alert({
					message: __("Error syncing to SAIBA. Please try again."),
					indicator: "red",
				});
				console.error("SAIBA sync error:", error);
				frm.reload_doc();
			},
		});
	});
}

function highlight_saiba_field(frm, fieldname) {
	const field = frm.fields_dict[fieldname];
	if (!field || !field.$wrapper) return;

	field.$wrapper.addClass("saiba-error-field").css({
		background: "#fff1f1",
		border: "2px solid #e53e3e",
		"border-radius": "6px",
		padding: "6px",
	});

	field.$wrapper.find("label").css("color", "#e53e3e");
}

function clear_saiba_highlights(frm) {
	frm.wrapper.find(".saiba-error-field").each(function () {
		$(this).css({ background: "", border: "", padding: "" });
		$(this).find("label").css("color", "");
		$(this).removeClass("saiba-error-field");
	});
}
