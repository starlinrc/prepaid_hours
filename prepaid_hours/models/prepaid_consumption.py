from odoo import api, fields, models, _


class PrepaidConsumption(models.Model):
    _name = 'prepaid.consumption'
    _description = 'Prepaid Balance Consumption'
    _order = 'date desc, id desc'

    balance_id = fields.Many2one(
        'prepaid.balance',
        string='Balance',
        required=True,
        ondelete='cascade',
        index=True,
    )
    partner_id = fields.Many2one(
        related='balance_id.partner_id',
        string='Customer',
        store=True,
        index=True,
    )
    analytic_line_id = fields.Many2one(
        'account.analytic.line',
        string='Timesheet Entry',
        ondelete='set null',
    )
    qty_consumed = fields.Float(
        string='Qty Consumed',
        required=True,
    )
    prepaid_unit = fields.Selection(
        related='balance_id.prepaid_unit',
        string='Unit',
        store=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Technician',
    )
    note = fields.Char(string='Description')

    # Tipo: consumo real, ajuste manual, reversión
    consumption_type = fields.Selection([
        ('timesheet', 'Timesheet'),
        ('manual', 'Manual Adjustment'),
        ('reversal', 'Reversal'),
    ], string='Type', default='timesheet', required=True)
