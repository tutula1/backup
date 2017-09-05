# -*- coding: utf-8 -*-

from odoo import models, fields, api
from threading import Thread
import logging
_logger = logging.getLogger(__name__)

class cb_account_invoice(models.Model):
    _inherit = 'account.invoice'

    external_id = fields.Char('External id')
    external_type = fields.Char('External Type')
    created_user_id = fields.Many2one(
        'res.users',
        string='Created User',
        readonly=True, 
    )
    created_user_code = fields.Char(
        string='Created User',
        readonly=True, 
    )
    updated_user_id = fields.Many2one(
        'res.users',
        string='Updated User',
        readonly=True, 
    )
    updated_user_code = fields.Char(
        string='Updated User',
        readonly=True, 
    )
    send_rabbit = fields.Integer(
        string='Send rabbit',
        default=0
    )

    @api.model
    def create(self, vals):
        res = super(cb_account_invoice, self).create(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            _logger.info('===============JOB RUN===================') 
            self.env['account.invoice'].create_update_invoice(res.id, 'account.invoice', 'create')
        return res

    @api.multi
    def write(self, vals):
        res = super(cb_account_invoice, self).write(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            _logger.info('=======================CONTEXT==================================')
            _logger.info(ctx)
            for invoice in self:
                _logger.info(vals)
                # self.env['account.invoice'].with_delay(8).update_status_invoice(invoice.id, 'account.invoice', 'write')
                self.env['account.invoice'].create_update_invoice(invoice.id, 'account.invoice', 'write')
        return res
class cb_account_payment(models.Model):
    _inherit = 'account.payment'
    
    @api.model
    def create(self, vals):
        res = super(cb_account_payment, self).create(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            for payment in self:
                for invoice in payment.invoice_ids:
                    # self.env['account.invoice'].with_delay(8).update_status_invoice(invoice.id, 'account.invoice', 'write')
                    self.env['account.invoice'].create_update_invoice(invoice.id, 'account.invoice', 'write')
        return res

    @api.multi
    def write(self, vals):
        res = super(cb_account_payment, self).write(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            for payment in self:
                for invoice in payment.invoice_ids:
                    # self.env['account.invoice'].with_delay(8).update_status_invoice(invoice.id, 'account.invoice', 'write')
                    self.env['account.invoice'].create_update_invoice(invoice.id, 'account.invoice', 'write')
        return res



