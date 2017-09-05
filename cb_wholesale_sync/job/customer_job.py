# -*- coding: utf-8 -*-
from odoo import _, fields, api, models, sql_db
import logging
import datetime
import requests
import redis
import urllib
_logger = logging.getLogger(__name__)
from threading import Thread
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.queue_job.exception import RetryableJobError
try:
    import simplejson as json
except ImportError:
    import json

class PartnerJob(models.Model):

    _inherit = 'res.partner'

   
    
    CREATEUPDATECUSTOMER_URL = '/pos/savewholecustomer/odoo'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0
 

    def my_method(self, a, k=None):
        _logger.info('executed with a: %s and k: %s', a, k)

    def create_update_partner(self, customer_id = None, model=None, action=None):
        if customer_id > 0:
            customer = self.env[model].browse(customer_id)
            url = self.env['authentication.queue.job'].get_oss_url() + self.CREATEUPDATECUSTOMER_URL + '/' + str(self.OSS_COMPANYID)
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
                    tags = []
                    if child.category_id:
                        for tag in child.category_id:
                            tags.append({'id': tag.id, 'name': tag.name})
                    child_ids.append({
                            'name': child.name if child.name else '',
                            'zip': child.zip if child.zip else '',
                            'street': child.street if child.street else '',
                            'city': child.city if child.city else '',
                            'type': child.type if child.type else '',
                            'phone': child.phone if child.phone else '',
                            'mobile': child.mobile if child.mobile else '',
                            'id' : child.id if child.id else 0,
                            'email': child.email if child.email else '',
                            'country_id': child.country_id.id if child.country_id.id else 0,
                            'city_id': child.city_id.id if child.city_id.id else 0,
                            'district_id': child.district_id.id if child.district_id.id else 0,
                            'ward_id': child.ward_id.id if child.ward_id.id else 0,
                            'comment': child.comment if child.comment else '',
                            'function': child.function if child.function else '',
                            "company_type": customer.company_type if customer.company_type else '',
                            "tags": tags,
                        })
            tags = []
            if customer.category_id:
                for tag in customer.category_id:
                    tags.append({'id': tag.id, 'name': tag.name})
            createcustomerdata = {
                "company_type": customer.company_type if customer.company_type else '',
                "fax": customer.fax if customer.fax else '',
                "name": customer.name if customer.name else '', #(required)
                "zip": customer.zip if customer.zip else '',
                "mobile": customer.mobile if customer.mobile else '', #(required)
                "child_ids": child_ids,
                "email": customer.email if customer.email else '',
                "phone": customer.phone if customer.phone else '',
                "tax_code": customer.tax_code if customer.tax_code else '',
                "comment": customer.comment if customer.comment else '',
                "website": customer.website if customer.website else '',
                "contact_name": customer.contact_name if customer.contact_name else '',
                "customer_type": customer.customer_type if customer.customer_type else '',
                "type_code": customer.type_code.id if customer.type_code.id else 0,
                "parent_id": customer.parent_id.id if customer.parent_id.id else 0,
                "title": customer.title.id if customer.title.id else 0,
                "agent_channel_id": customer.type_code.id if customer.type_code.id else 0,
                'country_id': customer.country_id.id if customer.country_id.id else 0,
                'street': customer.street if customer.street else '',
                'city_id': customer.city_id.id if customer.city_id.id else 0,
                'district_id': customer.district_id.id if customer.district_id.id else 0,
                'ward_id': customer.ward_id.id if customer.ward_id.id else 0,
                "customer_id": customer.customer_id if customer.customer_id else '',
                "source_id": customer.source_id.id if customer.source_id.id else 0,
                "images": images,
                "property_product_pricelist": customer.property_product_pricelist.id if customer.property_product_pricelist.id else 0,
                "property_payment_term_id": customer.property_payment_term_id.id if customer.property_payment_term_id.id else 0,
                "sale_person": customer.user_id.id if customer.user_id.id else 0,
                "delivery_service": customer.delivery_service if customer.delivery_service else '',
                "id": customer.id,#ID bên odoo (required)
                "tags": tags,
                "created_user": customer.create_uid.code if customer.create_uid.id else '',
                "updated_user": customer.write_uid.code if customer.write_uid.code else '',
                "sale_warn": customer.sale_warn,
                "sale_warn_msg": customer.sale_warn_msg if customer.sale_warn_msg else '',
                "active_debt_limit": customer.active_debt_limit,
                "debt_limit": customer.debt_limit,
            }
            log = self.env['cb.logs'].create({
                'name': 'log_send_oss',
                'model': model,
                'action': action,
                'request': json.dumps(createcustomerdata),
                'response': '',
                'object_id' : customer.id,
                'output': '',
                'status': 'inprocess',
                'url': ''
            })
            data_oss = {
                "method": "POST" if action == 'create' else "PUT",
                "url": url,
                "model": model,
                "id": customer_id,
                "log": log.id,
                "data": createcustomerdata
            }
            self.env['rabbit.queue.job'].publish('wholesale_cus_' + str(action), data_oss, model, customer.id, action)
        return True

