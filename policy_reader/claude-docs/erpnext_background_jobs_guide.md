# ERPNext Background Jobs Processing Guide

## Overview
ERPNext uses a Redis-based queue system for background job processing. Jobs are processed by worker processes that run separately from the web server, allowing heavy operations to run without blocking the user interface.

## Core Components

### 1. Queue System
- **Redis**: Acts as the message broker for job queues
- **RQ (Redis Queue)**: Python library used by Frappe for job queuing
- **Worker Processes**: Background processes that consume jobs from queues

### 2. Queue Types
- **default**: General purpose queue for most background jobs
- **short**: For quick jobs that should complete fast
- **long**: For long-running jobs that may take significant time

## Creating Background Jobs

### Method 1: Using `frappe.enqueue()`
```python
import frappe

# Basic job enqueueing
frappe.enqueue(
    method='my_app.module.function_name',
    queue='default',
    timeout=300,
    job_name='unique_job_identifier',
    **kwargs  # Arguments to pass to the function
)

# Example with specific parameters
frappe.enqueue(
    method='erpnext.accounts.utils.process_invoices',
    queue='long',
    timeout=600,
    job_name=f'process_invoices_{frappe.session.user}',
    invoice_list=['INV-001', 'INV-002'],
    update_stock=True
)
```

### Method 2: Using `frappe.enqueue_doc()`
```python
# For document-specific operations
doc = frappe.get_doc('Sales Order', 'SO-001')
frappe.enqueue_doc(
    doc.doctype,
    doc.name,
    method='submit_in_background',
    queue='default',
    timeout=300
)
```

### Method 3: Using Decorators
```python
from frappe.utils.background_jobs import enqueue

@enqueue(queue='long', timeout=1200)
def heavy_computation(data):
    # Your heavy processing logic here
    pass

# Call the function normally - it will automatically be queued
heavy_computation(my_data)
```

## Scheduled Jobs (Cron Jobs)

### 1. Hooks Configuration
In `hooks.py`:
```python
# Scheduled jobs
scheduler_events = {
    "cron": {
        "0 0 * * *": [  # Daily at midnight
            "my_app.tasks.daily_cleanup"
        ],
        "0 */6 * * *": [  # Every 6 hours
            "my_app.tasks.sync_data"
        ]
    },
    "daily": [
        "my_app.tasks.daily_report"
    ],
    "weekly": [
        "my_app.tasks.weekly_summary"
    ],
    "monthly": [
        "my_app.tasks.monthly_closing"
    ]
}
```

### 2. Manual Scheduling
```python
from frappe.utils.scheduler import enqueue_events

# Manually trigger scheduled events
enqueue_events('daily')
enqueue_events('weekly')
```

## Job Management

### 1. Job Status Monitoring
```python
import frappe
from rq import get_current_job

def my_background_function():
    job = get_current_job()
    if job:
        # Update job progress
        job.meta['progress'] = 50
        job.save_meta()
        
        # Check if job should be cancelled
        if frappe.db.get_value('Job Status', job.id, 'status') == 'cancelled':
            return
```

### 2. Job Querying
```python
from rq import Queue
from frappe.utils.redis_wrapper import RedisWrapper

redis = RedisWrapper.from_url(frappe.conf.redis_queue)
queue = Queue('default', connection=redis)

# Get job count
job_count = len(queue)

# Get all jobs
jobs = queue.jobs

# Get job by ID
job = queue.fetch_job('job_id')
```

## Error Handling

### 1. Job Failure Handling
```python
def my_background_job():
    try:
        # Your job logic here
        pass
    except Exception as e:
        frappe.log_error(
            message=str(e),
            title=f"Background Job Failed: {frappe.local.site}"
        )
        # Re-raise to mark job as failed
        raise
```

### 2. Retry Logic
```python
from rq.decorators import job

@job('default', connection=redis, timeout=300, result_ttl=86400)
def retryable_job():
    # Job with automatic retry capability
    pass
```

