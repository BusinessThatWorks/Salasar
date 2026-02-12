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

    // Add custom styles
    policy_reader.saiba._add_modal_styles();

    return dialog;
};

/**
 * Build summary header HTML
 * Uses Frappe CSS variables for light/dark mode support
 */
policy_reader.saiba._build_summary_html = function(summary) {
    const ready = summary.ready_to_sync;
    const statusClass = ready ? 'saiba-status-success' : 'saiba-status-error';
    const iconBgColor = ready ? '#22c55e' : '#ef4444';
    const icon = ready ? '&#10003;' : '&#10007;';
    const title = ready ? __('Ready to Sync') : __('Not Ready to Sync');

    return `
        <div class="validation-summary ${statusClass}">
            <div class="validation-summary-content">
                <div class="validation-summary-icon" style="background: ${iconBgColor};">
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
            const iconBgColor = field.is_valid ? '#22c55e' : '#ef4444';
            const icon = field.is_valid ? '&#10003;' : '&#10007;';

            html += `
                <tr class="validation-field-row">
                    <td class="validation-field-icon-cell">
                        <span class="validation-field-icon ${iconClass}" style="background: ${iconBgColor};">
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
 * Add custom styles to the modal
 * Uses Frappe CSS variables for light/dark mode support
 */
policy_reader.saiba._add_modal_styles = function() {
    if (document.getElementById('saiba-validation-styles')) return;

    const style = document.createElement('style');
    style.id = 'saiba-validation-styles';
    style.textContent = `
        /* Modal container */
        .saiba-validation-modal {
            max-height: 60vh;
            overflow-y: auto;
            padding: 4px;
        }

        /* Summary banner - Success state */
        .validation-summary.saiba-status-success {
            padding: 18px 20px;
            background: var(--alert-bg-success, #ecfdf5);
            border: 1px solid #22c55e;
            border-radius: 10px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(34, 197, 94, 0.1);
        }

        /* Summary banner - Error state */
        .validation-summary.saiba-status-error {
            padding: 18px 20px;
            background: var(--alert-bg-danger, #fef2f2);
            border: 1px solid #ef4444;
            border-radius: 10px;
            margin-bottom: 24px;
            box-shadow: 0 1px 3px rgba(239, 68, 68, 0.1);
        }

        .validation-summary-content {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .validation-summary-icon {
            width: 52px;
            height: 52px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
        }

        .validation-summary-icon span {
            color: white;
            font-size: 26px;
            font-weight: bold;
            line-height: 1;
        }

        .validation-summary-text h4 {
            margin: 0;
            font-weight: 600;
            font-size: 16px;
        }

        .saiba-status-success .validation-summary-text h4 {
            color: var(--alert-text-success, #065f46);
        }

        .saiba-status-error .validation-summary-text h4 {
            color: var(--alert-text-danger, #991b1b);
        }

        .validation-summary-text p {
            margin: 6px 0 0 0;
            color: var(--text-muted, #6b7280);
            font-size: 14px;
        }

        /* Categories container */
        .validation-categories {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        /* Individual category */
        .validation-category {
            background: var(--card-bg, #ffffff);
            border: 1px solid var(--border-color, #e5e7eb);
            border-radius: 8px;
            overflow: hidden;
        }

        /* Category header */
        .validation-category-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 14px 18px;
            background: var(--subtle-fg, var(--card-bg, #f9fafb));
            border-bottom: 1px solid var(--border-color, #e5e7eb);
        }

        .validation-category-header h5 {
            margin: 0;
            font-weight: 600;
            font-size: 14px;
            color: var(--fg-color, #374151);
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }

        /* Badge styles */
        .saiba-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
        }

        .saiba-badge-success {
            background: rgba(34, 197, 94, 0.15);
            color: #16a34a;
        }

        .saiba-badge-error {
            background: rgba(239, 68, 68, 0.15);
            color: #dc2626;
        }

        /* Fields table */
        .validation-fields-table {
            width: 100%;
            border-collapse: collapse;
        }

        .validation-field-row {
            border-bottom: 1px solid var(--border-color, #e5e7eb);
        }

        .validation-field-row:last-child {
            border-bottom: none;
        }

        .validation-field-row:hover {
            background: var(--subtle-fg, rgba(0, 0, 0, 0.02));
        }

        /* Icon cell */
        .validation-field-icon-cell {
            padding: 12px 8px 12px 16px;
            width: 40px;
            vertical-align: middle;
        }

        .validation-field-icon {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            font-size: 13px;
            font-weight: bold;
            color: white;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.15);
        }

        /* Label cell */
        .validation-field-label-cell {
            padding: 12px 8px;
            vertical-align: middle;
        }

        .validation-field-label {
            font-weight: 500;
            font-size: 13px;
            color: var(--fg-color, #374151);
        }

        .validation-field-error {
            font-size: 12px;
            color: #dc2626;
            margin-top: 4px;
        }

        /* Value cell */
        .validation-field-value-cell {
            padding: 12px 16px 12px 8px;
            text-align: right;
            font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, monospace;
            font-size: 13px;
            max-width: 220px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            vertical-align: middle;
        }

        .validation-field-value-cell.saiba-field-valid {
            color: var(--text-muted, #6b7280);
        }

        .validation-field-value-cell.saiba-field-invalid {
            color: #dc2626;
            font-weight: 500;
        }

        /* Scrollbar styling */
        .saiba-validation-modal::-webkit-scrollbar {
            width: 8px;
        }

        .saiba-validation-modal::-webkit-scrollbar-track {
            background: var(--border-color, #e5e7eb);
            border-radius: 4px;
        }

        .saiba-validation-modal::-webkit-scrollbar-thumb {
            background: var(--text-muted, #9ca3af);
            border-radius: 4px;
        }

        .saiba-validation-modal::-webkit-scrollbar-thumb:hover {
            background: var(--fg-color, #6b7280);
        }

        /* ========================================
           DARK MODE OVERRIDES
           ======================================== */
        [data-theme="dark"] .saiba-validation-modal,
        .dark .saiba-validation-modal {
            /* Dark mode detected */
        }

        /* Summary banner - dark mode */
        [data-theme="dark"] .validation-summary.saiba-status-success,
        .dark .validation-summary.saiba-status-success {
            background: rgba(34, 197, 94, 0.12);
            border-color: #22c55e;
        }

        [data-theme="dark"] .validation-summary.saiba-status-error,
        .dark .validation-summary.saiba-status-error {
            background: rgba(239, 68, 68, 0.12);
            border-color: #ef4444;
        }

        [data-theme="dark"] .saiba-status-success .validation-summary-text h4,
        .dark .saiba-status-success .validation-summary-text h4 {
            color: #4ade80;
        }

        [data-theme="dark"] .saiba-status-error .validation-summary-text h4,
        .dark .saiba-status-error .validation-summary-text h4 {
            color: #fca5a5;
        }

        [data-theme="dark"] .validation-summary-text p,
        .dark .validation-summary-text p {
            color: #a1a1aa;
        }

        /* Badge - dark mode */
        [data-theme="dark"] .saiba-badge-success,
        .dark .saiba-badge-success {
            background: rgba(34, 197, 94, 0.25);
            color: #86efac;
        }

        [data-theme="dark"] .saiba-badge-error,
        .dark .saiba-badge-error {
            background: rgba(239, 68, 68, 0.25);
            color: #fca5a5;
        }

        /* Field labels - dark mode (near white for readability) */
        [data-theme="dark"] .validation-field-label,
        .dark .validation-field-label {
            color: #fafafa;
        }

        /* Field errors - dark mode (brighter red, bolder) */
        [data-theme="dark"] .validation-field-error,
        .dark .validation-field-error {
            color: #fca5a5;
            font-weight: 500;
        }

        /* Field values - dark mode (near white) */
        [data-theme="dark"] .validation-field-value-cell.saiba-field-valid,
        .dark .validation-field-value-cell.saiba-field-valid {
            color: #e4e4e7;
        }

        [data-theme="dark"] .validation-field-value-cell.saiba-field-invalid,
        .dark .validation-field-value-cell.saiba-field-invalid {
            color: #fca5a5;
            font-weight: 600;
        }

        /* Status icons - dark mode (darker backgrounds) */
        [data-theme="dark"] .validation-field-icon.saiba-icon-valid,
        .dark .validation-field-icon.saiba-icon-valid {
            background: #166534 !important;
        }

        [data-theme="dark"] .validation-field-icon.saiba-icon-invalid,
        .dark .validation-field-icon.saiba-icon-invalid {
            background: #991b1b !important;
        }

        /* Category header - dark mode */
        [data-theme="dark"] .validation-category-header h5,
        .dark .validation-category-header h5 {
            color: #e4e4e7;
        }

        /* Row hover - dark mode */
        [data-theme="dark"] .validation-field-row:hover,
        .dark .validation-field-row:hover {
            background: rgba(255, 255, 255, 0.03);
        }
    `;
    document.head.appendChild(style);
};

/**
 * Mark fields that are required for SAIBA sync with a small blue "S" badge.
 * Respects the saiba_enabled toggle — badges only appear when enabled.
 * @param {object} frm - Frappe form object
 * @param {string} policy_type - 'Motor' or 'Health'
 */
policy_reader.saiba.mark_required_fields = function(frm, policy_type) {
    // Ensure indicator styles are injected
    policy_reader.saiba._add_indicator_styles();

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
 * Inject CSS for SAIBA required-field indicator badges.
 * Called once; subsequent calls are no-ops.
 */
policy_reader.saiba._add_indicator_styles = function() {
    if (document.getElementById('saiba-indicator-styles')) return;

    const style = document.createElement('style');
    style.id = 'saiba-indicator-styles';
    style.textContent = `
        .saiba-required-indicator {
            display: inline-block;
            margin-left: 5px;
            padding: 0 5px;
            font-size: 9px;
            font-weight: 700;
            line-height: 16px;
            color: #fff;
            background: #2490ef;
            border-radius: 8px;
            vertical-align: middle;
            cursor: default;
            letter-spacing: 0.3px;
        }

        /* Dark mode */
        [data-theme="dark"] .saiba-required-indicator,
        .dark .saiba-required-indicator {
            background: #5fa8f5;
            color: #1a1a2e;
        }
    `;
    document.head.appendChild(style);
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
