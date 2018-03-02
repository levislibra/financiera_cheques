# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta
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
    check_tasa_fija = fields.Float('Impuesto al cheque')
    check_monto_fijo = fields.Float(string='Monto Imp. al cheque', compute='_check_monto_fijo')
    check_tasa_mensual = fields.Float('Tasa de Interes')
    check_monto_mensual = fields.Float(string='Monto Interes', compute='_check_monto_mensual')
    check_vat_tax_id = fields.Many2one('account.tax', 'Tasa de IVA', readonly=True)
    check_monto_iva = fields.Float('IVA', compute='_check_monto_iva')
    check_monto_neto = fields.Float(string='Neto', compute='_check_monto_neto')
    check_scanner_id = fields.Many2one('check.scanner', 'Escaner')

    check_number_char = fields.Char("Numero")

    @api.one
    @api.onchange('check_number_char')
    def _change_check_number_char(self):
        print "change check number char ********----------"
        try:
            self.check_number = int(self.check_number_char)
        except Exception as e:
            raise UserError("Error al introducir el numero del cheque.")


    check_amount_char = fields.Char('Importe')

    @api.one
    @api.onchange('check_amount_char')
    def _check_check_amount_char(self):
        print "check constrains 2"
        try:
            self.amount = float(self.check_amount_char)
        except Exception as e:
            self.amount = float(self.check_amount_char)
            raise UserError("Error al introducir el importe del cheque.")


    @api.model
    def create(self, values):
        if values.has_key('check_liquidacion_id') and values['check_liquidacion_id'] != False:
            liquidacion_id = self.env['liquidacion'].browse(values['check_liquidacion_id'])
            values['payment_group_id'] = liquidacion_id.payment_group_id.id

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
        fecha_inicial_str = False
        fecha_final_str = False
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
        print("payment_date change")
        self.check_fecha_acreditacion = self.check_payment_date


