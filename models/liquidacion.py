# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError
from openerp.exceptions import ValidationError
from openerp.tools.translate import _

from pprint import pprint
import logging
from openerp.osv import orm
_logger = logging.getLogger(__name__)

class firmante(models.Model):
	_name = 'firmante'
	_description = 'Firmante del cheque'
	name = fields.Char("Nombre", size=30, required=True)
	cuit = fields.Char("Cuit", size=20, required=True)

class check_scanner(models.Model):
    _name = 'check.scanner'
    _description = 'Escaner del numero de 29 digitos y su procesamiento'

    name = fields.Char('Numero')
    bank_codigo = fields.Char('ID Banco')
    bank_suc = fields.Char('Nro de sucursal')
    bank_cp = fields.Char('Codigo postal')
    bank_nro = fields.Char('Nro de cheque')
    bank_cuenta_corriente = fields.Char('Cuenta Corriente')
    bank_imagen_frente = fields.Binary('Imagen frontal')
    bank_imagen_posterior = fields.Binary('Imagen posterior')

    @api.onchange('name')
    def set_values(self):
        if self.name != None and len(self.name) == 29:
            self.bank_codigo = self.name[0:3]
            self.bank_suc = self.name[3:6]
            self.bank_cp = self.name[6:10]
            self.bank_nro = self.name[10:18]
            self.bank_cuenta_corriente = self.name[18:29]
        else:
            raise ValidationError("El escaner no tiene 29 caracteres.")

class AccountPayment(models.Model):
    # This OpenERP object inherits from cheques.de.terceros
    # to add a new float field
    _inherit = 'account.payment'
    _name = 'account.payment'
    _description = 'Opciones extras de cheques para calculo de financiera'

    check_liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion id')
    check_firmante_id = fields.Many2one('firmante', 'Firmante')
    check_fecha_acreditacion = fields.Date('Acreditacion')
    check_dias = fields.Integer(string='Dias', compute='_check_dias')
    check_tasa_fija = fields.Float('Impuesto')
    check_monto_fijo = fields.Float(string='Monto', compute='_check_monto_fijo')
    check_tasa_mensual = fields.Float('Interes')
    check_monto_mensual = fields.Float(string='Monto', compute='_check_monto_mensual')
    check_vat_tax_id = fields.Many2one('account.tax', 'Tasa de IVA', readonly=True)
    check_monto_iva = fields.Float('IVA', compute='_check_monto_iva')
    check_monto_costo = fields.Float("Costo", compute='_compute_costo')
    check_monto_neto = fields.Float(string='Neto', compute='_check_monto_neto')
    check_scanner_id = fields.Many2one('check.scanner', 'Escaner')

    # check_number_char = fields.Char("Numero")

    @api.one
    @api.depends('amount', 'check_monto_fijo', 'check_monto_mensual', 'check_monto_iva')
    def _compute_costo(self):
        self.check_monto_costo = round(self.check_monto_fijo + self.check_monto_mensual + self.check_monto_iva, 2)

    # @api.one
    # @api.onchange('check_number_char')
    # def _change_check_number_char(self):
    #     try:
    #         self.check_number = int(self.check_number_char)
    #     except Exception as e:
    #         raise UserError("Error al introducir el numero del cheque.")


    # check_amount_char = fields.Char('Importe')

    # @api.one
    # @api.onchange('check_amount_char')
    # def _check_check_amount_char(self):
    #     try:
    #         self.amount = float(self.check_amount_char)
    #     except Exception as e:
    #         self.amount = float(self.check_amount_char)
    #         raise UserError("Error al introducir el importe del cheque.")


    @api.model
    def create(self, values):
        if values.has_key('check_liquidacion_id') and values['check_liquidacion_id'] != False:
            liquidacion_id = self.env['liquidacion'].browse(values['check_liquidacion_id'])
            values['payment_group_id'] = liquidacion_id.payment_group_id.id

