# -*- coding: utf-8 -*-
from odoo import api, fields, models
from openerp import _, fields, api, models, sql_db
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

LOG_FORMAT = ('%(levelname) -10s %(asctime)s %(name) -30s %(funcName) '
              '-35s %(lineno) -5d: %(message)s')
LOGGER = logging.getLogger(__name__)


class wholesale_oss_respone_msg(models.Model):

	_name = 'wholesale.oss.respone.msg'

	name = fields.Char()

	EXCHANGE = 'message'

	EXCHANGE_TYPE = 'topic'

	QUEUE = 'wholesale_oss_respone_msg'

	ROUTING_KEY = 'wholesale_oss_respone_msg'

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

	def convert_emptp_to_none(self, myobject):
		newobject = {}
		for attr, value in myobject.items():
			if value == "":
				newobject[attr] = None
			else:
				newobject[attr] = value
		return newobject
	def on_message(self, unused_channel, basic_deliver, properties, body):
		new_cr = sql_db.db_connect(self.env.cr.dbname).cursor()
		uid, context = self.env.uid, self.env.context
		with api.Environment.manage():
			self.env = api.Environment(new_cr, uid, context)
			try:
				LOGGER.info("-------------------------------------------")
				LOGGER.info(body)
				jdata = json.loads(body)
				if jdata:
					_logger.info(jdata)
					output = ""
					status = "error"
					log_response = ""
					odoo = jdata['odoo']
					oss = jdata['oss']
					status = jdata['status']
					message = jdata['message']
					log_id = jdata['log']
					if log_id:
						log = self.env['cb.logs'].browse(int(log_id))
						LOGGER.info("-------------------------------------------")
						LOGGER.info(log)
						object_id = self.env[log.model].browse(int(log.object_id))
						if object_id:
							send_rabbit = object_id.send_rabbit + 1
							if log:
								if status == 1 or status == '1':

									object_id.with_context({'from_rest_api': True}).write({'send_rabbit': 0, 'external_id': oss, 'external_type': 'OSS'})
									status = 'success'
								else:
									if send_rabbit < 2:
										LOGGER.info("-------------------send_rabbit------------------------")
										LOGGER.info(send_rabbit)
										if log.model == 'sale.order':
											object_id.create_update_order(object_id.id, 'sale.order', log.action)
										if log.model == 'res.partner':
											object_id.create_update_partner(object_id.id, 'res.partner', log.action)
										if log.model == 'stock.picking':
											object_id.create_update_picking(object_id.id, 'stock.picking', log.action)
										if log.model == 'account.invoice':
											object_id.create_update_invoice(object_id.id, 'account.invoice', log.action)
									else:
										send_rabbit = 0
									object_id.with_context({'from_rest_api': True}).write({'send_rabbit': send_rabbit})
									status = 'error'
								LOGGER.info(status)
								LOGGER.info(message)
								log.write({'status': status, 'response': message})
								new_cr.commit()

				else:
					output = "Load data fail"
					status = "error"
					self.env['cb.logs'].create({
					'name': 'wholesale_oss_respone_msg',
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
					LOGGER.info('Received message # %s from %s: %s', basic_deliver.delivery_tag, properties.app_id, body)
			except Exception, e:
				_logger.info(e)
			finally:
				new_cr.close()
				_logger.info("___________END______________")
			self.acknowledge_message(basic_deliver.delivery_tag)

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