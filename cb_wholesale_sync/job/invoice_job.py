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

class InvoiceJob(models.Model):

    _inherit = 'account.invoice'   

    CREATEUPDATEINVOICE_URL = '/pos/savewholeinv/odoo'
    CREATEUPDATESTATUS_URL = '/pos/updatestatuswholeinv/odoo'
    OSS_COMPANYID = 4
    OSS_SOUCESALE = 4
    STATUS_SUCCESS = 1
    STATUS_ERROR = 0

    def convert_false_to_none(self, myobject):
        newobject = {}
        for attr, value in myobject.items():
            if type(value) == list:
                newobject[attr] = []
                for rec in value:
                    newobject[attr] = [self.convert_false_to_none(rec)]
            elif value == False:
                newobject[attr] = ''
            else:
                newobject[attr] = value
        return newobject

    def create_update_invoice(self, invoice_id = None, model=None, action=None):
        if invoice_id > 0:
            invoice = self.env[model].browse(invoice_id)
            url = self.env['authentication.queue.job'].get_oss_url() +  self.CREATEUPDATEINVOICE_URL + '/' + str(self.OSS_COMPANYID)
            user_id = {
                "id": invoice.user_id.id,
                "name": invoice.user_id.name

            }
            account_id = {
                "display_name": invoice.account_id.display_name,
                "id": invoice.account_id.id
            }
            journal_id = {
                "display_name": invoice.journal_id.display_name,
                "id": invoice.journal_id.id
            }
            journal_id = {
                "display_name": invoice.journal_id.display_name,
                "id": invoice.journal_id.id
            }
            invoice_line_ids = []
            for line in invoice.invoice_line_ids:
                line_account_id = {
                    "display_name" : line.account_id.display_name,
                    "id" : line.account_id.id
                }
                categ_id = {
                    "id" : line.product_id.categ_id.id,
                    "name" : line.product_id.categ_id.name
                }
                line_product_id = {
                    "barcode" : line.product_id.barcode,
                    "categ_id" : categ_id,
                    "id" : line.product_id.id,
                    "name" : line.product_id.name,
                }
                invoice_line_ids.append(
                    self.convert_false_to_none({
                        "name" : line.name,
                        "discount_type" : line.discount_type,
                        "price_unit" : line.price_unit,
                        "price_subtotal" : line.price_subtotal,
                        "account_id" : line_account_id,
                        "discount" : line.discount,
                        "product_id" : line_product_id,
                        "id" : line.id,
                        "quantity" : line.quantity,
                    })
                )
            partner_id = self.convert_false_to_none({
                "city": invoice.partner_id.city,
                "name": invoice.partner_id.name,
                "id": invoice.partner_id.id
            })
            fiscal_position_id = self.convert_false_to_none({
                "name": invoice.fiscal_position_id.name,
                "id": invoice.fiscal_position_id.id
            })
            invoicedata = self.convert_false_to_none({
                "id" : invoice.id,
                "amount_tax" : invoice.amount_tax,
                "date_due" : invoice.date_due,
                "amount_untaxed" : invoice.amount_untaxed,
                "name" : invoice.name,
                "user_id" : user_id,
                "discount_type_id" : invoice.discount_type_id.id,
                "number" : invoice.number,
                "origin" : invoice.origin,
                "account_id" : account_id,
                "residual" : invoice.residual if invoice.state in ['open'] else 0.0,
                "date_invoice" : invoice.date_invoice,
                "journal_id" : journal_id,
                "state" : invoice.state,
                "invoice_line_ids" : invoice_line_ids,
                "discount_value" : invoice.discount_value,
                "payment_term_id" : invoice.payment_term_id.id,
                "partner_id" : partner_id,
                "fiscal_position_id" : fiscal_position_id,
                "amount_total" : invoice.amount_total,
                "created_user": invoice.create_uid.code if invoice.create_uid.id else '',
                "updated_user": invoice.write_uid.code if invoice.write_uid.code else ''
            })
            log = self.env['cb.logs'].create({
                'name': 'log_send_oss',
                'model': model,
                'action': action,
                'request': json.dumps(invoicedata),
                'response': '',
                'object_id' : invoice.id,
                'output': '',
                'status': 'inprocess',
                'url': ''
            })
            data_oss = {
                "method": "POST" if action == 'create' else "PUT",
                "url": url,
                "model": model,
                "id": invoice_id,
                "log": log.id,
                "data": invoicedata
            }
            self.env['rabbit.queue.job'].publish('wholesale_inv_' + str(action), data_oss, model, invoice.id, action)
        return True

    def update_status_invoice(self, invoice_id = None, model=None, action=None):
        try:
            if invoice_id > 0:
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
                    invoice = self.env[model].browse(invoice_id)
                    requestparam = '?id=' + str(invoice.id) + '&status=' + str(invoice.state)
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
                else:
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
                'object_id' : invoice_id,
                'output': message,
                'status': status,
                'url': url
            })
            if status == 'error':
                # myJob = job(self.update_status_invoice)
                # myJob.set_failed(exc_info=message)
                return False
        return True
