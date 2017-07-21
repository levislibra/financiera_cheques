# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta
from openerp.exceptions import UserError
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

class AccountPayment(models.Model):
    # This OpenERP object inherits from cheques.de.terceros
    # to add a new float field
    _inherit = 'account.payment'
    _name = 'account.payment'
    _description = 'Opciones extras de cheques para calculo de financiera'

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

    @api.model
    def default_get(self, fields):
        rec = super(AccountPayment, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        active_id = context.get('active_id')
        fecha = context.get('fecha')
        partner_id = context.get('partner_id')
        journal_id = context.get('journal_id')
        receiptbook_id = context.get('receiptbook_id')
        payment_method_id = context.get('payment_method_id')
        currency_id = context.get('currency_id')

        if active_model == 'liquidacion':
            print "valores"
            rec.update({
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner_id,
                'journal_id': journal_id,
                'payment_method_id': payment_method_id,
                'payment_method_code': 'received_third_check',
                'receiptbook_id': receiptbook_id,
                'payment_date': fecha,
                #'communication': 'Liquidacion Nro ' + str(self.id),
                'currency_id': currency_id,
                #'commercial_partner_id': cheque.type,
            })
        return rec


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

    @api.onchange('check_number')
    def _set_name_number(self):
        print self.check_owner_name
        if self.check_owner_name != False:
            self.check_name = str(self.check_number) + " " + self.check_owner_name

    @api.onchange('check_payment_date')
    def _fecha_acreditacion(self):
        print("payment_date change")
        self.fecha_acreditacion = self.check_payment_date

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
    cheque_ids = fields.One2many('account.payment', 'liquidacion_id', 'Cheques', ondelete='cascade')
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
        #self.partner_id.commercial_partner_id = self.partner_id.id
        for cheque in self.cheque_ids:
            cheque.check_name = str(cheque.check_number) + " " + cheque.firmante_id.name
            cheque.check_owner_name = cheque.firmante_id.name
            cheque.check_owner_vat = cheque.firmante_id.cuit
            #cheque.check_name = str(cheque.check_number) + " " + cheque.check_owner_name
            cheque.post()


    def pagar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        return True

    def editar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        return True