#        if values.has_key('amount') and values['amount'] == False:
#            values['amount'] = 1

        rec = super(AccountPayment, self).create(values)
        return rec

    @api.model
    def default_get(self, fields):
        rec = super(AccountPayment, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        active_id = context.get('active_id')
        action = context.get('action')

        if active_model == 'liquidacion':
            fecha = context.get('fecha')
            partner_id = context.get('partner_id')
            journal_id = context.get('journal_id')
            receiptbook_id = context.get('receiptbook_id')
            payment_method_id = context.get('payment_method_id')
            currency_id = context.get('currency_id')
            vat_tax_id = context.get('vat_tax_id')

            cr = self.env.cr
            uid = self.env.uid
            payment_method_obj = self.pool.get('account.payment.method')
            payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'manual'), ('payment_type', '=', 'inbound')])[0]
            liquidacion_id = self.env[active_model].browse(active_id)
            partner_id = self.env['res.partner'].browse(partner_id)

            if action == 'cheque_nuevo':
                rec.update({
                    #'name': "Liquidacion #" + str(liquidacion_id.id).zfill(6) + " - cheque",
                    #'communication': "Liquidacion #" + str(liquidacion_id.id).zfill(6) + " - cheque",
                    'payment_type': 'inbound',
                    'payment_type_copy': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': partner_id.id,
                    'journal_id': journal_id,
                    'payment_method_code': 'manual',
                    'check_type': 'third_check',
                    'receiptbook_id': receiptbook_id,
                    'payment_date': fecha,
                    'currency_id': currency_id,                    
                    'payment_method_id': payment_method_id,
                    'check_vat_tax_id': vat_tax_id,
                    'check_tasa_fija': partner_id.tasa_fija,
                    'check_tasa_mensual': partner_id.tasa_mensual,
                })
            elif action == 'realizar_pago':
                liquidacion_id = self.env[active_model].browse(active_id)
                amount = liquidacion_id.get_neto()
                fecha = liquidacion_id.fecha
                rec['payment_type'] = 'outbound'
                rec['partner_type'] = 'customer'
                rec['partner_id'] = partner_id.id
                rec['amount'] = amount
                rec['payment_date'] = fecha
        return rec

    @api.onchange('check_scanner_id')
    def set_scanner(self):
        self.check_number = int(self.check_scanner_id.bank_nro)


    @api.one
    @api.depends('check_liquidacion_id.fecha', 'check_fecha_acreditacion')
    def _check_dias(self):
        if len(self.check_liquidacion_id) > 0 and self.check_liquidacion_id.fecha and self.check_fecha_acreditacion:
            formato_fecha = "%Y-%m-%d"
            fecha_inicial = datetime.strptime(str(self.check_liquidacion_id.fecha), "%Y-%m-%d")
            fecha_final = datetime.strptime(str(self.check_fecha_acreditacion), "%Y-%m-%d")
            diferencia = fecha_final - fecha_inicial
            if diferencia.days > 0:
                self.check_dias = diferencia.days
            else:
                self.check_dias = 0

    @api.one
    @api.depends('check_monto_mensual', 'check_vat_tax_id')
    def _check_monto_iva(self):
        if self.check_vat_tax_id != None:
    	   self.check_monto_iva = self.check_monto_mensual * (self.check_vat_tax_id.amount / 100)

    @api.one
    @api.depends('amount', 'check_tasa_fija')
    def _check_monto_fijo(self):
    	self.check_monto_fijo = round(self.amount * (self.check_tasa_fija / 100), 2)

    @api.one
    @api.depends('amount', 'check_tasa_mensual', 'check_dias')
    def _check_monto_mensual(self):
    	self.check_monto_mensual = round(self.check_dias * ((self.check_tasa_mensual / 30) / 100) * self.amount,2)


    @api.one
    @api.depends('amount', 'check_monto_fijo', 'check_monto_mensual', 'check_monto_iva')
    def _check_monto_neto(self):
    	self.check_monto_neto = round(self.amount - self.check_monto_fijo - self.check_monto_mensual - self.check_monto_iva, 2)

    @api.onchange('check_payment_date')
    def _check_fecha_acreditacion(self):
        if self.check_payment_date:
            configuracion_id = self.env['liquidacion.config'].browse(1)
            dias_acreditacion_compra = configuracion_id.dias_acreditacion_compra
            tipo_dias_acreditacion_compra = configuracion_id.tipo_dias_acreditacion_compra
            fecha_inicial = datetime.strptime(self.check_payment_date, "%Y-%m-%d")
            if tipo_dias_acreditacion_compra == 'continuos':
                fecha_relativa = relativedelta.relativedelta(days=dias_acreditacion_compra)
                self.check_fecha_acreditacion = fecha_inicial + fecha_relativa
            elif tipo_dias_acreditacion_compra == 'habiles':
                if dias_acreditacion_compra > 0:
                    cr = self.env.cr
                    uid = self.env.uid
                    dias_no_habiles = 0
                    i = 1
                    while dias_acreditacion_compra != 0:
                        fecha_relativa = relativedelta.relativedelta(days=i)
                        check_fecha = fecha_inicial + fecha_relativa
                        es_sabado = check_fecha.weekday() == 5
                        es_domingo = check_fecha.weekday() == 6
                        es_feriado = len(self.pool.get('feriados.feriados.dia').search(cr, uid, [('date', '=', check_fecha)])) > 0
                        i += 1
                        if es_sabado or es_domingo or es_feriado:
                            pass
                        else:
                            dias_acreditacion_compra -= 1
                    self.check_fecha_acreditacion = check_fecha
                else:
                    self.check_fecha_acreditacion = fecha_inicial


# Clase Obsoleta - Usamos Wizards
class LiquidacionPagar(models.Model):
    _name = 'liquidacion.pago'

    payment_date = fields.Date('Fecha de pago', required=True)
    payment_journal_id = fields.Many2one('account.journal', 'Metodo de pago', domain="[('type', 'in', ('bank', 'cash'))]")
    payment_amount = fields.Float('Monto')
    payment_communication = fields.Char('Descripcion')
    liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion')

    # @api.model
    # def default_get(self, fields):
    #     rec = super(LiquidacionPagar, self).default_get(fields)
    #     context = dict(self._context or {})
    #     active_model = context.get('active_model')
    #     active_ids = context.get('active_ids')
    #     active_id = context.get('active_id')

    #     cr = self.env.cr
    #     uid = self.env.uid
    #     liquidacion_obj = self.pool.get('liquidacion')
    #     liquidacion_id = liquidacion_obj.browse(cr, uid, active_id, context=context)
    #     rec.update({
    #         'payment_date': liquidacion_id.fecha,
    #         'payment_amount': abs(liquidacion_id.saldo),
    #         'liquidacion_id': active_id,
    #         'payment_communication': "Pago liquidacion " + str(liquidacion_id.id).zfill(5),
    #     })
    #     return rec

    # @api.one
    # def confirmar_pagar_liquidacion(self):
    #     currency_id = self.env.user.company_id.currency_id.id
    #     cr = self.env.cr
    #     uid = self.env.uid

    #     #Pago al cliente
    #     payment_method_obj = self.pool.get('account.payment.method')
    #     payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'manual'), ('payment_type', '=', 'outbound')])[0]
    #     ap_values = {
    #         'payment_type': 'outbound',
    #         'partner_type': 'customer',
    #         'partner_id': self.liquidacion_id.partner_id.id,
    #         'amount': self.payment_amount,
    #         'payment_date': self.payment_date,
    #         'journal_id': self.payment_journal_id.id,
    #         'payment_method_code': 'manual',
    #         'currency_id': currency_id,
    #         'payment_method_id': payment_method_id,
    #         'cummunication': self.payment_communication,
    #         'description_financiera': "Liquidacion #" + str(self.liquidacion_id.id).zfill(8) + " - Pago al cliente",
    #     }
    #     payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
    #     payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]
    #     apg_values = {
    #         'payment_date': self.payment_date,
    #         'company_id': 1,
    #         'partner_id': self.liquidacion_id.partner_id.id,
    #         'currency_id': currency_id,
    #         'payment_ids': [(0,0,ap_values)],
    #         'receiptbook_id': payment_group_receiptbook_id,
    #         'partner_type': 'customer',
    #         'account_internal_type': 'payable',
    #         #'debt_move_line_ids': self.liquidacion_id._debt_not_reconcilie()[0],
    #         'communication': self.payment_communication,
    #     }
    #     new_payment_group_id = self.env['account.payment.group'].create(apg_values)
    #     new_payment_group_id.post()
    #     self.liquidacion_id.payment_group_ids = [new_payment_group_id.id]

