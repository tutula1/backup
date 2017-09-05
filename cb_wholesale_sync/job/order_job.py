# -*- coding: utf-8 -*-
from odoo import _, fields, api, models, sql_db
import logging
import requests
import redis
import urllib
_logger = logging.getLogger(__name__)
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.queue_job.exception import RetryableJobError
import pytz
import datetime
from datetime import date, datetime, time
try:
    import simplejson as json
except ImportError:
    import json

class PartnerJob(models.Model):

    _inherit = 'sale.order'

   
    CREATEUPDATEORDER_URL = '/pos/savewholeso/odoo'
    CREATEUPDATESTATUS_URL = '/pos/updatewholesostatus/odoo'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0

    def convertDateTime(self, sdate):
        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
        dbtz = pytz.timezone('UTC')
        utctz = pytz.timezone(db_timezone)
        if sdate != None and sdate != '' and sdate != False and sdate != 'False':
            sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
            utctz_dt = utctz.localize(sdate_dt, is_dst=None)
            db_dt = utctz_dt.astimezone(dbtz) 
            return db_dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        else:
            return None

    def create_update_order(self, order_id = None, model=None, action=None):
        if order_id > 0:
            order = self.env[model].browse(order_id)
            url = self.env['authentication.queue.job'].get_oss_url() +  self.CREATEUPDATEORDER_URL + '/' + str(self.OSS_COMPANYID)
            #Maping colums odoo vs oss
            order_discount = order.discount_value
            discount_type_percent_id = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
            if order.apply_discount == True and order.discount_type_id.id == discount_type_percent_id:
                order_discount = order.discount_value * (order.amount_untaxed + order.amount_tax) / 100

            my_line = []
            if order.order_line:
                for line in order.order_line:
                    discount = line.discount
                    price = 0
                    if line.discount_type == 'percent':
                        price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                        discount = (line.discount * line.price_total / 100)
                    else:
                        price = line.price_unit - line.discount
                    my_line.append({
                                'name': line.product_id.name,
                                'id' : line.id,
                                'product_id': {
                                    'id': line.product_id.id,
                                    'barcode': line.product_id.barcode,
                                    'type' : line.product_id.type,
                                    'name': line.product_id.name,
                                    'categ_id': line.product_id.categ_id.id
                                },
                                'product_uom_qty': line.product_uom_qty,
                                'price_discount': discount,
                                'subtotal': line.price_total,
                                'price_unit': line.price_unit,
                                # 'discount_type': 'fixprice'
                            })
            referid = order.external_id if order.external_id else 0
            if action == 'create':
                referid = 0
            orderdata = {
                "type_oss": "POST" if action == 'create' else "PUT",
                "model_oss": url,
                "id": order.id if order.id else 0,
                "name": order.name if order.name else '',
                "note": order.note if order.note else '',
                "delivery_cost": order.delivery_cost if order.delivery_cost else 0,
                "customer_id": order.partner_id.id if order.partner_id.id else 0,
                "payment_term_id": order.payment_term_id.id if order.payment_term_id.id else 0,
                "source": order.source_id.id if order.source_id.id else 0,
                "partner_reciver_id": order.partner_reciver_id.id if order.partner_reciver_id.id else 0,
                "partner_invoice_id": order.partner_invoice_id.id if order.partner_invoice_id.id else 0,
                "partner_shipping_id": order.partner_shipping_id.id if order.partner_shipping_id.id else 0,
                "sale_person": {
                    "id": order.user_id.id if order.user_id.id else 0,
                    "code": order.user_id.id if order.user_id.id else 0,
                    "name": order.user_id.name if order.user_id.name else 0
                },
                "warehouse_code": order.warehouse_id.code if order.warehouse_id.code else '',
                "category_id": order.category_id.id if order.category_id.id else 0,
                "internal_note": order.internal_note if order.internal_note else 0,
                "amount": order.amount_total if order.amount_total else 0, # total amount cua DH da tru discount (required)
                "discount": order_discount if order_discount else 0, # discount cua DH (required)
                "issueinvoice": 0, # 0: khong in HD GTGT, 1: in HD GTGT (required)
                "sourcesale": order.source_sale_id.code if order.source_sale_id else 0, # Kenh ban hang (required)
                "shipmethod": 0, # Phuong thuc giao hang(neu chua chon thi gia tri la: 0) (required)
                "createduser": order.user_id.login, # Nguoi tao DH (required)
                "enterpriseid": self.OSS_COMPANYID, # company id 4(CDF) (required)
                "companyid": self.OSS_COMPANYID, # company id 4(CDF)
                "order_line": my_line,
                "customer": {
                    "id": order.partner_id.id if order.partner_id.id else 0, # ID khach hang (required)
                    "name": order.partner_id.name if order.partner_id.name else '', # Ten khach (opt)
                    "mobile": order.partner_id.mobile if order.partner_id.mobile != False else order.partner_id.phone # SDT khach (required)
                },
                "template_id": order.template_id.id if order.template_id.id else 0,
                "pricelist_id": order.pricelist_id.id if order.pricelist_id.id != False else 0,
                "date_order": self.env['authentication.queue.job'].convertDateTime(order.date_order),
                "validity_date": self.env['authentication.queue.job'].convertDateTime(str(order.validity_date), True, False),
                "stock_tranfer_date": self.env['authentication.queue.job'].convertDateTime(order.stock_tranfer_date),
                "state": order.state if order.state else 'draft',
                "created_user": order.create_uid.code if order.create_uid.id else '',
                "updated_user": order.write_uid.code if order.write_uid.code else '',
                "created_time": self.convertDateTime(order.create_date),
                "referid": referid
            }
            if action == 'write':
                orderdata = {'orderIn': orderdata}
                url = url + '/' + str(order.id)
            log = self.env['cb.logs'].create({
                'name': 'log_send_oss',
                'model': model,
                'action': action,
                'request': json.dumps(orderdata),
                'response': '',
                'object_id' : order.id,
                'output': '',
                'status': 'inprocess',
                'url': ''
            })
            data_oss = {
                "method": "POST" if action == 'create' else "PUT",
                "url": url,
                "model": model,
                "id": order_id,
                "log": log.id,
                "data": orderdata
            }
            self.env['rabbit.queue.job'].publish('wholesale_so_' + str(action), data_oss, model, order.id, action)

        return True

    def update_status_order(self, order_id = None, model=None, action=None):
        try:
            if order_id > 0:
                status = 'inprocess'
                message = ''
                token = ''
                log_request = ''
                log_response = ''
                url = ''
                #========================AUTH DATA============================================
                response = self.env['authentication.queue.job'].get_token()
                
                token = response.get('access_token')
                _logger.info(token)
                if token != '':
                    order = self.env[model].browse(order_id)
                    requestparam = '?orderid=' + str(order.id) + '&status=' + str(order.state)
                    url = self.env['authentication.queue.job'].get_oss_url() +  self.CREATEUPDATESTATUS_URL + '/' + str(self.OSS_COMPANYID) +  requestparam
                    headers = {'Content-Type': 'application/json', 'Authorization': token}
                    
                    log_request = str(requestparam)
                    r = requests.put(url, json={}, headers=headers)
                    response = r.json()
                    log_response = str(response)
                    if 'status' in response and response.get('status') == '1':
                        status = 'success'
                        message = response.get('errorMessage')
                    else:
                        status = 'error'
                        message = response.get('errorMessage')
                else :
                    message = 'get token error'
                    status = 'error'
        except Exception, e:
            message = e.message
            status = 'error'
        finally:
            id = self.env['cb.logs'].create({
                'name': 'sync_with_oss',
                'model': model,
                'action': action,
                'request': log_request,
                'response': log_response,
                'object_id' : order_id,
                'output': message,
                'status': status,
                'url': url
            })
            if status == 'error':
                return False
        return True
