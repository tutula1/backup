# -*- coding: utf-8 -*-

from odoo import models, fields, api
import googlemaps
import json
import requests
from odoo.addons import decimal_precision as dp
import logging
_logger = logging.getLogger(__name__)
from urllib2 import Request, urlopen, URLError

import pytz
import datetime
from datetime import date, datetime, time

#https://github.com/googlemaps/google-maps-services-python
#https://console.developers.google.com/apis/api/distance_matrix_backend/overview?project=cdfdelivery-1484121296636&duration=PT1H
gmaps = googlemaps.Client(key='AIzaSyC-g9HBon4esEI0od1rZbUG7NOZYjg64lo')
class stock_picking(models.Model):
    _inherit = 'stock.picking'

    internal_note = fields.Text(
        string='Internal Note',
    )

    def action_cancel(self):
        res = super(stock_picking, self).action_cancel()
        if res == True:
            for line in self.move_lines:
                line.write({'product_uom_qty': 0, 'price_tax': 0, 'price_total': 0, 'price_subtotal': 0})
            _logger.info('===========CANCEL_DELIVERY============')
            _logger.info(self.delivery_cost)
            self.write({'delivery_cost': 0})
            _logger.info(self.delivery_cost)
        return res

    def default_start_point(self):
        address = self.env['cb.delivery.address'].search([('auto_select_start_point', '=', True)], limit=1)
        if address:
            return address
        return
    start_point = fields.Many2one('cb.delivery.address', string="Điểm bắt đầu", default=default_start_point)
    end_point = fields.Many2one('cb.delivery.address', string="Điểm đến")
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Term')
    delivery_service = fields.Selection([
        ('internal', "Nội bộ"),
        ('collaborators', "Cộng tác viên"),
        ('partner', "Đối tác"),
    ], default="internal", string="Dịch vụ giao hàng")
    collaborators = fields.Many2one('res.partner', string="Nhân viên giao hàng")
    delivery_fee = fields.Float('Phụ phí giao hàng')
    source_way = fields.Float('Quãng đường đi', compute='_compute_way', store=True)
    destination_way = fields.Float('Quãng đường về', compute='_compute_way', store=True)
    total_way = fields.Float('Tổng quãng đường', compute='_compute_way', store=True)

    forecast_time = fields.Char('Thời gian dự đoán', compute='_compute_way', store=True)

    start_time = fields.Float('Thời gian xuất phát')
    end_time = fields.Float('Thời gian trở về')
    duration_time = fields.Char('Thời gian thực tế', compute='_compute_time', store=True)

    postage_total = fields.Float('Tổng cước phí', compute="_compute_postage_total", store=True)
    postage_delivery = fields.Float('Phí vận chuyển', compute='_compute_way', store=True)
    postage_delivery_fee = fields.Float('Phụ phí giao hàng')

    google_map = fields.Char('Map', compute='_compute_way', store=True)

    stock_tranfer_date = fields.Datetime('Dự kiến giao hàng')

    def default_stock_live_date(self):
        return self.stock_tranfer_date

    stock_live_date = fields.Datetime('Thực tế giao hàng' , default=default_stock_live_date)

    stock_outin_date = fields.Datetime('Thời gian xuất/nhập kho')

    def do_new_transfer(self):
        res = super(stock_picking, self).do_new_transfer()
        _logger.info('++++++++++++++++++++++++++++++++++++++++++')
        _logger.info(res)
        self.stock_outin_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S") 
        return res

    warehouse_name = fields.Char(string="Source Location Name", related='location_id.warehouse_name', store=True)
    warehouse_destination_name = fields.Char(string="Destination Location Name", related='location_dest_id.warehouse_name', store=True)

    delivery_status = fields.Selection([
        ('pending_delivery', 'Chờ giao'),
        ('delivering', 'Đang giao'),
        ('delivered', 'Đã giao')
    ], default="pending_delivery")

    note_stock_picking = fields.Text(string='Ghi chú', compute="_compute_get_note_stock_picking", store=True)
    customer_reference = fields.Char("Customer reference")

    customer_type = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('debts', 'Công nợ'),
        ('deposit', 'Ký gởi'),
        ('internal', 'Nội bộ')
    ], compute="_compute_get_customer_type") 

    amount_untaxed = fields.Float(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all')
    amount_tax = fields.Float(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Float(string='Total', store=True, readonly=True, compute='_amount_all')
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', readonly=True, help="Pricelist for current sales order.")


    apply_discount = fields.Boolean('Apply Discount', default=False)
    discount_type_id = fields.Many2one('discount.type', 'Discount Type')
    discount_value = fields.Float('Sale Discount')
    discount_value_const = fields.Float('Sale Discount')
    discount_account = fields.Many2one('account.account', 'Discount Account')
    amount_after_discount = fields.Float('Amount After Discount' , store=True, readonly=True , compute = '_amount_all')

    @api.depends('discount_value', 'delivery_cost', 'move_lines.price_total')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        discount_tmp = 0.0
        delivery_cost = 0.0
        amount_untaxed = 0.0

        amount_untaxed_tmp = 0.0 #add more
        amount_tax_tmp = 0.0 #add more

        amount_tax = 0.0
        amount_after_discount = 0.0
        discount = 0.0
        for pick in self:
            amount_untaxed = amount_tax = 0.0
            for line in pick.move_lines:
                if line.product_uom_qty > 0:
                    amount_untaxed += line.price_subtotal
                    amount_tax += line.price_tax if line.price_tax != False else 0

            total_cost = amount_untaxed + amount_tax if (amount_untaxed + amount_tax) > 0 else 0.0
            amount_after_discount = total_cost
            discount_value = pick.discount_value 
            if pick.apply_discount == True:
                discount_type_percent = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
                discount_type_fixed = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_fixed_id')
                
                if pick.discount_type_id.id == discount_type_fixed:
                    discount = total_cost  - pick.discount_value 
                    amount_after_discount = discount
                elif pick.discount_type_id.id == discount_type_percent:
                    discount_percent = total_cost * ((pick.discount_value or 0.0) / 100.0)
                    discount = total_cost - discount_percent
                    amount_after_discount = discount
                else:
                    amount_after_discount = total_cost


            _logger.info(pick.picking_type_code)
            if pick.picking_type_code == 'incoming':
                
                pick.update({
                    'discount_tmp': 0, 
                    'amount_untaxed': amount_untaxed,
                    'amount_tax': amount_tax,
                    'amount_total': amount_after_discount + delivery_cost,
                    'total_cost' : total_cost,
                    'amount_after_discount' : amount_after_discount
                })
            elif pick.picking_type_code == 'outgoing':
                delivery_cost = pick.delivery_cost
                if (amount_after_discount + delivery_cost) <= 0:
                    discount_tmp = abs(amount_after_discount + delivery_cost)
                    discount_value = total_cost + delivery_cost
                    # amount_after_discount -= delivery_cost
                
                if pick.pricelist_id:
                    amount_untaxed_tmp = pick.pricelist_id.currency_id.round(amount_untaxed)
                    amount_tax_tmp = pick.pricelist_id.currency_id.round(amount_tax)
                else:
                    amount_untaxed_tmp = amount_untaxed
                    amount_tax_tmp = amount_tax
                amount_untaxed = amount_untaxed_tmp if amount_untaxed_tmp > 0 else amount_untaxed
                amount_tax = amount_tax_tmp if amount_tax_tmp > 0 else amount_tax                     
                amount_total = amount_after_discount + delivery_cost if (amount_after_discount + delivery_cost) > 0 else 0.0

                pick.update({
                    'discount_value': discount_value,
                    'discount_tmp': discount_tmp,
                    # 'delivery_cost': delivery_cost if pick.state != 'cancel' else 0,
                    'amount_untaxed': amount_untaxed if pick.state != 'cancel' else 0,
                    'amount_tax': amount_tax if pick.state != 'cancel' else 0,
                    'amount_total': amount_total if pick.state != 'cancel' else 0,
                    'total_cost' : total_cost if pick.state != 'cancel' else 0,
                    'amount_after_discount' : amount_after_discount if pick.state != 'cancel' else 0
                })

    def _create_backorder(self, backorder_moves=[]):
        res = super(stock_picking, self)._create_backorder(backorder_moves)
        if res:
            do = self.search([('backorder_id', '=', self.id)], limit = 1)
            if do:
                if self.apply_discount == True:
                    discount_value = self.discount_value
                    discount_type_fixed = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_fixed_id')
                    if self.discount_type_id.id == discount_type_fixed:
                        if self.discount_tmp > 0:
                            discount_value = self.discount_tmp
                        else:
                            discount_value = 0.0
                    do.write({'discount_value': discount_value, 'delivery_cost': 0.0})
                    do.update_total()
                    self.update_total()
                else:
                    do.write({'delivery_cost': 0.0})
                    do.update_total()
                    self.update_total()

        return res

    def update_total(self):
        self._amount_all()
        # discount_tmp = 0.0
        # delivery_cost = 0.0
        # amount_untaxed = 0.0

        # amount_untaxed_tmp = 0.0 #add more
        # amount_tax_tmp = 0.0 #add more

        # amount_tax = 0.0
        # amount_after_discount = 0.0
        # discount = 0.0
        # amount_untaxed = amount_tax = 0.0
        # for line in self.move_lines:
        #     if line.product_uom_qty > 0:
        #         amount_untaxed += line.price_subtotal
        #         amount_tax += line.price_tax if line.price_tax != False else 0

        # total_cost = amount_untaxed + amount_tax if (amount_untaxed + amount_tax) > 0 else 0.0
        # amount_after_discount = total_cost
        # discount_value = self.discount_value
        # if self.apply_discount == True:
        #     discount_type_percent = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
        #     discount_type_fixed = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_fixed_id')
        #     discount_value = self.discount_value
        #     if self.discount_type_id.id == discount_type_fixed:
        #         discount = total_cost  - self.discount_value 
        #         amount_after_discount = discount

        #     elif self.discount_type_id.id == discount_type_percent:
        #         discount_percent = total_cost * ((self.discount_value or 0.0) / 100.0)
        #         discount = total_cost - discount_percent
        #         amount_after_discount = discount
        #     else:
        #         amount_after_discount = total_cost

        # _logger.info(self.picking_type_code)
        # if self.picking_type_code == 'incoming':
        #     self.write({
        #         'discount_tmp': 0, 
        #         'amount_untaxed': amount_untaxed,
        #         'amount_tax': amount_tax,
        #         'amount_total': amount_after_discount + delivery_cost,
        #         'total_cost' : total_cost,
        #         'amount_after_discount' : amount_after_discount,
        #         'no_update': 1
        #     })
        # elif self.picking_type_code == 'outgoing':
        #     delivery_cost = self.delivery_cost
        #     if (amount_after_discount + delivery_cost) < 0:
        #         discount_tmp = abs(amount_after_discount + delivery_cost)
        #         discount_value = total_cost + delivery_cost
        #         amount_after_discount -= delivery_cost
        #     if self.pricelist_id:
        #         amount_untaxed_tmp = self.pricelist_id.currency_id.round(amount_untaxed)
        #         amount_tax_tmp = self.pricelist_id.currency_id.round(amount_tax)
        #     else:
        #         amount_untaxed_tmp = amount_untaxed
        #         amount_tax_tmp = amount_tax
        #     amount_untaxed = amount_untaxed_tmp if amount_untaxed_tmp > 0 else amount_untaxed
        #     amount_tax = amount_tax_tmp if amount_tax_tmp > 0 else amount_tax
        #     amount_total = amount_after_discount + delivery_cost if (amount_after_discount + delivery_cost) > 0 else 0.0

        #     self.write({
        #         'discount_value': discount_value,
        #         'discount_tmp': discount_tmp,
        #         # 'delivery_cost': delivery_cost if self.state != 'cancel' else 0,
        #         'amount_untaxed': amount_untaxed if self.state != 'cancel' else 0,
        #         'amount_tax': amount_tax if self.state != 'cancel' else 0,
        #         'amount_total': amount_total if self.state != 'cancel' else 0,
        #         'total_cost' : total_cost if self.state != 'cancel' else 0,
        #         'amount_after_discount' : amount_after_discount if self.state != 'cancel' else 0,
        #         'no_update': 1
        #     })

    @api.model
    def create(self, vals):
        po = so = None
        if self.picking_type_code:
            if self.picking_type_code == 'incoming':
                po = self.env['purchase.order'].search([('name', '=', self.origin)], limit=1)
                # if po:
                #     vals.update({
                #         'amount_untaxed': po.amount_untaxed,
                #         'amount_tax': po.amount_tax,
                #         'amount_total': po.amount_total,
                #         'delivery_cost': 0,
                #         'discount_tmp': 0,
                #         'total_cost': po.amount_untaxed + po.amount_tax,
                #         'apply_discount': po.apply_discount,
                #         'discount_value': po.discount_value,
                #         'discount_value_const': po.discount_value,
                #         'discount_account': po.discount_account.id if po.discount_account != False else False
                #     })
            elif self.picking_type_code == 'outgoing':
                so = self.env['sale.order'].search([('name', '=', self.origin)], limit=1)
                # if so:
                #     vals.update({
                #         'amount_untaxed': so.amount_untaxed,
                #         'amount_tax': so.amount_tax,
                #         'amount_total': so.amount_total,
                #         'pricelist_id': so.pricelist_id.id if so.pricelist_id != False else False,
                #         'delivery_cost': so.delivery_cost,
                #         'discount_tmp': 0,
                #         'total_cost': so.amount_untaxed + so.amount_tax,
                #         'apply_discount': so.apply_discount,
                #         'discount_type_id': so.discount_type_id.id if so.discount_type_id != False else False,
                #         'discount_value': so.discount_value,
                #         'discount_value_const': so.discount_value,
                #         'discount_account': so.discount_account.id if so.discount_account != False else False
                #     })
        _logger.info("=============LOG====")
        _logger.info(vals)
        if vals.has_key('move_lines'):
            for index,value in enumerate(vals['move_lines']):
                if vals['move_lines'][index][2]:
                    product_id = vals['move_lines'][index][2]['product_id']
                    product = self.env['product.product'].browse(product_id)
                    vals['move_lines'][index][2]['product_uom'] = product.uom_po_id.id or product.uom_id.id
        # if vals.has_key('pack_operation_product_ids'):
        #     for index,value in enumerate(vals['pack_operation_product_ids']):
        #         if vals['pack_operation_product_ids'][index][2]:
        #             product_id = vals['pack_operation_product_ids'][index][2]['product_id']
        #             product = self.env['product.product'].browse(product_id)
        #             vals['pack_operation_product_ids'][index][2]['product_uom'] = product.uom_po_id.id or product.uom_id.id
        _logger.info(vals)
        res = super(stock_picking, self).create(vals)
        if po:
            if po.delivery_status != self.state:
                po.write({
                'delivery_status': self.state
            })
        if so:
            if so.delivery_status != self.state:
                so.write({
                'delivery_status': self.state
            })
        return res

    @api.multi
    def write(self, vals):
        po = so = None
        _logger.info(vals)
        for record in self:
            if record.picking_type_code:
                if record.picking_type_code == 'incoming':
                    po = record.env['purchase.order'].search([('name', '=', record.origin)], limit=1)
                    # if po:
                    #     if vals.has_key('no_update') == False:
                    #         vals.update({
                    #             #'amount_untaxed': po.amount_untaxed,
                    #             #'amount_tax': po.amount_tax,
                    #             #'amount_total': po.amount_total,
                    #             'delivery_cost': 0,
                    #             'apply_discount': po.apply_discount,
                    #             'discount_type_id': po.discount_type_id.id if po.discount_type_id != False else False,
                    #             'discount_value': po.discount_value,
                    #             'discount_value_const': po.discount_value,
                    #             'discount_account': po.discount_account.id if po.discount_account != False else False
                    #         })
                    #     else:
                    #         del vals['no_update']
                elif record.picking_type_code == 'outgoing':
                    so = record.env['sale.order'].search([('name', '=', record.origin)], limit = 1)
                    # if so:
                    #     if vals.has_key('no_update') == False:
                    #         vals.update({
                    #             #'amount_untaxed': so.amount_untaxed if record.state != 'cancel' else 0,
                    #             #'amount_tax': so.amount_tax if record.state != 'cancel' else 0,
                    #             #'amount_total': so.amount_total if record.state != 'cancel' else 0,
                    #             'delivery_cost': so.delivery_cost if record.state != 'cancel' else 0,
                    #             'apply_discount': so.apply_discount,
                    #             'discount_type_id': so.discount_type_id.id if so.discount_type_id != False else False,
                    #             'discount_value': so.discount_value,
                    #             'discount_value_const': so.discount_value,
                    #             'discount_account': so.discount_account.id if so.discount_account != False else False
                    #         })
                    #     else:
                    #         del vals['no_update']
        _logger.info("===========MOVE_LINES============")
        _logger.info(vals)
        if vals.has_key('move_lines'):
            for index,value in enumerate(vals['move_lines']):
                if vals['move_lines'][index][2] and  vals['move_lines'][index][2].has_key('product_id'):
                    product_id = vals['move_lines'][index][2]['product_id']
                    product = self.env['product.product'].browse(product_id)
                    vals['move_lines'][index][2]['product_uom'] = product.uom_po_id.id or product.uom_id.id
        res = super(stock_picking, self).write(vals)
        for record in self:
            if po:
                if po.delivery_status != record.state:
                    po.write({
                    'delivery_status': record.state
                })
            if so:
                if so.delivery_status != record.state:
                    so.write({
                    'delivery_status': record.state
                })
            if vals.has_key("delivery_service") and vals.has_key("postage_delivery") and ( vals.get("delivery_service") == 'partner' or vals.get("delivery_service") == 'internal'):
                record.write({'postage_delivery' : vals.get("postage_delivery")})
        return res


    
    @api.onchange('delivery_service')
    def _onchange_delivery_service(self):
        if self.delivery_service != '':
            self.collaborators = None
            return {
                'domain': {
                    'collaborators': [('delivery_service','=',self.delivery_service)]
                }
            }

    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="Pricelist for current sales order.")
    currency_id = fields.Many2one("res.currency", related='pricelist_id.currency_id', string="Currency", readonly=True, required=True)

    delivery_cost = fields.Monetary(
        string='Phí giao hàng', 
        store=True,
        default=0, 
        readonly=True
    )

    total_cost = fields.Monetary(
        store=True,
        string='Tồng tiền tạm tính',
        readonly=True, 
        compute="_amount_all"
    )
    discount_tmp = fields.Monetary(
        store=True,
        string='Giam gia con lai',
        readonly=True, 
        compute="_amount_all"
    )

    @api.onchange('start_point', 'end_point', 'delivery_service')
    def _onchange_start_end_point(self):
    	if self.start_point.id > 0 and self.end_point.id > 0 :
            return self.calc_way(self.start_point.name, self.end_point.name, self.delivery_service, self.start_point.id, self.end_point.id)

    @api.depends('start_point', 'end_point', 'source_way', 'destination_way', 'total_way', 'forecast_time', 'delivery_service')
    def _compute_way(self):
        if self.start_point.id > 0 and self.end_point.id > 0 :
            ways =  self.calc_way(self.start_point.name, self.end_point.name, self.delivery_service, self.start_point.id, self.end_point.id)
            self.source_way = ways['value']['source_way']
            self.destination_way = ways['value']['destination_way']
            self.total_way = ways['value']['total_way']
            self.forecast_time = ways['value']['forecast_time']
            self.postage_delivery = ways['value']['postage_delivery']
            self.google_map = ways['value']['google_map']

    def calc_way(self, start_point_name, end_point_name, delivery_service, start_point_id, end_point_id):

        source_way = 0.0
        destination_way = 0.0
        total_way = 0.0
        forecast_time = '0 mins'
        postage_delivery = 0
        google_map = ''
        delivery_address_info_object = self.env['cb.delivery.address.info']
        delivery_address_info = delivery_address_info_object.search([('start_point', '=', start_point_id), ('end_point', '=', end_point_id)], limit=1)
        if delivery_address_info:
            source_way = delivery_address_info.source_way
            destination_way = delivery_address_info.destination_way
            total_way = delivery_address_info.total_way
            forecast_time = delivery_address_info.forecast_time
            google_map = delivery_address_info.google_map
            if total_way > 0:
                postage_delivery = self.calc_postage_delivery(total_way, delivery_service, source_way)
        else:
            distance_matrix =  gmaps.distance_matrix(origins=start_point_name, destinations=end_point_name, mode="driving")
            _logger.info('================GOOGLE MAPS=======================')
            _logger.info(distance_matrix)
            _logger.info(distance_matrix.get('status'))
            if distance_matrix.get('status') == 'OK':
                rows = distance_matrix.get('rows')
                _logger.info(rows[0])
                elements = rows[0]['elements'][0]
                if (elements.get('status') == 'OK') :
                    duration = elements.get('duration')
                    distance = elements.get('distance')
                    source_way = round(float(distance.get('value') / 1000.0), 2)
                    destination_way = source_way
                    total_way = source_way + destination_way
                    forecast_time = duration.get('text')
            if total_way > 0:
                postage_delivery = self.calc_postage_delivery(total_way, delivery_service)

            google_map = "https://maps.google.com?saddr="+str(start_point_name)+"&daddr=" + str(end_point_name)

            delivery_address_info_object.create({
                'name': start_point_name + end_point_name,
                'start_point': start_point_id,
                'end_point': end_point_id,
                'source_way': source_way,
                'destination_way' : destination_way,
                'total_way': total_way,
                'forecast_time': forecast_time,
                'google_map': google_map,
            })
        return {
            'value': {
                'source_way': source_way,
                'destination_way' : destination_way,
                'total_way': total_way,
                'forecast_time': forecast_time,
                'postage_delivery': postage_delivery,
                'google_map': google_map
            }
        }

    # duration
    @api.onchange('start_time', 'end_time')
    def _get_duration_date(self):
        durationtext = '0 mins'
        if self.start_time and self.end_time:
            return self.calc_time(self.start_time, self.end_time)
            # duration = duration.days
    @api.depends('start_time', 'end_time', 'duration_time')
    def _compute_time(self):
        time = self.calc_time(self.start_time, self.end_time)
        self.duration_time = time['value']['duration_time']

    def calc_time(self, start_time, end_time):
        duration = end_time - start_time
        _logger.info(duration)
        calcduration = duration * 60.0
        if calcduration > 60:
            intpart = int(duration)
            floatpart = duration - intpart
            durationtext = str(int(round(intpart,2))) + ' hours'
            if (floatpart > 0) :
                _logger.info(floatpart)
                durationtext = durationtext + ' ' + str(int(round(floatpart * 60.0))) + ' mins'
        else :
            durationtext = str(calcduration) + ' mins'
        return {
            'value': {
                'duration_time': durationtext
            }
        }

    @api.depends('postage_delivery', 'postage_delivery_fee', 'postage_total')
    def _compute_postage_total(self):
        self.postage_total = self.postage_delivery + self.postage_delivery_fee

    @api.onchange('postage_delivery', 'postage_delivery_fee')
    def _onchange_postage(self):
        postage_total = self.postage_delivery + self.postage_delivery_fee
        return {
            'value': {
                'postage_total': postage_total
            }
        }

    def calc_postage_delivery(self, total_way, delivery_service, source_way = 0):
        postage_delivery = 0
        conf = self.env['ir.config_parameter']
        if delivery_service == 'internal':
            _logger.info('internal')
            # gas = float(conf.get_param('gas_verification.gas'))
            # avggasinkm = float(conf.get_param('avggasinkm_verification.avggasinkm'))
            # if avggasinkm > 0:
            #     postage_delivery = (total_way * gas) / avggasinkm
        else:
            if delivery_service == 'collaborators':
                if source_way < 5:
                    postage_delivery = 20000
                else :
                    if source_way < 10:
                        postage_delivery = 30000
                    else :
                        if source_way < 15:
                            postage_delivery = 40000
                        else:
                            if source_way < 20:
                                postage_delivery = 50000
                            else:
                                postage_delivery = 60000

            else :
                _logger.info('partner')

        return postage_delivery

    def export_data(self, fields, data = False):
        dataindex_1 = dataindex_2 = dataindex_3 = dataindex_4 = dataindex_5 = dataindex_6 = dataindex_7 = None
        _logger.info('+' * 20)
        for index, fieldlabel in enumerate(fields):
            _logger.info(fieldlabel)
            if fieldlabel == 'stock_tranfer_date':
                dataindex_1 = index
            if fieldlabel == 'min_date':
                dataindex_2 = index
            if fieldlabel == 'stock_outin_date':
                dataindex_3 = index 
            if fieldlabel == 'stock_live_date':
                dataindex_4 = index
            if fieldlabel == 'sale_id/date_order':
                dataindex_5 = index
            if fieldlabel == 'sale_id/confirmation_date':
                dataindex_6 = index
            if fieldlabel == 'sale_id/stock_tranfer_date':
                dataindex_7 = index        
        res = super(stock_picking, self).export_data(fields, data) 
        try:
            for index, val in enumerate(res['datas']):
                if dataindex_1:           
                    service_date = res['datas'][index][dataindex_1] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex_1] = sdate
                if dataindex_2:           
                    service_date = res['datas'][index][dataindex_2] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex_2] = sdate
                if dataindex_3:           
                    service_date = res['datas'][index][dataindex_3] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex_3] = sdate
                if dataindex_4:           
                    service_date = res['datas'][index][dataindex_4] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex_4] = sdate
                if dataindex_5:           
                    service_date = res['datas'][index][dataindex_5] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex_5] = sdate
                if dataindex_6:           
                    service_date = res['datas'][index][dataindex_6] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex_6] = sdate
                if dataindex_7:           
                    service_date = res['datas'][index][dataindex_7] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex_7] = sdate
        except Exception:
            pass    
        return res

    @api.depends('origin')
    def _compute_get_note_stock_picking(self):
        for record in self:
            if record.picking_type_code:
                if record.picking_type_code == 'incoming':
                    po = record.env['purchase.order'].search([('name', '=', record.origin)], limit =1)
                    if po:
                        record.note_stock_picking = po.notes
                elif record.picking_type_code == 'outgoing':
                    so = record.env['sale.order'].search([('name', '=', record.origin)], limit =1)
                    if so:
                        record.note_stock_picking = so.note
    @api.depends('partner_id')
    def _compute_get_customer_type(self):
        for record in self:
            if record.partner_id:
                if record.partner_id.customer_type:
                    record.customer_type = record.partner_id.customer_type

    api.onchange('partner_id')
    def _onchange_partner_id(self):
        if record.partner_id:
            if record.partner_id.customer_type:
                record.customer_type = record.partner_id.customer_type
                        

