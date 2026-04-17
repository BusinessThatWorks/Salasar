// Copyright (c) 2025, Clapgrow Software and contributors
// For license information, please see license.txt
frappe.ui.form.on("Insurance Customer", {
    city(frm) {
        if (frm.doc.city && !frm.doc.location) {
            frm.set_value("location", frm.doc.city);}
        
    },

    refresh(frm) {
        frm.clear_custom_buttons();
        frappe.db.get_single_value("Policy Reader Settings", "saiba_enabled").then((enabled) => {
            if (!enabled) return;

            const colorMap = {
                "Synced": "green",
                "Failed": "red",
                "Pending": "orange",
                "Duplicate Entry": "yellow",
            };

            // Show status indicator
            if (frm.doc.saiba_sync_status && frm.doc.saiba_sync_status !== "Not Synced") {
                frm.page.set_indicator(
                    frm.doc.saiba_sync_status,
                    colorMap[frm.doc.saiba_sync_status] || "gray"
                );
            }
            if (!frm.is_new()) {
                frm.add_custom_button(__("Sync to SAIBA"), function () {
                    frappe.confirm(
                        __("Are you sure you want to sync this Customer to SAIBA?"),
                        function () {
                            frappe.show_alert({
                                message: __("Syncing Customer to SAIBA..."),
                                indicator: "blue",
                            });

                            frappe.call({
                                method: "policy_reader.policy_reader.services.saiba_sync_service.sync_customer_details",
                                args: {
                                    customer_name: frm.doc.name,
                                },
                                freeze: true,
                                callback: function (response) {
                                    if (response.message && response.message.success) {
                                        frappe.show_alert({
                                            message: __("Successfully synced to SAIBA. Customer Code: {0}", [
                                                response.message.customer_code || "N/A",
                                            ]),
                                            indicator: "green",
                                        });
                                    frm.reload_doc();
                                    } else {
                                        frappe.show_alert({
                                            message: __("Sync failed: {0}", [
                                                response.message && response.message.error
                                                    ? response.message.error
                                                    : "Unknown error",
                                            ]),
                                            indicator: "red",
                                        });
                                    frm.reload_doc();
                                    }
                                   
                                },
                            });
                        }
                    );
                });  
            }
        });
        frappe.model.on(frm.doctype, "*", function (fieldname, value, doc) {
            if (doc.name === frm.docname) {
                frm.clear_custom_buttons();
            }
        });
    },
});