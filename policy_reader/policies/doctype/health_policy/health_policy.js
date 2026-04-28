// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt
/* global policy_reader */
frappe.ui.form.on("Health Policy", {
	refresh(frm) {
		// if (!frm.remarks) {
		// 	frm.set_value("remarks", "NA");
		// }
		if (!frm.policy_status){
			frm.set_value("policy_status","Issued")
		}
		if(!frm.pos_policy){
			frm.set_value("pos_policy","Yes")
		}
		if(!frm.payment_mode_1){
			frm.set_value("payment_mode","Bank Transfer")
		}
		if (!frm.bank_name) {
			frm.set_value("bank_name", "NONE");
		}
		if(!frm.payment_transaction_no){
			frm.set_value("payment_transaction_no",0)
		}
		// Mark AI fields first so indicators are always visible regardless of status
		if (!frm.doc.__islocal && typeof policy_reader !== "undefined" && policy_reader.saiba) {
			policy_reader.saiba.mark_saiba_ai_fields(frm, "Health");
		}


		// for enabling users to check ai_extracted_fields manually and then allow them to mark it as approved
		if (!frm.is_new() && frm.doc.approval_status !== "Approved") {
			frm.add_custom_button(
				__("Approve"),
				() => {
					frappe.confirm(
						__("Are you sure you want to approve this Health Policy?"),
						() => {
							frappe.call({
								method: "sync_health_policy",
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

		// Add SAIBA buttons (sync + validation)
		if (!frm.doc.__islocal && frm.doc.approval_status === "Approved") {
			add_saiba_sync_button_health(frm);
			// Add SAIBA validation button and field indicators (uses shared functions from saiba_validation.js)
			if (typeof policy_reader !== "undefined" && policy_reader.saiba) {
				policy_reader.saiba.add_validate_button(frm, "Health");
				policy_reader.saiba.mark_required_fields(frm, "Health");
			}
		}
	},

	onload(frm) {
		// Add "View Policy Document" button if policy_document is linked
		if (frm.doc.policy_document) {
			frm.add_custom_button(
				__("View Policy Document"),
				function () {
					const url = `/app/policy-file-view?policy_document=${frm.doc.policy_document}&health_policy=${frm.doc.name}`;
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
					populate_health_policy_fields(frm);
				},
				__("Actions")
			);
		}
	},
});

function populate_health_policy_fields(frm) {
	frappe.show_alert({
		message: __("Populating fields from Policy Document..."),
		indicator: "blue",
	});

	frappe.call({
		method: "populate_fields_from_policy_document",
		doc: frm.doc,
		args: {
			policy_document_name: frm.doc.policy_document,
		},
		callback: function (response) {
			console.log("=== POPULATE HEALTH POLICY FIELDS DEBUG ===");
			console.log("Full response:", response);

			if (response.message) {
				console.log("Response message:", response.message);
				console.log("Error message:", response.message.error);

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
			console.error("Error populating health policy fields:", error);
		},
	});
}

function add_saiba_sync_button_health(frm) {
	frappe.db.get_single_value("Policy Reader Settings", "saiba_enabled").then((enabled) => {
		if (!enabled) {
			return;
		}

		frm.add_custom_button(
			__("Sync to SAIBA"),
			function () {
				sync_health_policy_to_saiba(frm);
			},
			__("Actions")
		);

		update_saiba_button_indicator_health(frm);
	});
}

function update_saiba_button_indicator_health(frm) {
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

	if (status && status !== "Not Synced") {
		frm.page.set_indicator(status, indicator);
	}
}

function sync_health_policy_to_saiba(frm) {
	frappe.confirm(__("Are you sure you want to sync this Health Policy to SAIBA?"), function () {
		frappe.show_alert({
			message: __("Syncing to SAIBA..."),
			indicator: "blue",
		});

		frappe.call({
			method: "policy_reader.policy_reader.services.saiba_sync_service.sync_health_policy",
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
					const error_fields = response.message?.error_fields || [];
					error_fields.forEach((fieldname) =>
						highlight_saiba_field_health(frm, fieldname)
					);

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

function highlight_saiba_field_health(frm, fieldname) {
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

function clear_saiba_highlights_health(frm) {
	frm.wrapper.find(".saiba-error-field").each(function () {
		$(this).css({ background: "", border: "", padding: "" });
		$(this).find("label").css("color", "");
		$(this).removeClass("saiba-error-field");
	});
}