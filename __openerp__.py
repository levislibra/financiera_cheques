# -*- coding: utf-8 -*-
{
    'name': "Financiera - Descuento de cheques",

    'summary': """
        Descuento de cheques para Financieras.
        """,

    'description': """
        Modulo para financieras que se dedican a Descuento de cheques
        Funcionalidades:
        * Crear Liquidacion a un cliente asociando multiples cheques.
        * Impresion de liquidacion.
        * Neto a cuenta corriente.
        * Pago de liquidacion en efectivo o cheques y generacion de recibo.
        * Manejo de cartera de cheques.
        * Gestion de cheques rechazados.
        * Carga de nota de debito del proveedor por cheque rechazado.
        * Generacion de nota de debito a cliente por cheque rechazado.
    """,

    'author': "LIBRASOFT",
    'website': "http://libra-soft.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Financiera',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'account_check', 'payment_cost',
                'fixed_term'],

    # always loaded
    'data': [
        'security/user_groups.xml',
        'security/ir.model.access.csv',
        'views/liquidacion.xml',
        'views/extends_res_company.xml',
        'views/reports.xml',
        'data/defaultdata.xml',
        'wizards/financiera_cheques_wizard_view.xml',
        'wizards/financiera_cheque_opciones_wizard_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],

    'css': [
        'static/src/css/liquidacion.css'
    ],
    'application': True,
}