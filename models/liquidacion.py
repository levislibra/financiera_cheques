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

    check_liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion id')
    check_firmante_id = fields.Many2one('firmante', 'Firmante')
    check_fecha_acreditacion = fields.Date('Acreditacion')
    check_dias = fields.Integer(string='Dias', compute='_check_dias')
    check_tasa_fija = fields.Float('Impuesto al cheque')
    check_monto_fijo = fields.Float(string='Monto Imp. al cheque', compute='_check_monto_fijo')
    check_tasa_mensual = fields.Float('Tasa de Interes')
    check_monto_mensual = fields.Float(string='Monto Interes', compute='_check_monto_mensual')
    check_vat_tax_id = fields.Many2one('account.tax', 'Tasa de IVA', readonly=True)
    check_monto_iva = fields.Float('IVA', compute='_check_monto_iva')
    check_monto_neto = fields.Float(string='Neto', compute='_check_monto_neto')

    @api.model
    def default_get(self, fields):
        rec = super(AccountPayment, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        active_id = context.get('active_id')
        action = context.get('action')

        print "ACTION"
        print action
        if active_model == 'liquidacion':
            print "LIQUIDACION"
            fecha = context.get('fecha')
            partner_id = context.get('partner_id')
            journal_id = context.get('journal_id')
            receiptbook_id = context.get('receiptbook_id')
            payment_method_id = context.get('payment_method_id')
            currency_id = context.get('currency_id')
            vat_tax_id = context.get('vat_tax_id')
            print "get context"
            print payment_method_id
            print "================"

            cr = self.env.cr
            uid = self.env.uid
            payment_method_obj = self.pool.get('account.payment.method')
            payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'received_third_check')])[0]


            if action == 'cheque_nuevo':
                print "CHEQUE NUEVO"
                rec.update({
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': partner_id,
                    'journal_id': journal_id,
                    'payment_method_code': 'received_third_check',
                    'check_type': 'third_check',
                    'receiptbook_id': receiptbook_id,
                    'payment_date': fecha,
                    'currency_id': currency_id,                    
                    'payment_method_id': payment_method_id,
                    'check_vat_tax_id': vat_tax_id,
                })
            elif action == 'realizar_pago':
                print "REALIZAR PAGO"
                print active_id
                print active_ids
                liquidacion_id = self.env[active_model].browse(active_id)
                amount = liquidacion_id.get_neto()
                fecha = liquidacion_id.fecha
                rec.update({
                    'payment_type': 'outbound',
                    'partner_type': 'customer',
                    'partner_id': partner_id,
                    'amount': amount,
                    'payment_date': fecha,
                })
        return rec
    
    @api.one
    @api.depends('check_liquidacion_id.fecha', 'check_fecha_acreditacion')
    def _check_dias(self):
        fecha_inicial_str = False
        fecha_final_str = False
        _logger.error("_calcular_descuento_dias")
        if self.check_liquidacion_id.fecha != False:
           fecha_inicial_str = str(self.check_liquidacion_id.fecha)
        if self.check_fecha_acreditacion != False:
           fecha_final_str = str(self.check_fecha_acreditacion)
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
                self.check_dias = diferencia.days
            else:
                self.check_dias = 0
            print "DIAS: "
            print self.check_dias


    @api.one
    @api.depends('check_monto_mensual', 'check_vat_tax_id')
    def _check_monto_iva(self):
        if self.check_vat_tax_id != None:
    	   self.check_monto_iva = self.check_monto_mensual * (self.check_vat_tax_id.amount / 100)

    @api.one
    @api.depends('amount', 'check_tasa_fija')
    def _check_monto_fijo(self):
    	self.check_monto_fijo = self.amount * (self.check_tasa_fija / 100)

    @api.one
    @api.depends('amount', 'check_tasa_mensual', 'check_dias')
    def _check_monto_mensual(self):
    	self.check_monto_mensual = self.check_dias * ((self.check_tasa_mensual / 30) / 100) * self.amount

    @api.one
    @api.depends('amount', 'check_monto_fijo', 'check_monto_mensual', 'check_monto_iva')
    def _check_monto_neto(self):
    	self.check_monto_neto = self.amount - self.check_monto_fijo - self.check_monto_mensual - self.check_monto_iva

    @api.onchange('check_payment_date')
    def _check_fecha_acreditacion(self):
        print("payment_date change")
        self.check_fecha_acreditacion = self.check_payment_date

