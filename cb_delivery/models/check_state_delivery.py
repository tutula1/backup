# -*- coding: utf-8 -*-

from openerp import models, fields, api
import datetime
from datetime import date, datetime, time
import logging
_logger = logging.getLogger(__name__)

class do_new_transfer_override(models.AbstractModel):
    _inherit='stock.picking'

    stock_outin_date = fields.Datetime('Thời gian xuất/nhập kho')

    def do_new_transfer(self):
        res = super(do_new_transfer_override, self).do_new_transfer()
        try:
            self.stock_outin_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass  
        _logger.info(res)  
        return res