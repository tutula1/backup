# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
import re
import logging
_logger = logging.getLogger(__name__)

class cb_partner(models.Model):
    _inherit = 'res.partner'

    delivery_service = fields.Selection([
        ('internal', "Nội bộ"),
        ('partner', "Đối tác"),
        ('collaborators', "Cộng tác viên"),
    ], default="")

class cb_source_sale(models.Model):
    _name = 'cb.source.sale'

    name = fields.Char(
        string='Name',
        required=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
    )
    description = fields.Text(
        string='Description',
    )
    _sql_constraints = [
        ('code_uniq', 'unique (code)', _('The code must be unique !')),
    ]