class Liquidacion(models.Model):
    _name = 'liquidacion'

    _order = 'id desc'
    id = fields.Integer('Nro Liquidacion')
    fecha = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
    active = fields.Boolean('Activa', default=True)
    partner_id = fields.Many2one('res.partner', 'Cliente', required=True)
    journal_id = fields.Many2one('account.journal', 'Diario de cheques', domain="[('type', 'in', ('bank', 'cash')), ('inbound_payment_method_ids.code', 'in', ['received_third_check'])]")
    journal_invoice_id = fields.Many2one('account.journal', 'Diario de factura', domain="[('use_documents', '=', False), ('type', '=', 'sale')]")
    journal_invoice_use_doc_id = fields.Many2one('account.journal', 'Diario de factura', domain="[('use_documents', '=', True), ('type', '=', 'sale')]")
    journal_invoice_id_venta = fields.Many2one('account.journal', 'Diario de factura', domain="[('type', '=', 'purchase')]")
    analytic_id = fields.Many2one('account.analytic.account', 'Cuenta analítica')
    move_id = fields.Many2one('account.move', 'Asiento', readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Factura', readonly=True)
    payment_ids = fields.One2many('account.payment', 'check_liquidacion_id', 'Cheques', ondelete='cascade')
    state = fields.Selection([('cotizacion', 'Cotizacion'), ('confirmada', 'Confirmada'), ('facturada', 'Facturada'), ('cancelada', 'Cancelada')], default='cotizacion', string='Estado', readonly=True, track_visibility='onchange')
    receiptbook_id = fields.Many2one('account.payment.receiptbook', "ReceiptBook", domain="[('partner_type','=', 'customer')]")
    payment_method_id = fields.Many2one('account.payment.method', "Payment Method", readonly=True)
    currency_id = fields.Many2one('res.currency', "Moneda", readonly=True)
    factura_electronica = fields.Boolean('¿Factura electronica?', default=False)
    vat_tax_id = fields.Many2one('account.tax', 'Tasa de IVA', domain="[('type_tax_use', '=', 'sale')]", readonly=True)
    payment_group_id = fields.Many2one('account.payment.group', 'Contenedor de cheques', readonly=True)
    # Campo obsoleto - Reemplazado por widget
    pago_ids = fields.One2many('liquidacion.pago', 'liquidacion_id', 'Pagos')
    payment_group_ids = fields.One2many('account.payment.group', 'liquidacion_id','Pagos al cliente', readonly=True)
    total_pagos = fields.Float('Total pagos')
    # Campo obsoleto
    debt_move_line_ids = fields.One2many('account.move.line', 'liquidacion_id', 'Deuda a pagar', compute='_update_debt', default=None)
    saldo = fields.Float('Saldo', compute='_compute_saldo')

    tasa_fija = fields.Float('Tasa fija', compute='compute_tasa_fija')
    tasa_mensual = fields.Float('Tasa mensual', compute='compute_tasa_mensual')
    saldo_cta_cte = fields.Float('Saldo Cuenta Corriente', compute='_compute_saldo_cta_cte')
    cheques_en_cartera = fields.Float('Cheques en cartera', compute='_compute_cheques_en_cartera')

    type_operation = fields.Selection([('compra', 'Compra'), ('venta', 'Venta')], default='compra', string='Tipo de operacion', readonly=True)
    cheques_venta_ids = fields.One2many('account.check', 'check_liquidacion_id_venta', string='Cheques')
    #cheques_venta_ids_copy = fields.One2many(related='cheques_venta_ids', string='Cheques')
    account_id = fields.Many2one('account.account', 'Cuenta')
    property_account_receivable_id = fields.Integer('Default debit id', compute='_compute_receivable')
    property_account_payable_id = fields.Integer('Default Credit id', compute='_compute_payable')
    partner_type = fields.Selection([('customer', 'Cliente'), ('supplier', 'Proveedor')], string='Tipo de partner', compute='_compute_partner_type', readonly=True)

    @api.model
    def create(self, values):
        cr = self.env.cr
        uid = self.env.uid
        context = dict(self._context or {})
        type_operation = context.get('default_type_operation')
        currency_id = self.env.user.company_id.currency_id.id

        if type_operation == 'compra':
            payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
            payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]
            apg_values = {
                'payment_date': values['fecha'],
                'company_id': 1,
                'partner_id': values['partner_id'],
                'currency_id': currency_id,
                'receiptbook_id': payment_group_receiptbook_id,
                #'partner_type': 'customer',
                'account_internal_type': 'receivable',
            }
            new_payment_group_id = self.env['account.payment.group'].create(apg_values)
            values['payment_group_id'] = new_payment_group_id.id

        rec = super(Liquidacion, self).create(values)
        return rec

    @api.one
    @api.onchange('partner_id')
    def compute_tasa_fija(self):
        if self.type_operation == 'compra':
            self.tasa_fija = self.partner_id.tasa_fija
        elif self.type_operation == 'venta':
            self.tasa_fija = self.partner_id.tasa_fija_venta

    @api.one
    @api.onchange('partner_id')
    def compute_tasa_mensual(self):
        if self.type_operation == 'compra':
            self.tasa_mensual = self.partner_id.tasa_mensual
        elif self.type_operation == 'venta':
            self.tasa_mensual = self.partner_id.tasa_mensual_venta

    @api.model
    def default_get(self, fields):
        rec = super(Liquidacion, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        active_id = context.get('active_id')
        type_operation = context.get('default_type_operation')

        configuracion_id = self.env['liquidacion.config'].browse(1)
        journal_cartera_id = None
        journal_compra_id = None
        journal_venta_id = None
        if len(configuracion_id.journal_cartera_id) > 0:
            journal_cartera_id = configuracion_id.journal_cartera_id.id
        if len(configuracion_id.journal_compra_id) > 0:
            journal_compra_id = configuracion_id.journal_compra_id.id
        if len(configuracion_id.journal_venta_id) > 0:
            journal_venta_id = configuracion_id.journal_venta_id.id
        cr = self.env.cr
        uid = self.env.uid
        currency_id = self.env.user.company_id.currency_id.id
        if type_operation == 'compra':
            payment_method_obj = self.pool.get('account.payment.method')
            payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'received_third_check')])[0]

            payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
            payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]

            payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
            payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]
            
            rec.update({
                'receiptbook_id': payment_group_receiptbook_id,
                'payment_method_id': payment_method_id,
                'currency_id': currency_id,
                'journal_id': journal_cartera_id,
                'journal_invoice_id': journal_compra_id,
                'journal_invoice_use_doc_id': None,
            })
        elif type_operation == 'venta':

            rec.update({
                'currency_id': currency_id,
                'journal_id': journal_cartera_id,
                'journal_invoice_id_venta': journal_venta_id,
            })
        return rec

    @api.one
    @api.onchange('partner_id')
    def _compute_receivable(self):
        self.property_account_receivable_id = self.partner_id.property_account_receivable_id.id

    @api.one
    @api.onchange('partner_id')
    def _compute_payable(self):
        self.property_account_payable_id = self.partner_id.property_account_payable_id.id

    @api.one
    def _compute_partner_type(self):
        if len(self.account_id) > 0:
            if self.account_id.id == self.property_account_receivable_id:
                self.partner_type = 'customer'
            elif self.account_id.id == self.property_account_payable_id:
                self.partner_type = 'supplier'

    # Obsoleto
    @api.one
    def _update_debt(self):
        for move_line_id in self.invoice_id.move_id.line_ids:
            if move_line_id.debit > 0:
                self.debt_move_line_ids = [move_line_id.id]

        for payment_id in self.payment_group_id.payment_ids:
            for move_line_id in payment_id.move_line_ids:
                if move_line_id.credit > 0:
                    self.debt_move_line_ids = [move_line_id.id]

    # Obsoleto
    @api.one
    def _debt_not_reconcilie(self):
        ret = []
        for ail_id in self.debt_move_line_ids:
            if not ail_id.reconciled:
                ret.append(ail_id.id)
        return ret


    def get_bruto(self):
        bruto = 0
        if self.type_operation == 'compra':
            for payment in self.payment_ids:
                bruto += payment.amount
        elif self.type_operation == 'venta':
            for cheque_id in self.cheques_venta_ids:
                bruto += cheque_id.amount
        return bruto

    def get_gasto(self):
        gasto = 0
        if self.type_operation == 'compra':
            for payment in self.payment_ids:
                gasto += payment.check_monto_fijo
        elif self.type_operation == 'venta':
            for cheque_id in self.cheques_venta_ids:
                gasto += cheque_id.check_monto_fijo_venta
        return gasto

    def get_interes(self):
        interes = 0
        if self.type_operation == 'compra':
            for payment in self.payment_ids:
                interes += payment.check_monto_mensual
        elif self.type_operation == 'venta':
            for cheque_id in self.cheques_venta_ids:
                interes += cheque_id.check_monto_mensual_venta
        return interes

    def get_iva(self):
        iva = 0
        for payment in self.payment_ids:
            iva += payment.check_monto_iva
        return iva

    def get_neto(self):
        neto = 0
        if self.type_operation == 'compra':
            for payment in self.payment_ids:
                neto += payment.check_monto_neto
        elif self.type_operation == 'venta':
            for cheque_id in self.cheques_venta_ids:
                neto += cheque_id.check_monto_neto_venta
        return neto

    def get_cobrado(self):
        neto = 0
        for payment_group_id in self.payment_group_ids:
            for payment_id in payment_group_id.payment_ids:
                neto += abs(payment_id.amount)
        return neto

    @api.one
    def _compute_saldo(self):
        saldo = 0
        self.saldo = self.get_neto()-self.get_cobrado()

    @api.onchange('journal_id')
    def _set_journal_id(self):
        for payment in self.payment_ids:
            payment.journal_id = self.journal_id
            #payment.payment_method_id = self.payment_method_id.id
            #payment.payment_method_code = 'received_third_check'

    @api.onchange('vat_tax_id')
    def _set_vat_tax_id(self):
        for payment in self.payment_ids:
            payment.check_vat_tax_id = self.vat_tax_id.id


    @api.one
    @api.onchange('account_id')
    def _onchange_account(self):
        #self._compute_saldo_cta_cte()
        self._compute_partner_type()


    @api.one
    @api.depends('account_id')
    def _compute_saldo_cta_cte(self):
        cr = self.env.cr
        uid = self.env.uid
        line_obj = self.pool.get('account.move.line')
        if len(self.account_id) > 0:
            line_ids = line_obj.search(cr, uid, [
                ('partner_id', '=', self.partner_id.id),
                ('account_id', '=', self.account_id.id)
                ])
            for _id in line_ids:
                line_id = line_obj.browse(cr, uid, _id)
                self.saldo_cta_cte += line_id.amount_residual
        else:
            self.saldo_cta_cte = 0

    @api.one
    @api.onchange('partner_id')
    def _onchange_partner(self):
        if self.type_operation == 'compra':
            self.account_id = self.property_account_receivable_id
        elif self.type_operation == 'venta':
            self.account_id = self.property_account_payable_id        
        self._compute_cheques_en_cartera()

    @api.one
    def _compute_cheques_en_cartera(self):
        cr = self.env.cr
        uid = self.env.uid
        line_obj = self.pool.get('account.check')
        line_ids = line_obj.search(cr, uid, [
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'holding')
            ])
        for _id in line_ids:
            line_id = line_obj.browse(cr, uid, _id)
            self.cheques_en_cartera += line_id.amount

    @api.one
    def borrador(self):
        self.state = 'cotizacion'

    @api.one
    def confirmar(self):
        if self.type_operation == 'compra':
            if len(self.payment_ids) == 0:
                raise UserError("No puede confirmar una compra de cheques vacia.")
            else:
                for payment_id in self.payment_ids:
                    payment_id.payment_date = self.fecha
                    if len(payment_id.check_firmante_id) == 0:
                        raise UserError("Faltan datos de cheques (Firmante).")
                    if payment_id.check_payment_date == False:
                        raise UserError("Faltan datos de cheques (Fecha de pago).")
                    if payment_id.check_fecha_acreditacion == False:
                        raise UserError("Faltan datos de cheques (Fecha de acreditacion).")
                self.state = 'confirmada'
                self.confirmar_payments()
                self.facturar()
        elif self.type_operation == 'venta':
            if len(self.cheques_venta_ids) == 0:
                raise UserError("No puede confirmar una venta de cheques vacia.")
            else:
                self.state = 'confirmada'
                self.confirmar_venta()
                self.facturar_venta()
                return True

    @api.multi
    def ver_factura(self):
        self.ensure_one()
        action = self.env.ref('account.action_invoice_tree1')
        result = action.read()[0]
        form_view = self.env.ref('account.invoice_form')
        result['views'] = [(form_view.id, 'form')]
        result['res_id'] = self.invoice_id.id
        return result

    def confirmar_payments(self):
        i = 1
        for payment in self.payment_ids:
            payment.check_name = str(payment.check_number) + " " + payment.check_firmante_id.name
            payment.check_owner_name = payment.check_firmante_id.name
            payment.check_owner_vat = payment.check_firmante_id.cuit
            payment.check_type = 'third_check'
            payment.partner_type = self.partner_type
            if i == len(self.payment_ids):
                payment.description_financiera = "Liquidacion #" + str(self.id).zfill(8) + " - Cheque Nro " + str(payment.check_number)
            elif payment.check_number > 0:
                payment.description_financiera = 'Liquidacion #' + str(self.id).zfill(8) + " - Cheque Nro " + str(payment.check_number)
            i += 1
        self.payment_group_id.partner_type = self.partner_type
        self.payment_group_id.post()

    def confirmar_venta(self):
        #Cheques al proveedor
        cr = self.env.cr
        uid = self.env.uid
        payment_method_obj = self.pool.get('account.payment.method')
        payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'delivered_third_check'), ('payment_type', '=', 'outbound')])[0]
        ap_values = {
            'payment_type_copy': 'outbound',
            'payment_type': 'outbound',
            'partner_type': self.partner_type,
            'partner_id': self.partner_id.id,
            'payment_date': self.fecha,
            'journal_id': self.journal_id.id,
            'payment_method_code': 'delivered_third_check',
            #'check_ids': self.cheques_venta_ids,
            'readonly_amount': self.get_bruto(),
            'amount': self.get_bruto(),
            'currency_id': self.currency_id.id,
            'payment_method_id': payment_method_id,
            'description_financiera': "Venta #" + str(self.id).zfill(8) + " - cheques",
        }

        payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
        payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'supplier')])[0]
        apg_values = {
            'payment_date': self.fecha,
            'company_id': 1,
            'partner_id': self.partner_id.id,
            'currency_id': self.currency_id.id,
            'receiptbook_id': payment_group_receiptbook_id,
            'payment_ids': [(0,0,ap_values)],
            'partner_type': 'supplier',
            'account_internal_type': 'payable',
        }
        new_payment_group_id = self.env['account.payment.group'].create(apg_values)
        self.payment_group_id = new_payment_group_id.id
        self.payment_group_id.payment_ids[0].check_ids = self.cheques_venta_ids
        self.payment_group_id.post()

    @api.one
    def cancelar(self):
        if self.invoice_id.state == 'paid':
            raise UserError("La factura esta pagada. Debera cancelar manualmente la liquidacion. Buscar y devolver los cheques al cliente (desde Cheques de terceros) y Crear Factura Rectificativa (desde Otra Informacion -> Factura).")
        self.state = 'cancelada'
        for payment_id in self.payment_ids:
            check = payment_id.check_id
            if check.state != 'holding':
                raise UserError("Para cancelar la liquidacion, todos los cheques deben estar En Mano.")
            else:
                check.customer_return()
                for op_id in check.operation_ids:
                    if op_id.operation == 'returned':
                        op_id.origin.signal_workflow('invoice_open')
        if len(self.invoice_id) > 0:
            if self.invoice_id.state == 'open':
                self.invoice_id.signal_workflow('invoice_cancel')
            elif self.invoice_id.state == 'paid':
                # Crear factura rectificativa
                pass
        return True

    @api.one
    def actualizar_por_defecto(self):
        for check_id in self.cheques_venta_ids:
            check_id.check_fecha_acreditacion_venta = check_id.payment_date
            check_id.check_tasa_fija_venta = self.partner_id.tasa_fija_venta
            check_id.check_tasa_mensual_venta = self.partner_id.tasa_mensual_venta


    # Metodo Obsoleto - Reemplazado por wizard
    def pagar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        return True

    @api.multi
    def wizard_payment(self):
        # configuracion_id = self.env['liquidacion.config'].browse(1)
        # default_journal_id = None
        # if len(configuracion_id) > 0:
        #     default_journal_id = configuracion_id.journal_id
        params = {
            'liquidacion_id': self.id,
            'amount': self.saldo,
        }
        if self.type_operation == 'compra':
            name = "Compra de cheques - Pago"
        else:
            name = "Venta de cheques - Cobro"
        view_id = self.env['liquidacion.payment.wizard']
        new = view_id.create(params)
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'liquidacion.payment.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id'    : new.id,
            'view_id': self.env.ref('financiera_cheques.liquidacion_payment_wizard', False).id,
            'target': 'new',
        }

    @api.one
    def pagar_liquidacion(self, date, amount, journal_id):
        currency_id = self.env.user.company_id.currency_id.id
        cr = self.env.cr
        uid = self.env.uid

        #Pago al cliente
        payment_method_obj = self.pool.get('account.payment.method')
        payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'manual'), ('payment_type', '=', 'outbound')])[0]
        ap_values = {
            'payment_type': 'outbound',
            'partner_type': self.partner_type,
            'partner_id': self.partner_id.id,
            'amount': amount,
            'payment_date': date,
            'journal_id': journal_id.id,
            'payment_method_code': 'manual',
            'currency_id': currency_id,
            'payment_method_id': payment_method_id,
            'description_financiera': "Liquidacion #" + str(self.id).zfill(8) + " - Pago al cliente",
        }
        payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
        payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', self.partner_type)])[0]
        apg_values = {
            'payment_date': date,
            'company_id': 1,
            'partner_id': self.partner_id.id,
            'currency_id': currency_id,
            'payment_ids': [(0,0,ap_values)],
            'receiptbook_id': payment_group_receiptbook_id,
            'partner_type': self.partner_type,
            'account_internal_type': 'payable',
        }
        new_payment_group_id = self.env['account.payment.group'].create(apg_values)
        new_payment_group_id.post()
        self.payment_group_ids = [new_payment_group_id.id]


    @api.one
    def cobrar_liquidacion(self, date, amount, journal_id):
        currency_id = self.env.user.company_id.currency_id.id
        cr = self.env.cr
        uid = self.env.uid

        #Cobro al cliente
        payment_method_obj = self.pool.get('account.payment.method')
        payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'manual'), ('payment_type', '=', 'inbound')])[0]
        ap_values = {
            'payment_type': 'inbound',
            'partner_type': self.partner_type,
            'partner_id': self.partner_id.id,
            'amount': amount,
            'payment_date': date,
            'journal_id': journal_id.id,
            'payment_method_code': 'manual',
            'currency_id': currency_id,
            'payment_method_id': payment_method_id,
            'description_financiera': "Venta #" + str(self.id).zfill(8) + " - Cobro al cliente",
        }
        payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
        payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', self.partner_type)])[0]
        apg_values = {
            'payment_date': date,
            'company_id': 1,
            'partner_id': self.partner_id.id,
            'currency_id': currency_id,
            'payment_ids': [(0,0,ap_values)],
            'receiptbook_id': payment_group_receiptbook_id,
            'partner_type': self.partner_type,
            'account_internal_type': 'receivable',
        }
        new_payment_group_id = self.env['account.payment.group'].create(apg_values)
        new_payment_group_id.post()
        self.payment_group_ids = [new_payment_group_id.id]


    @api.one
    def facturar(self):
        journal_id = None
        vat_tax_id = None
        invoice_line_tax_ids = None

        if self.factura_electronica:
            journal_id = self.journal_invoice_use_doc_id
            vat_tax_id = self.vat_tax_id.id
            invoice_line_tax_ids = [(6, 0, [vat_tax_id])]
        else:
            journal_id = self.journal_invoice_id
        if journal_id != False and journal_id != None:
            # Create invoice line
            ail = {
                'name': "Interes por servicios financieros",
                'quantity':1,
                'price_unit': self.get_interes(),
                'vat_tax_id': vat_tax_id,
                'invoice_line_tax_ids': invoice_line_tax_ids,
                'account_id': journal_id.default_debit_account_id.id,
            }

            # Create invoice line
            ail2 = {
                'name': "Impuesto a los debitos y creditos bancarios por cuenta del cliente.",
                'quantity':1,
                'price_unit': self.get_gasto(),
                #'vat_tax_id': vat_tax_id,
                #'invoice_line_tax_ids': [(6, 0, [vat_tax_id])],
                'account_id': journal_id.default_debit_account_id.id,
            }
            account_invoice_customer0 = {
                # 'name': "Liquidacion #" + str(self.id).zfill(8) + " - Intereses",
                'description_financiera': "Liquidacion #" + str(self.id).zfill(8) + " - Intereses",
                'account_id': self.account_id.id,
                'partner_id': self.partner_id.id,
                'journal_id': journal_id.id,
                'currency_id': self.currency_id.id,
                'company_id': 1,
                'date': self.fecha,
                'invoice_line_ids': [(0, 0, ail), (0, 0, ail2)],
            }
            new_invoice_id = self.env['account.invoice'].create(account_invoice_customer0)
            #hacer configuracion de validacion automatica
            new_invoice_id.signal_workflow('invoice_open')
            self.invoice_id = new_invoice_id.id

            self.state = 'facturada'
        else:
            raise ValidationError("Falta Diario de ventas.")
        return True

    @api.one
    def facturar_venta(self):
        journal_id = None
        vat_tax_id = None
        invoice_line_tax_ids = None

        journal_id = self.journal_invoice_id_venta
        if journal_id != False and journal_id != None:
            # Create invoice line
            ail = {
                'name': "Interes por venta de cheques varios",
                'quantity':1,
                'price_unit': self.get_interes(),
                'vat_tax_id': vat_tax_id,
                'invoice_line_tax_ids': invoice_line_tax_ids,
                'account_id': journal_id.default_debit_account_id.id,
            }

            # Create invoice line
            ail2 = {
                'name': "Impuesto a los debitos y creditos bancarios a pagar por venta de cheques.",
                'quantity':1,
                'price_unit': self.get_gasto(),
                #'vat_tax_id': vat_tax_id,
                #'invoice_line_tax_ids': [(6, 0, [vat_tax_id])],
                'account_id': journal_id.default_debit_account_id.id,
            }
            account_invoice_customer0 = {
                # 'name': "Liquidacion #" + str(self.id).zfill(8) + " - Intereses",
                'description_financiera': "Venta #" + str(self.id).zfill(8) + " - Intereses e impuestos",
                'account_id': self.account_id.id,
                'partner_id': self.partner_id.id,
                'journal_id': journal_id.id,
                'currency_id': self.currency_id.id,
                'company_id': 1,
                'date': self.fecha,
                'invoice_line_ids': [(0, 0, ail), (0, 0, ail2)],
                'type': 'in_invoice',
            }
            new_invoice_id = self.env['account.invoice'].create(account_invoice_customer0)
            #hacer configuracion de validacion automatica
            new_invoice_id.signal_workflow('invoice_open')
            self.invoice_id = new_invoice_id.id
            self.state = 'facturada'
        else:
            raise ValidationError("Falta Diario de Proveedores")
        return True

    # Metodo Obsoleto - Reemplazado por wizard
    # @api.multi
    # def pagar_liquidacion(self):
    #     if self.saldo <= 0:
    #         raise UserError("El saldo de la liquidacion debe ser mayor a cero.")
    #     else:
    #         cr = self.env.cr
    #         uid = self.env.uid
    #         view_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'financiera_cheques', 'pagar_liquidacion_view')
    #         view_id = view_ref and view_ref[1] or False,

    #         return {
    #             'type': 'ir.actions.act_window',
    #             'name': 'Registrar Pago Liquidacion',
    #             'view_mode': 'form',
    #             'view_type': 'form',
    #             'view_id': view_id,
    #             'res_model': 'liquidacion.pago',
    #             'nodestroy': True,
    #             'target': 'new',
    #             #'search_view_id': sale_order_tree,
    #         }

