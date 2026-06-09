from odoo import api, fields, models, _
from dateutil.relativedelta import relativedelta


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    prepaid_balance_ids = fields.One2many(
        'prepaid.balance',
        'sale_order_id',
        string='Prepaid Balances',
    )
    prepaid_balance_count = fields.Integer(
        compute='_compute_prepaid_balance_count',
    )

    @api.depends('prepaid_balance_ids')
    def _compute_prepaid_balance_count(self):
        for order in self:
            order.prepaid_balance_count = len(order.prepaid_balance_ids)

    def action_confirm(self):
        res = super().action_confirm()
        self._create_prepaid_balances()
        return res

    def _create_prepaid_balances(self):
        Balance = self.env['prepaid.balance']
        for order in self:
            for line in order.order_line:
                product = line.product_id
                if not product.is_prepaid_package:
                    continue

                # Calcular fecha de expiración
                date_start = fields.Date.today()
                date_expiry = False
                if product.prepaid_validity_days > 0:
                    date_expiry = date_start + relativedelta(
                        days=product.prepaid_validity_days
                    )

                # Cantidad total = qty del paquete × qty vendida en el SO
                qty_total = product.prepaid_qty * line.product_uom_qty

                balance = Balance.create({
                    'partner_id': order.partner_id.id,
                    'product_id': product.product_variant_id.id,
                    'sale_line_id': line.id,
                    'qty_total': qty_total,
                    'date_start': date_start,
                    'date_expiry': date_expiry,
                    'alert_threshold': product.prepaid_alert_threshold,
                    'state': 'active',
                })

                balance.message_post(
                    body=_('Balance created from Sale Order <a href="#">%s</a>')
                    % order.name
                )

    def action_view_prepaid_balances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Prepaid Balances'),
            'res_model': 'prepaid.balance',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_partner_id': self.partner_id.id},
        }


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    prepaid_balance_id = fields.Many2one(
        'prepaid.balance',
        string='Prepaid Balance',
        compute='_compute_prepaid_balance_id',
        store=True,
    )

    @api.depends('product_id', 'order_id.prepaid_balance_ids')
    def _compute_prepaid_balance_id(self):
        for line in self:
            balance = line.order_id.prepaid_balance_ids.filtered(
                lambda b: b.sale_line_id == line
            )
            line.prepaid_balance_id = balance[:1]

class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_view_prepaid_balances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Prepaid Balances'),
            'res_model': 'prepaid.balance',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }




