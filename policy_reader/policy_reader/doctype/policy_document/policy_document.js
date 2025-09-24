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
			
			// Add Process with AI button
			frm.add_custom_button(
				__("Process with AI"),
				function () {
					frm.trigger("start_ai_processing");
				},
				__("Actions")
			);
		}

		// Add AI-Extract button for completed documents
		if (frm.doc.status === "Completed" && frm.doc.extracted_fields) {
			frm.add_custom_button(
				__("AI-Extract"),
				function () {
					frm.trigger("ai_extract_fields");
				},
				__("Actions")
			);
		}

		// Add Create Policy Entry button
		frm.trigger("setup_policy_creation_button");

		// Add View Policy button for completed documents
		if (frm.doc.status === "Completed" && frm.doc.policy_file) {
			frm.add_custom_button(
				__("View Policy"),
				function () {
					frm.trigger("open_policy_viewer");
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

		// Show processing status in dashboard (but not the persistent indicator)
		if (frm.doc.status === "Processing") {
			frm.dashboard.add_comment(__("Processing in progress..."), "blue", true);
			// Note: We don't automatically show the processing indicator on refresh
			// It will only show when user explicitly starts processing
		}

		// Show processing method if available
		if (frm.doc.processing_method) {
			let method_text, method_color;
			switch(frm.doc.processing_method) {
				case "claude_vision":
					method_text = "Claude AI (Vision)";
					method_color = "purple";
					break;
				default:
					method_text = "Local OCR";
					method_color = "blue";
			}
			frm.dashboard.add_comment(
				__("Processing Method: {0}", [method_text]),
				method_color,
				true
			);
		}

		// Processing method selection logic removed

		// Policy type changed - no special handling needed

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
				// Hide both regular and AI processing indicators
				frm.trigger("hide_processing_indicator");
				frm.trigger("hide_ai_processing_indicator");

				// Show completion notification
				if (message.status === "Completed") {
					let method_text;
					switch(message.processing_method) {
						case "claude_vision":
							method_text = "Claude AI (Vision)";
							break;
						default:
							method_text = "Local OCR";
					}
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

	start_ai_processing: function (frm) {
		// Show confirmation dialog
		frappe.confirm(
			__('Process this policy document directly with Claude AI (Vision)? This bypasses OCR and sends the PDF directly to Claude.'),
			function() {
				// Show processing indicator
				frm.trigger("show_ai_processing_indicator");
				
				// Call the new AI processing method
				frm.call("process_with_ai")
					.then((r) => {
						frm.trigger("hide_ai_processing_indicator");
						
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __("AI processing completed successfully! Processing time: {0}s", [r.message.processing_time]),
								indicator: "green",
							});
							frm.reload_doc();
						} else if (r.message) {
							frappe.msgprint({
								title: __("AI Processing Failed"),
								message: r.message.message || __("Unknown error occurred"),
								indicator: "red",
							});
						}
					})
					.catch((err) => {
						frm.trigger("hide_ai_processing_indicator");
						frappe.msgprint({
							title: __("AI Processing Error"),
							message: __("Failed to start AI processing: {0}", [err.message]),
							indicator: "red",
						});
					});
			}
		);
	},

	show_ai_processing_indicator: function (frm) {
		// Remove any existing indicators first
		frm.trigger("cleanup_all_processing_indicators");

		// Add visual AI processing indicator with dismiss button
		frm.processing_indicator = $(
			'<div class="processing-indicator" style="position: fixed; top: 60px; right: 20px; z-index: 1050; background: #9c27b0; color: white; padding: 10px 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); max-width: 300px;">' +
				'<i class="fa fa-spin fa-brain"></i> Processing with Claude AI...' +
				'<button class="btn btn-sm" style="background: none; border: none; color: white; margin-left: 10px; padding: 0 5px; font-size: 16px;" title="Dismiss notification">&times;</button>' +
				"</div>"
		).appendTo("body");

		// Add click handler for dismiss button
		frm.processing_indicator.find("button").on("click", function () {
			frm.trigger("hide_ai_processing_indicator");
		});

		// Auto-hide after 5 minutes if no completion event
		frm.processing_timeout = setTimeout(function () {
			if (frm.processing_indicator) {
				frm.trigger("hide_ai_processing_indicator");
				frappe.show_alert({
					message: __(
						"AI processing indicator auto-hidden. Check document status for updates."
					),
					indicator: "orange",
				});
			}
		}, 300000); // 5 minutes
	},

	hide_ai_processing_indicator: function (frm) {
		// Remove AI processing indicator
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

	check_api_key_status: function (frm) {
		// Check API key status and display as a clean status bubble
		frappe.call({
			method: "policy_reader.policy_reader.doctype.policy_document.policy_document.check_api_key_status",
			callback: function (r) {
				if (r.message) {
					let status = r.message;
					
					// Remove existing API status indicators
					$(".api-status-bubble").remove();

					// Create status bubble HTML
					let bubbleHtml = '';
					if (status.configured) {
						// API key configured - show health check
						bubbleHtml = `
							<div class="api-status-bubble" style="display: inline-flex; align-items: center; gap: 12px; padding: 8px 16px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 6px; margin-left: 12px;">
								<div style="display: flex; align-items: center; gap: 6px;">
									<span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%;"></span>
									<span style="color: #065f46; font-weight: 500; font-size: 13px;">Claude API Ready</span>
								</div>
								<button class="btn btn-xs" onclick="frappe.cur_frm.trigger('test_api_health')" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 2px 8px; font-size: 11px;">
									Test Connection
								</button>
							</div>
						`;
					} else {
						// API key not configured
						bubbleHtml = `
							<div class="api-status-bubble" style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; background: #fef2f2; border: 1px solid #ef4444; border-radius: 6px; margin-left: 12px;">
								<span style="display: inline-block; width: 8px; height: 8px; background: #ef4444; border-radius: 50%;"></span>
								<span style="color: #991b1b; font-weight: 500; font-size: 13px;">API Key Not Configured</span>
							</div>
						`;
					}

					// Add status bubble after the page title
					let statusBubble = $(bubbleHtml);
					$(".form-layout .title-area h1").after(statusBubble);
				}
			},
		});
	},

	test_api_health: function(frm) {
		// Test Claude API connectivity
		frappe.show_alert({
			message: __('Testing Claude API connection...'),
			indicator: 'blue'
		});

		frappe.call({
			method: "policy_reader.policy_reader.doctype.policy_document.policy_document.test_claude_api_health",
			callback: function(r) {
				if (r.message && r.message.success) {
					// Update bubble to show healthy status
					$(".api-status-bubble").html(`
						<div style="display: flex; align-items: center; gap: 12px;">
							<div style="display: flex; align-items: center; gap: 6px;">
								<span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%; animation: pulse 2s infinite;"></span>
								<span style="color: #065f46; font-weight: 500; font-size: 13px;">Claude API Healthy</span>
							</div>
							<span style="color: #6b7280; font-size: 11px;">Response: ${r.message.response_time}ms</span>
							<button class="btn btn-xs" onclick="frappe.cur_frm.trigger('test_api_health')" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 2px 8px; font-size: 11px;">
								Retest
							</button>
						</div>
					`);
					
					frappe.show_alert({
						message: __('Claude API is healthy! Response time: {0}ms', [r.message.response_time]),
						indicator: 'green'
					});
				} else {
					// Update bubble to show error status
					$(".api-status-bubble").html(`
						<div style="display: flex; align-items: center; gap: 12px;">
							<div style="display: flex; align-items: center; gap: 6px;">
								<span style="display: inline-block; width: 8px; height: 8px; background: #ef4444; border-radius: 50%;"></span>
								<span style="color: #991b1b; font-weight: 500; font-size: 13px;">API Connection Failed</span>
							</div>
							<button class="btn btn-xs" onclick="frappe.cur_frm.trigger('test_api_health')" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 2px 8px; font-size: 11px;">
								Retry
							</button>
						</div>
					`);
					
					frappe.show_alert({
						message: __('Claude API test failed: {0}', [r.message.error || 'Unknown error']),
						indicator: 'red'
					});
				}
			}
		});
	},


	policy_type: function (frm) {
		// Policy type changed - no special handling needed
	},

	ai_extract_fields: function (frm) {
		// Rerun AI extraction on the OCR text
		if (!frm.doc.extracted_fields) {
			frappe.msgprint(__("No extracted fields found. Please process the document first."));
			return;
		}

		frappe.confirm(
			__("This will rerun the AI extraction on the OCR text. Continue?"),
			function () {
				// Show loading indicator
				frm.dashboard.add_comment(__("🤖 Rerunning AI extraction..."), "blue", true);

				frm.call("ai_extract_fields_from_ocr")
					.then((r) => {
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __("AI extraction completed successfully!"),
								indicator: "green",
							});
							frm.reload_doc();
						} else {
							frappe.msgprint({
								title: __("AI Extraction Failed"),
								message: r.message?.message || __("Failed to extract fields"),
								indicator: "red",
							});
						}
					})
					.catch((err) => {
						frappe.msgprint({
							title: __("AI Extraction Error"),
							message: __("Error: {0}", [err.message]),
							indicator: "red",
						});
					});
			}
		);
	},

	setup_policy_creation_button: function (frm) {
		// Check if policy already exists
		const hasMotorPolicy = frm.doc.motor_policy;
		const hasHealthPolicy = frm.doc.health_policy;
		
		// Always show policy creation options if policy type is set
		if (frm.doc.policy_type) {
			const policyType = frm.doc.policy_type;
			
			// Show appropriate buttons based on policy type and existence
			if (policyType === "Motor") {
				if (!hasMotorPolicy) {
					// Show Create Motor Policy button
					frm.add_custom_button(
						__("Create Motor Policy"),
						function () {
							frm.trigger("create_policy");
						},
						__("Policy Actions")
					);
				} else {
					// Show View Motor Policy button
					frm.add_custom_button(
						__("View Motor Policy"),
						function () {
							frappe.set_route("Form", "Motor Policy", frm.doc.motor_policy);
						},
						__("Policy Actions")
					);
				}
			} 
			else if (policyType === "Health") {
				if (!hasHealthPolicy) {
					// Show Create Health Policy button
					frm.add_custom_button(
						__("Create Health Policy"),
						function () {
							frm.trigger("create_policy");
						},
						__("Policy Actions")
					);
				} else {
					// Show View Health Policy button
					frm.add_custom_button(
						__("View Health Policy"),
						function () {
							frappe.set_route("Form", "Health Policy", frm.doc.health_policy);
						},
						__("Policy Actions")
					);
				}
			}
			
			// Always show manual create option as fallback (even if policy exists)
			frm.add_custom_button(
				__("Manual Create Policy"),
				function () {
					frm.trigger("manual_create_policy");
				},
				__("Policy Actions")
			);
		}
	},

	create_policy: function (frm) {
		// Check if we have extracted fields
		if (frm.doc.status === "Completed" && frm.doc.extracted_fields) {
			// Show confirmation dialog for automatic creation
			frappe.confirm(
				__("Create {0} policy from extracted fields?", [frm.doc.policy_type]),
				function () {
					frm.trigger("execute_policy_creation");
				}
			);
		} else {
			// No extracted fields - show manual create dialog
			frm.trigger("manual_create_policy");
		}
	},

	manual_create_policy: function (frm) {
		// Manual policy creation dialog with more options
		let dialog = new frappe.ui.Dialog({
			title: __("Create Policy Record"),
			fields: [
				{
					fieldtype: "HTML",
					fieldname: "info",
					options: `
						<div class="alert alert-info">
							<h5><i class="fa fa-info-circle"></i> Manual Policy Creation</h5>
							<p>Create a ${frm.doc.policy_type || 'new'} policy record manually. This will create a blank policy that you can fill in with the extracted data or enter manually.</p>
						</div>
					`
				},
				{
					fieldtype: "Select",
					fieldname: "policy_type",
					label: __("Policy Type"),
					options: ["Motor", "Health"],
					default: frm.doc.policy_type || "Motor",
					reqd: 1
				},
				{
					fieldtype: "Select",
					fieldname: "creation_method",
					label: __("Creation Method"),
					options: [
						"From Extracted Fields",
						"Blank Policy Record"
					],
					default: frm.doc.extracted_fields ? "From Extracted Fields" : "Blank Policy Record",
					reqd: 1,
					description: "Choose whether to use extracted fields (if available) or create a blank policy"
				},
				{
					fieldtype: "Check",
					fieldname: "force_create",
					label: __("Force Create (even if policy exists)"),
					default: 0,
					description: "Check this to create a new policy even if one already exists"
				}
			],
			primary_action_label: __("Create Policy"),
			primary_action: function(values) {
				dialog.hide();
				
				// Update the policy type if changed
				if (values.policy_type !== frm.doc.policy_type) {
					frm.set_value("policy_type", values.policy_type);
				}
				
				if (values.creation_method === "From Extracted Fields" && frm.doc.extracted_fields) {
					// Use extracted fields method
					frm.trigger("execute_policy_creation");
				} else {
					// Create blank policy
					frm.trigger("create_blank_policy", values.policy_type);
				}
			}
		});
		
		dialog.show();
	},

	execute_policy_creation: function (frm) {
		// Show loading indicator
		frm.dashboard.add_comment(
			__("Creating {0} policy...", [frm.doc.policy_type]),
			"blue"
		);

		// Call server method
		frm.call("create_policy_entry")
			.then((r) => {
				// Remove loading indicator
				frm.dashboard.clear_comment();

				if (r.message && r.message.success) {
					// Show success message
					frappe.show_alert({
						message: __("Policy created successfully!"),
						indicator: "green",
					});

					// Refresh the form to show the new policy link
					frm.reload_doc();
				} else {
					// Show error message
					frappe.show_alert({
						message: __("Failed to create policy: {0}", [
							r.message?.error || "Unknown error",
						]),
						indicator: "red",
					});
				}
			})
			.catch((error) => {
				// Remove loading indicator
				frm.dashboard.clear_comment();

				// Show error message
				frappe.show_alert({
					message: __("Error creating policy: {0}", [
						error.message || "Unknown error",
					]),
					indicator: "red",
				});
			});
	},

	create_blank_policy: function (frm, policy_type) {
		// Create a blank policy record
		policy_type = policy_type || frm.doc.policy_type;
		
		frappe.show_alert({
			message: __("Creating blank {0} policy...", [policy_type]),
			indicator: "blue",
		});

		// Create new policy document directly
		frappe.route_options = {
			"policy_document": frm.doc.name,
			"policy_file": frm.doc.policy_file
		};
		
		frappe.new_doc(`${policy_type} Policy`);
	},

	open_policy_viewer: function (frm) {
		// Open the policy viewer page with the document ID as parameter
		const url = `/app/policy-file-view?policy_document=${frm.doc.name}`;
		window.open(url, "_blank");
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
