{
    'name': 'Prepaid Hours / Service Packages',
    'version': '1.0.0',
    'summary': 'Sell prepaid hour packages and track consumption via timesheets',
    'description': """
        Allows selling prepaid service packages (hours or credits).
        Automatically tracks consumption from validated timesheets.
        Alerts when balance is low or expired.
        Compatible with Odoo 17, 18 and 19.
    """,
    'author': 'TPI - Soluciones Informáticas',
    'website': 'https://tpi.com.do',
    'category': 'Services/Timesheets',
    'license': 'OPL-1',
    'price': 149.00,
    'currency': 'USD',
    'images': ['static/description/banner.png'],
    'depends': [
        'sale_management',
        'analytic',
        'project',
        'mail',
    ],
    'data': [
        'security/prepaid_security.xml',
        'security/ir.model.access.csv',
        'data/mail_template_alert.xml',
        'data/ir_cron.xml',
        'views/prepaid_balance_views.xml',
        'views/prepaid_consumption_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/res_partner_views.xml',
        'views/menu_views.xml',
        'wizard/prepaid_adjust_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