class Liquidacion(models.Model):
    _name = 'liquidacion'

    id = fields.Integer('Nro Liquidacion')
    fecha = fields.Date('Fecha', required=True, default=lambda *a: time.strftime('%Y-%m-%d'))
    active = fields.Boolean('Activa', default=True)
    partner_id = fields.Many2one('res.partner', 'Cliente', required=True)
    journal_id = fields.Many2one('account.journal', 'Diario', domain="[('type', 'in', ('bank', 'cash')), ('inbound_payment_method_ids.code', 'in', ['received_third_check'])]")
    analytic_id = fields.Many2one('account.analytic.account', 'Cuenta analítica')
    move_id = fields.Many2one('account.move', 'Asiento', readonly=True)
    invoice_id = fields.Many2one('account.invoice', 'Factura', readonly=True)
    payment_ids = fields.One2many('account.payment', 'check_liquidacion_id', 'Cheques', ondelete='cascade')
    state = fields.Selection([('cotizacion', 'Cotizacion'), ('confirmada', 'Confirmada'), ('facturada', 'Facturada'), ('pagada', 'Pagada'), ('cancelada', 'Cancelada')], default='cotizacion', string='Status', readonly=True, track_visibility='onchange')
    receiptbook_id = fields.Many2one('account.payment.receiptbook', "ReceiptBook", domain="[('partner_type','=', 'customer')]")
    payment_method_id = fields.Many2one('account.payment.method', "Payment Method", readonly=True)
    currency_id = fields.Many2one('res.currency', "Moneda", readonly=True)
    factura_electronica = fields.Boolean('¿Factura electronica?', default=False)
    vat_tax_id = fields.Many2one('account.tax', 'Tasa de IVA', domain="[('type_tax_use', '=', 'sale')]", readonly=True)


    @api.model
    def default_get(self, fields):
        rec = super(Liquidacion, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        active_id = context.get('active_id')

        cr = self.env.cr
        uid = self.env.uid
        payment_method_obj = self.pool.get('account.payment.method')
        payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'received_third_check')])[0]

        rec.update({
            'receiptbook_id': 2,
            'payment_method_id': payment_method_id,
            'currency_id': 20,
        })
        return rec

    def get_bruto(self):
        bruto = 0
        for payment in self.payment_ids:
            bruto += payment.amount
        return bruto

    def get_gasto(self):
        gasto = 0
        for payment in self.payment_ids:
            gasto += payment.check_monto_fijo
        return gasto

    def get_interes(self):
        interes = 0
        for payment in self.payment_ids:
            interes += payment.check_monto_mensual
        return interes

    def get_iva(self):
        iva = 0
        for payment in self.payment_ids:
            iva += payment.check_monto_iva
        return iva

    def get_neto(self):
        neto = 0
        for payment in self.payment_ids:
            neto += payment.check_monto_neto
        return neto

    @api.onchange('journal_id')
    def _set_journal_id(self):
        print("journal change en liquidacion")
        for payment in self.payment_ids:
            payment.journal_id = self.journal_id
            payment.payment_method_id = self.payment_method_id.id
            payment.payment_method_code = 'received_third_check'

    @api.onchange('vat_tax_id')
    def _set_vat_tax_id(self):
        print("vat_tax change en liquidacion")
        for payment in self.payment_ids:
            payment.check_vat_tax_id = self.vat_tax_id.id

    @api.one
    def print_datos(self):
        _logger.error("Print")
        print self.journal_id
        print self.payment_method_id
        print self.payment_method_id.id
        print "****************************"

        return True

    @api.one
    def confirmar(self):
        _logger.error("CONFIRMAR2")
        self.state = 'confirmada'
        self.confirmar_payments()

        return True

    def confirmar_payments(self):
        for payment in self.payment_ids:
            payment.check_name = str(payment.check_number) + " " + payment.check_firmante_id.name
            payment.check_owner_name = payment.check_firmante_id.name
            payment.check_owner_vat = payment.check_firmante_id.cuit
            payment.payment_method_id = self.payment_method_id.id
            payment.payment_method_code = 'received_third_check'
            payment.check_type = 'third_check'
            payment.post()


    def pagar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        return True

    @api.one
    def facturar(self):
        print "Facturar ***********************************"
        account_invoice_obj = self.env['account.invoice']
        cr = self.env.cr
        uid = self.env.uid
        journal_obj = self.pool.get('account.journal')
        journal_ids = journal_obj.search(cr, uid, [('type', '=', 'sale'), ('use_documents', '=', self.factura_electronica)])
        if len(journal_ids) > 0:
            print "journal 1"
            print journal_ids
            print journal_ids[0]
            journal_id = journal_obj.browse(cr, uid, journal_ids[0], context=None)
            print "len > 0"
            print journal_id
            print journal_id.id
            vat_tax_id = None
            if self.factura_electronica:
                vat_tax_id = self.vat_tax_id.id
            # Create invoice line
            ail = {
                'name': "Interes por servicios financieros",
                'quantity':1,
                'price_unit': self.get_interes(),
                #'vat_tax_id': vat_tax_id,
                'invoice_line_tax_ids':  [vat_tax_id],
                'account_id': journal_id.default_debit_account_id.id,
            }

            # Create invoice line
            ail2 = {
                'name': "Impuesto a los debitos y creditos bancarios por cuenta del cliente.",
                'quantity':1,
                'price_unit': self.get_gasto(),
                #'vat_tax_id': vat_tax_id,
                'invoice_line_tax_ids': [vat_tax_id],
                'account_id': journal_id.default_credit_account_id.id,
            }
            print "Creamos la factura 1"
            account_invoice_customer0 = {
                'account_id': self.partner_id.property_account_receivable_id.id,
                'partner_id': self.partner_id.id,
                'journal_id': journal_id.id,
                'currency_id': self.currency_id.id,
                'company_id': 1,
                'date': self.fecha,
                'invoice_line_ids': [(0, 0, ail), (0, 0, ail2)],
            }
            print "Creamos la factura 2"
            new_invoice_id = self.env['account.invoice'].create(account_invoice_customer0)
            #account_invoice_customer0.signal_workflow('invoice_open')
            print "Creamos la factura 3"
            #account_invoice_customer0.reconciled = True
            #account_invoice_customer0.state = 'paid'
            self.invoice_id = new_invoice_id.id

            #self.state = 'facturada'
            #self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        else:
            raise ValidationError("Falta Diario de ventas.")
        return True