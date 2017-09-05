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
    CREATEUPDATECUSTOMER_URL = '/wholeso/pos/savewholecustomer/odoo'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0
    @api.model
    def create_update_partner(self, customer_id = None, model=None, action=None):
        self._logger.info(self.env.cr.dbname)
        #========================AUTH DATA=====================
        self._logger.info('=' * 20)
        self._logger.info(customer_id)
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            print 'BEGIN create_order()'
            try:
                if customer_id > 0:
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
                        customer = self.env[model].browse(customer_id)
                        url = base_url + self.CREATEUPDATECUSTOMER_URL + '/' + str(self.OSS_COMPANYID)
                        self._logger.info(url)
                        headers = {'Content-Type': 'application/json', 'Authorization': token}
                        images = []
                        if customer.images:
                            for myimage in customer.images:
                                images.append({
                                            'name' : myimage.name if myimage.name else '',
                                            'image_medium' : myimage.image_medium if myimage.image_medium else '',
                                            'image_alt' : myimage.image_alt if myimage.image_alt else '',
                                            'sequence' : myimage.sequence if myimage.sequence else 0,
                                            'image' : myimage.image if myimage.image else '',
                                            'description' : myimage.description if myimage.description else '',
                                        })
                        child_ids = []
                        if customer.child_ids:
                            for child in customer.child_ids:
                                tags = ''
                                if child.category_id:
                                    for tag in child.category_id:
                                        if tags == '':
                                            tag += str(tag.id)
                                        else:
                                            tag += "," + str(tag.id)
                                child_ids.append({
                                            'name': child.name if child.name else '',
                                            'zip': child.zip if child.zip else '',
                                            'street': child.street if child.street else '',
                                            'street2': child.street2 if child.street2 else '',
                                            'city': child.city if child.city else '',
                                            'type': child.type if child.type else '',
                                            'phone': child.phone if child.phone else '',
                                            'mobile': child.mobile if child.mobile else '',
                                            'id' : child.id if child.id else 0,
                                            'email': child.email if child.email else '',
                                            'country_id': child.country_id.id if child.country_id.id else None,
                                            'city_id': child.city_id.id if child.city_id.id else None,
                                            'district_id': child.district_id.id if child.district_id.id else None,
                                            'ward_id': child.ward_id.id if child.ward_id.id else None,
                                            'comment': child.comment if child.comment else '',
                                            'function': child.function if child.function else '',
                                            "company_type": customer.company_type if customer.company_type else '',
                                            "tags": tags,
                                        })
                        self._logger.info(child_ids)
                        tags = ''
                        if customer.category_id:
                            for tag in customer.category_id:
                                if tags == '':
                                    tag += str(tag.id)
                                else:
                                    tag += "," + str(tag.id)
                        createcustomerdata = {
                            "company_type": customer.company_type if customer.company_type else '',
                            "fax": customer.fax if customer.fax else '',
                            "name": customer.name if customer.name else '', #(required)
                            "zip": customer.zip if customer.zip else '',
                            "mobile": customer.mobile if customer.mobile else '', #(required)
                            "child_ids": child_ids,
                            "email": customer.email if customer.email else '',
                            "phone": customer.phone if customer.phone else '',
                            "customer_type": customer.customer_type if customer.customer_type else '',
                            "type_code": customer.type_code.id if customer.type_code.id else 0,
                            'country_id': child.country_id.id if child.country_id.id else None,
                            'city_id': child.city_id.id if child.city_id.id else None,
                            'district_id': child.district_id.id if child.district_id.id else None,
                            'ward_id': child.ward_id.id if child.ward_id.id else None,
                            "customer_id": customer.customer_id if customer.customer_id else '',
                            "images": images,
                            "property_product_pricelist": customer.property_product_pricelist.id if customer.property_product_pricelist.id else 0,
                            "delivery_service": customer.delivery_service if customer.delivery_service else '',
                            "id": customer.id#ID bên odoo (required)
                            "tags": tags,
                            "sale_warn": customer.sale_warn,
                            "sale_warn_msg": customer.sale_warn_msg if customer.sale_warn_msg else '',
                            "active_debt_limit": customer.active_debt_limit,
                            "debt_limit": customer.debt_limit,
                        }
                        self._logger.info(createcustomerdata)
                        r = None
                        self._logger.info(action)
                        if action == 'create':
                            r = requests.post(url, json=createcustomerdata, headers=headers)
                        if action == 'write':
                            r = requests.put(url, json=createcustomerdata, headers=headers)
                        response = r.json()
                        self._logger.info('===================RESPONSE=====================')
                        self._logger.info(response)
                        if 'status' in response and response.get('status') == '1':
                            customer.write({
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
                    'object_id' : customer_id,
                    'output': message,
                    'status': status
                })
                new_cr.commit()
                self._logger.info('==================================')
                self._logger.info(id)
                self.env.cr.close()

            return True
