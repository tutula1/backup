# -*- coding: utf-8 -*-
{
    'name': "Delivery info",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
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
    'depends': ['base', 'stock', 'sale', 'cb_partner', 'cb_custom_fields', 'purchase', 'delivery', 'bi_sale_purchase_invoice_discount'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/delivery_address_view.xml',
        'views/partner_view.xml',
        'views/stock_picking_view.xml',
        'views/stock_config_settings_view.xml',
        'views/sale_view.xml',
        'views/purchase_view.xml',
        'views/resource.xml',
        'views/check_state_stock_picking.xml'
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    'application': True,
}