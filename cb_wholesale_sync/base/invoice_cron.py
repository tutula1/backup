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
    CREATEINVOICE_URL = '/wholeso/pos/createwholeinv'
    UPDATEINVOICE_URL = '/wholeso/pos/savewholeinv'
    UPDATESTATUSINVOICE_URL = '/wholeso/pos/updatestatuswholeinv'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0
    @api.model
    def create_invoice(self, invoice_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(invoice_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if invoice_id > 0:
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
                        invoice = self.env[model].browse(invoice_id)
                        order = self.env['sale.order'].search([('name', '=', invoice.origin)], limit=1)
                        url = base_url + self.CREATEINVOICE_URL + '/' + str(self.OSS_COMPANYID)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        self._logger.info(headers)
                        #Maping colums odoo vs oss
                        order_discount = invoice.discount_value
                        discount_type_percent_id = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
                        if invoice.apply_discount == True and invoice.discount_type_id.id == discount_type_percent_id:
                            order_discount = invoice.amount_untaxed - (invoice.discount_value * invoice.amount_untaxed / 100)
                        self._logger.info(order_discount)
                        self._logger.info('=========================================================')
                        self._logger.info(invoice.order_line)
                        my_invoice_line = []
                        if invoice.invoice_line_ids:
                            for line in invoice.invoice_line_ids:
                                discount = line.discount
                                price = 0
                                if line.discount_type == 'percent':
                                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                                    discount = line.price_total - (line.discount * line.price_total / 100) + line.price_tax
                                else:
                                    price = line.price_unit - line.discount + line.price_tax
                                my_invoice_line.append({
                                            "name": line.name,
                                            "discount_type": line.discount_type,
                                            "price_unit": line.price_unit,
                                            "price_subtotal": line.subtotal,
                                            "account_id": {
                                                "display_name": line.account_id.display_name,
                                                "id": line.account_id.id
                                            },
                                            "discount": discount,
                                            "product_id": {
                                                "barcode": line.product_id.barcode,
                                                "categ_id": {
                                                    "id": line.product_id.categ_id.id,
                                                    "name": line.product_id.categ_id.name
                                                },
                                                "id": line.product_id.id,
                                                "name": line.product_id.name
                                            },
                                            "id": line.id,
                                            "quantity": line.quantity
                                        })
                        createorderdata = {
                            "amount_tax": invoice.amount_tax,
                            "date_due": invoice.date_due,
                            "external_id": order.external_id if order.external_id != False else None,
                            "amount_untaxed": invoice.amount_untaxed,
                            "account_id": {
                                "display_name": invoice.account_id.display_name,
                                "id": invoice.account_id.id
                            },
                            "user_id": {
                                "id": invoice.user_id.id,
                                "name": invoice.user_id.name
                            },
                            "discount_type_id": invoice.discount_type_id.id,
                            "number": invoice.number,
                            "residual": invoice.residual,
                            "date_invoice": invoice.date_invoice,
                            "journal_id": {
                                "display_name": invoice.journal_id.display_name,
                                "id": invoice.journal_id.id
                            },
                            "state": invoice.state,
                            "invoice_line_ids": my_invoice_line,
                            "discount_value": invoice.discount_value,
                            "payment_term_id": {
                                "id": invoice.payment_term_id.id,
                                "name": invoice.payment_term_id.name
                            },
                            "partner_id": {
                                "city": invoice.partner_id.city,
                                "id": invoice.partner_id.id,
                                "name": invoice.partner_id.name
                            },
                            "id": invoice.id,
                            "fiscal_position_id": {
                                "id": invoice.fiscal_position_id.id,
                                "name": invoice.fiscal_position_id.id
                            },
                            "amount_total": invoice.amount_total
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
                    'object_id' : invoice_id,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True

    def update_invoice(self, invoice_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(invoice_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if invoice_id > 0:
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
                        invoice = self.env[model].browse(invoice_id)
                        order = self.env['sale.order'].search([('name', '=', invoice.origin)], limit=1)
                        url = base_url + self.CREATEINVOICE_URL + '/' + str(self.OSS_COMPANYID)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        self._logger.info(headers)
                        #Maping colums odoo vs oss
                        order_discount = invoice.discount_value
                        discount_type_percent_id = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
                        if invoice.apply_discount == True and invoice.discount_type_id.id == discount_type_percent_id:
                            order_discount = invoice.amount_untaxed - (invoice.discount_value * invoice.amount_untaxed / 100)
                        self._logger.info(order_discount)
                        self._logger.info('=========================================================')
                        self._logger.info(invoice.order_line)
                        my_invoice_line = []
                        if invoice.invoice_line_ids:
                            for line in invoice.invoice_line_ids:
                                discount = line.discount
                                price = 0
                                if line.discount_type == 'percent':
                                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                                    discount = line.price_total - (line.discount * line.price_total / 100) + line.price_tax
                                else:
                                    price = line.price_unit - line.discount + line.price_tax
                                my_invoice_line.append({
                                            "name": line.name,
                                            "discount_type": line.discount_type,
                                            "price_unit": line.price_unit,
                                            "price_subtotal": line.subtotal,
                                            "account_id": {
                                                "display_name": line.account_id.display_name,
                                                "id": line.account_id.id
                                            },
                                            "discount": discount,
                                            "product_id": {
                                                "barcode": line.product_id.barcode,
                                                "categ_id": {
                                                    "id": line.product_id.categ_id.id,
                                                    "name": line.product_id.categ_id.name
                                                },
                                                "id": line.product_id.id,
                                                "name": line.product_id.name
                                            },
                                            "id": line.id,
                                            "quantity": line.quantity
                                        })
                        createorderdata = {
                            "amount_tax": invoice.amount_tax,
                            "date_due": invoice.date_due,
                            "external_id": order.external_id if order.external_id != False else None,
                            "amount_untaxed": invoice.amount_untaxed,
                            "account_id": {
                                "display_name": invoice.account_id.display_name,
                                "id": invoice.account_id.id
                            },
                            "user_id": {
                                "id": invoice.user_id.id,
                                "name": invoice.user_id.name
                            },
                            "discount_type_id": invoice.discount_type_id.id,
                            "number": invoice.number,
                            "residual": invoice.residual,
                            "date_invoice": invoice.date_invoice,
                            "journal_id": {
                                "display_name": invoice.journal_id.display_name,
                                "id": invoice.journal_id.id
                            },
                            "state": invoice.state,
                            "invoice_line_ids": my_invoice_line,
                            "discount_value": invoice.discount_value,
                            "payment_term_id": {
                                "id": invoice.payment_term_id.id,
                                "name": invoice.payment_term_id.name
                            },
                            "partner_id": {
                                "city": invoice.partner_id.city,
                                "id": invoice.partner_id.id,
                                "name": invoice.partner_id.name
                            },
                            "id": invoice.id,
                            "fiscal_position_id": {
                                "id": invoice.fiscal_position_id.id,
                                "name": invoice.fiscal_position_id.id
                            },
                            "amount_total": invoice.amount_total
                        }
                        self._logger.info(createorderdata)
                        r = requests.put(url, json=createorderdata, headers=headers)
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
                    'object_id' : invoice_id,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True

    def update_invoice_status(self, invoice_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(invoice_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if invoice_id > 0:
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
                        invoice = self.env[model].browse(invoice_id)
                        url = base_url + self.UPDATESTATUSINVOICE_URL + '?' + str(invoice.id) + '&status=' + str(invoice.state)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        r = requests.post(url, json={}, headers=headers)
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
                    'object_id' : invoice_id,
                    'action': action,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True