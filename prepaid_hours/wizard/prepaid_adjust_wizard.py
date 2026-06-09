from odoo import api, fields, models, _
from odoo.exceptions import UserError


class PrepaidAdjustWizard(models.TransientModel):
    _name = 'prepaid.adjust.wizard'
    _description = 'Manual Balance Adjustment'

    balance_id = fields.Many2one(
        'prepaid.balance',
        string='Balance',
        required=True,
    )
    partner_id = fields.Many2one(
        related='balance_id.partner_id',
        string='Customer',
        readonly=True,
    )
    qty_remaining = fields.Float(
        related='balance_id.qty_remaining',
        string='Current Remaining',
        readonly=True,
    )
    adjustment_type = fields.Selection([
        ('add', 'Add units (credit / bonus)'),
        ('subtract', 'Subtract units (correction)'),
    ], string='Type', required=True, default='add')

    qty = fields.Float(string='Quantity', required=True)
    note = fields.Char(string='Reason', required=True)

    def action_apply(self):
        self.ensure_one()
        if self.qty <= 0:
            raise UserError(_('Quantity must be greater than zero.'))

        balance = self.balance_id

        if self.adjustment_type == 'add':
            # Añadir crédito: consumo negativo
            self.env['prepaid.consumption'].create({
                'balance_id': balance.id,
                'partner_id': balance.partner_id.id,
                'qty_consumed': -self.qty,
                'date': fields.Date.today(),
                'user_id': self.env.uid,
                'note': _('[Manual Credit] %s') % self.note,
                'consumption_type': 'manual',
            })
            # Si estaba exhausted, reactivar
            if balance.state == 'exhausted':
                balance.state = 'active'
                balance.alert_sent = False

        else:
            # Restar unidades
            if self.qty > balance.qty_remaining:
                raise UserError(
                    _('Cannot subtract %.2f units. Only %.2f remaining.')
                    % (self.qty, balance.qty_remaining)
                )
            self.env['prepaid.consumption'].create({
                'balance_id': balance.id,
                'partner_id': balance.partner_id.id,
                'qty_consumed': self.qty,
                'date': fields.Date.today(),
                'user_id': self.env.uid,
                'note': _('[Manual Debit] %s') % self.note,
                'consumption_type': 'manual',
            })
            balance._check_thresholds()

        balance.message_post(
            body=_('Manual adjustment by %s: %s %s %s. Reason: %s')
            % (
                self.env.user.name,
                '+' if self.adjustment_type == 'add' else '-',
                self.qty,
                balance.prepaid_unit,
                self.note,
            )
        )
        return {'type': 'ir.actions.act_window_close'}
