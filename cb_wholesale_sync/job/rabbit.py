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
import pika
try:
    import simplejson as json
except ImportError:
    import json

class Rabbit(models.Model):
	_name = 'rabbit.queue.job'
	name = fields.Char()
	
	def wholesale_confirm(self):
		host = self.env['ir.config_parameter'].get_param('oss_rabbit_host')
		port = self.env['ir.config_parameter'].get_param('oss_rabbit_port')
		username = self.env['ir.config_parameter'].get_param('oss_rabbit_username')
		password = self.env['ir.config_parameter'].get_param('oss_rabbit_password')
		url = 'amqp://' + str(username) + ':' + str(password) + '@' + str(host) + ':' + str(port) + '/%2F'
		confirm = self.env['wholesale.oss.respone.msg']
		confirm.run(url)
		confirm.with_delay(59).stop()

	def wholesale_so(self):
		host = self.env['ir.config_parameter'].get_param('oss_rabbit_host')
		port = self.env['ir.config_parameter'].get_param('oss_rabbit_port')
		username = self.env['ir.config_parameter'].get_param('oss_rabbit_username')
		password = self.env['ir.config_parameter'].get_param('oss_rabbit_password')
		url = 'amqp://' + str(username) + ':' + str(password) + '@' + str(host) + ':' + str(port) + '/%2F'
		so = self.env['wholesale.save.so.oss']
		so.run(url)
		so.with_delay(59).stop()

	def write_log(self, log, status, response):
		log.write({'status': status, 'response': response})



	def publish(self, channel_name, data, model, object_id, action):
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
			channel.queue_declare(queue='wholesale_odoo_request_oss')
			channel.confirm_delivery()
			if channel.basic_publish(exchange='', routing_key='wholesale_odoo_request_oss', body=json.dumps(data)):
				output = "Success"
				status = "success"
			else:
				output = "ERROR: Message could not be confirmed"
				status = 'error'
			connection.close()
		except Exception, e:
			message = e
			output = "ERROR: " + str(message)
			status = 'error'
		finally:
			self.env['cb.logs'].create({
				'name': 'publish_wholesale_odoo_request_oss',
				'model': model,
				'action': action,
				'request': json.dumps(data),
				'response': '',
				'object_id' : object_id,
				'output': output,
				'status': status,
				'url': str(host) + ':' + str(port) if str(port) != '' else str(host)
			})

	def publish_oss(self, data, model, object_id, action):
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
	
	def callback_ACK_Queue(self, ch, method, properties, body):
		_logger.info(" [x] Received %r" % body)
		ch.basic_ack(delivery_tag=method.delivery_tag)
		jdata = json.loads(body)
		if jdata:
			_logger.info(jdata)
			output = ""
			status = "error"
			log_response = ""
			
		else:
			output = "Load data fail"
			status = "error"
			self.env['cb.logs'].create({
				'name': 'consume_with_rabbit',
				'model': 'consume',
				'action': '',
				'request': '',
				'response': '',
				'object_id' : '',
				'output': output,
				'status': status,
				'url': ''
			})

	def callback(self, ch, method, properties, body):
		_logger.info(" [x] Received %r" % body)
		ch.basic_ack(delivery_tag=method.delivery_tag)
		jdata = json.loads(body)
		if jdata:
			_logger.info(jdata)
			output = ""
			status = "error"
			log_response = ""
			##
		else:
			output = "Load data fail"
			status = "error"
			self.env['cb.logs'].create({
				'name': 'consume_with_rabbit',
				'model': 'consume',
				'action': '',
				'request': '',
				'response': '',
				'object_id' : '',
				'output': output,
				'status': status,
				'url': ''
			})


	def consume(self, channel_name):
		if channel_name != '':
			status = "error"
			output = ""
			host = ""
			port = ""
			_logger.info('__________________________'+ channel_name +'______________________')
			try:
				host = self.env['ir.config_parameter'].get_param('oss_rabbit_host')
				port = self.env['ir.config_parameter'].get_param('oss_rabbit_port')
				username = self.env['ir.config_parameter'].get_param('oss_rabbit_username')
				password = self.env['ir.config_parameter'].get_param('oss_rabbit_password')
				credentials = pika.PlainCredentials(str(username), str(password))
				parameters = pika.ConnectionParameters(str(host), int(port), '/', credentials)
				connection = pika.BlockingConnection(parameters)
				channel = connection.channel()
				channel.queue_declare(queue=channel_name)
				if channel_name == 'ACK_Queue':
					channel.basic_consume(self.callback_ACK_Queue, queue=channel_name)
				else:
					channel.basic_consume(self.callback, queue=channel_name)
				try:
					channel.start_consuming()
					output = "Success"
					status = "success"
				except Exception, e:
					message = e.message
					output = "ERROR: " + str(message)
					status = 'error'
					self.env['cb.logs'].create({
						'name': 'receive_with_rabbit',
						'model': channel_name,
						'action': '',
						'request': '',
						'response': '',
						'object_id' : '',
						'output': output,
						'status': status,
						'url': str(host) + ':' + str(port) if str(port) != '' else str(host)
					})
					channel.stop_consuming()
				connection.close()
			except Exception, e:
				message = e.message
				output = "ERROR: " + str(message)
				status = 'error'
				self.env['cb.logs'].create({
					'name': 'receive_with_rabbit',
					'model': channel_name,
					'action': '',
					'request': '',
					'response': '',
					'object_id' : '',
					'output': output,
					'status': status,
					'url': str(host) + ':' + str(port) if str(port) != '' else str(host)
				})
				