class pack_operation(models.Model):
    _inherit = 'stock.pack.operation'

    product_unit_price = fields.Float(
        'Unit Price',
        compute="_compute_get_unit_price",
        store=True
    )

    @api.depends('product_id')
    def _compute_get_unit_price(self):
        for record in self: 
                if record.picking_id.picking_type_code:
                    if record.picking_id.picking_type_code == 'incoming':
                        po = record.env['purchase.order'].search([('name', '=', record.picking_id.origin)], limit =1)
                        if po:
                            _logger.info(po)
                            for ol in po.order_line:
                                price_unit = ol.price_unit
                                product_id = ol.product_id.id
                                spo = ol.env['stock.pack.operation'].search([('picking_id', '=', record.picking_id.id), ('product_id', '=', product_id)])
                                if spo:
                                    for myspo in spo:
                                        myspo.product_unit_price = price_unit if price_unit > 0 else False
                    elif record.picking_id.picking_type_code == 'outgoing':
                        so = record.env['sale.order'].search([('name', '=', record.picking_id.origin)], limit = 1)
                        if so:
                            for ol in so.order_line:
                                price_unit = ol.price_unit
                                product_id = ol.product_id.id
                                spo = ol.env['stock.pack.operation'].search([('picking_id', '=', record.picking_id.id), ('product_id', '=', product_id)])
                                if spo:
                                    for myspo in spo:
                                        myspo.product_unit_price = price_unit if price_unit > 0 else False

