# -*- coding: utf-8 -*-

from openerp import models, fields, api

class LiquidacionConfig(models.Model):
    _name = 'liquidacion.config'

    name = fields.Char('Nombre', defualt='Configuracion general', readonly=True, required=True)
    journal_compra_id = fields.Many2one('account.journal', 'Diario de compra')
    journal_venta_id = fields.Many2one('account.journal', 'Diario de venta')
    journal_cartera_id = fields.Many2one('account.journal', 'Diario de cheques')
    automatic_validate = fields.Boolean('Validacion automatica de facturas', default=True)
    dias_acreditacion_compra = fields.Integer('Dias de acreditacion en compra')
    tipo_dias_acreditacion_compra = fields.Selection([('habiles', 'Habiles'), ('continuos', 'Continuos')], default='habiles', string='Tipo de dias')
    vat_tax2_id = fields.Many2one('account.tax', 'Tasa de IVA Imp Deb y Cred.', domain="[('type_tax_use', '=', 'sale')]")
    fiscal_position_id = fields.Many2one('account.fiscal.position', 'Posicion Fiscal')
    company_id = fields.Many2one('res.company', 'Empresa', default=lambda self: self.env['res.company']._company_default_get('liquidacion'))
    # Mutuo
    mutuante_nombre = fields.Char('Razon social')
    mutuante_nombre_fantasia = fields.Char('Nombre de fantasia')
    mutuante_cuit = fields.Char('CUIT/DNI')
    mutuante_domicilio_calle = fields.Char('Domicilio calle')
    mutuante_domicilio_ciudad = fields.Char('Domicilio ciudad')
    mutuo_tribunales = fields.Char('Tribunales de')