## Performance Considerations

### 1. Queue Selection
- Use `short` queue for jobs < 30 seconds
- Use `default` queue for jobs 30 seconds - 5 minutes  
- Use `long` queue for jobs > 5 minutes

### 2. Batch Processing
```python
def process_documents_in_batches(doc_list, batch_size=100):
    for i in range(0, len(doc_list), batch_size):
        batch = doc_list[i:i + batch_size]
        frappe.enqueue(
            method='process_document_batch',
            queue='default',
            batch=batch,
            job_name=f'batch_process_{i//batch_size}'
        )
```

### 3. Progress Tracking
```python
def long_running_job(total_items):
    job = get_current_job()
    
    for i, item in enumerate(items):
        # Process item
        process_item(item)
        
        # Update progress
        if job:
            progress = (i + 1) / total_items * 100
            job.meta['progress'] = progress
            job.save_meta()
            
            # Publish progress via websocket
            frappe.publish_realtime(
                'job_progress',
                {'progress': progress, 'job_id': job.id},
                user=frappe.session.user
            )
```

## Common Patterns

### 1. Document Processing
```python
def process_sales_orders_background(filters=None):
    """Process sales orders in background"""
    orders = frappe.get_all('Sales Order', filters=filters or {})
    
    for order in orders:
        frappe.enqueue(
            method='erpnext.selling.doctype.sales_order.sales_order.make_delivery_note',
            queue='default',
            sales_order=order.name,
            job_name=f'create_dn_{order.name}'
        )
```

### 2. Report Generation
```python
def generate_report_background(report_name, filters, user):
    """Generate report in background and email to user"""
    frappe.enqueue(
        method='my_app.reports.generate_and_email_report',
        queue='long',
        timeout=1800,
        report_name=report_name,
        filters=filters,
        recipient=user,
        job_name=f'report_{report_name}_{user}'
    )
```

### 3. Data Import/Export
```python
def import_data_background(file_path, doctype, user):
    """Import data from file in background"""
    frappe.enqueue(
        method='frappe.core.doctype.data_import.data_import.import_data',
        queue='long',
        timeout=3600,
        file_path=file_path,
        doctype=doctype,
        user=user,
        job_name=f'import_{doctype}_{user}'
    )
```

## CLI Commands

### Worker Management
```bash
# Start workers
bench start

# Start specific worker
bench worker --queue default

# Check worker status
bench show-config

# Clear failed jobs
bench clear-cache --user all
```

### Job Monitoring
```bash
# Monitor job queues
bench console
>>> from rq import Queue, Connection
>>> with Connection():
...     q = Queue('default')
...     print(f"Jobs in queue: {len(q)}")
```

## Debugging Tips

1. **Check Redis Connection**: Ensure Redis is running and accessible
2. **Monitor Worker Logs**: Check bench logs for worker errors
3. **Queue Inspection**: Use RQ dashboard or CLI tools to inspect queues
4. **Job Timeouts**: Set appropriate timeouts for different job types
5. **Memory Usage**: Monitor worker memory consumption for large jobs

## Security Considerations

1. **User Context**: Jobs run without user context by default
2. **Permissions**: Explicitly set user context when needed:
   ```python
   frappe.set_user('Administrator')  # Or specific user
   ```
3. **Data Validation**: Always validate data in background jobs
4. **Error Logging**: Log errors without exposing sensitive information

## Integration with Frontend

### Progress Updates
```javascript
// Listen for job progress updates
frappe.realtime.on('job_progress', function(data) {
    update_progress_bar(data.progress);
});

// Start background job and show progress
frappe.call({
    method: 'my_app.api.start_background_job',
    callback: function(r) {
        if (r.message.job_id) {
            show_progress_dialog(r.message.job_id);
        }
    }
});
```

This guide provides the foundation for understanding and implementing background job processing in ERPNext. Reference this when working with background jobs to ensure proper implementation and best practices.