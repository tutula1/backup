# -*- coding: utf-8 -*-

from odoo import models, fields, api
from threading import Thread
import logging
_logger = logging.getLogger(__name__)
class SaleOrderSync(models.TransientModel):
    _name = 'sale.order.sync'

    @api.multi
    def sync(self):
        # use active_ids to add picking line to the selected wave
        self.ensure_one()
        order_ids = self.env.context.get('active_ids')
        for id in order_ids:
            self.env['sale.order'].create_update_order(id, 'sale.order', 'write')
        return {'type': 'ir.actions.act_window_close'}
    @api.multi
    def create_so(self):
        # use active_ids to add picking line to the selected wave
        self.ensure_one()
        order_ids = self.env.context.get('active_ids')
        for id in order_ids:
            self.env['sale.order'].create_update_order(id, 'sale.order', 'create')
        return {'type': 'ir.actions.act_window_close'}
class cb_sale_order(models.Model):
    _inherit = 'sale.order'

    external_id = fields.Char('External id', copy=False)
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

    @api.multi
    def action_confirm(self):
        res = super(cb_sale_order, self).action_confirm()
        return res

    @api.model
    def create(self, vals):
        res = super(cb_sale_order, self).create(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            _logger.info(vals)
            _logger.info("+GO+")
            self.env['sale.order'].create_update_order(res.id, 'sale.order', 'create')
        return res

    @api.multi
    def write(self, vals):
        res = super(cb_sale_order, self).write(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            for order in self:
                try:
                    _logger.info(vals)
                    if vals != None and vals != False:
                        if len(vals) == 1 and vals.has_key('effective_date') == True:
                            _logger.info(vals)
                        else:
                            _logger.info(vals)
                            _logger.info("+GO+")
                            self.env['sale.order'].create_update_order(order.id, 'sale.order', 'write')
                    # if 'state' in vals:
                    #     self.env['sale.order'].with_delay().update_status_order(order.id, 'sale.order', 'updatestatus')
                except Exception, e:
                    _logger.info('*' * 20)
                    _logger.info(e)
        return res