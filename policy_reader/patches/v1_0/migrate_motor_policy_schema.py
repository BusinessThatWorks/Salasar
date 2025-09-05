import frappe
from frappe.utils import getdate


def execute():
    """
    Migrate existing Motor Policy records to new SAIBA ERP schema structure.
    
    This migration handles:
    1. Mapping old field names to new SAIBA-compliant field names
    2. Converting text date fields to proper date fields
    3. Preserving existing data while adapting to new schema structure
    """
    
    frappe.log_error("Starting Motor Policy SAIBA schema migration", "Data Migration")
    
    try:
        # Get all existing Motor Policy records
        motor_policies = frappe.get_all("Motor Policy", fields=["name"])
        
        if not motor_policies:
            frappe.log_error("No Motor Policy records found to migrate", "Data Migration")
            return
        
        migrated_count = 0
        error_count = 0
        
        # Field mapping from old structure to new SAIBA structure
        field_mappings = {
            # Policy information
            'policy_number': 'policy_no',
            'policy_from': 'policy_start_date',  # Convert text to date
            'policy_to': 'policy_expiry_date',   # Convert text to date
            
            # Vehicle information  
            'vehicle_number': 'vehicle_no',
            'registration_number': 'vehicle_no',  # Alternative source
            'chassis_number': 'chasis_no',
            'engine_number': 'engine_no',
            'make_model': 'make',  # Will need to split make and model
            'vehicle_class': 'vehicle_category',
            'seat_capacity': 'passenger_gvw',  # Convert to text
            
            # Financial information
            'premium_amount': 'net_od_premium',
            # sum_insured already exists with same name
            # Other financial fields (gst, tp_premium, ncb) exist but may be 0
        }
        
        for policy in motor_policies:
            try:
                # Get the full document
                doc = frappe.get_doc("Motor Policy", policy.name)
                
                updated = False
                updates = {}
                
                # Map old fields to new fields
                for old_field, new_field in field_mappings.items():
                    if hasattr(doc, old_field) and doc.get(old_field):
                        old_value = doc.get(old_field)
                        
                        # Handle special conversions
                        if new_field in ['policy_start_date', 'policy_expiry_date']:
                            # Convert date text like "01/07/2023" to date object
                            try:
                                if isinstance(old_value, str):
                                    # Parse DD/MM/YYYY format
                                    date_parts = old_value.split('/')
                                    if len(date_parts) == 3:
                                        # Convert DD/MM/YYYY to YYYY-MM-DD for getdate
                                        date_str = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"
                                        date_value = getdate(date_str)
                                        updates[new_field] = date_value
                                        updated = True
                            except Exception as e:
                                frappe.log_error(f"Date conversion error for {old_field}: {old_value} - {str(e)}")
                        
                        elif new_field == 'make':
                            # Split make_model into make and model
                            try:
                                if isinstance(old_value, str) and '-' in old_value:
                                    parts = old_value.split('-', 1)
                                    updates['make'] = parts[0].strip()
                                    if len(parts) > 1:
                                        updates['model'] = parts[1].strip()
                                else:
                                    updates['make'] = old_value
                                updated = True
                            except:
                                updates['make'] = old_value
                                updated = True
                        
                        elif new_field == 'passenger_gvw':
                            # Convert seat capacity number to text
                            updates[new_field] = str(old_value)
                            updated = True
                        
                        else:
                            # Direct mapping
                            updates[new_field] = old_value
                            updated = True
                
                # Handle variant field from existing variant field
                if hasattr(doc, 'variant') and doc.get('variant'):
                    # Variant field already exists, no need to map
                    pass
                
                # Apply updates using db.set_value to avoid validation issues
                if updated and updates:
                    for field_name, field_value in updates.items():
                        frappe.db.set_value("Motor Policy", doc.name, field_name, field_value)
                    
                    frappe.db.commit()
                    migrated_count += 1
                    
            except Exception as e:
                error_count += 1
                frappe.log_error(
                    f"Error migrating Motor Policy {policy.name}: {str(e)}", 
                    "Motor Policy Migration Error"
                )
        
        # Log migration summary
        frappe.log_error(
            f"Motor Policy SAIBA migration completed. Migrated: {migrated_count}, Errors: {error_count}, Total: {len(motor_policies)}", 
            "Data Migration Summary"
        )
        
        print(f"Motor Policy SAIBA schema migration completed:")
        print(f"- Total records: {len(motor_policies)}")
        print(f"- Successfully migrated: {migrated_count}")
        print(f"- Errors encountered: {error_count}")
        
    except Exception as e:
        frappe.log_error(f"Motor Policy migration failed: {str(e)}", "Data Migration Error")
        print(f"Migration failed: {str(e)}")
        raise