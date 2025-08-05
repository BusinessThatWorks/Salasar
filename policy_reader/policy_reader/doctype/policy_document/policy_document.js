// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.ui.form.on('Policy Document', {
    refresh: function(frm) {
        // Clear any processing indicators first
        frm.trigger('cleanup_all_processing_indicators');
        
        // Set up real-time event listener for background processing updates
        frm.trigger('setup_realtime_listener');
        
        // Check and display API key status
        frm.trigger('check_api_key_status');
        
        // Add Process Now button
        if (frm.doc.policy_file && frm.doc.policy_type && frm.doc.status !== 'Processing') {
            frm.add_custom_button(__('Process Now'), function() {
                frm.trigger('start_processing');
            }, __('Actions'));
        }
        
        // Show processing status in dashboard (but not the persistent indicator)
        if (frm.doc.status === 'Processing') {
            frm.dashboard.add_comment(__('Processing in progress...'), 'blue', true);
            // Note: We don't automatically show the processing indicator on refresh
            // It will only show when user explicitly starts processing
        }
        
        // Extracted fields display removed per user request
        
        // Add field state indicators for manual vs extracted data
        frm.trigger('add_field_state_indicators');
        
        // Add cleanup handler for navigation/form close
        frm.trigger('setup_navigation_cleanup');
    },
    
    setup_navigation_cleanup: function(frm) {
        // Cleanup indicators when form is destroyed or navigating away
        $(window).off('beforeunload.policy_processing').on('beforeunload.policy_processing', function() {
            frm.trigger('cleanup_all_processing_indicators');
        });
        
        // Also cleanup when hash changes (navigation within Frappe)
        $(window).off('hashchange.policy_processing').on('hashchange.policy_processing', function() {
            frm.trigger('cleanup_all_processing_indicators');
        });
    },
    
    policy_file: function(frm) {
        // Auto-generate title from filename
        if (frm.doc.policy_file && !frm.doc.title) {
            let filename = frm.doc.policy_file.split('/').pop();
            let title = filename.replace('.pdf', '').replace('.PDF', '');
            frm.set_value('title', title);
        }
        
        // Auto-trigger processing when both file and policy type are set
        if (frm.doc.policy_file && frm.doc.policy_type && frm.doc.status === 'Draft') {
            frm.trigger('auto_process_policy');
        }
    },
    
    policy_type: function(frm) {
        // Auto-trigger processing when both file and policy type are set
        if (frm.doc.policy_file && frm.doc.policy_type && frm.doc.status === 'Draft') {
            frm.trigger('auto_process_policy');
        }
    },
    
    auto_process_policy: function(frm) {
        // Automatically start processing when PDF and policy type are set
        if (frm.doc.policy_file && frm.doc.policy_type && frm.doc.status === 'Draft') {
            frappe.confirm(
                __('Do you want to automatically process this policy document?'),
                function() {
                    frm.call('process_policy').then(r => {
                        if (r.message && r.message.success) {
                            frappe.show_alert({
                                message: __(r.message.message),
                                indicator: 'blue'
                            });
                            frm.reload_doc();
                        }
                    });
                },
                function() {
                    // User declined, do nothing
                }
            );
        }
    },
    
    
    setup_realtime_listener: function(frm) {
        // Set up real-time event listener for policy processing completion
        frappe.realtime.on('policy_processing_complete', function(message) {
            if (message.doc_name === frm.doc.name) {
                // Hide processing indicator
                frm.trigger('hide_processing_indicator');
                
                // Show completion notification
                if (message.status === 'Completed') {
                    frappe.show_alert({
                        message: __('Policy processing completed successfully! Processing time: {0}s', [message.processing_time]),
                        indicator: 'green'
                    });
                } else {
                    frappe.show_alert({
                        message: __('Policy processing failed: {0}', [message.message]),
                        indicator: 'red'
                    });
                }
                
                // Reload the document to show updated data
                frm.reload_doc();
            }
        });
    },
    
    start_processing: function(frm) {
        // Show loading indicator immediately
        frm.trigger('show_processing_indicator');
        
        // Call the background processing method
        frm.call('process_policy').then(r => {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: __(r.message.message),
                    indicator: 'blue'
                });
                frm.reload_doc();
            } else if (r.message) {
                frm.trigger('hide_processing_indicator');
                frappe.msgprint({
                    title: __('Processing Failed'),
                    message: r.message.message || __('Unknown error occurred'),
                    indicator: 'red'
                });
            }
        }).catch(err => {
            frm.trigger('hide_processing_indicator');
            frappe.msgprint({
                title: __('Processing Error'),
                message: __('Failed to start processing: {0}', [err.message]),
                indicator: 'red'
            });
        });
    },
    
    show_processing_indicator: function(frm) {
        // Remove any existing indicators first
        frm.trigger('cleanup_all_processing_indicators');
        
        // Add visual processing indicator with dismiss button
        frm.processing_indicator = $(
            '<div class="processing-indicator" style="position: fixed; top: 60px; right: 20px; z-index: 1050; background: #007bff; color: white; padding: 10px 15px; border-radius: 5px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); max-width: 300px;">' +
            '<i class="fa fa-spin fa-spinner"></i> Processing Policy...' +
            '<button class="btn btn-sm" style="background: none; border: none; color: white; margin-left: 10px; padding: 0 5px; font-size: 16px;" title="Dismiss notification">&times;</button>' +
            '</div>'
        ).appendTo('body');
        
        // Add click handler for dismiss button
        frm.processing_indicator.find('button').on('click', function() {
            frm.trigger('hide_processing_indicator');
        });
        
        // Auto-hide after 5 minutes if no completion event
        frm.processing_timeout = setTimeout(function() {
            if (frm.processing_indicator) {
                frm.trigger('hide_processing_indicator');
                frappe.show_alert({
                    message: __('Processing indicator auto-hidden. Check document status for updates.'),
                    indicator: 'orange'
                });
            }
        }, 300000); // 5 minutes
    },
    
    hide_processing_indicator: function(frm) {
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
    
    cleanup_all_processing_indicators: function(frm) {
        // Remove any existing processing indicators from the page
        $('.processing-indicator').remove();
        
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
    
    add_field_state_indicators: function(frm) {
        // Add visual indicators to show which fields were extracted vs manually entered
        if (frm.doc.status === 'Completed' && frm.doc.extracted_fields && frm.doc.policy_type) {
            try {
                let extracted_data = JSON.parse(frm.doc.extracted_fields);
                let field_mapping = {};
                
                // Define field mappings based on policy type
                if (frm.doc.policy_type.toLowerCase() === 'motor') {
                    field_mapping = {
                        "Policy Number": "policy_number_motor",
                        "Insured Name": "insured_name_motor", 
                        "Vehicle Number": "vehicle_number_motor",
                        "Chassis Number": "chassis_number_motor",
                        "Engine Number": "engine_number_motor",
                        "From": "policy_from_motor",
                        "To": "policy_to_motor",
                        "Premium Amount": "premium_amount_motor",
                        "Sum Insured": "sum_insured_motor",
                        "Make / Model": "make_model_motor",
                        "Variant": "variant_motor",
                        "Vehicle Class": "vehicle_class_motor",
                        "Registration Number": "registration_number_motor",
                        "Fuel": "fuel_motor",
                        "Seat Capacity": "seat_capacity_motor"
                    };
                } else if (frm.doc.policy_type.toLowerCase() === 'health') {
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
                        "Date of Birth": "date_of_birth_health"
                    };
                }
                
                // Add indicators to each field
                Object.keys(field_mapping).forEach(extracted_field => {
                    let doctype_field = field_mapping[extracted_field];
                    let field_wrapper = frm.fields_dict[doctype_field];
                    
                    if (field_wrapper && field_wrapper.wrapper) {
                        // Remove existing indicators
                        $(field_wrapper.wrapper).find('.field-state-indicator').remove();
                        
                        let was_extracted = extracted_data[extracted_field];
                        let current_value = frm.doc[doctype_field];
                        
                        let indicator_html = '';
                        let indicator_class = '';
                        let indicator_title = '';
                        
                        if (was_extracted && current_value === was_extracted) {
                            // Field was extracted and unchanged
                            indicator_class = 'text-success';
                            indicator_html = '<i class="fa fa-robot"></i>';
                            indicator_title = 'Extracted by OCR';
                        } else if (was_extracted && current_value !== was_extracted) {
                            // Field was extracted but manually modified
                            indicator_class = 'text-warning';
                            indicator_html = '<i class="fa fa-edit"></i>';
                            indicator_title = 'Extracted by OCR, manually modified';
                        } else if (!was_extracted && current_value) {
                            // Field was not extracted but manually entered
                            indicator_class = 'text-info';
                            indicator_html = '<i class="fa fa-user"></i>';
                            indicator_title = 'Manually entered';
                        } else {
                            // Field was not extracted and still empty
                            indicator_class = 'text-muted';
                            indicator_html = '<i class="fa fa-question-circle"></i>';
                            indicator_title = 'Not extracted - please enter manually';
                        }
                        
                        let indicator = $(
                            `<span class="field-state-indicator ${indicator_class}" style="position: absolute; right: 5px; top: 8px;" title="${indicator_title}">
                                ${indicator_html}
                            </span>`
                        );
                        
                        $(field_wrapper.wrapper).find('.control-input-wrapper').css('position', 'relative').append(indicator);
                    }
                });
                
            } catch (e) {
                console.error('Error adding field state indicators:', e);
            }
        }
    },
    
    check_api_key_status: function(frm) {
        // Check API key status and display in dashboard
        frappe.call({
            method: 'policy_reader.policy_reader.doctype.policy_document.policy_document.check_api_key_status',
            callback: function(r) {
                if (r.message) {
                    let status = r.message;
                    let color = status.configured ? 'green' : 'red';
                    let icon = status.configured ? '✓' : '✗';
                    let message = `${icon} API Key: ${status.message}`;
                    
                    // Remove existing API key status
                    $('.api-key-status').remove();
                    
                    // Add to dashboard
                    frm.dashboard.add_comment(message, color, true);
                    
                    // Also add a small indicator near the form title
                    let indicator = $(`<span class="api-key-status" style="margin-left: 10px; color: ${color === 'green' ? '#28a745' : '#dc3545'}; font-size: 12px;">${message}</span>`);
                    $('.form-layout .title-area h1').append(indicator);
                }
            }
        });
    }
});

// Global cleanup function for processing indicators
// Can be called from browser console if needed: frappe.policy_reader.cleanup_processing_indicators()
frappe.policy_reader = frappe.policy_reader || {};
frappe.policy_reader.cleanup_processing_indicators = function() {
    // Remove all processing indicators from the page
    $('.processing-indicator').remove();
    console.log('All Policy processing indicators cleared');
};
