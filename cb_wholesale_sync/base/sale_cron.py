# -*- coding: utf-8 -*-
from odoo import _, fields, api, models, sql_db
import logging
import datetime
import requests
import redis
import urllib

class Cron(models.Model):

    _inherit = "ir.cron"
    _logger = logging.getLogger(_inherit)
    AUTH_URL = '/auth/oauth/token'
    CREATEORDER_URL = '/wholeso/pos/createwholeso'
    UPDATEORDER_URL = '/wholeso/pos/updatewholeso'
    UPDATESTATUSORDER_URL = '/wholeso/pos/updatewholesostatus'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0
    @api.model
    def create_order(self, order_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(order_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if order_id > 0:
                    status = 'inprocess'
                    message = ''
                    token = ''
                    #========================AUTH DATA============================================
                    protocol = self.env['ir.config_parameter'].get_param('oss_wholesale_protocol')
                    host = self.env['ir.config_parameter'].get_param('oss_wholesale_host')
                    port = self.env['ir.config_parameter'].get_param('oss_wholesale_port')
                    basic_auth = self.env['ir.config_parameter'].get_param('oss_basic_auth')
                    username = self.env['ir.config_parameter'].get_param('oss_username')
                    grant_type = self.env['ir.config_parameter'].get_param('oss_grant_type')
                    password = self.env['ir.config_parameter'].get_param('oss_password')
                    base_url = str(protocol) + str(host)
                    if str(port) != '80':
                        base_url = str(base_url) + ':' + str(port)
                    self._logger.info('BASE_URL')
                    self._logger.info(base_url)
                    #========================END AUTH DATA============================================

                    url = base_url + self.AUTH_URL
                    headers = {'Content-Type': 'application/json', 'Authorization': basic_auth}
                    authdata = {
                        'grant_type' : grant_type,
                        'username' : username,
                        'password': password
                    }
                    #========================Get token url============================================
                    self._logger.info(url + '?' + urllib.urlencode(authdata))
                    r = requests.post(url + '?' + urllib.urlencode(authdata), json={}, headers=headers)
                    self._logger.info(r)
                    response = r.json()
                    
                    token = response.get('access_token')
                    self._logger.info(token)
                    if token != '':
                        order = self.env[model].browse(order_id)
                        url = base_url + self.CREATEORDER_URL + '/' + str(self.OSS_COMPANYID)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        self._logger.info(headers)
                        #Maping colums odoo vs oss
                        order_discount = order.discount_value
                        discount_type_percent_id = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
                        if order.apply_discount == True and order.discount_type_id.id == discount_type_percent_id:
                            order_discount = order.amount_untaxed - (order.discount_value * order.amount_untaxed / 100)
                        self._logger.info(order_discount)
                        self._logger.info('=========================================================')
                        self._logger.info(order.order_line)
                        my_line = []
                        if order.order_line:
                            for line in order.order_line:
                                discount = line.discount
                                price = 0
                                if line.discount_type == 'percent':
                                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                                    discount = line.price_total - (line.discount * line.price_total / 100) + line.price_tax
                                else:
                                    price = line.price_unit - line.discount + line.price_tax
                                my_line.append({
                                            'name': line.product_id.name,
                                            'id' : line.product_id.barcode,
                                            'quantity': line.product_uom_qty,
                                            'discount': discount,
                                            'subtotal': line.price_total,
                                            'saleprice': price
                                        })
                        createorderdata = {
                            "id": order.id,
                            "amount": order.amount_total, # total amount cua DH da tru discount (required)
                            "discount": order_discount, # discount cua DH (required)
                            "issueinvoice": 0, # 0: khong in HD GTGT, 1: in HD GTGT (required)
                            "internal_note": order.internal_note,
                            "sourcesale": order.source_sale_id.id if order.source_sale_id.id else 0, # Kenh ban hang (required)
                            "shipmethod": 0, # Phuong thuc giao hang(neu chua chon thi gia tri la: 0) (required)
                            "createduser": order.user_id.login, # Nguoi tao DH (required)
                            "enterpriseid": self.OSS_COMPANYID, # company id 4(CDF) (required)
                            "companyid": self.OSS_COMPANYID, # company id 4(CDF)
                            "products": my_line,
                            "customer": {
                                "id": order.partner_id.customer_id, # ID khach hang (required)
                                "name": order.partner_id.name, # Ten khach (opt)
                                "mobile": order.partner_id.mobile if order.partner_id.mobile != False else order.partner_id.phone # SDT khach (required)
                            }
                        }
                        self._logger.info(createorderdata)
                        r = requests.post(url, json=createorderdata, headers=headers)
                        response = r.json()
                        self._logger.info('===================RESPONSE=====================')
                        self._logger.info(response)
                        if 'status' in response and response.get('status') == '1':
                            order.write({
                                'external_id' : response.get('data'),
                                'external_type' : 'oss'
                            })
                            new_cr.commit()
                            status = 'success'
                            message = response.get('errorMessage')
                        else:
                            status = 'error'
                            message = response.get('errorMessage')
                    else :
                        message = 'get token error'
                        status = 'error'
                    self._logger.info(message)
            except Exception, e:
                message = e.message
                self._logger.info(message)
                status = 'error'
            finally:
                id = self.env['cb.logs'].create({
                    'name': 'sync_with_oss',
                    'model': model,
                    'action': action,
                    'object_id' : order_id,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True

    def update_order(self, order_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(order_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if order_id > 0:
                    status = 'inprocess'
                    message = ''
                    token = ''
                    #========================AUTH DATA============================================
                    protocol = self.env['ir.config_parameter'].get_param('oss_wholesale_protocol')
                    host = self.env['ir.config_parameter'].get_param('oss_wholesale_host')
                    port = self.env['ir.config_parameter'].get_param('oss_wholesale_port')
                    basic_auth = self.env['ir.config_parameter'].get_param('oss_basic_auth')
                    username = self.env['ir.config_parameter'].get_param('oss_username')
                    grant_type = self.env['ir.config_parameter'].get_param('oss_grant_type')
                    password = self.env['ir.config_parameter'].get_param('oss_password')
                    base_url = str(protocol) + str(host)
                    if str(port) != '80':
                        base_url = str(base_url) + ':' + str(port)
                    self._logger.info('BASE_URL')
                    self._logger.info(base_url)
                    #========================END AUTH DATA============================================

                    url = base_url + self.AUTH_URL
                    headers = {'Content-Type': 'application/json', 'Authorization': basic_auth}
                    authdata = {
                        'grant_type' : grant_type,
                        'username' : username,
                        'password': password
                    }
                    #========================Get token url============================================
                    self._logger.info(url + '?' + urllib.urlencode(authdata))
                    r = requests.post(url + '?' + urllib.urlencode(authdata), json={}, headers=headers)
                    self._logger.info(r)
                    response = r.json()
                    
                    token = response.get('access_token')
                    self._logger.info(token)
                    if token != '':
                        order = self.env[model].browse(order_id)
                        url = base_url + self.UPDATEORDER_URL + '/' + str(self.OSS_COMPANYID) + '?status=' + str(order.state)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        self._logger.info(headers)
                        #Maping colums odoo vs oss
                        order_discount = order.discount_value
                        discount_type_percent_id = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
                        if order.apply_discount == True and order.discount_type_id.id == discount_type_percent_id:
                            order_discount = order.amount_untaxed - (order.discount_value * order.amount_untaxed / 100)
                        self._logger.info(order_discount)
                        self._logger.info('=========================================================')
                        self._logger.info(order.order_line)
                        my_line = []
                        if order.order_line:
                            for line in order.order_line:
                                discount = line.discount
                                price = 0
                                if line.discount_type == 'percent':
                                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                                    discount = line.price_total - (line.discount * line.price_total / 100) + line.price_tax
                                else:
                                    price = line.price_unit - line.discount + line.price_tax
                                my_line.append({
                                            'name': line.product_id.name,
                                            'id' : line.product_id.barcode,
                                            'quantity': line.product_uom_qty,
                                            'discount': discount,
                                            'subtotal': line.price_total,
                                            'saleprice': price
                                        })
                        createorderdata = {
                            "id": order.id,
                            "amount": order.amount_total, # total amount cua DH da tru discount (required)
                            "discount": order_discount, # discount cua DH (required)
                            "issueinvoice": 0, # 0: khong in HD GTGT, 1: in HD GTGT (required)
                            "sourcesale": self.OSS_SOUCESALE, # Kenh ban hang (required)
                            "shipmethod": 0, # Phuong thuc giao hang(neu chua chon thi gia tri la: 0) (required)
                            "createduser": order.user_id.login, # Nguoi tao DH (required)
                            "enterpriseid": self.OSS_COMPANYID, # company id 4(CDF) (required)
                            "companyid": self.OSS_COMPANYID, # company id 4(CDF)
                            "products": my_line,
                            "customer": {
                                "id": order.partner_id.customer_id, # ID khach hang (required)
                                "name": order.partner_id.name, # Ten khach (opt)
                                "mobile": order.partner_id.mobile if order.partner_id.mobile != False else order.partner_id.phone # SDT khach (required)
                            }
                        }
                        self._logger.info(createorderdata)
                        r = requests.post(url, json=createorderdata, headers=headers)
                        response = r.json()
                        self._logger.info(response)
                        if 'status' in response and response.get('status') == '1':
                            status = 'success'
                            message = response.get('errorMessage')
                        else:
                            status = 'error'
                            message = response.get('errorMessage')
                    else :
                        message = 'get token error'
                        status = 'error'
                    self._logger.info(message)
            except Exception, e:
                message = e.message
                self._logger.info(message)
                status = 'error'
            finally:
                id = self.env['cb.logs'].create({
                    'name': 'sync_with_oss',
                    'model': model,
                    'action': action,
                    'object_id' : order_id,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True

    def update_order_status(self, order_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(order_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if order_id > 0:
                    status = 'inprocess'
                    message = ''
                    token = ''
                    #========================AUTH DATA============================================
                    protocol = self.env['ir.config_parameter'].get_param('oss_wholesale_protocol')
                    host = self.env['ir.config_parameter'].get_param('oss_wholesale_host')
                    port = self.env['ir.config_parameter'].get_param('oss_wholesale_port')
                    basic_auth = self.env['ir.config_parameter'].get_param('oss_basic_auth')
                    username = self.env['ir.config_parameter'].get_param('oss_username')
                    grant_type = self.env['ir.config_parameter'].get_param('oss_grant_type')
                    password = self.env['ir.config_parameter'].get_param('oss_password')
                    base_url = str(protocol) + str(host)
                    if str(port) != '80':
                        base_url = str(base_url) + ':' + str(port)
                    self._logger.info('BASE_URL')
                    self._logger.info(base_url)
                    #========================END AUTH DATA============================================

                    url = base_url + self.AUTH_URL
                    headers = {'Content-Type': 'application/json', 'Authorization': basic_auth}
                    authdata = {
                        'grant_type' : grant_type,
                        'username' : username,
                        'password': password
                    }
                    #========================Get token url============================================
                    self._logger.info(url + '?' + urllib.urlencode(authdata))
                    r = requests.post(url + '?' + urllib.urlencode(authdata), json={}, headers=headers)
                    self._logger.info(r)
                    response = r.json()
                    
                    token = response.get('access_token')
                    self._logger.info(token)
                    if token != '':
                        order = self.env[model].browse(order_id)
                        url = base_url + self.UPDATESTATUSORDER_URL + '/' + str(self.OSS_COMPANYID) + '?orderid=' + str(order.external_id) + '&status=' + str(order.state)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        r = requests.put(url, json={}, headers=headers)
                        response = r.json()
                        self._logger.info(response)
                        if 'status' in response and response.get('status') == 1:
                            status = 'success'
                            message = response.get('errorMessage')
                        else:
                            status = 'error'
                            message = response.get('errorMessage')
                    else :
                        message = 'get token error'
                        status = 'error'
                    self._logger.info(message)
            except Exception, e:
                message = e.message
                self._logger.info(message)
                status = 'error'
            finally:
                id = self.env['cb.logs'].create({
                    'name': 'sync_with_oss',
                    'model': model,
                    'object_id' : order_id,
                    'action': action,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True