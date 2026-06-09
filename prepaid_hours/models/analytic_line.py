from odoo import api, fields, models, _
from odoo.release import version_info

ODOO_VERSION = version_info[0]  # 17, 18 o 19


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    prepaid_balance_id = fields.Many2one(
        'prepaid.balance',
        string='Prepaid Balance',
        index=True,
        ondelete='set null',
        help='Prepaid balance this timesheet entry will be charged to.',
    )
    is_prepaid = fields.Boolean(
        compute='_compute_is_prepaid',
        store=True,
    )
    prepaid_consumed = fields.Boolean(
        default=False,
        copy=False,
        help='Whether this entry has already been charged to a prepaid balance.',
    )

    @api.depends('prepaid_balance_id')
    def _compute_is_prepaid(self):
        for line in self:
            line.is_prepaid = bool(line.prepaid_balance_id)

    # -------------------------------------------------------------------------
    # Auto-assign balance when partner/project is set
    # -------------------------------------------------------------------------

    @api.onchange('partner_id', 'account_id')
    def _onchange_partner_prepaid(self):
        """Try to auto-assign a prepaid balance when partner changes."""
        if self.partner_id and not self.prepaid_balance_id:
            balance = self.env['prepaid.balance']._get_active_balance_for_partner(
                self.partner_id.id,
                analytic_account_id=self.account_id.id if self.account_id else None,
            )
            if balance:
                self.prepaid_balance_id = balance

    # -------------------------------------------------------------------------
    # Main hook — different per Odoo version
    # -------------------------------------------------------------------------

    def write(self, vals):
        res = super().write(vals)

        if ODOO_VERSION >= 18:
            # Odoo 18/19: timesheets have a 'validated' field on analytic line
            if vals.get('validated'):
                self._trigger_prepaid_consumption()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if ODOO_VERSION == 17:
            # In v17, timesheets can be consumed on create if already validated
            lines.filtered(
                lambda l: l.prepaid_balance_id and not l.prepaid_consumed
            )._trigger_prepaid_consumption()
        return lines

    def action_validate_timesheet(self):
        """
        Called in Odoo 17 from project timesheet validation.
        We hook here to consume after native validation.
        """
        res = super().action_validate_timesheet() if hasattr(
            super(), 'action_validate_timesheet'
        ) else None
        self._trigger_prepaid_consumption()
        return res

    # -------------------------------------------------------------------------
    # Core consumption logic (version-agnostic)
    # -------------------------------------------------------------------------

    def _trigger_prepaid_consumption(self):
        """
        For each analytic line that has a prepaid balance assigned
        and hasn't been consumed yet, consume the units.
        """
        for line in self:
            if line.prepaid_consumed:
                continue
            if not line.prepaid_balance_id:
                # Try auto-assign if partner has active balance
                if line.partner_id:
                    balance = self.env[
                        'prepaid.balance'
                    ]._get_active_balance_for_partner(
                        line.partner_id.id,
                        analytic_account_id=line.account_id.id
                        if line.account_id else None,
                    )
                    if balance:
                        line.prepaid_balance_id = balance
                    else:
                        continue
                else:
                    continue

            balance = line.prepaid_balance_id
            if balance.state != 'active':
                continue

            qty = line.unit_amount  # horas registradas
            balance._consume(qty=qty, analytic_line=line)
            line.prepaid_consumed = True
