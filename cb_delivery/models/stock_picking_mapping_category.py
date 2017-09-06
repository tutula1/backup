# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from HTMLParser import HTMLParser

import logging
_logger = logging.getLogger(__name__)


class map_category_warehouse(models.Model):
    _inherit = 'stock.picking'

    category_id = fields.Many2one('product.category', 'Category')

    @api.onchange('category_id')
    def onchange_category_id(self):
        id_list = []
        result = {}
        product_category = []
        result['domain'] = {}
        if self.category_id:
            product_category_query = "SELECT * FROM product_category_stock_warehouse_rel WHERE product_category_id=" + str(self.category_id.id)
            self.env.cr.execute(product_category_query)
            product_category = self.env.cr.fetchall()
            _logger.info("=============WAREHOUSE============")
            if len(product_category) > 0:
                for item in product_category:
                    stock_picking_query = "SELECT * FROM stock_picking_type WHERE warehouse_id=" + str(item[1])
                    self.env.cr.execute(stock_picking_query)
                    stock_pickings = self.env.cr.fetchall()
                    if len(stock_pickings) > 0:
                        for stock_picking in stock_pickings:
                            id_list.append(stock_picking[0])
                        self.picking_type_id = id_list[0]
                    else:
                        _logger.info("=========PICKING TYPE ID===============")
                        self.picking_type_id = False
            else:
                self.picking_type_id = False
            result['domain'] = {'picking_type_id': [('id', 'in', id_list)]}
            return result
            
# class map_category_warehouse_product(models.Model):
#     _inherit = 'product.product'
#     @api.model
#     def name_search(self, name, args=None, operator='ilike', limit=100):
#         id_list = []
#         Product = self.env['product.template'].search([('categ_id', '=', self.env.context.get('category_id'))])
#         _logger.info("====================TEMPLATE=====================")
#         for item in Product:
#             id_list.append(item.id)
#         return super(map_category_warehouse_product, self).name_search(
#             '', args=[('id', 'in', id_list)],
#             operator='ilike', limit=limit)