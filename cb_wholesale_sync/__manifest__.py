# -*- coding: utf-8 -*-
{
    'name': "Wholesale sync order, contact, delivery, invoice with oss",

    'summary': """
        pip install pika
        Wholesale sync order, delivery, invoice with oss""",

    'description': """
        pip install pika
    """,
    'sequence': 1,
    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale', 'delivery', 'account','cb_custom_fields', 'cb_sync_with_oss', 'cb_sale', 'cb_delivery'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'data/ir_configparameter.xml',
        'views/sale_view.xml',
        'views/stock_picking_view.xml',
        'cron/cron.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}