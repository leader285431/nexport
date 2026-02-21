app_name = "nexport"
app_title = "NexPort"
app_publisher = "NexPort"
app_description = "NexPort ERP custom app"
app_email = "support@nexport.local"
app_license = "MIT"

fixtures = [
    {
        "doctype": "Role",
        "filters": [
            [
                "role_name",
                "in",
                [
                    "NexPort Admin",
                    "NexPort Finance",
                    "NexPort Warehouse",
                    "NexPort Sales",
                    "NexPort Procurement",
                ],
            ]
        ],
    },
    {
        "doctype": "Workflow",
        "filters": [
            [
                "name",
                "in",
                [
                    "Shipment Workflow",
                    "Purchase Order Workflow",
                    "Invoice Workflow",
                    "Quote Workflow",
                    "Sales Order Workflow",
                    "Delivery Note Workflow",
                ],
            ]
        ],
    },
]

scheduler_events = {
    "daily": [
        "nexport.services.payment_service.mark_overdue_installments",
        "nexport.services.payment_service.send_payment_reminders",
        "nexport.services.exchange_rate_service.fetch_and_cache",
        "nexport.services.stock_service.auto_generate_material_requests",
    ],
}
