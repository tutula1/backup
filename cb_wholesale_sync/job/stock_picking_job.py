# -*- coding: utf-8 -*-
from odoo import _, fields, api, models, sql_db
import logging
import datetime
import requests
import redis
import urllib
_logger = logging.getLogger(__name__)
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.queue_job.exception import RetryableJobError
try:
    import simplejson as json
except ImportError:
    import json

class StockPicking(models.Model):

    _inherit = "stock.picking"
    
    CREATEDELIVERY_URL = '/pos/createwholedo/odoo'
    UPDATEDELIVERY_URL = '/pos/savewholedo/odoo'
    UPDATESTATUSDELIVERY_URL = '/pos/updatestatuswholedo/odoo'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0

    def create_update_picking(self, pick_id = None, model=None, action=None):
        if pick_id > 0:
            pick = self.env[model].browse(pick_id)
            if pick:
                if pick.picking_type_code == 'outgoing':
                    # order = self.env['sale.order'].search([('name', '=', pick.origin)], limit=1)

                    if action == 'create':
                        url = self.env['authentication.queue.job'].get_oss_url() + self.CREATEDELIVERY_URL + '/' + str(self.OSS_COMPANYID)
                    else:
                        url = self.env['authentication.queue.job'].get_oss_url() + self.UPDATEDELIVERY_URL + '/' + str(self.OSS_COMPANYID)
                    #Maping colums odoo vs oss
                    order_discount = pick.discount_value
                    discount_type_percent_id = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
                    if pick.apply_discount == True and pick.discount_type_id.id == discount_type_percent_id:
                        order_discount = pick.amount_untaxed - (pick.discount_value * pick.amount_untaxed / 100)


                    my_move_lines = []
                    if pick.move_lines:
                        for line in pick.move_lines:
                            discount = line.discount
                            price = 0
                            if line.discount_type == 'percent':
                                price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                                discount = line.price_total - (line.discount * line.price_total / 100) + line.price_tax
                            else:
                                price = line.price_unit - line.discount + line.price_tax
                            my_move_lines.append(self.convert_false_to_none({
                                "price_total": line.price_total,
                                "price_tax": line.price_tax,
                                "product_id": line.product_id.id,
                                "discount_type": line.discount_type,
                                "price_unit": line.price_unit,
                                "product_uom_qty": line.product_uom_qty,
                                "price_subtotal": line.price_subtotal,
                                "discount": discount,
                                "state": line.state,
                                "tax_id": []
                            }))
                    my_pack_operation_product_ids = []
                    if pick.pack_operation_product_ids:
                        for pack_operation_product_id in pick.pack_operation_product_ids:
                            my_pack_operation_product_ids.append(self.convert_false_to_none({
                                                                 'product_id': pack_operation_product_id.product_id.id,
                                                                 'product_name': pack_operation_product_id.product_id.name,
                                                                 'product_qty': pack_operation_product_id.product_qty,
                                                                 'qty_done': pack_operation_product_id.qty_done,
                                                                 'product_unit_price': pack_operation_product_id.product_unit_price,
                                                            }))
                    apply_discount = 'false'
                    if pick.apply_discount:
                        apply_discount = 'true'
                    createpickdata = self.convert_false_to_none({
                        "origin": pick.origin,
                        "sale_id": pick.sale_id.id if pick.sale_id.id else 0,
                        "pack_operation_product_ids": my_pack_operation_product_ids,
                        "apply_discount": apply_discount,
                        "delivery_fee": pick.delivery_fee if pick.delivery_fee != False else 0,
                        "customer_reference": pick.customer_reference if pick.customer_reference != False else '',
                        "note_stock_picking": pick.note_stock_picking if pick.note_stock_picking != False else '',
                        "duration_time": pick.duration_time,
                        "source_way": pick.source_way,
                        "partner_id": {
                            "id": pick.partner_id.id,
                            "name": pick.partner_id.name,
                        },
                        "id": pick.id,
                        "postage_delivery_fee": pick.postage_delivery_fee,
                        "amount_untaxed": pick.amount_untaxed,
                        "stock_tranfer_date": str(pick.stock_tranfer_date).replace('-', '/') if pick.stock_tranfer_date != False else '',
                        "location_id": {
                            "id": pick.location_id.id,
                            "name": pick.location_id.complete_name
                        },
                        "postage_delivery": pick.postage_delivery,
                        "discount_type_id": pick.discount_type_id.id if pick.discount_type_id.id != False else 0,
                        "amount_tax": pick.amount_tax,
                        "state": pick.state,
                        "picking_type_code": pick.picking_type_code,
                        "pricelist_id": pick.pricelist_id.id,
                        "delivery_service": pick.delivery_service,
                        "move_lines": my_move_lines,
                        "start_time": pick.start_time,
                        "destination_way": pick.destination_way,
                        "min_date": str(pick.min_date).replace('-', '/') if pick.min_date != False else '',
                        "discount_account": pick.discount_account.id if pick.discount_account.id != False else 0,
                        "amount_after_discount": pick.amount_after_discount,
                        "google_map": pick.google_map,
                        "warehouse_destination_name": pick.warehouse_destination_name if pick.warehouse_destination_name != False else '',
                        "delivery_status": pick.delivery_status,
                        "warehouse_name": pick.warehouse_name,
                        "postage_total": pick.postage_total,
                        "amount_total": pick.amount_total,
                        "collaborators": {
                            "id": pick.collaborators.id if pick.collaborators.id != False else 0,
                            "name": pick.collaborators.name if pick.collaborators.name != False else ""
                        },
                        "name": pick.name,
                        "total_way": pick.total_way,
                        "stock_outin_date": str(pick.stock_outin_date).replace('-', '/') if pick.stock_outin_date != False else '',
                        "forecast_time": pick.forecast_time if pick.forecast_time != False else '',
                        "customer_type": pick.customer_type if pick.customer_type != False else '',
                        "location_dest_id": {
                            "id": pick.location_dest_id.id if pick.location_dest_id.id != False else 0,
                            "name": pick.location_dest_id.complete_name,
                        },
                        "end_time": pick.end_time,
                        "end_point": {
                          "lat": pick.end_point.lat if pick.end_point.lat != False else 0,
                          "lng": pick.end_point.lng if pick.end_point.lng != False else 0,
                          "id": pick.end_point.id if pick.end_point.id != False else 0,
                          "name": pick.end_point.name if pick.end_point.name != False else ''
                        },
                        "discount_value": pick.discount_value,
                        "start_point": {
                          "lat": pick.start_point.lat if pick.start_point.lat != False else '',
                          "lng": pick.start_point.lng if pick.start_point.lng != False else '',
                          "id": pick.start_point.id if pick.start_point.id != False else 0,
                          "name": pick.start_point.name if pick.start_point.name != False else ''
                        },
                        "create_uid": {
                            "id" : pick.create_uid.id,
                            "name": pick.create_uid.name
                        },
                        "created_user": pick.create_uid.code if pick.create_uid.id else '',
                        "updated_user": pick.write_uid.code if pick.write_uid.code else ''
                    })
                    log = self.env['cb.logs'].create({
                        'name': 'log_send_oss',
                        'model': model,
                        'action': action,
                        'request': json.dumps(createpickdata),
                        'response': '',
                        'object_id' : pick_id,
                        'output': '',
                        'status': 'inprocess',
                        'url': ''
                    })
                    data_oss = {
                        "method": "POST" if action == 'create' else "PUT",
                        "url": url,
                        "model": model,
                        "id": pick_id,
                        "log": log.id,
                        "data": createpickdata
                    }
                    self.env['rabbit.queue.job'].publish('wholesale_do_' + str(action), data_oss, model, pick.id, action)
        return True

            

    def update_picking_status(self, pick_id = None, model=None, action=None):
     
        status = 'inprocess'
        message = ''
        token = ''
        log_request = ''
        log_response = ''
        url = ''
        try:
            if pick_id > 0:
                response = self.env['authentication.queue.job'].get_token()
                token = response.get('access_token')
                _logger.info(token)
                if token != '':
                    pick = self.env[model].browse(pick_id)

                    if pick:
                        requestparam = '?id=' + str(pick.id) + '&status=' + str(pick.state)
                        url = self.env['authentication.queue.job'].get_oss_url() + self.UPDATESTATUSDELIVERY_URL + '/' + str(self.OSS_COMPANYID) + requestparam
                        headers = {'Content-Type': 'application/json', 'Authorization': token}

                        log_request = str(requestparam)

                        r = requests.put(url, json={}, headers=headers)
                        response = r.json()

                        log_response = str(response)
                        if 'status' in response and response.get('status') == 1:
                            status = 'success'
                            message = response.get('errorMessage')
                        else:
                            status = 'error'
                            message = response.get('errorMessage')
                    else :
                        status = 'error'
                        message = 'Không tìm thấy order or pick'
                else :
                    message = 'get token error'
                    status = 'error'
                _logger.info(message)
        except Exception, e:
            message = e.message
            _logger.info(message)
            status = 'error'
        finally:
            id = self.env['cb.logs'].create({
                'name': 'sync_with_oss',
                'model': model,
                'object_id' : pick_id,
                'request': log_request,
                'repsonse': log_response,
                'action': action,
                'output': message,
                'status': status,
                'url': url
            })

            if status == 'error':
                return False
        return True


    def convert_false_to_none(self, myobject):
        newobject = {}
        for attr, value in myobject.items():
            if value == False:
                newobject[attr] = ''
            else:
                newobject[attr] = value
        return newobject

