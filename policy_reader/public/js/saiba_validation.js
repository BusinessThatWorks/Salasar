// Copyright (c) 2026, Clapgrow Software and contributors
// For license information, please see license.txt

frappe.provide('policy_reader.saiba');

/**
 * Validate a policy for SAIBA sync and show results modal
 * @param {string} policy_type - 'Motor' or 'Health'
 * @param {string} policy_name - Name of the policy document
 * @param {function} on_sync_callback - Callback to execute when user clicks sync
 */
policy_reader.saiba.validate = function(policy_type, policy_name, on_sync_callback) {
    const method = policy_type.toLowerCase() === 'motor'
        ? 'policy_reader.policy_reader.services.saiba_validation_service.validate_motor_policy'
        : 'policy_reader.policy_reader.services.saiba_validation_service.validate_health_policy';

    frappe.show_alert({
        message: __('Validating policy for SAIBA sync...'),
        indicator: 'blue'
    });

    frappe.call({
        method: method,
        args: { policy_name: policy_name },
        callback: function(response) {
            if (response.message && response.message.success) {
                policy_reader.saiba.show_validation_modal(response.message, on_sync_callback);
            } else {
                frappe.msgprint({
                    title: __('Validation Error'),
                    message: response.message?.error || __('Failed to validate policy'),
                    indicator: 'red'
                });
            }
        },
        error: function(error) {
            frappe.msgprint({
                title: __('Validation Error'),
                message: __('Error validating policy. Please try again.'),
                indicator: 'red'
            });
            console.error('SAIBA validation error:', error);
        }
    });
};

/**
 * Show the validation results modal
 * @param {object} result - Validation result from backend
 * @param {function} on_sync - Callback when user clicks sync
 */
policy_reader.saiba.show_validation_modal = function(result, on_sync) {
    const summary = result.summary;
    const categories = result.categories;
    const ready = summary.ready_to_sync;

    // Build HTML content
    let html = policy_reader.saiba._build_summary_html(summary);
    html += policy_reader.saiba._build_categories_html(categories);

    // Always show sync button, but add warning style if validation failed
    const syncLabel = ready ? __('Sync to SAIBA') : __('Sync to SAIBA (with warnings)');

    // Create dialog
    const dialog = new frappe.ui.Dialog({
        title: __('SAIBA Validation - {0}', [result.policy_name]),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'validation_content',
                options: `<div class="saiba-validation-modal">${html}</div>`
            }
        ],
        primary_action_label: syncLabel,
        primary_action: function() {
            if (!ready) {
                // Show confirmation before syncing with validation errors
                frappe.confirm(
                    __('Some required fields are missing or invalid. SAIBA may reject this policy. Continue anyway?'),
                    function() {
                        dialog.hide();
                        if (on_sync) on_sync();
                    }
                );
            } else {
                dialog.hide();
                if (on_sync) on_sync();
            }
        },
        secondary_action_label: __('Close'),
        secondary_action: function() {
            dialog.hide();
        }
    });

    // Add warning style to sync button if validation failed
    if (!ready) {
        dialog.$wrapper.find('.btn-primary')
            .removeClass('btn-primary')
            .addClass('btn-warning');
    }

    dialog.show();

    return dialog;
};

/**
 * Build summary header HTML
 * Uses Frappe CSS variables for light/dark mode support
 */
policy_reader.saiba._build_summary_html = function(summary) {
    const ready = summary.ready_to_sync;
    const statusClass = ready ? 'saiba-status-success' : 'saiba-status-error';
    const iconClass = ready ? 'saiba-icon-valid' : 'saiba-icon-invalid';
    const icon = ready ? '&#10003;' : '&#10007;';
    const title = ready ? __('Ready to Sync') : __('Not Ready to Sync');

    return `
        <div class="validation-summary ${statusClass}">
            <div class="validation-summary-content">
                <div class="validation-summary-icon ${iconClass}">
                    <span>${icon}</span>
                </div>
                <div class="validation-summary-text">
                    <h4>${title}</h4>
                    <p>${summary.valid} of ${summary.total_required} required fields are valid</p>
                </div>
            </div>
        </div>
    `;
};

/**
 * Build categories HTML with field lists
 * Uses CSS classes for theme-aware styling
 */
