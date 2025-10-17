// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on("Policy Document", {
	onload: function (frm) {
		// Populate processor info on form load
		frm.trigger("populate_processor_info");
	},

	refresh: function (frm) {
		// Cleanup and setup
		$(".processing-indicator").remove();
		frm.trigger("setup_realtime_listener");
		frm.trigger("check_api_key_status");

		// Add buttons based on document state
		if (frm.doc.policy_file && frm.doc.policy_type && frm.doc.status !== "Processing") {
			frm.add_custom_button(
				__("Process with AI"),
				() => frm.trigger("start_ai_processing"),
				__("Actions")
			);
		}

		if (frm.doc.status === "Completed" && frm.doc.policy_file) {
			frm.add_custom_button(
				__("View Policy"),
				() => frm.trigger("open_policy_viewer"),
				__("Actions")
			);
		}

		if (frm.doc.status === "Processing") {
			frm.add_custom_button(
				__("Reset Status"),
				() => frm.trigger("reset_status"),
				__("Actions")
			);
			frm.dashboard.add_comment(__("Processing in progress..."), "blue", true);
		}

		// Policy creation buttons
		frm.trigger("setup_policy_creation_button");

		// Field indicators and cleanup
		frm.trigger("add_field_state_indicators");
		$(window)
			.off("beforeunload.policy_processing hashchange.policy_processing")
			.on("beforeunload.policy_processing hashchange.policy_processing", () =>
				$(".processing-indicator").remove()
			);
	},

	policy_file: function (frm) {
		if (frm.doc.policy_file && !frm.doc.title) {
			const title = frm.doc.policy_file
				.split("/")
				.pop()
				.replace(/\.(pdf|PDF)$/, "");
			frm.set_value("title", title);
		}
		frm.refresh();
	},

	policy_type: function (frm) {
		frm.refresh();
	},

	setup_realtime_listener: function (frm) {
		frappe.realtime.on("policy_processing_complete", function (message) {
			if (message.doc_name === frm.doc.name) {
				$(".processing-indicator").remove();
				const method_text =
					message.processing_method === "claude_vision"
						? "Claude AI (Vision)"
						: "Local OCR";
				const indicator = message.status === "Completed" ? "green" : "red";
				const msg =
					message.status === "Completed"
						? __(
								"Policy processing completed successfully via {0}! Processing time: {1}s",
								[method_text, message.processing_time]
						  )
						: __("Policy processing failed: {0}", [message.message]);
				frappe.show_alert({ message: msg, indicator });
				frm.reload_doc();
			}
		});
	},

	start_ai_processing: function (frm) {
		frappe.confirm(
			__(
				"Process this policy document directly with Claude AI (Vision)? This bypasses OCR and sends the PDF directly to Claude."
			),
			() => {
				frm.trigger("show_processing_indicator");
				frm.call("process_policy", { background: false })
					.then((r) => {
						$(".processing-indicator").remove();
						if (r.message && r.message.success) {
							frappe.show_alert({
								message: __(
									"AI processing completed successfully! Processing time: {0}s",
									[r.message.processing_time]
								),
								indicator: "green",
							});
							frm.reload_doc();
						} else {
							frappe.msgprint({
								title: __("AI Processing Failed"),
								message: r.message?.message || __("Unknown error occurred"),
								indicator: "red",
							});
						}
					})
					.catch((err) => {
						$(".processing-indicator").remove();
						frappe.msgprint({
							title: __("AI Processing Error"),
							message: __("Failed to start AI processing: {0}", [err.message]),
							indicator: "red",
						});
					});
			}
		);
	},

	show_processing_indicator: function (frm) {
		$(".processing-indicator").remove();
		const indicator =
			$(`<div class="processing-indicator" style="position: fixed; top: 60px; right: 20px; z-index: 1050; background: #9c27b0; color: white; padding: 10px 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); max-width: 300px;">
			<i class="fa fa-spin fa-brain"></i> Processing with Claude AI...
			<button class="btn btn-sm" style="background: none; border: none; color: white; margin-left: 10px; padding: 0 5px; font-size: 16px;" title="Dismiss notification">&times;</button>
		</div>`).appendTo("body");

		indicator.find("button").on("click", () => $(".processing-indicator").remove());
		setTimeout(() => {
			if ($(".processing-indicator").length) {
				$(".processing-indicator").remove();
				frappe.show_alert({
					message: __(
						"AI processing indicator auto-hidden. Check document status for updates."
					),
					indicator: "orange",
				});
			}
		}, 300000);
	},

	reset_status: function (frm) {
		frappe.confirm(
			__(
				"Are you sure you want to reset the processing status? This will allow you to retry processing."
			),
			() => {
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

	check_api_key_status: function (frm) {
		frappe.call({
			method: "policy_reader.policy_reader.doctype.policy_document.policy_document.check_api_key_status",
			callback: function (r) {
				if (r.message) {
					$(".api-status-bubble").remove();
					const status = r.message;
					const bubbleHtml = status.configured
						? `<div class="api-status-bubble" style="display: inline-flex; align-items: center; gap: 12px; padding: 8px 16px; background: #ecfdf5; border: 1px solid #10b981; border-radius: 6px; margin-left: 12px;">
							<div style="display: flex; align-items: center; gap: 6px;">
								<span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%;"></span>
								<span style="color: #065f46; font-weight: 500; font-size: 13px;">Claude API Ready</span>
							</div>
							<button class="btn btn-xs" onclick="frappe.cur_frm.trigger('test_api_health')" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 2px 8px; font-size: 11px;">Test Connection</button>
						</div>`
						: `<div class="api-status-bubble" style="display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; background: #fef2f2; border: 1px solid #ef4444; border-radius: 6px; margin-left: 12px;">
							<span style="display: inline-block; width: 8px; height: 8px; background: #ef4444; border-radius: 50%;"></span>
							<span style="color: #991b1b; font-weight: 500; font-size: 13px;">API Key Not Configured</span>
						</div>`;
					$(".form-layout .title-area h1").after($(bubbleHtml));
				}
			},
		});
	},

	test_api_health: function (frm) {
		frappe.show_alert({ message: __("Testing Claude API connection..."), indicator: "blue" });
		frappe.call({
			method: "policy_reader.policy_reader.doctype.policy_document.policy_document.test_claude_api_health",
			callback: function (r) {
				if (r.message && r.message.success) {
					$(".api-status-bubble")
						.html(`<div style="display: flex; align-items: center; gap: 12px;">
						<div style="display: flex; align-items: center; gap: 6px;">
							<span style="display: inline-block; width: 8px; height: 8px; background: #10b981; border-radius: 50%; animation: pulse 2s infinite;"></span>
							<span style="color: #065f46; font-weight: 500; font-size: 13px;">Claude API Healthy</span>
						</div>
						<span style="color: #6b7280; font-size: 11px;">Response: ${r.message.response_time}ms</span>
						<button class="btn btn-xs" onclick="frappe.cur_frm.trigger('test_api_health')" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 2px 8px; font-size: 11px;">Retest</button>
					</div>`);
					frappe.show_alert({
						message: __("Claude API is healthy! Response time: {0}ms", [
							r.message.response_time,
						]),
						indicator: "green",
					});
				} else {
					$(".api-status-bubble")
						.html(`<div style="display: flex; align-items: center; gap: 12px;">
						<div style="display: flex; align-items: center; gap: 6px;">
							<span style="display: inline-block; width: 8px; height: 8px; background: #ef4444; border-radius: 50%;"></span>
							<span style="color: #991b1b; font-weight: 500; font-size: 13px;">API Connection Failed</span>
						</div>
						<button class="btn btn-xs" onclick="frappe.cur_frm.trigger('test_api_health')" style="background: white; border: 1px solid #d1d5db; color: #374151; padding: 2px 8px; font-size: 11px;">Retry</button>
					</div>`);
					frappe.show_alert({
						message: __("Claude API test failed: {0}", [
							r.message.error || "Unknown error",
						]),
						indicator: "red",
					});
				}
			},
		});
	},

	add_field_state_indicators: function (frm) {
		if (frm.doc.status === "Completed" && frm.doc.extracted_fields && frm.doc.policy_type) {
			try {
				const extracted_data = JSON.parse(frm.doc.extracted_fields);
				const field_mapping =
					frm.doc.policy_type.toLowerCase() === "motor"
						? {
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
						  }
						: {
								"Policy Number": "policy_number_health",
								"Insured Name": "insured_name_health",
								"Sum Insured": "sum_insured_health",
								"Policy Start Date": "policy_start_date_health",
								"Policy End Date": "policy_end_date_health",
								"Customer Code": "customer_code_health",
								"Net Premium": "net_premium_health",
								"Policy Period": "policy_period_health",
								"Issuing Office": "issuing_office_health",
								"Relationship to Policyholder":
									"relationship_to_policyholder_health",
								"Date of Birth": "date_of_birth_health",
						  };

				Object.keys(field_mapping).forEach((extracted_field) => {
					const doctype_field = field_mapping[extracted_field];
					const field_wrapper = frm.fields_dict[doctype_field];
					if (field_wrapper && field_wrapper.wrapper) {
						$(field_wrapper.wrapper).find(".field-state-indicator").remove();
						const was_extracted = extracted_data[extracted_field];
						const current_value = frm.doc[doctype_field];
						let indicator_class, indicator_html, indicator_title;

						if (was_extracted && current_value === was_extracted) {
							indicator_class = "text-success";
							indicator_html = '<i class="fa fa-robot"></i>';
							indicator_title = "Extracted by OCR";
						} else if (was_extracted && current_value !== was_extracted) {
							indicator_class = "text-warning";
							indicator_html = '<i class="fa fa-edit"></i>';
							indicator_title = "Extracted by OCR, manually modified";
						} else if (!was_extracted && current_value) {
							indicator_class = "text-info";
							indicator_html = '<i class="fa fa-user"></i>';
							indicator_title = "Manually entered";
						} else {
							indicator_class = "text-muted";
							indicator_html = '<i class="fa fa-question-circle"></i>';
							indicator_title = "Not extracted - please enter manually";
						}

						const indicator = $(
							`<span class="field-state-indicator ${indicator_class}" style="position: absolute; right: 5px; top: 8px;" title="${indicator_title}">${indicator_html}</span>`
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

	setup_policy_creation_button: function (frm) {
		if (frm.doc.policy_type) {
			const policyType = frm.doc.policy_type;
			const hasPolicy =
				policyType === "Motor" ? frm.doc.motor_policy : frm.doc.health_policy;

			if (!hasPolicy) {
				frm.add_custom_button(
					__(`Create ${policyType} Policy`),
					() => frm.trigger("create_policy"),
					__("Policy Actions")
				);
			} else {
				frm.add_custom_button(
					__(`View ${policyType} Policy`),
					() => frappe.set_route("Form", `${policyType} Policy`, hasPolicy),
					__("Policy Actions")
				);
			}
		}
	},

	create_policy: function (frm) {
		if (frm.doc.status === "Completed" && frm.doc.extracted_fields) {
			frappe.confirm(
				__("Create {0} policy from extracted fields?", [frm.doc.policy_type]),
				() => frm.trigger("execute_policy_creation")
			);
		} else {
			frappe.msgprint({
				title: __("Cannot Create Policy"),
				message: __(
					"Please process the document first to extract fields before creating a policy."
				),
				indicator: "orange",
			});
		}
	},

	execute_policy_creation: function (frm) {
		// Ensure document is saved first
		if (!frm.doc.name) {
			frappe.msgprint(
				__("Please save the document first before creating a policy."),
				__("Document Not Saved")
			);
			return;
		}

		frm.dashboard.add_comment(__("Creating {0} policy...", [frm.doc.policy_type]), "blue");
		frappe
			.call({
				method: "policy_reader.policy_reader.doctype.policy_document.policy_creation_endpoints.create_policy_entry",
				args: {
					policy_document_name: frm.doc.name,
				},
			})
			.then((r) => {
				frm.dashboard.clear_comment();
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __("Policy created successfully!"),
						indicator: "green",
					});
					frm.reload_doc();
				} else {
					frappe.show_alert({
						message: __("Failed to create policy: {0}", [
							r.message?.error || "Unknown error",
						]),
						indicator: "red",
					});
				}
			})
			.catch((error) => {
				frm.dashboard.clear_comment();
				frappe.show_alert({
					message: __("Error creating policy: {0}", [error.message || "Unknown error"]),
					indicator: "red",
				});
			});
	},

	open_policy_viewer: function (frm) {
		window.open(`/app/policy-file-view?policy_document=${frm.doc.name}`, "_blank");
	},

	populate_processor_info: function (frm) {
		console.log("=== POPULATE PROCESSOR INFO DEBUG ===");
		console.log("Current logged-in user:", frappe.session.user);
		console.log("Current user's full name:", frappe.session.user_fullname);
		console.log("Processor employee code already set?:", frm.doc.processor_employee_code);

		// Only populate if fields are empty (not already set)
		if (!frm.doc.processor_employee_code) {
			console.log("Fetching Insurance Employee info for user:", frappe.session.user);
			frappe.call({
				method: "policy_reader.policy_reader.doctype.policy_document.policy_document.get_current_user_employee_info",
				callback: function (r) {
					console.log("API Response:", r);
					if (r.message && r.message.employee) {
						const emp = r.message.employee;
						console.log("Found Insurance Employee:", emp);
						console.log("Employee Code:", emp.employee_code);
						console.log("Employee Type:", emp.employee_type);
						console.log("Employee Full Name:", emp.employee_name);

						frm.set_value("processor_employee_name", emp.employee_name);
						frm.set_value("processor_employee_code", emp.employee_code);
						frm.set_value("processor_employee_type", emp.employee_type);

						console.log("Successfully populated processor fields");
					} else {
						console.warn("No Insurance Employee found for user:", frappe.session.user);
						console.log("Full response:", r.message);
					}
				},
				error: function(err) {
					console.error("Error fetching Insurance Employee:", err);
				}
			});
		} else {
			console.log("Processor fields already populated, skipping auto-population");
		}
	},
});

// Global cleanup function
frappe.policy_reader = frappe.policy_reader || {};
frappe.policy_reader.cleanup_processing_indicators = function () {
	$(".processing-indicator").remove();
	console.log("All Policy processing indicators cleared");
};
