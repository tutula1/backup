from odoo import api, fields, models
import logging
import pytz
import datetime
from datetime import date, datetime, time
import requests
import redis
import urllib
_logger = logging.getLogger(__name__)
from odoo.addons.queue_job.job import job, related_action
from odoo.addons.queue_job.exception import RetryableJobError

class Authentication(models.Model):
    _name = 'authentication.queue.job'
    name = fields.Char()
    AUTH_URL = '/auth/oauth/token'

    def get_token(self):
        #========================AUTH DATA============================================
        
        basic_auth = self.env['ir.config_parameter'].get_param('oss_basic_auth')
        username = self.env['ir.config_parameter'].get_param('oss_username')
        grant_type = self.env['ir.config_parameter'].get_param('oss_grant_type')
        password = self.env['ir.config_parameter'].get_param('oss_password')
        url = self.env['ir.config_parameter'].get_param('oss_wholesale_url_get_token')
        
        #========================END AUTH DATA============================================
        
        
        headers = {'Content-Type': 'application/json', 'Authorization': basic_auth}
        authdata = {
            'grant_type' : grant_type,
            'username' : username,
            'password': password
        }
        #========================Get token url============================================
        _logger.info(url + '?' + urllib.urlencode(authdata))
        r = requests.post(url + '?' + urllib.urlencode(authdata), json={}, headers=headers)
        _logger.info(r)
        response = r.json()
        return response

    def get_root_url(self):
        protocol = self.env['ir.config_parameter'].get_param('oss_wholesale_protocol')
        host = self.env['ir.config_parameter'].get_param('oss_wholesale_host')
        port = self.env['ir.config_parameter'].get_param('oss_wholesale_port')
        base_url = str(protocol) + str(host)
        if str(port) != '80':
            base_url = str(base_url) + ':' + str(port)
        return base_url

    def get_oss_url(self):
        protocol = self.env['ir.config_parameter'].get_param('oss_wholesale_protocol')
        host = self.env['ir.config_parameter'].get_param('oss_wholesale_host')
        port = self.env['ir.config_parameter'].get_param('oss_wholesale_port')
        path = self.env['ir.config_parameter'].get_param('oss_wholesale_path')
        base_url = str(protocol) + str(host)
        if str(port) != '80':
            base_url = str(base_url) + ':' + str(port)
        if path != '':
            base_url += str(path)
        return base_url

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
