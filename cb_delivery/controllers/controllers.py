# -*- coding: utf-8 -*-
from odoo import http

# class CbDelivery(http.Controller):
#     @http.route('/cb_delivery/cb_delivery/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/cb_delivery/cb_delivery/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('cb_delivery.listing', {
#             'root': '/cb_delivery/cb_delivery',
#             'objects': http.request.env['cb_delivery.cb_delivery'].search([]),
#         })

#     @http.route('/cb_delivery/cb_delivery/objects/<model("cb_delivery.cb_delivery"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('cb_delivery.object', {
#             'object': obj
#         })