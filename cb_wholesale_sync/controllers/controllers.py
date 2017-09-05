# -*- coding: utf-8 -*-
from odoo import http

# class CbAccounting(http.Controller):
#     @http.route('/cb_accounting/cb_accounting/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/cb_accounting/cb_accounting/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('cb_accounting.listing', {
#             'root': '/cb_accounting/cb_accounting',
#             'objects': http.request.env['cb_accounting.cb_accounting'].search([]),
#         })

#     @http.route('/cb_accounting/cb_accounting/objects/<model("cb_accounting.cb_accounting"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('cb_accounting.object', {
#             'object': obj
#         })