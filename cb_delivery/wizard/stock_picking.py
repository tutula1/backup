# -*- coding: utf-8 -*-

from openerp import models, fields, api
import logging
_logger = logging.getLogger(__name__)
import pytz
import datetime
from datetime import date, datetime, time

class export_data_override(models.AbstractModel):
    _inherit='stock.picking'
    def export_data(self, fields, data = False):
        dataindex = None
        for index, fieldlabel in enumerate(fields):
            if fieldlabel == 'stock_tranfer_date':
                dataindex = index         
        res = super(export_data_override, self).export_data(fields, data) 
        try:
            for index, val in enumerate(res['datas']):
                if dataindex:           
                    service_date = res['datas'][index][dataindex] 
                    sdate = service_date
                    if sdate:
                        sdate = str(sdate)
                        db_timezone = self.env.context.get('tz') or 'Asia/Ho_Chi_Minh'
                        dbtz = pytz.timezone(db_timezone)
                        utctz = pytz.timezone('UTC')
                        sdate_dt = datetime.strptime(sdate, "%Y-%m-%d %H:%M:%S")
                        utctz_dt = utctz.localize(sdate_dt, is_dst=None)
                        db_dt = utctz_dt.astimezone(dbtz)                         
                        sdate = db_dt.strftime('%m/%d/%Y %H:%M:%S')
                        res['datas'][index][dataindex] = sdate
        except Exception:
            pass    
        return res