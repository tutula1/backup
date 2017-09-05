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
    CREATEDELIVERY_URL = '/wholeso/pos/createwholedo/odoo'
    UPDATEDELIVERY_URL = '/wholeso/pos/savewholedo/odoo'
    UPDATESTATUSDELIVERY_URL = '/wholeso/pos/updatestatuswholedo/odoo'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0
    @api.model
    def create_picking(self, pick_id = None, model=None, action=None)       
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_picking()'
            try:
                if pick_id > 0:
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

                    #========================END AUTH DATA============================================
                    url = base_url + self.AUTH_URL
                    headers = {'Content-Type': 'application/json', 'Authorization': basic_auth}
                    authdata = {
                        'grant_type' : grant_type,
                        'username' : username,
                        'password': password
                    }
                    #========================Get token url============================================
                    
                    r = requests.post(url + '?' + urllib.urlencode(authdata), json={}, headers=headers)
                    response = r.json()
                    
                    token = response.get('access_token')
                    
                    if token != '':
                        pick = self.env[model].browse(pick_id)

                        order = self.env['sale.order'].search([('name', '=', pick.origin)], limit=1)

                        url = base_url + self.CREATEDELIVERY_URL + '/' + str(self.OSS_COMPANYID)

                        self._logger.info('====REQUEST URL====')
                        self._logger.info(url)

                        headers = {'Content-Type': 'application/json', 'Authorization': token}
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
                                my_move_lines.append({
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
                                })
                        my_pack_operation_product_ids = []
                        if pick.pack_operation_product_ids:
                            for pack_operation_product_id in pick.pack_operation_product_ids:
                                my_pack_operation_product_ids.append({
                                                                     'product_id': pack_operation_product_id.product_id.id,
                                                                     'product_name': pack_operation_product_id.product_id.name,
                                                                     'product_qty': pack_operation_product_id.product_qty,
                                                                     'qty_done': pack_operation_product_id.qty_done,
                                                                     'product_unit_price': pack_operation_product_id.product_unit_price,
                                                                })
                        createpickdata = {
                            "origin": pick.origin,
                            "pack_operation_product_ids": my_pack_operation_product_ids,
                            "apply_discount": pick.apply_discount if pick.apply_discount != False else 0,
                            "delivery_fee": pick.delivery_fee,
                            "customer_reference": pick.customer_reference if pick.customer_reference != False else '',
                            "note_stock_picking": pick.note_stock_picking if pick.note_stock_picking != False else '',
                            "duration_time": pick.duration_time,
                            "source_way": pick.source_way,
                            "partner_id": {
                              "id": pick.partner_id.id,
                              "name": pick.partner_id.name
                            },
                            "id": pick.id,
                            "postage_delivery_fee": pick.postage_delivery_fee,
                            "amount_untaxed": pick.amount_untaxed,
                            "stock_tranfer_date": pick.stock_tranfer_date,
                            "location_id": pick.location_id.id,
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
                            "min_date": pick.min_date,
                            "discount_account": pick.discount_account.id if pick.discount_account.id != False else 0,
                            "amount_after_discount": pick.amount_after_discount,
                            "google_map": pick.google_map,
                            "warehouse_destination_name": pick.warehouse_destination_name if pick.warehouse_destination_name != False else '',
                            "delivery_status": pick.delivery_status,
                            "warehouse_name": pick.warehouse_name,
                            "postage_total": pick.postage_total,
                            "amount_total": pick.amount_total,
                            "collaborators": pick.collaborators.id,
                            "name": pick.name,
                            "external_id": order.external_id if order.external_id != False else None,
                            "total_way": pick.total_way,
                            "stock_outin_date": pick.stock_outin_date,
                            "forecast_time": pick.forecast_time if pick.forecast_time != False else '',
                            "customer_type": pick.customer_type if pick.customer_type != False else '',
                            "location_dest_id": pick.location_dest_id.id,
                            "end_time": pick.end_time,
                            "end_point": {
                              "lat": pick.end_point.lat,
                              "lng": pick.end_point.lng,
                              "id": pick.end_point.id,
                              "name": pick.end_point.name
                            },
                            "discount_value": pick.discount_value,
                            "start_point": {
                              "lat": pick.start_point.lat if pick.start_point.lat != False else '',
                              "lng": pick.start_point.lng if pick.start_point.lng != False else '',
                              "id": pick.start_point.id if pick.start_point.id != False else 0,
                              "name": pick.start_point.name if pick.start_point.name != False else ''
                            }
                        }
                        self._logger.info(createpickdata)
                        r = requests.post(url, json=createpickdata, headers=headers)
                        response = r.json()
                        self._logger.info('===================RESPONSE=====================')
                        self._logger.info(response)
                        if 'status' in response and response.get('status') == '1':
                            pick.write({
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
                    'object_id' : pick_id,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True

    def update_picking(self, pick_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(pick_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_picking()'
            try:
                if pick_id > 0:
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
                        pick = self.env[model].browse(pick_id)

                        order = self.env['sale.order'].search([('name', '=', pick.origin)], limit=1)

                        url = base_url + self.CREATEDELIVERY_URL + '/' + str(self.OSS_COMPANYID)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        self._logger.info(headers)
                        #Maping colums odoo vs oss
                        order_discount = pick.discount_value
                        discount_type_percent_id = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_percent_id')
                        if pick.apply_discount == True and pick.discount_type_id.id == discount_type_percent_id:
                            order_discount = pick.amount_untaxed - (pick.discount_value * pick.amount_untaxed / 100)
                        self._logger.info(order_discount)
                        self._logger.info('=========================================================')
                        self._logger.info(pick.move_lines)
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
                                my_move_lines.append({
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
                                })
                        my_pack_operation_product_ids = []
                        if pick.pack_operation_product_ids:
                            for pack_operation_product_id in pick.pack_operation_product_ids:
                                my_pack_operation_product_ids.append({
                                                                     'product_id': pack_operation_product_id.product_id.id,
                                                                     'product_name': pack_operation_product_id.product_id.name,
                                                                     'product_qty': pack_operation_product_id.product_qty,
                                                                     'qty_done': pack_operation_product_id.qty_done,
                                                                     'product_unit_price': pack_operation_product_id.product_unit_price,
                                                                })
                        createpickdata = {
                            "origin": pick.origin,
                            "pack_operation_product_ids": my_pack_operation_product_ids,
                            "apply_discount": pick.apply_discount if pick.apply_discount != False else 0,
                            "delivery_fee": pick.delivery_fee,
                            "customer_reference": pick.customer_reference if pick.customer_reference != False else '',
                            "note_stock_picking": pick.note_stock_picking if pick.note_stock_picking != False else '',
                            "duration_time": pick.duration_time,
                            "source_way": pick.source_way,
                            "partner_id": {
                              "id": pick.partner_id.id,
                              "name": pick.partner_id.name
                            },
                            "id": pick.id,
                            "postage_delivery_fee": pick.postage_delivery_fee,
                            "amount_untaxed": pick.amount_untaxed,
                            "stock_tranfer_date": pick.stock_tranfer_date,
                            "location_id": pick.location_id.id,
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
                            "min_date": pick.min_date,
                            "discount_account": pick.discount_account.id if pick.discount_account.id != False else 0,
                            "amount_after_discount": pick.amount_after_discount,
                            "google_map": pick.google_map,
                            "warehouse_destination_name": pick.warehouse_destination_name if pick.warehouse_destination_name != False else '',
                            "delivery_status": pick.delivery_status,
                            "warehouse_name": pick.warehouse_name,
                            "postage_total": pick.postage_total,
                            "amount_total": pick.amount_total,
                            "collaborators": pick.collaborators.id,
                            "name": pick.name,
                            "external_id": order.external_id if order.external_id != False else None,
                            "total_way": pick.total_way,
                            "stock_outin_date": pick.stock_outin_date,
                            "forecast_time": pick.forecast_time if pick.forecast_time != False else '',
                            "customer_type": pick.customer_type if pick.customer_type != False else '',
                            "location_dest_id": pick.location_dest_id.id,
                            "end_time": pick.end_time,
                            "end_point": {
                              "lat": pick.end_point.lat,
                              "lng": pick.end_point.lng,
                              "id": pick.end_point.id,
                              "name": pick.end_point.name
                            },
                            "discount_value": pick.discount_value,
                            "start_point": {
                              "lat": pick.start_point.lat if pick.start_point.lat != False else '',
                              "lng": pick.start_point.lng if pick.start_point.lng != False else '',
                              "id": pick.start_point.id if pick.start_point.id != False else 0,
                              "name": pick.start_point.name if pick.start_point.name != False else ''
                            }
                        }
                        self._logger.info(createpickdata)
                        r = requests.put(url, json=createpickdata, headers=headers)
                        response = r.json()
                        self._logger.info('===================RESPONSE=====================')
                        self._logger.info(response)
                        if 'status' in response and response.get('status') == '1':
                            pick.write({
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
                    'object_id' : pick_id,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True

    def update_picking_status(self, pick_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(pick_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if pick_id > 0:
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
                        pick = self.env[model].browse(pick_id)

                        if pick:
                            url = base_url + self.UPDATESTATUSDELIVERY_URL + '?id=' + str(pick.id) + '&status=' + str(pick.state)
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
                            status = 'error'
                            message = 'Không tìm thấy order or pick'
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
                    'object_id' : pick_id,
                    'action': action,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True