# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta

from pprint import pprint
import logging
from openerp.osv import orm
_logger = logging.getLogger(__name__)

class firmante(models.Model):
	_name = 'firmante'
	_description = 'Firmante del cheque'
	name = fields.Char("Nombre", size=30, required=True)
	cuit = fields.Char("Cuit", size=20, required=True)

class AccountCheck(models.Model):
    # This OpenERP object inherits from cheques.de.terceros
    # to add a new float field
    _inherit = 'account.check'
    _name = 'account.check'
    _description = 'Opciones extras de cheques para calculo del descuento'

    liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion id')
    firmante_id = fields.Many2one('firmante', 'Firmante')

    fecha_acreditacion = fields.Date('Acreditacion')
    dias = fields.Integer(string='Dias', compute='_dias')
    tasa_fija = fields.Float('% Fija')
    monto_fijo = fields.Float(string='Gasto', compute='_monto_fijo')
    tasa_mensual = fields.Float('% Mensual')
    monto_mensual = fields.Float(string='Interes', compute='_monto_mensual')
    vat_tax_id = fields.Many2one('account.tax', '% IVA')
    monto_iva = fields.Float('IVA', compute='_monto_iva')
    monto_neto = fields.Float(string='Neto', compute='_monto_neto')

    @api.one
    @api.depends('liquidacion_id.fecha', 'fecha_acreditacion')
    def _dias(self):
        fecha_inicial_str = False
        fecha_final_str = False
        _logger.error("_calcular_descuento_dias")
        if self.liquidacion_id.fecha != False:
           fecha_inicial_str = str(self.liquidacion_id.fecha)
        if self.fecha_acreditacion != False:
           fecha_final_str = str(self.fecha_acreditacion)
        if fecha_inicial_str != False and fecha_final_str != False:
            formato_fecha = "%Y-%m-%d"
            fecha_inicial = datetime.strptime(fecha_inicial_str, formato_fecha)
            fecha_final = datetime.strptime(fecha_final_str, formato_fecha)
            diferencia = fecha_final - fecha_inicial
            ultimos_dias = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            i = 0
            fines_de_mes = []
            while fecha_inicial < fecha_final:
                ano_actual = fecha_inicial.year
                mes_actual = fecha_inicial.month
                dia_actual_fin_de_mes = ultimos_dias[mes_actual-1]
                fecha_fin_de_mes_str = str(ano_actual)+"-"+str(mes_actual)+"-"+str(dia_actual_fin_de_mes)
                fecha_fin_de_mes = datetime.strptime(fecha_fin_de_mes_str, formato_fecha)
                if fecha_fin_de_mes >= fecha_inicial and fecha_fin_de_mes <= fecha_final:
                    fines_de_mes.append(fecha_fin_de_mes)

                if mes_actual == 12:
                    mes_proximo = 1
                    ano_proximo = ano_actual + 1
                else:
                    mes_proximo = mes_actual + 1
                    ano_proximo = ano_actual
                dia_proximo = 15
                fecha_inicial_str = str(ano_proximo)+"-"+str(mes_proximo)+"-"+str(dia_proximo)
                fecha_inicial = datetime.strptime(fecha_inicial_str, formato_fecha)
                i = i + 1
            if diferencia.days > 0:
                self.dias = diferencia.days
            else:
                self.dias = 0
            print "DIAS: "
            print self.dias


    @api.one
    @api.depends('monto_mensual', 'vat_tax_id')
    def _monto_iva(self):
        if self.vat_tax_id != None:
    	   self.monto_iva = self.monto_mensual * (self.vat_tax_id.amount / 100)

    @api.one
    @api.depends('amount', 'tasa_fija')
    def _monto_fijo(self):
    	self.monto_fijo = self.amount * (self.tasa_fija / 100)

    @api.one
    @api.depends('amount', 'tasa_mensual', 'dias')
    def _monto_mensual(self):
    	self.monto_mensual = self.dias * ((self.tasa_mensual / 30) / 100) * self.amount

    @api.one
    @api.depends('amount', 'monto_fijo', 'monto_mensual', 'monto_iva')
    def _monto_neto(self):
    	self.monto_neto = self.amount - self.monto_fijo - self.monto_mensual - self.monto_iva

    @api.onchange('firmante_id')
    def _set_defaults(self):
    	print('names')
    	self.owner_name = self.firmante_id.name
        print self.firmante_id
    	self.owner_vat = self.firmante_id.cuit
    	if self.owner_name != False:
    		self.name = "Ch nro " + str(self.number) + " " + self.owner_name
        if self.liquidacion_id.journal_id != False:
        	self.journal_id = self.liquidacion_id.journal_id

    @api.onchange('number')
    def _set_name_number(self):
        print self.owner_name
        if self.owner_name != False:
            self.name = "Cheque nro " + str(self.number) + " " + self.owner_name

    @api.onchange('payment_date')
    def _fecha_acreditacion(self):
        print("payment_date change")
        self.fecha_acreditacion = self.payment_date

