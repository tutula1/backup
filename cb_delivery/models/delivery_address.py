# -*- coding: utf-8 -*-

from odoo import models, fields, api

class delivery_address(models.Model):
    _name = 'cb.delivery.address'

    name = fields.Char('Address')
    lat = fields.Float('Latitute', compute="_compute_lat_lng", store=True)
    lng = fields.Float('Longitute', compute="_compute_lat_lng", store=True)
    auto_select_start_point = fields.Boolean(
        string='Điểm bắt đầu', default=False
    )

    @api.onchange("auto_select_start_point")
    def _onchange_auto_select_start_point(self):
        addresss = self.env['cb.delivery.address'].search([('auto_select_start_point', '=', True)])
        if addresss:
            for address in addresss:
                address.write({'auto_select_start_point': False})
        return {
            'value': {
                'auto_select_start_point': self.auto_select_start_point
            }
        }
 
class delivery_address_info(models.Model):
    _name = 'cb.delivery.address.info'

    name = fields.Char('Address info')
    start_point = fields.Many2one('cb.delivery.address', 'Điểm bắt đầu')
    end_point = fields.Many2one('cb.delivery.address', 'Điểm kết thúc')
    source_way = fields.Float('Quãng đường đi')
    destination_way = fields.Float('Quãng đường về')
    total_way = fields.Float('Tổng quãng đường')
    forecast_time = fields.Char('Thời gian dự đoán', store=True)
    google_map = fields.Char('Map')