// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Policy Document", {
	refresh: function (frm) {
		// Clear any processing indicators first
		frm.trigger("cleanup_all_processing_indicators");

		// Set up real-time event listener for background processing updates
		frm.trigger("setup_realtime_listener");

		// Check and display API key status
		frm.trigger("check_api_key_status");

		// Add Process Now button
		if (frm.doc.policy_file && frm.doc.policy_type && frm.doc.status !== "Processing") {
			frm.add_custom_button(
				__("Process Now"),
				function () {
					frm.trigger("start_processing");
				},
				__("Actions")
			);
		}

		// Add Reset Status button for stuck documents using Frappe patterns
		if (frm.doc.status === "Processing") {
			frm.add_custom_button(
				__("Reset Status"),
				function () {
					frappe.confirm(
						__(
							"Are you sure you want to reset the processing status? This will allow you to retry processing."
						),
						function () {
							frm.call("reset_processing_status")
								.then((r) => {
									if (r.message && r.message.success) {
										frappe.show_alert({
											message: __(r.message.message),
											indicator: "blue",
										});
										frm.reload_doc();
									}
								})
								.catch((err) => {
									frappe.msgprint({
										title: __("Reset Failed"),
										message: __("Failed to reset status: {0}", [err.message]),
										indicator: "red",
									});
								});
						}
					);
				},
				__("Actions")
			);
		}

		// Add Create Policy Record button when conditions are met
		if (frm.trigger("should_show_create_policy_button")) {
			let policy_type = frm.doc.policy_type;
			frm.add_custom_button(
				__("Create {0} Policy", [policy_type]),
				function () {
					frm.trigger("create_policy_record");
				},
				__("Actions")
			);
		}

		// Show processing status in dashboard (but not the persistent indicator)
		if (frm.doc.status === "Processing") {
			frm.dashboard.add_comment(__("Processing in progress..."), "blue", true);
			// Note: We don't automatically show the processing indicator on refresh
			// It will only show when user explicitly starts processing
		}

		// Show processing method if available (but don't duplicate with health status)
		if (frm.doc.processing_method && !$(".runpod-health-status").length) {
			let method_text = frm.doc.processing_method === "runpod" ? "RunPod API" : "Local OCR";
			let method_color = frm.doc.processing_method === "runpod" ? "green" : "blue";
			frm.dashboard.add_comment(
				__("Processing Method: {0}", [method_text]),
				method_color,
				true
			);
		}

		// Show RunPod health status to inform processing method choice
		frm.trigger("check_runpod_health_status");

		// Extracted fields display removed per user request

		// Add field state indicators for manual vs extracted data
		frm.trigger("add_field_state_indicators");

		// Add cleanup handler for navigation/form close
		frm.trigger("setup_navigation_cleanup");
	},

	setup_navigation_cleanup: function (frm) {
		// Cleanup indicators when form is destroyed or navigating away
		$(window)
			.off("beforeunload.policy_processing")
			.on("beforeunload.policy_processing", function () {
				frm.trigger("cleanup_all_processing_indicators");
			});

		// Also cleanup when hash changes (navigation within Frappe)
		$(window)
			.off("hashchange.policy_processing")
			.on("hashchange.policy_processing", function () {
				frm.trigger("cleanup_all_processing_indicators");
			});
	},

	policy_file: function (frm) {
		// Auto-generate title from filename
		if (frm.doc.policy_file && !frm.doc.title) {
			let filename = frm.doc.policy_file.split("/").pop();
			let title = filename.replace(".pdf", "").replace(".PDF", "");
			frm.set_value("title", title);
		}

		// Refresh the form to show Process Policy button if both file and type are set
		frm.refresh();
	},

	policy_type: function (frm) {
		// Refresh the form to show Process Policy button if both file and type are set
		frm.refresh();
	},

	setup_realtime_listener: function (frm) {
		// Set up real-time event listener for policy processing completion
		frappe.realtime.on("policy_processing_complete", function (message) {
			if (message.doc_name === frm.doc.name) {
				// Hide processing indicator
				frm.trigger("hide_processing_indicator");

				// Show completion notification
				if (message.status === "Completed") {
					let method_text =
						message.processing_method === "runpod" ? "RunPod API" : "Local OCR";
					frappe.show_alert({
						message: __(
							"Policy processing completed successfully via {0}! Processing time: {1}s",
							[method_text, message.processing_time]
						),
						indicator: "green",
					});
				} else {
					frappe.show_alert({
						message: __("Policy processing failed: {0}", [message.message]),
						indicator: "red",
					});
				}

				// Reload the document to show updated data
				frm.reload_doc();
			}
		});
	},

	start_processing: function (frm) {
		// Show loading indicator immediately
		frm.trigger("show_processing_indicator");

		// Call the background processing method
		frm.call("process_policy")
			.then((r) => {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __(r.message.message),
						indicator: "blue",
					});
					frm.reload_doc();
				} else if (r.message) {
					frm.trigger("hide_processing_indicator");
					frappe.msgprint({
						title: __("Processing Failed"),
						message: r.message.message || __("Unknown error occurred"),
						indicator: "red",
					});
				}
			})
			.catch((err) => {
				frm.trigger("hide_processing_indicator");
				frappe.msgprint({
					title: __("Processing Error"),
					message: __("Failed to start processing: {0}", [err.message]),
					indicator: "red",
				});
			});
	},

	show_processing_indicator: function (frm) {
		// Remove any existing indicators first
		frm.trigger("cleanup_all_processing_indicators");

		// Add visual processing indicator with dismiss button
		frm.processing_indicator = $(
			'<div class="processing-indicator" style="position: fixed; top: 60px; right: 20px; z-index: 1050; background: #007bff; color: white; padding: 10px 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); max-width: 300px;">' +
				'<i class="fa fa-spin fa-spinner"></i> Processing Policy...' +
				'<button class="btn btn-sm" style="background: none; border: none; color: white; margin-left: 10px; padding: 0 5px; font-size: 16px;" title="Dismiss notification">&times;</button>' +
				"</div>"
		).appendTo("body");

		// Add click handler for dismiss button
		frm.processing_indicator.find("button").on("click", function () {
			frm.trigger("hide_processing_indicator");
		});

		// Auto-hide after 5 minutes if no completion event
		frm.processing_timeout = setTimeout(function () {
			if (frm.processing_indicator) {
				frm.trigger("hide_processing_indicator");
				frappe.show_alert({
					message: __(
						"Processing indicator auto-hidden. Check document status for updates."
					),
					indicator: "orange",
				});
			}
		}, 300000); // 5 minutes
	},

	hide_processing_indicator: function (frm) {
		// Remove processing indicator
		if (frm.processing_indicator) {
			frm.processing_indicator.remove();
			frm.processing_indicator = null;
		}

		// Clear timeout if exists
		if (frm.processing_timeout) {
			clearTimeout(frm.processing_timeout);
			frm.processing_timeout = null;
		}
	},

	cleanup_all_processing_indicators: function (frm) {
		// Remove any existing processing indicators from the page
		$(".processing-indicator").remove();

		// Clear form-specific references
		if (frm.processing_indicator) {
			frm.processing_indicator = null;
		}

		// Clear timeout if exists
		if (frm.processing_timeout) {
			clearTimeout(frm.processing_timeout);
			frm.processing_timeout = null;
		}
	},

	add_field_state_indicators: function (frm) {
		// Add visual indicators to show which fields were extracted vs manually entered
		if (frm.doc.status === "Completed" && frm.doc.extracted_fields && frm.doc.policy_type) {
			try {
				let extracted_data = JSON.parse(frm.doc.extracted_fields);
				let field_mapping = {};

				// Define field mappings based on policy type
				if (frm.doc.policy_type.toLowerCase() === "motor") {
					field_mapping = {
						"Policy Number": "policy_number_motor",
						"Insured Name": "insured_name_motor",
						"Vehicle Number": "vehicle_number_motor",
						"Chassis Number": "chassis_number_motor",
						"Engine Number": "engine_number_motor",
						From: "policy_from_motor",
						To: "policy_to_motor",
						"Premium Amount": "premium_amount_motor",
						"Sum Insured": "sum_insured_motor",
						"Make / Model": "make_model_motor",
						Variant: "variant_motor",
						"Vehicle Class": "vehicle_class_motor",
						"Registration Number": "registration_number_motor",
						Fuel: "fuel_motor",
						"Seat Capacity": "seat_capacity_motor",
					};
				} else if (frm.doc.policy_type.toLowerCase() === "health") {
					field_mapping = {
						"Policy Number": "policy_number_health",
						"Insured Name": "insured_name_health",
						"Sum Insured": "sum_insured_health",
						"Policy Start Date": "policy_start_date_health",
						"Policy End Date": "policy_end_date_health",
						"Customer Code": "customer_code_health",
						"Net Premium": "net_premium_health",
						"Policy Period": "policy_period_health",
						"Issuing Office": "issuing_office_health",
						"Relationship to Policyholder": "relationship_to_policyholder_health",
						"Date of Birth": "date_of_birth_health",
					};
				}

				// Add indicators to each field
				Object.keys(field_mapping).forEach((extracted_field) => {
					let doctype_field = field_mapping[extracted_field];
					let field_wrapper = frm.fields_dict[doctype_field];

					if (field_wrapper && field_wrapper.wrapper) {
						// Remove existing indicators
						$(field_wrapper.wrapper).find(".field-state-indicator").remove();

						let was_extracted = extracted_data[extracted_field];
						let current_value = frm.doc[doctype_field];

						let indicator_html = "";
						let indicator_class = "";
						let indicator_title = "";

						if (was_extracted && current_value === was_extracted) {
							// Field was extracted and unchanged
							indicator_class = "text-success";
							indicator_html = '<i class="fa fa-robot"></i>';
							indicator_title = "Extracted by OCR";
						} else if (was_extracted && current_value !== was_extracted) {
							// Field was extracted but manually modified
							indicator_class = "text-warning";
							indicator_html = '<i class="fa fa-edit"></i>';
							indicator_title = "Extracted by OCR, manually modified";
						} else if (!was_extracted && current_value) {
							// Field was not extracted but manually entered
							indicator_class = "text-info";
							indicator_html = '<i class="fa fa-user"></i>';
							indicator_title = "Manually entered";
						} else {
							// Field was not extracted and still empty
							indicator_class = "text-muted";
							indicator_html = '<i class="fa fa-question-circle"></i>';
							indicator_title = "Not extracted - please enter manually";
						}

						let indicator = $(
							`<span class="field-state-indicator ${indicator_class}" style="position: absolute; right: 5px; top: 8px;" title="${indicator_title}">
                                ${indicator_html}
                            </span>`
						);

						$(field_wrapper.wrapper)
							.find(".control-input-wrapper")
							.css("position", "relative")
							.append(indicator);
					}
				});
			} catch (e) {
				console.error("Error adding field state indicators:", e);
			}
		}
	},

	should_show_create_policy_button: function (frm) {
		// Show button when:
		// - Status is "Completed" (fields extracted)
		// - Policy type is selected
		// - Extracted fields exist
		// - No existing policy record linked for the selected type

		if (frm.doc.status !== "Completed") {
			return false;
		}

		if (!frm.doc.policy_type) {
			return false;
		}

		if (!frm.doc.extracted_fields) {
			return false;
		}

		// Check if policy record already exists based on policy type
		if (frm.doc.policy_type.toLowerCase() === "motor") {
			return !frm.doc.motor_policy; // Show button if no motor policy linked
		} else if (frm.doc.policy_type.toLowerCase() === "health") {
			return !frm.doc.health_policy; // Show button if no health policy linked
		}

		return false;
	},

	create_policy_record: function (frm) {
		let policy_type = frm.doc.policy_type;

		frappe.confirm(
			__(
				"Create a new {0} Policy record from the extracted fields?<br><br>This will create a new policy record using the data extracted from the uploaded document.",
				[policy_type]
			),
			function () {
				// Show loading indicator
				frappe.show_alert({
					message: __("Creating {0} Policy record...", [policy_type]),
					indicator: "blue",
				});

				frm.call("create_policy_record")
					.then((r) => {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __(r.message.message + ": {0}", [r.message.policy_name]),
								indicator: "green",
							});
							// Reload document to show the new policy link
							frm.reload_doc();
						} else {
							frappe.msgprint({
								title: __("Policy Creation Failed"),
								message: r.message
									? r.message.message
									: __("Unknown error occurred"),
								indicator: "red",
							});
						}
					})
					.catch((err) => {
						frappe.msgprint({
							title: __("Policy Creation Error"),
							message: __("Failed to create policy record: {0}", [err.message]),
							indicator: "red",
						});
					});
			},
			function () {
				// User cancelled - no action needed
			}
		);
	},

	check_api_key_status: function (frm) {
		// Check API key status and display in dashboard
		frappe.call({
			method: "policy_reader.policy_reader.doctype.policy_document.policy_document.check_api_key_status",
			callback: function (r) {
				if (r.message) {
					let status = r.message;
					let color = status.configured ? "green" : "red";
					let icon = status.configured ? "✓" : "✗";
					let message = `${icon} API Key: ${status.message}`;

					// Remove existing API key status
					$(".api-key-status").remove();

					// Add to dashboard
					frm.dashboard.add_comment(message, color, true);

					// Also add a small indicator near the form title
					let indicator = $(
						`<span class="api-key-status" style="margin-left: 10px; color: ${
							color === "green" ? "#28a745" : "#dc3545"
						}; font-size: 12px;">${message}</span>`
					);
					$(".form-layout .title-area h1").append(indicator);
				}
			},
		});
	},

	check_runpod_health_status: function (frm) {
		// Check RunPod health status and show recommendations
		frappe.call({
			method: "policy_reader.policy_reader.doctype.policy_reader_settings.policy_reader_settings.get_runpod_health_info",
			callback: function (r) {
				if (r.message) {
					let health = r.message;

					// Remove existing health status display
					$(".runpod-health-status").remove();

					// Create clean health status display
					let healthHtml = "";
					let methodRecommendation = "";

					if (health.status === "healthy" && health.response_time < 5) {
						healthHtml = `
							<div class="runpod-health-status" style="margin: 10px 0; padding: 12px; border-radius: 6px; background: #d4edda; border: 1px solid #c3e6cb; color: #155724;">
								<div style="font-weight: 600; margin-bottom: 5px;">✅ RunPod API Status: Healthy</div>
								<div style="font-size: 13px; color: #0f5132;">Response time: ${health.response_time.toFixed(
									2
								)}s | 🚀 Recommended for processing</div>
							</div>
						`;
						methodRecommendation = "runpod";

						// Auto-set to runpod if not already set
						if (!frm.doc.processing_method || frm.doc.processing_method === "local") {
							frm.set_value("processing_method", "runpod");
						}
					} else if (health.status === "healthy" && health.response_time >= 5) {
						healthHtml = `
							<div class="runpod-health-status" style="margin: 10px 0; padding: 12px; border-radius: 6px; background: #fff3cd; border: 1px solid #ffeaa7; color: #856404;">
								<div style="font-weight: 600; margin-bottom: 5px;">⚠️ RunPod API Status: Slow</div>
								<div style="font-size: 13px; color: #856404;">Response time: ${health.response_time.toFixed(
									2
								)}s | 💻 Local processing recommended</div>
							</div>
						`;
						methodRecommendation = "local";

						// Auto-set to local if RunPod is slow
						if (frm.doc.processing_method === "runpod") {
							frm.set_value("processing_method", "local");
						}
					} else {
						healthHtml = `
							<div class="runpod-health-status" style="margin: 10px 0; padding: 12px; border-radius: 6px; background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24;">
								<div style="font-weight: 600; margin-bottom: 5px;">❌ RunPod API Status: ${
									health.status || "Unavailable"
								}</div>
								<div style="font-size: 13px; color: #721c24;">💻 Local processing only available</div>
							</div>
						`;
						methodRecommendation = "local";

						// Auto-set to local if RunPod is unhealthy
						if (frm.doc.processing_method === "runpod") {
							frm.set_value("processing_method", "local");
						}
					}

					// Add health status after the policy information section
					let policyInfoSection = frm
						.get_field("policy_type")
						.$wrapper.closest(".form-section");
					if (policyInfoSection.length) {
						policyInfoSection.after(healthHtml);
					}

					// Update processing method field with recommendation
					if (
						methodRecommendation &&
						frm.doc.processing_method !== methodRecommendation
					) {
						frm.set_value("processing_method", methodRecommendation);
					}
				}
			},
		});
	},
});

// Global cleanup function for processing indicators
// Can be called from browser console if needed: frappe.policy_reader.cleanup_processing_indicators()
frappe.policy_reader = frappe.policy_reader || {};
frappe.policy_reader.cleanup_processing_indicators = function () {
	// Remove all processing indicators from the page
	$(".processing-indicator").remove();
	console.log("All Policy processing indicators cleared");
};