policy_reader.saiba._build_categories_html = function(categories) {
    let html = '<div class="validation-categories">';

    categories.forEach(function(category) {
        const validCount = category.fields.filter(f => f.is_valid).length;
        const totalCount = category.fields.length;
        const allValid = validCount === totalCount;
        const badgeClass = allValid ? 'saiba-badge-success' : 'saiba-badge-error';

        html += `
            <div class="validation-category">
                <div class="validation-category-header">
                    <h5>${category.name}</h5>
                    <span class="saiba-badge ${badgeClass}">${validCount}/${totalCount}</span>
                </div>
                <table class="validation-fields-table">
                    <tbody>
        `;

        category.fields.forEach(function(field) {
            const statusClass = field.is_valid ? 'saiba-field-valid' : 'saiba-field-invalid';
            const iconClass = field.is_valid ? 'saiba-icon-valid' : 'saiba-icon-invalid';
            const icon = field.is_valid ? '&#10003;' : '&#10007;';

            html += `
                <tr class="validation-field-row">
                    <td class="validation-field-icon-cell">
                        <span class="validation-field-icon ${iconClass}">
                            ${icon}
                        </span>
                    </td>
                    <td class="validation-field-label-cell">
                        <div class="validation-field-label">${field.label}</div>
                        ${!field.is_valid && field.error
                            ? `<div class="validation-field-error">${field.error}</div>`
                            : ''}
                    </td>
                    <td class="validation-field-value-cell ${statusClass}">
                        ${field.value}
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
    });

    html += '</div>';
    return html;
};

/**
 * Mark fields that are required for SAIBA sync with a small blue "S" badge.
 * Respects the saiba_enabled toggle — badges only appear when enabled.
 * @param {object} frm - Frappe form object
 * @param {string} policy_type - 'Motor' or 'Health'
 */
policy_reader.saiba.mark_required_fields = function(frm, policy_type) {
    frappe.call({
        method: 'policy_reader.policy_reader.services.saiba_validation_service.get_required_fields',
        args: { policy_type: policy_type },
        callback: function(r) {
            if (!r.message || !r.message.length) return;

            r.message.forEach(function(fieldname) {
                const field = frm.fields_dict[fieldname];
                if (!field || !field.$wrapper) return;

                const $label = field.$wrapper.find('.control-label, label').first();
                if (!$label.length) return;

                // Skip if badge already present
                if ($label.find('.saiba-required-indicator').length) return;

                $label.append(
                    '<span class="saiba-required-indicator" title="Required for SAIBA Sync">S</span>'
                );
            });
        }
    });
};

/**
 * Add "Validate for SAIBA" button to a form
 * @param {object} frm - Frappe form object
 * @param {string} policy_type - 'Motor' or 'Health'
 */
policy_reader.saiba.add_validate_button = function(frm, policy_type) {
    // Check if validation is enabled
    frappe.call({
        method: 'policy_reader.policy_reader.services.saiba_validation_service.is_validation_enabled',
        async: false,
        callback: function(r) {
            if (r.message && r.message.enabled) {
                frm.add_custom_button(__('Validate for SAIBA'), function() {
                    policy_reader.saiba.validate(policy_type, frm.doc.name, function() {
                        // Sync callback - trigger the actual sync
                        policy_reader.saiba._perform_sync(frm, policy_type);
                    });
                }, __('Actions'));
            }
        }
    });
};

/**
 * Perform the actual SAIBA sync
 */
policy_reader.saiba._perform_sync = function(frm, policy_type) {
    const method = policy_type.toLowerCase() === 'motor'
        ? 'policy_reader.policy_reader.services.saiba_sync_service.sync_motor_policy'
        : 'policy_reader.policy_reader.services.saiba_sync_service.sync_health_policy';

    frappe.show_alert({
        message: __('Syncing to SAIBA...'),
        indicator: 'blue'
    });

    frappe.call({
        method: method,
        args: { policy_name: frm.doc.name },
        callback: function(response) {
            if (response.message && response.message.success) {
                frappe.show_alert({
                    message: __('Successfully synced to SAIBA. Control Number: {0}',
                        [response.message.control_number || 'N/A']),
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.show_alert({
                    message: __('Sync failed: {0}', [response.message?.error || 'Unknown error']),
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
};
