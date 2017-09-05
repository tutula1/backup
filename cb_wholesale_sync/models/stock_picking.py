# -*- coding: utf-8 -*-

from odoo import models, fields, api
from threading import Thread
import logging
_logger = logging.getLogger(__name__)
class StockPickingSync(models.TransientModel):
    _name = 'stock.picking.sync'

    @api.multi
    def sync(self):
        # use active_ids to add picking line to the selected wave
        self.ensure_one()
        picking_ids = self.env.context.get('active_ids')
        for id in picking_ids:
            self.env['stock.picking'].create_update_picking(id, 'stock.picking', 'write')
        return {'type': 'ir.actions.act_window_close'}
    @api.multi
    def create_do(self):
        # use active_ids to add picking line to the selected wave
        self.ensure_one()
        picking_ids = self.env.context.get('active_ids')
        for id in picking_ids:
            self.env['stock.picking'].create_update_picking(id, 'stock.picking', 'create')
        return {'type': 'ir.actions.act_window_close'}

class cb_delivery(models.Model):
    _inherit = 'stock.picking'

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

    @api.model
    def create(self, vals):
        res = super(cb_delivery, self).create(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            try:
                if res.picking_type_code == 'outgoing':
                    self.env['stock.picking'].create_update_picking(res.id, 'stock.picking', 'create')
            except Exception, e:
                _logger.info('*' * 20)
                _logger.info(e)
        return res

    @api.multi
    def write(self, vals):
        res = super(cb_delivery, self).write(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            _logger.info('=======================CONTEXT==================================')
            _logger.info(ctx)
            for picking in self:
                try:
                    if picking.picking_type_code == 'outgoing':
                        _logger.info(vals)
                        self.env['stock.picking'].create_update_picking(picking.id, 'stock.picking', 'write')
                    # self.env['stock.picking'].with_delay(9).update_picking_status(picking.id, 'stock.picking', 'updatestatus')
                except Exception, e:
                    _logger.info('*' * 20)
                    _logger.info(e)
        return res