class Liquidacion(models.Model):
    _name = 'liquidacion'

    id = fields.Integer('Nro Liquidacion')
    fecha = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
    active = fields.Boolean('Activa', default=True)
    partner_id = fields.Many2one('res.partner', 'Cliente', required=True)
    journal_id = fields.Many2one('account.journal', 'Diario', required=True, domain="[('type', 'in', ('bank', 'cash'))]")
    analytic_id = fields.Many2one('account.analytic.account', 'Cuenta analítica')
    move_id = fields.Many2one('account.move', 'Asiento', readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Factura', readonly=True)
    cheque_ids = fields.One2many('account.check', 'liquidacion_id', 'Cheques', ondelete='cascade')
    state = fields.Selection([('cotizacion', 'Cotizacion'), ('confirmada', 'Confirmada'), ('pagado', 'Pagado'), ('cancelada', 'Cancelada')], default='cotizacion', string='Status', readonly=True, track_visibility='onchange')
    receiptbook_id = fields.Many2one('account.payment.receiptbook', "ReceiptBook")
    payment_method_id = fields.Many2one('account.payment.method', "Payment Method")
    currency_id = fields.Many2one('res.currency', "Moneda")

    def get_bruto(self):
        bruto = 0
        for cheque in self.cheque_ids:
            bruto += cheque.amount
        return bruto

    def get_gasto(self):
        gasto = 0
        for cheque in self.cheque_ids:
            gasto += cheque.monto_fijo
        return gasto

    def get_interes(self):
        interes = 0
        for cheque in self.cheque_ids:
            interes += cheque.monto_mensual
        return interes

    def get_iva(self):
        iva = 0
        for cheque in self.cheque_ids:
            iva += cheque.monto_iva
        return iva

    def get_neto(self):
        neto = 0
        for cheque in self.cheque_ids:
            neto += cheque.monto_neto
        return neto

    @api.onchange('journal_id')
    def _set_journal_id(self):
        for cheque in self.cheque_ids:
            cheque.journal_id = self.journal_id
            print("cheque Nro %r", cheque.number)
            print("set journal")
    
    @api.one
    def confirmar(self):
        _logger.error("CONFIRMAR2")
        self.state = 'confirmada'
        self.confirmar_cheques()

        return True

    def confirmar_cheques(self):
        #._add_operation('holding', payment, partner=payment.partner_id, date=payment.payment_date)
        datenow = datetime.now()
        for cheque in self.cheque_ids:
            #Generamos el Pago que se realiza con el cheque creado
            #display_name = self.receiptbook_id.document_type_id.doc_code_prefix + " " + self.receiptbook_id.prefix + 
            val_payment = {
                #'display_name': display_name,
                'payment_type': 'inbound',
                'partner_type': 'customer',                
                'partner_id': self.partner_id.id,
                'journal_id': self.journal_id.id,
                'payment_method_id': self.payment_method_id.id,
                'payment_method_code': 'received_third_check',
                'amount': cheque.amount,
                'receiptbook_id': self.receiptbook_id.id,
                'payment_date': datenow,
                'communication': 'Liquidacion Nro ' + str(self.id),
                'currency_id': self.currency_id.id,
                'check_ids': [(4, cheque.id, False)],
                'check_bank_id': cheque.bank_id.id,
                'check_name': cheque.name,
                'check_number': cheque.number,
                'check_number_readonly': cheque.number,
                'check_owner_name': cheque.owner_name,
                'check_owner_vat': cheque.owner_vat,
                'check_payment_date': cheque.payment_date,
                'check_type': cheque.type,
            }
            new_payment_id = self.env['account.payment'].create(val_payment)
            #new_payment_id.state = 'posted'
            cheque.number = 77777733
            new_payment_id.post()
            print "New payment"
            print new_payment_id

            new_payment_id.check_id = cheque
            print "check payment 22"


            val = {
                'check_id': cheque.id,
                'date': datenow,
                'operation': 'holding',
                'partner_id': self.partner_id.id,
                'notes': "Liquidacion " + str(self.id),
            }
            #new_operation_id = self.env['account.check.operation'].create(val)
            cheque.type = 'third_check'
            print "asigno third_check"
            #cheque.operation_ids = [(4, new_operation_id.id, False)]
            cheque._add_operation('holding', new_payment_id, partner=self.partner_id, date=self.fecha)



    def pagar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        return True

    def editar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        return True