# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

import pytz
import datetime
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta

class cb_logs(models.Model):
    _inherit = 'cb.logs'

    run = fields.Integer(
        string='Run',
        default=1
    )

    def wholesale_reload(self):
        _logger.info("*" * 40)
        try:
            create_date_unlink = datetime.today() - relativedelta(months=+1)
            logs = self.env['cb.logs'].search([('create_date', '<', create_date_unlink)])
            if logs:
                logs.unlink()
        except Exception, e:
            _logger.info(e.message)
            pass
        create_date = datetime.today() - relativedelta(hours=+12)
        _logger.info(create_date)
        logs = self.env['cb.logs'].search([('run', '=', 1),('name', '=', 'log_send_oss'),('create_date', '>=', create_date),('status', '=', 'error')])
        _logger.info(logs)
        if logs:
            for log in logs:
                log.write({'run': 2})
                _logger.info(log.id)
                check = self.env['cb.logs'].search([('object_id', '=', log.object_id),('action', '=', log.action),('model', '=', log.model),('name', '=', 'log_send_oss'),('create_date', '>=', log.create_date),('status', '=', 'success')])
                _logger.info(check)
                if not check:
                    try:
                        object_id = self.env[log.model].browse(int(log.object_id))
                        if object_id:
                            if log.model == 'sale.order':
                                object_id.create_update_order(object_id.id, 'sale.order', log.action)
                            if log.model == 'res.partner':
                                object_id.create_update_partner(object_id.id, 'res.partner', log.action)
                            if log.model == 'stock.picking':
                                object_id.create_update_picking(object_id.id, 'stock.picking', log.action)
                            if log.model == 'account.invoice':
                                object_id.create_update_invoice(object_id.id, 'account.invoice', log.action)
                    except Exception, e:
                        _logger.info(e.message)
                        pass
    