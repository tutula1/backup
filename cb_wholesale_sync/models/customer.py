# -*- coding: utf-8 -*-

from odoo import models, fields, api
from threading import Thread
import logging
_logger = logging.getLogger(__name__)

class cb_res_partner(models.Model):
    _inherit = 'res.partner'

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
        res = super(cb_res_partner, self).create(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            _logger.info('===============JOB RUN===================')
            
            self.env['res.partner'].create_update_partner(res.id, 'res.partner', 'create')
            # ctx = dict(self._context or {})
            # try:
            #     threaded_calculation = Thread(target=self.env['ir.cron'].create_update_partner, args=(res.id, 'res.partner', 'create'))
            #     threaded_calculation.start()
            # except Exception, e:
            #     _logger.info('*' * 20)
            #     _logger.info(e)
        return res

    @api.multi
    def write(self, vals):
        res = super(cb_res_partner, self).write(vals)
        ctx = dict(self._context or {})
        from_rest_api = ctx.has_key('from_rest_api')
        if from_rest_api == False:
            _logger.info('=======================CONTEXT==================================')
            _logger.info(ctx)
            for partner in self:
                self.env['res.partner'].create_update_partner(partner.id, 'res.partner', 'write')
        return res