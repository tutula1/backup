# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class cb_delivery_stock_move(models.Model):
    _inherit = 'stock.move'