class stock_move(models.Model):
    _inherit = 'stock.move'

    discount = fields.Float(string='Discount', digits=dp.get_precision('Discount'), default=0.0)
    discount_type = fields.Selection([
        ('percent', '%'),
        ('fixprice', '$'),
    ], default="percent", string="Discount type")

    price_tax = fields.Float(string='Price Taxes', compute="_compute_amount", readonly=True, store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes')
    price_total = fields.Float(string='Total', compute="_compute_amount", readonly=True, store=True)
    price_subtotal = fields.Float(string='Total (Untaxed)', compute="_compute_amount", readonly=True, store=True)
    order_id = fields.Many2one('sale.order', string='Order Reference', index=True, copy=False)
    sale_line_id = fields.Many2one('sale.order.line', 'Sales Order Line', related='procurement_id.sale_line_id', store=True)

    @api.onchange('product_id')
    def onchange_product_id(self):

        res = super(stock_move, self).onchange_product_id()
        product = self.product_id.with_context(lang=self.partner_id.lang or self.env.user.lang)
        self.price_unit = product.list_price
        return res

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'price_tax', 'discount_type')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            if line.discount_type == 'fixprice':
                price = line.price_unit - line.discount
            else :
                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            _logger.info((price, line.order_id.currency_id, line.product_uom_qty, line.product_id, line.order_id.partner_id))
            taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=line.order_id.partner_id)
            line.update({
                'price_tax': taxes['total_included'] - taxes['total_excluded'],
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

class ProcurementOrder(models.Model):
    _inherit = "procurement.order"

    def _get_stock_move_values(self):
        vals = super(ProcurementOrder, self)._get_stock_move_values()
        tax_id = []
        if self.sale_line_id:
            vals.update({'price_unit': self.sale_line_id.price_unit})
            vals.update({'discount': self.sale_line_id.discount})
            vals.update({'discount_type': self.sale_line_id.discount_type})
            if self.sale_line_id.tax_id.id != False:
                tax_id.append(self.sale_line_id.tax_id.id)
            vals.update({'order_id': self.sale_line_id.order_id.id})
        vals.update({'tax_id': [(6,0, tax_id)]})
        return vals
