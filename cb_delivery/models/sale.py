# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class cb_delivery_sale_order(models.Model):
    _inherit = 'sale.order'

    internal_note = fields.Text(
        string='Internal Note',
    )
    def default_source_sale_id(self):
        return self.env['cb.source.sale'].search(['|', ('code', '=', '4'), ('code', '=', 4)], limit=1)
    source_sale_id = fields.Many2one(
        'cb.source.sale',
        string='Source Sale',
        default=default_source_sale_id
    )

    stock_tranfer_date = fields.Datetime('Dự kiến giao hàng', default=fields.Datetime.now)

    delivery_status = fields.Selection([
        ('draft', 'Draft'), ('cancel', 'Cancelled'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting Availability'),
        ('partially_available', 'Partially Available'),
        ('assigned', 'Available'), ('done', 'Done'),
        ('delivery_success', 'Delivery Success'),
        ('delivery_fail', 'Delivery Fail')], string='Delivery Status', index=True, copy=False, store=True)


    @api.multi
    def action_confirm(self):
        res = super(cb_delivery_sale_order, self).action_confirm()
        for order in self:
    		#build address
            address = self.env['res.partner'].get_display_customer_address(order.partner_shipping_id)
            _logger.info('===============DELIVERY ADDRESS=================')
            _logger.info(address)
            address = address.replace('\n\n', '\n')
            address = address.replace('\n\n', '\n')
            address = address.replace('\n', ', ')
            _logger.info('===============DELIVERY ADDRESS=================')
            _logger.info(address)
            
            for pick in order.picking_ids:
                pick.write({
                    'internal_note': order.internal_note
                })
                if address != '':
                    #writing address 
                    delivery_address_object = self.env['cb.delivery.address']
                    check_address = delivery_address_object.search([('name', '=', address)], limit=1)
                    _logger.info(check_address)
                    if not check_address:
                        delivery_address = delivery_address_object.create({
                            'name': address
                        })
                    else:
                        delivery_address = check_address

                    if delivery_address:
                        pick.end_point = delivery_address.id
                if order.stock_tranfer_date != False:
                    pick.stock_tranfer_date = order.stock_tranfer_date
                    pick.stock_live_date = order.stock_tranfer_date


            return res


    @api.multi
    def write(self, vals):
        res = super(cb_delivery_sale_order, self).write(vals)
        if vals.has_key('stock_tranfer_date'):
            for order in self:            
                for pick in order.picking_ids:
                    if order.stock_tranfer_date != False:
                        pick.stock_tranfer_date = order.stock_tranfer_date
        return res