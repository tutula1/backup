from odoo import _, fields, api, models
import logging
_logger = logging.getLogger(__name__)

class cron(models.Model):

    _inherit = "ir.cron"

    @api.model
    def receive_rabbit(self):
    	_logger.info('_logger_')