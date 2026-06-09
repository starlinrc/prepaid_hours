from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_prepaid_package = fields.Boolean(
        string='Is Prepaid Package',
        default=False,
        help='If enabled, selling this product creates a prepaid balance for the customer.',
    )
    prepaid_unit = fields.Selection([
        ('hours', 'Hours'),
        ('credits', 'Credits'),
    ], string='Prepaid Unit', default='hours')

    prepaid_qty = fields.Float(
        string='Package Quantity',
        default=10.0,
        help='Number of hours or credits included in this package.',
    )
    prepaid_validity_days = fields.Integer(
        string='Validity (days)',
        default=0,
        help='Number of days the balance is valid. 0 = no expiration.',
    )
    prepaid_alert_threshold = fields.Float(
        string='Alert Threshold (%)',
        default=20.0,
        help='Alert customer when remaining balance falls below this percentage.',
    )

    @api.onchange('is_prepaid_package')
    def _onchange_is_prepaid_package(self):
        if self.is_prepaid_package:
            self.type = 'service'
