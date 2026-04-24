frappe.listview_settings["Motor Policy"] = {
    formatters: {
        saiba_control_number: function(value, df, doc) {
            if (!value) return "";

            if (value === "Pending") {
                return `<span style="
                    background-color:#ffe6e6;
                    color:#cc0000;
                    font-weight:bold;
                    padding:2px 8px;
                    border-radius:4px;">
                    ${value}
                </span>`;
            } else {
                return `<span style="
                    background-color:#e6ffe6;
                    color:#008000;
                    font-weight:bold;
                    padding:2px 8px;
                    border-radius:4px;">
                    ${value}
                </span>`;
            }
        }
    }
};