class LiquidacionConfig(models.Model):
    _name = 'liquidacion.config'

    name = fields.Char('Nombre', defualt='Configuracion general', readonly=True, required=True)
    journal_compra_id = fields.Many2one('account.journal', 'Diario de compra')
    journal_venta_id = fields.Many2one('account.journal', 'Diario de venta')
    journal_cartera_id = fields.Many2one('account.journal', 'Diario de cheques')
    automatic_validate = fields.Boolean('Validacion automatica de facturas', default=True)
    dias_acreditacion_compra = fields.Integer('Dias de acreditacion en compra')
    tipo_dias_acreditacion_compra = fields.Selection([('habiles', 'Habiles'), ('continuos', 'Continuos')], default='habiles', string='Tipo de dias')



class ExtendsPaymentGroup(models.Model):
    _name = 'account.payment.group'
    _inherit = 'account.payment.group'

    liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion')

    @api.one
    def post(self):
        rec = super(ExtendsPaymentGroup, self).post()
        for payment_id in self.payment_ids:
            payment_id.confirm_cost()

class ExtendsAccountMoveLine(models.Model):
    _name = 'account.move.line'
    _inherit = 'account.move.line'

    liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion')

    # @api.model
    # def create(self, values):

    #     rec = super(ExtendsAccountMoveLine, self).create(values)
    #     return rec

class ExtendsPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    tasa_fija = fields.Float('Tasa de impuestos')
    tasa_mensual = fields.Float('Tasa mensual de descuento')
    tasa_fija_venta = fields.Float('Tasa de impuestos de venta')
    tasa_mensual_venta = fields.Float('Tasa mensual de descuento en venta')

class ExtendsAccountAccount(models.Model):
    _name = 'account.account'
    _inherit = 'account.account'

    move_line_ids = fields.One2many('account.move.line', 'account_id', 'Movimientos')

class ExtendsAccountDebtLine(models.Model):
    _name = 'account.debt.line'
    _inherit = 'account.debt.line'

    _order = 'date desc, id desc'


class ExtendsAccountCheck(models.Model):
    _name = 'account.check'
    _inherit = 'account.check'

    operacion_recibir = fields.Many2one('account.check.operation', 'Op Recibir', compute='_compute_datos', store=True)
    cliente_id = fields.Many2one('res.partner', 'Cliente', related='operacion_recibir.partner_id')
    fecha_ingreso = fields.Date('Fecha ingreso', related='operacion_recibir.date')
    fecha_salida = fields.Date('Fecha salida', compute='_compute_fecha_salida', store=True)
    operaciones_count = fields.Integer("Cantidad de operaciones", compute='_compute_operaciones_count')
    company_currency_id = fields.Many2one('res.currency', string="Moneda de la Compania", compute='_compute_currency_id')

    # Campos para el calculo de venta de cheques
    check_liquidacion_id_venta = fields.Many2one('liquidacion', 'Liquidacion venta')
    check_fecha_acreditacion_venta = fields.Date('Acreditacion')
    check_dias_venta = fields.Integer(string='Dias', compute='_check_dias_venta')
    check_tasa_fija_venta = fields.Float('Impuesto')
    check_monto_fijo_venta = fields.Monetary(string='Monto', compute='_check_monto_fijo_venta')
    check_tasa_mensual_venta = fields.Float('Interes')
    check_monto_mensual_venta = fields.Monetary(string='Monto', compute='_check_monto_mensual_venta')
    check_monto_costo_venta = fields.Monetary("Costo", compute='_compute_costo_venta')
    check_monto_neto_venta = fields.Monetary(string='Neto', compute='_check_monto_neto_venta')

    @api.one
    @api.onchange('amount', 'check_monto_fijo_venta', 'check_monto_mensual_venta')
    def _compute_costo_venta(self):
        self.check_monto_costo_venta = round(self.check_monto_fijo_venta + self.check_monto_mensual_venta, 2)

    @api.one
    @api.onchange('check_liquidacion_id_venta.fecha', 'check_fecha_acreditacion_venta')
    def _check_dias_venta(self):
        if len(self.check_liquidacion_id_venta) > 0 and self.check_liquidacion_id_venta.fecha and self.check_fecha_acreditacion_venta:
            fecha_inicial = datetime.strptime(str(self.check_liquidacion_id_venta.fecha), "%Y-%m-%d")
            fecha_final = datetime.strptime(str(self.check_fecha_acreditacion_venta), "%Y-%m-%d")
            diferencia = fecha_final - fecha_inicial
            if diferencia.days > 0:
                self.check_dias_venta = diferencia.days
            else:
                self.check_dias_venta = 0

    @api.one
    @api.onchange('amount', 'check_tasa_fija_venta')
    def _check_monto_fijo_venta(self):
        self.check_monto_fijo_venta = round(self.amount * (self.check_tasa_fija_venta / 100), 2)

    @api.one
    @api.onchange('amount', 'check_tasa_mensual_venta', 'check_dias_venta')
    def _check_monto_mensual_venta(self):
        self.check_monto_mensual_venta = round(self.check_dias_venta * ((self.check_tasa_mensual_venta / 30) / 100) * self.amount,2)


    @api.one
    @api.onchange('amount', 'check_monto_fijo_venta', 'check_monto_mensual_venta')
    def _check_monto_neto_venta(self):
        self.check_monto_neto_venta = round(self.amount - self.check_monto_fijo_venta - self.check_monto_mensual_venta, 2)
    
    @api.one
    def _compute_currency_id(self):
        currency_id = self.env.user.company_id.currency_id.id

    @api.one
    @api.depends('operation_ids')
    def _compute_datos(self):
        for op_id in self.operation_ids:
            if op_id.operation == 'holding':
                self.operacion_recibir = op_id

    @api.one
    @api.depends('operation_ids')
    def _compute_fecha_salida(self):
        if len(self.operation_ids) > 1:
            self.fecha_salida = self.operation_ids[0].date

    @api.one
    def _compute_operaciones_count(self):
        self.operaciones_count = len(self.operation_ids)

    # Override function
    def _check_unique(self):
        return True

    @api.multi
    def wizard_eliminar_seleccion(self):
        print "Wizards eliminar_seleccion"
        print self
        params = {
            'cheque_id': self.id,
            'liquidacion_id': self.check_liquidacion_id_venta.id,
        }
        view_id = self.env['liquidacion.cheque.wizard']
        new = view_id.create(params)
        return {
            'type': 'ir.actions.act_window',
            'name': "Eliminar cheque seleccionado?",
            'res_model': 'liquidacion.cheque.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id'    : new.id,
            'view_id': self.env.ref('financiera_cheques.liquidacion_cheque_wizard', False).id,
            'target': 'new',
        }

    @api.one
    def eliminar_seleccion(self):
        self.check_liquidacion_id_venta = None

