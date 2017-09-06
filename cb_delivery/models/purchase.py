# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class cb_delivery_purchase_order(models.Model):
    _inherit = 'purchase.order'

    stock_tranfer_date = fields.Datetime('Thời gian giao hàng', default=fields.Datetime.now)
    #d4 add 09:15 14/03/2017 , nhan vien mua hang
    
    def default_buyer(self):
        context = self.env.context
        uid = context.get('uid')
        current_user = self.env['res.users'].browse(uid)
        partner = current_user.partner_id
        return partner
    buyer = fields.Many2one('res.partner', string=u'Nhân viên mua hàng', default=default_buyer)

    delivery_status = fields.Selection([
        ('draft', 'Draft'), ('cancel', 'Cancelled'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting Availability'),
        ('partially_available', 'Partially Available'),
        ('assigned', 'Available'), ('done', 'Done'),
        ('delivery_success', 'Delivery Success'),
        ('delivery_fail', 'Delivery Fail')], string='Delivery Status', index=True, copy=False, store=True)

    @api.multi
    def button_confirm(self):
        res = super(cb_delivery_purchase_order, self).button_confirm()
        for order in self:
            for pick in order.picking_ids:
                if self.stock_tranfer_date != False:
                    pick.stock_tranfer_date = self.stock_tranfer_date
        return res