class LiquidacionPagar(models.Model):
    _name = 'liquidacion.pago'

    payment_date = fields.Date('Fecha de pago', required=True)
    payment_journal_id = fields.Many2one('account.journal', 'Metodo de pago', domain="[('type', 'in', ('bank', 'cash'))]")
    payment_amount = fields.Float('Monto')
    payment_communication = fields.Char('Descripcion')
    liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion')

    @api.model
    def default_get(self, fields):
        rec = super(LiquidacionPagar, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        active_id = context.get('active_id')

        cr = self.env.cr
        uid = self.env.uid
        liquidacion_obj = self.pool.get('liquidacion')
        liquidacion_id = liquidacion_obj.browse(cr, uid, active_id, context=context)
        rec.update({
            'payment_date': liquidacion_id.fecha,
            'payment_amount': abs(liquidacion_id.saldo),
            'liquidacion_id': active_id,
            'payment_communication': "Pago liquidacion " + str(liquidacion_id.id).zfill(5),
        })
        return rec

    @api.one
    def confirmar_pagar_liquidacion(self):
        currency_id = self.env.user.company_id.currency_id.id
        cr = self.env.cr
        uid = self.env.uid

        #Pago al cliente
        payment_method_obj = self.pool.get('account.payment.method')
        payment_method_id = payment_method_obj.search(cr, uid, [('code', '=', 'manual'), ('payment_type', '=', 'outbound')])[0]
        ap_values = {
            'payment_type': 'outbound',
            'partner_type': 'customer',
            'partner_id': self.liquidacion_id.partner_id.id,
            'amount': self.payment_amount,
            'payment_date': self.payment_date,
            'journal_id': self.payment_journal_id.id,
            'payment_method_code': 'manual',
            'currency_id': currency_id,
            'payment_method_id': payment_method_id,
            'cummunication': self.payment_communication,
        }
        payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
        payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]
        apg_values = {
            'payment_date': self.payment_date,
            'company_id': 1,
            'partner_id': self.liquidacion_id.partner_id.id,
            'currency_id': currency_id,
            'payment_ids': [(0,0,ap_values)],
            'receiptbook_id': payment_group_receiptbook_id,
            'partner_type': 'customer',
            'account_internal_type': 'payable',
            'debt_move_line_ids': self.liquidacion_id._debt_not_reconcilie()[0],
            'communication': self.payment_communication,
        }
        new_payment_group_id = self.env['account.payment.group'].create(apg_values)
        new_payment_group_id.post()
        self.liquidacion_id.payment_group_ids = [new_payment_group_id.id]

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
    pago_ids = fields.One2many('liquidacion.pago', 'liquidacion_id', 'Pagos')
    payment_group_ids = fields.One2many('account.payment.group', 'liquidacion_id','Pagos al cliente', readonly=True)
    total_pagos = fields.Float('Total pagos')
    debt_move_line_ids = fields.One2many('account.move.line', 'liquidacion_id', 'Deuda a pagar', compute='_update_debt', default=None)
    saldo = fields.Float('Saldo', compute='_compute_saldo')

    tasa_fija = fields.Float('Tasa fija', related='partner_id.tasa_fija', readonly=True)
    tasa_mensual = fields.Float('Tasa mensual', related='partner_id.tasa_mensual', readonly=True)
    saldo_cta_cte = fields.Float('Saldo Cuenta Corriente', compute='_compute_saldo_cta_cte')
    cheques_en_cartera = fields.Float('Cheques en cartera', compute='_compute_cheques_en_cartera')

    @api.model
    def create(self, values):
        cr = self.env.cr
        uid = self.env.uid
        payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
        payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]
        currency_id = self.env.user.company_id.currency_id.id

        apg_values = {
            'payment_date': values['fecha'],
            'company_id': 1,
            'partner_id': values['partner_id'],
            'currency_id': currency_id,
            'receiptbook_id': payment_group_receiptbook_id,
            'partner_type': 'customer',
            'account_internal_type': 'receivable',
            #'payment_ids': [(0,0,ap_values)],
            #'debt_move_line_ids': self._debt_not_reconcilie()[0],
        }
        new_payment_group_id = self.env['account.payment.group'].create(apg_values)
        values['payment_group_id'] = new_payment_group_id.id

        rec = super(Liquidacion, self).create(values)
        return rec

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

        payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
        payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]
        currency_id = self.env.user.company_id.currency_id.id

        payment_group_receiptbook_obj = self.pool.get('account.payment.receiptbook')
        payment_group_receiptbook_id = payment_group_receiptbook_obj.search(cr, uid, [('sequence_type', '=', 'automatic'), ('partner_type', '=', 'customer')])[0]
        
        rec.update({
            'receiptbook_id': payment_group_receiptbook_id,
            'payment_method_id': payment_method_id,
            'currency_id': currency_id,
        })
        return rec

    @api.one
    def _update_debt(self):
        for move_line_id in self.invoice_id.move_id.line_ids:
            if move_line_id.debit > 0:
                self.debt_move_line_ids = [move_line_id.id]

        for payment_id in self.payment_group_id.payment_ids:
            for move_line_id in payment_id.move_line_ids:
                if move_line_id.credit > 0:
                    self.debt_move_line_ids = [move_line_id.id]

    @api.one
    def _debt_not_reconcilie(self):
        ret = []
        for ail_id in self.debt_move_line_ids:
            if not ail_id.reconciled:
                ret.append(ail_id.id)
        return ret


    def get_bruto(self):
        bruto = 0
        for payment in self.payment_ids:
            bruto += payment.amount
        return bruto

    #@api.multi
    def _compute_saldo(self):
        #self.ensure_one()
        saldo = 0
        for line_id in self.debt_move_line_ids:
            saldo += line_id.amount_residual
        self.saldo = abs(saldo)

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
        for payment in self.payment_ids:
            payment.journal_id = self.journal_id
            #payment.payment_method_id = self.payment_method_id.id
            #payment.payment_method_code = 'received_third_check'

    @api.onchange('vat_tax_id')
    def _set_vat_tax_id(self):
        for payment in self.payment_ids:
            payment.check_vat_tax_id = self.vat_tax_id.id

    @api.one
    @api.onchange('partner_id')
    def _compute_saldo_cta_cte(self):
        cr = self.env.cr
        uid = self.env.uid
        line_obj = self.pool.get('account.move.line')
        line_ids = line_obj.search(cr, uid, [
            ('partner_id', '=', self.partner_id.id),
            ('account_id', '=', self.partner_id.property_account_receivable_id.id)
            ])
        for _id in line_ids:
            line_id = line_obj.browse(cr, uid, _id)
            self.saldo_cta_cte +=line_id.amount_residual

    @api.one
    @api.onchange('partner_id')
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
    def confirmar(self):
        if len(self.payment_ids) == 0:
            raise UserError("No puede confirmar una liquidacion sin cheques.")
        else:
            self.state = 'confirmada'
            self.confirmar_payments()
            self.facturar()
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
        for payment in self.payment_ids:
            payment.check_name = str(payment.check_number) + " " + payment.check_firmante_id.name
            payment.check_owner_name = payment.check_firmante_id.name
            payment.check_owner_vat = payment.check_firmante_id.cuit
            payment.check_type = 'third_check'
        self.payment_group_id.post()

    def pagar(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state':'cotizacion'}, context=None)
        return True

    @api.one
    def facturar(self):
        journal_id = None
        vat_tax_id = None
        if self.factura_electronica:
            journal_id = self.journal_invoice_use_doc_id
            vat_tax_id = self.vat_tax_id.id
        else:
            journal_id = self.journal_invoice_id
        if journal_id != False and journal_id != None:
            # Create invoice line
            ail = {
                'name': "Interes por servicios financieros",
                'quantity':1,
                'price_unit': self.get_interes(),
                #'vat_tax_id': vat_tax_id,
                #'invoice_line_tax_ids':  [vat_tax_id],
                'account_id': journal_id.default_debit_account_id.id,
            }

            # Create invoice line
            ail2 = {
                'name': "Impuesto a los debitos y creditos bancarios por cuenta del cliente.",
                'quantity':1,
                'price_unit': self.get_gasto(),
                #'vat_tax_id': vat_tax_id,
                #'invoice_line_tax_ids': [vat_tax_id],
                'account_id': journal_id.default_debit_account_id.id,
            }
            account_invoice_customer0 = {
                'account_id': self.partner_id.property_account_receivable_id.id,
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

    @api.multi
    def pagar_liquidacion(self):
        if self.saldo <= 0:
            raise UserError("El saldo de la liquidacion debe ser mayor a cero.")
        else:
            cr = self.env.cr
            uid = self.env.uid
            view_ref = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'financiera_cheques', 'pagar_liquidacion_view')
            view_id = view_ref and view_ref[1] or False,

            return {
                'type': 'ir.actions.act_window',
                'name': 'Registrar Pago Liquidacion',
                'view_mode': 'form',
                'view_type': 'form',
                'view_id': view_id,
                'res_model': 'liquidacion.pago',
                'nodestroy': True,
                'target': 'new',
                #'search_view_id': sale_order_tree,
            }

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

    @api.model
    def create(self, values):

        rec = super(ExtendsAccountMoveLine, self).create(values)
        return rec

class ExtendsPartner(models.Model):
    _name = 'res.partner'
    _inherit = 'res.partner'

    tasa_fija = fields.Float('Tasa de gastos')
    tasa_mensual = fields.Float('Tasa mensual')

class ExtendsAccountAccount(models.Model):
    _name = 'account.account'
    _inherit = 'account.account'

    move_line_ids = fields.One2many('account.move.line', 'account_id', 'Movimientos')
