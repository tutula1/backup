# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class CB_Stock_Config(models.TransientModel):
    _inherit = 'stock.config.settings'

    gas = fields.Float('Gas price')
    avggasinkm = fields.Float('Gas/km')


    @api.model
    def get_default_gas_values(self, fields):
        conf = self.env['ir.config_parameter']
        return {
            'gas': float(conf.get_param('gas_verification.gas')),
            'avggasinkm': float(conf.get_param('avggasinkm_verification.avggasinkm')),
        }

    @api.one
    def set_age_values(self):
        conf = self.env['ir.config_parameter']
        conf.set_param('gas_verification.gas', float(self.gas))
        conf.set_param('avggasinkm_verification.avggasinkm', float(self.avggasinkm))

