from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date


class PrepaidBalance(models.Model):
    _name = 'prepaid.balance'
    _description = 'Prepaid Service Balance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start asc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Package',
        required=True,
        domain=[('is_prepaid_package', '=', True)],
    )
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Sale Order Line',
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        related='sale_line_id.order_id',
        string='Sale Order',
        store=True,
        readonly=True,
    )

    # --- Unidades ---
    prepaid_unit = fields.Selection(
        related='product_id.prepaid_unit',
        string='Unit',
        store=True,
        readonly=True,
    )
    qty_total = fields.Float(
        string='Total Purchased',
        required=True,
        tracking=True,
    )
    qty_consumed = fields.Float(
        string='Consumed',
        compute='_compute_qty_consumed',
        store=True,
    )
    qty_remaining = fields.Float(
        string='Remaining',
        compute='_compute_qty_consumed',
        store=True,
    )
    alert_threshold = fields.Float(
        string='Alert Threshold (%)',
        default=20.0,
        help='Send alert when remaining balance falls below this percentage.',
    )
    alert_sent = fields.Boolean(default=False, copy=False)

    # --- Fechas ---
    date_start = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    date_expiry = fields.Date(
        string='Expiry Date',
        tracking=True,
        help='Leave empty for no expiration.',
    )

    # --- Estado ---
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('exhausted', 'Exhausted'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True)

    consumption_ids = fields.One2many(
        'prepaid.consumption',
        'balance_id',
        string='Consumption History',
    )
    consumption_count = fields.Integer(
        compute='_compute_consumption_count',
    )

    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        help='Link timesheets to this balance via analytic account.',
    )

    # -------------------------------------------------------------------------
    # Compute
    # -------------------------------------------------------------------------

    @api.depends('consumption_ids.qty_consumed', 'qty_total')
    def _compute_qty_consumed(self):
        for rec in self:
            consumed = sum(rec.consumption_ids.mapped('qty_consumed'))
            rec.qty_consumed = consumed
            rec.qty_remaining = rec.qty_total - consumed

    @api.depends('consumption_ids')
    def _compute_consumption_count(self):
        for rec in self:
            rec.consumption_count = len(rec.consumption_ids)

    # -------------------------------------------------------------------------
    # ORM
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'prepaid.balance'
                ) or _('New')
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_activate(self):
        self.filtered(lambda r: r.state == 'draft').write({'state': 'active'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_view_consumptions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consumption History'),
            'res_model': 'prepaid.consumption',
            'view_mode': 'list,form',
            'domain': [('balance_id', '=', self.id)],
            'context': {'default_balance_id': self.id},
        }

    def action_manual_adjust(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Manual Adjustment'),
            'res_model': 'prepaid.adjust.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_balance_id': self.id},
        }

    # -------------------------------------------------------------------------
    # Business logic
    # -------------------------------------------------------------------------

    def _consume(self, qty, analytic_line=None, note=None):
        """
        Main entry point to consume units from this balance.
        Called from analytic_line hook.
        """
        self.ensure_one()
        if self.state not in ('active',):
            raise UserError(
                _('Cannot consume from balance "%s" in state "%s".')
                % (self.name, self.state)
            )
        if qty <= 0:
            return

        self.env['prepaid.consumption'].create({
            'balance_id': self.id,
            'partner_id': self.partner_id.id,
            'analytic_line_id': analytic_line.id if analytic_line else False,
            'qty_consumed': qty,
            'date': analytic_line.date if analytic_line else date.today(),
            'user_id': analytic_line.user_id.id if analytic_line else self.env.uid,
            'note': note or (analytic_line.name if analytic_line else ''),
        })

        # Recompute and check thresholds
        self._check_thresholds()

    def _check_thresholds(self):
        """Check alert and exhaustion after every consumption."""
        for rec in self:
            if rec.qty_remaining <= 0:
                rec.state = 'exhausted'
                rec._notify_exhausted()
            elif not rec.alert_sent:
                pct_remaining = (rec.qty_remaining / rec.qty_total * 100
                                 if rec.qty_total else 0)
                if pct_remaining <= rec.alert_threshold:
                    rec._notify_low_balance()
                    rec.alert_sent = True

    def _notify_low_balance(self):
        template = self.env.ref(
            'prepaid_hours.mail_template_low_balance', raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)

    def _notify_exhausted(self):
        template = self.env.ref(
            'prepaid_hours.mail_template_exhausted', raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)

    # -------------------------------------------------------------------------
    # Cron
    # -------------------------------------------------------------------------

    @api.model
    def _cron_check_expiry(self):
        """Daily cron: expire balances past their expiry date."""
        today = fields.Date.today()
        expired = self.search([
            ('state', '=', 'active'),
            ('date_expiry', '<', today),
            ('date_expiry', '!=', False),
        ])
        for rec in expired:
            rec.state = 'expired'
            rec.message_post(
                body=_('Balance automatically expired on %s.') % today
            )

    # -------------------------------------------------------------------------
    # Helper: find best balance for a partner (FIFO)
    # -------------------------------------------------------------------------

    @api.model
    def _get_active_balance_for_partner(self, partner_id, analytic_account_id=None):
        """
        Returns the oldest active balance for a partner.
        Optionally filters by analytic account.
        """
        domain = [
            ('partner_id', '=', partner_id),
            ('state', '=', 'active'),
        ]
        if analytic_account_id:
            domain += [
                '|',
                ('analytic_account_id', '=', analytic_account_id),
                ('analytic_account_id', '=', False),
            ]
        return self.search(domain, limit=1, order='date_start asc')
