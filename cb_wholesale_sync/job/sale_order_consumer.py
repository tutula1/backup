# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging
import pytz
import datetime
from datetime import date, datetime, time
import requests
import redis
import urllib
import time
_logger = logging.getLogger(__name__)
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.queue_job.exception import RetryableJobError
from threading import Thread
try:
    import simplejson as json
except ImportError:
    import json
from pika import adapters
import pika
from openerp import _, fields, api, models, sql_db

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)


class wholesale_save_so_oss(models.Model):

    _name = 'wholesale.save.so.oss'

    name = fields.Char()
    EXCHANGE = 'message'
    EXCHANGE_TYPE = 'topic'
    QUEUE = 'wholesale_oss_save_so'
    ROUTING_KEY = 'wholesale_oss_save_so'
    COMPANY_ID = 1
    _connection = None
    _channel = None
    _closing = False
    _consumer_tag = None
    _url = None

    def connect(self):
        
        LOGGER.info('Connecting to %s', self._url)
        return pika.SelectConnection(pika.URLParameters(self._url), self.on_connection_open,stop_ioloop_on_close=False)

    def on_connection_open(self, unused_connection):
        LOGGER.info('Connection opened')
        self.add_on_connection_close_callback()
        self.open_channel()

    def add_on_connection_close_callback(self):
        LOGGER.info('Adding connection close callback')
        self._connection.add_on_close_callback(self.on_connection_closed)

    def on_connection_closed(self, connection, reply_code, reply_text):
        self._channel = None
        if self._closing:
            self._connection.ioloop.stop()
        else:
            LOGGER.warning('Connection closed, reopening in 5 seconds: (%s) %s', reply_code, reply_text)
            self._connection.add_timeout(5, self.reconnect)

    def reconnect(self):
        self._connection.ioloop.stop()

        if not self._closing:

        # Create a new connection
            self._connection = self.connect()

        # There is now a new connection, needs a new ioloop to run
            self._connection.ioloop.start()

    def open_channel(self):
        LOGGER.info('Creating a new channel')
        self._connection.channel(on_open_callback=self.on_channel_open)

    def on_channel_open(self, channel):
        LOGGER.info('Channel opened')
        self._channel = channel
        self.add_on_channel_close_callback()
        self.setup_exchange(self.EXCHANGE)

    def add_on_channel_close_callback(self):
        LOGGER.info('Adding channel close callback')
        self._channel.add_on_close_callback(self.on_channel_closed)

    def on_channel_closed(self, channel, reply_code, reply_text):
        LOGGER.warning('Channel %i was closed: (%s) %s', channel, reply_code, reply_text)
        self._connection.close()

    def setup_exchange(self, exchange_name):
        LOGGER.info('Declaring exchange %s', exchange_name)
        self._channel.exchange_declare(self.on_exchange_declareok, exchange_name, self.EXCHANGE_TYPE)

    def on_exchange_declareok(self, unused_frame):
        LOGGER.info('Exchange declared')
        self.setup_queue(self.QUEUE)

    def setup_queue(self, queue_name):
        LOGGER.info('Declaring queue %s', queue_name)
        self._channel.queue_declare(self.on_queue_declareok, queue_name)

    def on_queue_declareok(self, method_frame):
        LOGGER.info('Binding %s to %s with %s', self.EXCHANGE, self.QUEUE, self.ROUTING_KEY)
        self._channel.queue_bind(self.on_bindok, self.QUEUE, self.EXCHANGE, self.ROUTING_KEY)

    def on_bindok(self, unused_frame):
        LOGGER.info('Queue bound')
        self.start_consuming()

    def start_consuming(self):
        LOGGER.info('Issuing consumer related RPC commands')
        self.add_on_cancel_callback()
        self._consumer_tag = self._channel.basic_consume(self.on_message, self.QUEUE)

    def add_on_cancel_callback(self):
        LOGGER.info('Adding consumer cancellation callback')
        self._channel.add_on_cancel_callback(self.on_consumer_cancelled)

    def on_consumer_cancelled(self, method_frame):
        LOGGER.info('Consumer was cancelled remotely, shutting down: %r', method_frame)
        if self._channel:
            self._channel.close()

    
    def getWarehouseId(self, code):
        id = 0
        warehouse = self.env['stock.warehouse'].search([('code', '=', code)], limit=1)
        if warehouse:
            id = warehouse.id
        return id

    def get_type_code(self, type_code):
        MKDL = self.env['cb.type.customer.category']
        try:
            KDL = MKDL.browse(int(type_code))
            if KDL:
                return {
                "type_code": KDL.id if KDL.id else False,
                "team_id": KDL.sales_team.id if KDL.sales_team.id else False,
                "sales_manager": KDL.team_leader.id if KDL.team_leader.id else False,
                "user_id": KDL.sales_person.id if KDL.sales_person.id else False,
                "head_barista_trainer": KDL.head_barista_trainer_kdl.id if KDL.head_barista_trainer_kdl.id else False,
                "barista_trainer": KDL.barista_trainer.id if KDL.barista_trainer.id else False
                }
        except:
            pass
        try:
            KDL = MKDL.browse(int(self.env['ir.config_parameter'].get_param('default_type_code')))
            if KDL:
                return {
                "type_code": KDL.id if KDL.id else False,
                "team_id": KDL.sales_team.id if KDL.sales_team.id else False,
                "sales_manager": KDL.team_leader.id if KDL.team_leader.id else False,
                "user_id": KDL.sales_person.id if KDL.sales_person.id else False,
                "head_barista_trainer": KDL.head_barista_trainer_kdl.id if KDL.head_barista_trainer_kdl.id else False,
                "barista_trainer": KDL.barista_trainer.id if KDL.barista_trainer.id else False
                }
        except:
            pass
        return {
            "type_code": False,
            "team_id": False,
            "sales_manager": False,
            "user_id": False,
            "head_barista_trainer": False,
            "barista_trainer": False
        }

    def convertTime(self, date):
        new_dateorder = convertTimestampToDate(date)
        fmt = "%Y-%m-%d %H:%M:%S"
        local = pytz.timezone("Etc/GMT-7")
        naive = datetime.strptime(new_dateorder, "%Y-%m-%d %H:%M:%S")
        local_dt = local.localize(naive, is_dst=None)
        utc_dt = local_dt.astimezone (pytz.utc)
        return utc_dt

    def convertTimestampToDate(self, date):
        floattime = date/1000
        return datetime.fromtimestamp(floattime).strftime('%Y-%m-%d %H:%M:%S')

    def convertDateTime(self, sdate, plus7 = True, is_datetime = True):
        if plus7:
            db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
            dbtz = pytz.timezone(db_timezone)
            utctz = pytz.timezone('UTC')
        else:
            db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
            dbtz = pytz.timezone('UTC')
            utctz = pytz.timezone(db_timezone)
        if sdate != None and sdate != '' and sdate != False and sdate != 'False':
            if is_datetime:
                sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
            else:
                sdate_dt = datetime.strptime(sdate, "%Y-%m-%d")
            utctz_dt = utctz.localize(sdate_dt, is_dst=None)
            db_dt = utctz_dt.astimezone(dbtz) 
            if is_datetime:
                sdate = db_dt.strftime('%Y/%m/%d %H:%M:%S')
            else:
                sdate = db_dt.strftime('%Y/%m/%d')
            return sdate
        else:
            return None


    def calc_promotion_line(self, order_line, warehouse_id):
        new_order_line = []
        check_product = True
        _logger.info(order_line)
        for line in order_line:
            if 'id' in line and line['id'] != None and 'delete' in line and line['delete'] == 1:
                myOrderLine = self.env['sale.order.line'].browse(line['id'])
                if myOrderLine:
                    myOrderLine.unlink()
            else:
                product = self.env['product.product'].browse(line['product_id'])
                if product:
                    line['product_id'] = product.id
                    line['name'] = product.name
                    line['warehouse'] = warehouse_id
                    line['product_uom'] = product.uom_id.id
                    del line['barcode']
                    if 'price_discount' in line:
                        line['discount'] = float(line['price_discount'])
                        line['discount_type'] = 'fixprice'
                        del line['price_discount']
                if 'id' in line and line['id'] != None:
                    new_order_line.append([1, line['id'], line])
                else:
                    new_order_line.append([0, False, line])
        _logger.info('=================LINE=====================')     
        _logger.info(new_order_line)   
        return new_order_line
    def create_so(self, jdata):
        try:
            _logger.info('=================partner=====================')
            partner_id = self.env['res.partner'].browse(int(jdata['customer_id']))
            _logger.info('=================search partner=====================')
            if partner_id:
                _logger.info('=================here partner=====================')
                jdata['partner_id'] = partner_id.id
                jdata['company_id'] = self.COMPANY_ID
                #get company info
                company = self.env['res.company'].browse(int(jdata['company_id']))
                if company.name != '':
                    _logger.info('=================here company=====================')
                    jdata['warehouse_id'] = self.getWarehouseId(jdata['warehouse_code'])
                    del jdata['warehouse_code']
                    if jdata['warehouse_id'] > 0:

                        if 'discount' in jdata:
                            discount_type_fixed = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_fixed_id')
                            jdata['discount_type_id'] = discount_type_fixed
                            jdata['discount_value'] = jdata['discount']
                            jdata['apply_discount'] = True
                            discount_account_obj = self.env['account.account'].search([('discount_account', '=', True), ('user_type_id.name','=','Expenses')], limit=1)
                            _logger.info('=================ACCOUNT DISCOUNT=====================')
                            _logger.info(discount_account_obj)
                            if discount_account_obj:
                                jdata['discount_account'] = discount_account_obj.id
                            del jdata['discount']
                        if partner_id.type_code:
                            type_code = partner_id.type_code
                        else:
                            type_code = self.env['ir.config_parameter'].get_param('default_type_code')
                        default_type_code = self.get_type_code(type_code)
                        jdata['team_id'] = default_type_code.get('team_id')
                        jdata['sales_manager'] = default_type_code.get('sales_manager')
                        if 'sale_person' in jdata and jdata['sale_person']['code'] != None:
                            jdata['user_id'] = jdata['sale_person']['code']
                            # del jdata['sale_person']
                        else:
                            jdata['user_id'] = default_type_code.get('user_id')
                        user_id = int(jdata['user_id'])
                        jdata['head_barista_trainer'] = default_type_code.get('head_barista_trainer')
                        jdata['barista_trainer'] = default_type_code.get('barista_trainer')


                        if jdata['sourcesale']:
                            source_sale = self.env['cb.source.sale'].search([('code', '=', jdata['sourcesale'])], limit=1)
                            if source_sale:
                                jdata['source_sale_id'] = source_sale.id
                            del jdata['sourcesale']

                        if user_id > 0:
                            jdata['user_id'] = user_id
                            jdata['order_line'] = self.calc_promotion_line(jdata['order_line_send'], jdata['warehouse_id'])
                            jdata['origin'] = jdata['order_channel']
                            jdata['partner_invoice_id'] = int(jdata['partner_invoice_id']) if int(jdata['partner_invoice_id']) > 0 else jdata['customer_id']
                            jdata['partner_shipping_id'] = int(jdata['partner_shipping_id']) if int(jdata['partner_shipping_id']) > 0 else jdata['customer_id']
                            jdata['partner_reciver_id'] = int(jdata['partner_reciver_id']) if int(jdata['partner_reciver_id']) > 0 else jdata['customer_id']

                            #Convert time
                            if "date_order" in jdata:
                                jdata['date_order'] = self.convertDateTime(jdata['date_order'], False)
                            if "validity_date" in jdata:
                                jdata['validity_date'] = self.convertDateTime(jdata['validity_date'], False, False)
                            if "stock_tranfer_date" in jdata:
                                jdata['stock_tranfer_date'] = self.convertDateTime(jdata['stock_tranfer_date'], False)

                            jdata['name'] = self.env['ir.sequence'].next_by_code('sale.order') or 'New'
                            jdata['state'] = 'draft'
                            if jdata['created_user']:
                                jdata['created_user_code'] = jdata['created_user']
                                u = self.env['res.users'].search([('code', '=', jdata['created_user'])], limit=1)
                                if u:
                                    jdata['created_user_id'] = u.id

                            _logger.info('=================ORDER DATA=====================')
                            _logger.info(jdata)

                            # source = jdata['source']
                            # del jdata['source']
                            # create_delivery = jdata['create_delivery']
                            # del jdata['create_delivery']
                            # register_payment = jdata['register_payment']
                            # del jdata['register_payment']
                            # order_channel = jdata['order_channel']
                            # del jdata['order_channel']

                            del jdata['status']
                            del jdata['order_line_send']
                            del jdata['order_line_delete']
                            del jdata['updated_time']
                            del jdata['referid']
                            order = self.env['sale.order'].with_context({'from_rest_api': 1}).create(jdata)
                            _logger.info(order)
                            # _logger.info(order.id)
                            # _logger.info(order.name)
                            order_id = 0
                            if order:
                                # self.cr.commit()
                                order_id = order.id
                                



                            _logger.info('=================ORDER ID=====================')
                            _logger.info(order_id)

                            if order_id > 0:
                                # order1 = self.env['sale.order'].browse(int(order_id))
                                # _logger.info('=================ORDER=====================')
                                # if order1:
                                #     _logger.info('=================ORDER1=====================')
                                #     _logger.info(order1)
                                #     _logger.info(order1.id)
                                #     _logger.info(order1.order_line)
                                # jdata['source'] = source
                                # jdata['create_delivery'] = create_delivery
                                # jdata['register_payment'] = register_payment
                                # jdata['order_channel'] = order_channel
                                # if 'create_delivery' in jdata and bool(jdata['create_delivery']) == True:
                                #     Model = self.env['sale.order']
                                #     myOrder = Model.browse(order_id)
                                #     myOrder.action_confirm()
                                #     # if jdata['order_channel'] in ('offline', ) :
                                #     for pick in myOrder.picking_ids:
                                #         if pick.state == 'waiting':
                                #             _logger.info('... confirm picking: %s' % pick.name)
                                #             pick.action_confirm()
                                #             if pick.state != 'assigned':
                                #                 _logger.info('... action_assign pick %s' % pick.name)
                                #                 pick.action_assign()

                                #             for pack in pick.pack_operation_ids:
                                #                 if pack.product_qty > 0:
                                #                     _logger.info('======================LOT=========================')
                                #                     _logger.info(pack.product_id.tracking)
                                #                     if pack.product_id.tracking in ['lot','serial']:
                                #                         ProductLotModel = self.env['stock.production.lot']
                                #                         # Get lot from product_id
                                #                         countqtyinlot = 0
                                #                         lotpush = []
                                #                         lots = ProductLotModel.search([('product_id', '=', pack.product_id.id)], order='product_qty desc')
                                #                         _logger.info('======================LOT=========================')
                                #                         _logger.info(lots)
                                #                         if lots:
                                #                             for lot in lots:
                                #                                 while countqtyinlot < pack.product_qty:
                                #                                     lotpush.append(lot.id)
                                #                                     countqtyinlot = countqtyinlot + lot.product_qty
                                #                         pack.write({
                                #                                 'qty_done': pack.product_qty,
                                #                                 'pack_lot_ids': [(6,0, lotpush)]
                                #                             })

                                #                     else:
                                #                         pack.write({'qty_done': pack.product_qty})
                                #                 # else:
                                #                 #     pack.unlink()
                                #             _logger.info('... do_transfer pick %s' % pick.name)
                                #             pick.do_transfer()
                                #             _logger.info('... force_assign: %s' % pickings_confirmed_list)
                                #         #state waiting confirmed and assigned
                                #         else:
                                #             if pick.state == 'comfirmed':
                                #                 _logger.info('... force_assign: %s' % pick.name)
                                #                 pick.force_assign()

                                #             for pack in pick.pack_operation_ids:
                                #                 if pack.product_qty > 0:
                                #                     _logger.info('======================LÒT=========================')
                                #                     _logger.info(pack.product_id.tracking)
                                #                     if pack.product_id.tracking in ['lot','serial']:
                                #                         ProductLotModel = self.env['stock.production.lot']
                                #                         # Get lot from product_id
                                #                         countqtyinlot = 0
                                #                         lotpush = []

                                #                         lots = ProductLotModel.search([('product_id', '=', pack.product_id.id)], order='product_qty desc')
                                #                         _logger.info('======================LỎT=========================')
                                #                         _logger.info(lots)
                                #                         _logger.info(pack.product_id.id)
                                #                         if lots:
                                #                             for lot in lots:
                                #                                 while countqtyinlot < pack.product_qty:
                                #                                     lotpush.append(lot.id)
                                #                                     countqtyinlot = countqtyinlot + lot.product_qty
                                #                         pack.write({
                                #                                 'qty_done': pack.product_qty,
                                #                                 'pack_lot_ids': [(6,0, lotpush)]
                                #                             })

                                #                     else:
                                #                         pack.write({'qty_done': pack.product_qty})
                                #             _logger.info('... do_transfer pick %s' % pick.name)
                                #             pick.do_transfer()
                                    
                                #         invoices = myOrder.action_invoice_create()
                                        
                                #         for invoice in invoices:
                                #             invoice_object = self.env['account.invoice'].browse(invoice)
                                #             if invoice_object:
                                #                 invoice_object.action_invoice_open()
                                #                 if 'payment_method_id' in jdata and jdata['payment_method_id'] > 0 and 'register_payment' in  jdata and jdata['register_payment'] == True:
                                #                     account_rsa = self.env['account.account'].search([('user_type_id', '=', self.env['ir.model.data'].xmlid_to_res_id('account.data_account_type_payable'))], limit=1)
                                #                     _logger.info(account_rsa.id)
                                #                     _logger.info(account_rsa.name)

                                #                     payment_method_id = OUT__sale_order__map__payment_method[str(jdata['payment_method_id'])]
                                #                     _logger.info('=========PAYMENT METHOD ID=======')
                                #                     _logger.info(payment_method_id)
                                #                     _logger.info('=========PAYMENT METHOD ID=======')
                                #                     bank_journal = self.env['account.journal'].browse(int(payment_method_id))
                                #                     invoice_object.pay_and_reconcile(bank_journal, invoice_object.amount_total, None, account_rsa)
                                #                     invoice_object.action_invoice_paid()


                                return {
                                    'status': 1,
                                    'message': order_id
                                }
                            else :
                                self.cr.rollback()
                                error_descrip = "Create order eror"
                                error = 'create_server_error'
                                return {
                                    'status': 0,
                                    'message': error_descrip
                                }
                        else:
                            self.cr.rollback()
                            error_descrip = "Server error"
                            error = 'server_error'
                            return {
                                    'status': 0,
                                    'message': error_descrip
                                }
                    else :
                        error_descrip = "Not found warehouse"
                        error = 'not_found_warehouse'
                        return {
                                    'status': 0,
                                    'message': error_descrip
                                }
                else:
                    error_descrip = "Not found company"
                    error = 'company_not_found'
                    return {
                                    'status': 0,
                                    'message': error_descrip
                                }
            else:
                error_descrip = "Not found customer"
                error = 'customer_not_found'
                return {
                                    'status': 0,
                                    'message': error_descrip
                                    }
        except Exception, e:
            _logger.info(e)
            error_descrip = e[0]
            error = 'internal_server_error'
            return {
                                'status': 0,
                                'message': error_descrip
                            }
                            
    def write_so(self, id, jdata):
        try:
            Model = self.env['sale.order']
            myOrder = Model.browse(int(id))
            if myOrder.id > 0:
                saleorderdata = {
                    "customer_id": myOrder.partner_id.id,
                    "warehouse_code": myOrder.warehouse_id.id,
                    "category_id" : myOrder.category_id.id,
                    "partner_invoice_id" : myOrder.partner_invoice_id.id,
                    "partner_shipping_id" : myOrder.partner_shipping_id.id,
                    "partner_reciver_id" : myOrder.partner_reciver_id.id,
                    # "source": myOrder.source,
                    "order_channel": myOrder.origin,
                    "state": myOrder.state,
                    "discount" : myOrder.discount_value,
                    "validity_date": myOrder.validity_date,
                    "date_order": myOrder.date_order,
                    "stock_tranfer_date": myOrder.stock_tranfer_date,
                    "template_id": myOrder.template_id.id,
                    "pricelist_id": myOrder.pricelist_id.id
                }
                tmpdata = jdata
                tmpdata = self.convert_emptp_to_none(tmpdata)
                jdata = dict(saleorderdata, **tmpdata)
                _logger.info(jdata)
                #select partner from customer

                partner_id = self.env['res.partner'].browse(int(jdata['customer_id']))
                _logger.info(partner_id)
                if partner_id:
                    jdata['partner_id'] = partner_id.id
                    jdata['company_id'] = self.COMPANY_ID
                    #get company info
                    company = self.env['res.company'].browse(int(jdata['company_id']))
                    if company.name != '':
                        jdata['warehouse_id'] = self.getWarehouseId(jdata['warehouse_code'])
                        del jdata['warehouse_code']
                        if jdata['warehouse_id'] > 0:

                            if 'discount' in jdata:
                                discount_type_fixed = self.env['ir.model.data'].xmlid_to_res_id('bi_sale_purchase_invoice_discount.discount_type_fixed_id')
                                jdata['discount_type_id'] = discount_type_fixed
                                jdata['discount_value'] = jdata['discount']
                                jdata['apply_discount'] = True
                                discount_account_obj = self.env['account.account'].search([('discount_account', '=', True), ('user_type_id.name','=','Expenses')], limit=1)
                                _logger.info('=================ACCOUNT DISCOUNT=====================')
                                _logger.info(discount_account_obj)
                                if discount_account_obj:
                                    jdata['discount_account'] = discount_account_obj.id
                                del jdata['discount']

                            if partner_id.type_code:
                                type_code = partner_id.type_code
                            else:
                                type_code = self.env['ir.config_parameter'].get_param('default_type_code')
                            default_type_code = self.get_type_code(type_code)
                            jdata['team_id'] = default_type_code.get('team_id')
                            jdata['sales_manager'] = default_type_code.get('sales_manager')
                            if 'sale_person' in jdata and jdata['sale_person']['code'] != None:
                                jdata['user_id'] = jdata['sale_person']['code']
                                del jdata['sale_person']
                            else:
                                jdata['user_id'] = default_type_code.get('user_id')
                            user_id = int(jdata['user_id'])
                            jdata['head_barista_trainer'] = default_type_code.get('head_barista_trainer')
                            jdata['barista_trainer'] = default_type_code.get('barista_trainer')

                            if jdata['sourcesale']:
                                source_sale = self.env['cb.source.sale'].search([('code', '=', jdata['sourcesale'])], limit=1)
                                if source_sale:
                                    jdata['source_sale_id'] = source_sale.id
                                del jdata['sourcesale']

                            if user_id > 0:
                                jdata['user_id'] = user_id
                                jdata['order_line'] = self.calc_promotion_line(jdata['order_line_send'], jdata['warehouse_id'])
                                # jdata['origin'] = jdata['order_channel']
                                jdata['partner_invoice_id'] = int(jdata['partner_invoice_id'])
                                jdata['partner_shipping_id'] = int(jdata['partner_invoice_id'])
                                jdata['partner_shipping_id'] = int(jdata['partner_reciver_id'])

                                #optional data

                                if "date_order" in jdata:
                                    jdata['date_order'] = self.convertDateTime(jdata['date_order'], False)
                                if "validity_date" in jdata:
                                    jdata['validity_date'] = self.convertDateTime(jdata['validity_date'], False, False)
                                if "stock_tranfer_date" in jdata:
                                    jdata['stock_tranfer_date'] = self.convertDateTime(jdata['stock_tranfer_date'], False)

                                if 'create_delivery' in jdata and bool(jdata['create_delivery']) == True:
                                    myOrder.action_confirm()
                                jdata['name'] = myOrder.name
                                del jdata['status']
                                del jdata['order_line_send']
                                del jdata['order_line_delete']
                                del jdata['updated_time']
                                del jdata['referid']
                                state = jdata.get('state') or None
                                if state not in ['pending_confirmation', 'confirmed_by_purchasing']:
                                    del jdata['state']

                                if jdata['updated_user']:
                                    jdata['updated_user_code'] = jdata['updated_user']
                                    u = self.env['res.users'].search([('code', '=', jdata['updated_user'])], limit=1)
                                    if u:
                                        jdata['updated_user_id'] = u.id

                                _logger.info('=================ORDER DATA=====================')
                                _logger.info(jdata)
                                order =  myOrder.with_context({'from_rest_api': 1}).write(jdata)
                                if order:
                                    if state == 'cancel':
                                        myOrder = Model.browse(int(id))
                                        myOrder.action_cancel()

                                    _logger.info('=================ORDER EDIT=====================')
                                    _logger.info(order)
                                    # _logger.info(order.id)
                                    # _logger.info(order.order_line)
                                    return {
                                        'status': 1,
                                        'message': id
                                    }
                                else :
                                    error_descrip = "Update order error"
                                    error = 'update_order_error'
                                    return {
                                'status': 0,
                                'message': error_descrip
                            }

                            else:
                                error_descrip = "Server error"
                                error = 'server_error'
                                return {
                                'status': 0,
                                'message': error_descrip
                            }
                        else :
                            error_descrip = "Not found warehouse"
                            error = 'not_found_warehouse'
                            return {
                                'status': 0,
                                'message': error_descrip
                            }
                    else:
                        error_descrip = "Not found company"
                        error = 'company_not_found'
                        return {
                                'status': 0,
                                'message': error_descrip
                            }
                else:
                    error_descrip = "Not found customer"
                    error = 'customer_not_found'
                    return {
                                'status': 0,
                                'message': error_descrip
                            }
            else:
                error_descrip = "Not found order"
                error = 'order_not_found'
                return {
                                'status': 0,
                                'message': error_descrip
                            }
        except Exception, e:
            _logger.info(e)
            error_descrip = e[0]
            error = 'internal_server_error'
            return {
                                'status': 0,
                                'message': error_descrip
                            }

    def convert_emptp_to_none(self, myobject):
        newobject = {}
        for attr, value in myobject.items():
            if value == "":
                newobject[attr] = None
            else:
                newobject[attr] = value
        return newobject

    def publish(self, data, model, object_id, action):
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            status = "error"
            output = ""
            host = ""
            port = ""
            try:
                host = self.env['ir.config_parameter'].get_param('oss_rabbit_host')
                port = self.env['ir.config_parameter'].get_param('oss_rabbit_port')
                username = self.env['ir.config_parameter'].get_param('oss_rabbit_username')
                password = self.env['ir.config_parameter'].get_param('oss_rabbit_password')
                credentials = pika.PlainCredentials(str(username), str(password))
                parameters = pika.ConnectionParameters(str(host), int(port), '/', credentials)
                connection = pika.BlockingConnection(parameters)
                channel = connection.channel()
                channel.queue_declare(queue='wholesale_odoo_respone_msg')
                channel.confirm_delivery()
                _logger.info(data)
                if channel.basic_publish(exchange='', routing_key='wholesale_odoo_respone_msg', body=json.dumps(data)):
                    output = "Success"
                    status = "success"
                else:
                    output = "ERROR: Message could not be confirmed"
                    status = 'error'
                connection.close()
            except Exception, e:
                message = e.message
                output = "ERROR: " + str(message)
                status = 'error'
            finally:
                self.env['cb.logs'].create({
                    'name': 'publish_wholesale_odoo_respone_msg',
                    'model': model,
                    'action': action,
                    'request': json.dumps(data),
                    'response': '',
                    'object_id' : object_id,
                    'output': output,
                    'status': status,
                    'url': str(host) + ':' + str(port) if str(port) != '' else str(host)
                })
                new_cr.commit()
                new_cr.close()

    def on_message(self, unused_channel, basic_deliver, properties, body):
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            try:
                jdata = self.convert_emptp_to_none(json.loads(body))
                if jdata:
                    _logger.info(jdata)
                    output = ""
                    status = "error"
                    log_response = ""
                    id = jdata['id']
                    method = jdata['method']
                    url = jdata['url']
                    model = jdata['model']
                    log = jdata['log']
                    data = jdata['data']
                    self.env['cb.logs'].create({
                        'name': 'wholesale_oss_data',
                        'model': model,
                        'action': method,
                        'request': json.dumps(data),
                        'response': '',
                        'object_id' : data['id'] or 0,
                        'output': '',
                        'status': 'success',
                        'url': ''
                    })
                    new_cr.commit()
                    # if data.has_key('order_line_send'):
                    #     data['order_line'] = data['order_line_send']
                    #     _logger.info(data)
                    # del data['order_line_send']
                    # del data['status']
                    # del data['order_line_delete']
                    # del data['updated_time']
                    # del data['referid']
                    r = None
                    _logger.info("=" * 20)
                    _logger.info(model)
                    _logger.info(data)
                    url = self.env['ir.config_parameter'].get_param('oss_odoo_url')
                    try:
                        if model == 'sale.order':
                            if method == 'POST':
                                so = self.env['sale.order'].search([('external_id', '=', id)], limit=1)
                                if so:
                                    status = 'error'
                                    new_cr.rollback()
                                    data = {
                                        'odoo': 0,
                                        'oss': id,
                                        'log': log,
                                        'status': -1,
                                        'message': 'Don hang da duoc tao'
                                    }
                                else:
                                    data['external_id'] = id
                                    r = self.create_so(data)
                                    _logger.info(r)
                                    if r:
                                        if r['status'] == 1:
                                            new_cr.commit()
                                            status = 'success'
                                            message = {'message': 'Success'}
                                            order = self.env['sale.order'].browse(int(r['message']))
                                            if order:
                                                order_line = []
                                                for line in order.order_line:
                                                    l = {
                                                        'id': line.id,
                                                        'product_id': line.product_id.id
                                                    }
                                                    order_line.append(l)
                                                message = {
                                                    'id': order.id,
                                                    'order_line': order_line
                                                }
                                            data = {
                                                'odoo': r['message'],
                                                'oss': id,
                                                'log': log,
                                                'status': 1,
                                                'message': json.dumps(message)
                                            }
                                        else:
                                            status = 'error'
                                            new_cr.rollback()
                                            data = {
                                                'odoo': 0,
                                                'oss': id,
                                                'log': log,
                                                'status': 0,
                                                'message': r['message']
                                            }
                            if method == 'PUT': 
                                r = self.write_so(data['id'], data)
                                _logger.info(r)
                                if r:
                                    if r['status'] == 1:
                                        new_cr.commit()
                                        status = 'success'
                                        message = {'message': 'Success'}
                                        order = self.env['sale.order'].browse(int(data['id']))
                                        if order:
                                            order_line = []
                                            for line in order.order_line:
                                                l = {
                                                    'id': line.id,
                                                    'product_id': line.product_id.id
                                                }
                                                order_line.append(l)
                                            message = {
                                                'id': order.id,
                                                'order_line': order_line
                                            }
                                        data = {
                                            'odoo': data['id'],
                                            'oss': id,
                                            'log': log,
                                            'status': 1,
                                            'message': json.dumps(message)
                                        }
                                    else:
                                        status = 'error'
                                        new_cr.rollback()
                                        data = {
                                            'odoo': data['id'],
                                            'oss': id,
                                            'log': log,
                                            'status': 0,
                                            'message': r['message']
                                        }

                    except Exception, e:
                        message = e.message
                        data = {
                            'odoo': 0,
                            'oss': id,
                            'log': log,
                            'status': 0,
                            'message': message
                        }           
                    self.publish(data, model, id, method) 
                else:
                    output = "Load data fail"
                    status = "error"
                    self.env['cb.logs'].create({
                        'name': 'wholesale_save_so_oss',
                        'model': 'consume',
                        'action': '',
                        'request': '',
                        'response': '',
                        'object_id' : '',
                        'output': output,
                        'status': status,
                        'url': ''
                    })
                    new_cr.commit()
                self.acknowledge_message(basic_deliver.delivery_tag)
            except Exception, e:
                _logger.info(e)
            finally:
                new_cr.close()
                _logger.info("___________END______________")

    def on_message1(self, unused_channel, basic_deliver, properties, body):
        new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
        uid, context = self.env.uid, self.env.context
        with api.Environment.manage():
            self.env = api.Environment(new_cr, uid, context)
            try:
                jdata = self.convert_emptp_to_none(json.loads(body))
                if jdata:
                    _logger.info(jdata)
                    output = ""
                    status = "error"
                    log_response = ""
                    id = jdata['id']
                    method = jdata['method']
                    url = jdata['url']
                    model = jdata['model']
                    log = jdata['log']
                    data = jdata['data']
                    _logger.info(data)
                    # if data.has_key('order_line_send'):
                    #     data['order_line'] = data['order_line_send']
                    #     _logger.info(data)
                    # del data['order_line_send']
                    # del data['status']
                    # del data['order_line_delete']
                    # del data['updated_time']
                    # del data['referid']
                    r = None
                    _logger.info("=" * 20)
                    _logger.info(model)
                    _logger.info(data)
                    url = self.env['ir.config_parameter'].get_param('oss_odoo_url')
                    try:
                        if model == 'sale.order':
                            if method == 'POST':
                                data['name'] = self.env['ir.sequence'].next_by_code('sale.order') or 'New'
                                data['state'] = 'draft'
                                r = requests.post(url + '/api/wholesale/sale.order', headers = {'Content-Type': 'text/html; charset=utf-8', 'AuthorizationOdoo': '12345679'}, data = json.dumps(data))
                                re = json.loads(r.text)
                                _logger.info("=" * 20)
                                _logger.info(re)
                                if re:
                                    if re.has_key('error_descrip') == False:
                                        new_cr.commit()
                                        status = 'success'
                                        data = {
                                            'odoo': r['message'],
                                            'oss': id,
                                            'log': log,
                                            'status': 1,
                                            'message': 'Success'
                                        }
                                    else:
                                        status = 'error'
                                        new_cr.rollback()
                                        data = {
                                            'odoo': 0,
                                            'oss': id,
                                            'log': log,
                                            'status': 0,
                                            'message': re['error_descrip']
                                        }
                            if method == 'PUT': 
                                r = requests.put(url + '/api/wholesale/sale.order.new/' + str(data['id']), headers = {'Content-Type': 'text/html; charset=utf-8', 'AuthorizationOdoo': '12345679'}, data = json.dumps(data))
                                re = json.loads(r.text)
                                _logger.info("=" * 20)
                                _logger.info(re)
                                if re:
                                    if re.has_key('error_descrip') == False:
                                        new_cr.commit()
                                        status = 'success'
                                        data = {
                                            'odoo': data['id'],
                                            'oss': id,
                                            'log': log,
                                            'status': 1,
                                            'message': 'Success'
                                        }
                                    else:
                                        status = 'error'
                                        new_cr.rollback()
                                        data = {
                                            'odoo': data['id'],
                                            'oss': id,
                                            'log': log,
                                            'status': 0,
                                            'message': re['error_descrip']
                                        }
                    except Exception, e:
                        message = e.message
                        data = {
                            'odoo': 0,
                            'oss': id,
                            'log': log,
                            'status': 0,
                            'message': message
                        }           
                    self.publish(data, model, id, method) 
                else:
                    output = "Load data fail"
                    status = "error"
                    self.env['cb.logs'].create({
                        'name': 'wholesale_save_so_oss',
                        'model': 'consume',
                        'action': '',
                        'request': '',
                        'response': '',
                        'object_id' : '',
                        'output': output,
                        'status': status,
                        'url': ''
                    })
                self.acknowledge_message(basic_deliver.delivery_tag)
            except Exception, e:
                _logger.info(e)
            finally:
                _logger.info("___________END______________")

    def acknowledge_message(self, delivery_tag):
        LOGGER.info('Acknowledging message %s', delivery_tag)
        self._channel.basic_ack(delivery_tag)

    def stop_consuming(self):
        if self._channel:
            LOGGER.info('Sending a Basic.Cancel RPC command to RabbitMQ')
            self._channel.basic_cancel(self.on_cancelok, self._consumer_tag)

    def on_cancelok(self, unused_frame):
        LOGGER.info('RabbitMQ acknowledged the cancellation of the consumer')
        self.close_channel()

    def close_channel(self):
        LOGGER.info('Closing the channel')
        self._channel.close()

    def run(self, url):
        self._url = url
        self._connection = self.connect()
        self._connection.ioloop.start()

    def stop(self):
        LOGGER.info('Stopping')
        self._closing = True
        self.stop_consuming()
        self._connection.ioloop.start()
        LOGGER.info('Stopped')

    def close_connection(self):
        LOGGER.info('Closing connection')
        self._connection.close()