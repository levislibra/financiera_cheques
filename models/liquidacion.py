# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError
from openerp.exceptions import ValidationError
from openerp.tools.translate import _
import amount_to_text_es_MX
from pprint import pprint
import logging
from openerp.osv import orm
_logger = logging.getLogger(__name__)

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
    total = fields.Float('Total', compute='_compute_total')
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
    company_id = fields.Many2one('res.company', 'Empresa', default=lambda self: self.env['res.company']._company_default_get('liquidacion'))
    # Mutuo
    mutuante_nombre = fields.Char('Mutuante')
    mutuante_cuit = fields.Char('CUIT/DNI')
    mutuante_domicilio_calle = fields.Char('Domicilio calle')
    mutuante_domicilio_ciudad = fields.Char('Domicilio ciudad')
    
    mutuario_nombre = fields.Char('Mutuario')
    mutuario_cuit = fields.Char('CUIT/DNI')
    mutuario_domicilio_calle = fields.Char('Domicilio calle')
    mutuario_domicilio_ciudad = fields.Char('Domicilio ciudad')
    mutuo_monto_texto = fields.Char('Monto', compute='_compute_mutuo_monto_texto')
    # Calcular cheque
    neto_cheque = fields.Float('Neto del cheque/s', digits=(16,2))

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
        # Mutuario
        self.mutuario_nombre = self.partner_id.name
        self.mutuario_cuit = self.partner_id.main_id_number
        self.mutuario_domicilio_calle = self.partner_id.street
        self.mutuario_domicilio_ciudad = self.partner_id.city

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

            mutuante_nombre = configuracion_id.mutuante_nombre
            mutuante_cuit = configuracion_id.mutuante_cuit
            mutuante_domicilio_calle = configuracion_id.mutuante_domicilio_calle
            mutuante_domicilio_ciudad = configuracion_id.mutuante_domicilio_ciudad

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
                'mutuante_nombre': mutuante_nombre or "",
                'mutuante_cuit': mutuante_cuit or "",
                'mutuante_domicilio_calle': mutuante_domicilio_calle or "",
                'mutuante_domicilio_ciudad': mutuante_domicilio_ciudad or "",
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
    def _compute_total(self):
        self.total = self.get_bruto()

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
    def get_descripcion_cheques(self):
        descripcion_cheques = ""
        for cheque_id in self.payment_ids:
            descripcion_cheques += "cheque numero "+str(cheque_id.check_number)
            descripcion_cheques += ", "+str(cheque_id.check_bank_id.name)+"; "
        return descripcion_cheques

    @api.one
    def facturar(self):
        journal_id = None
        vat_tax_id = None
        invoice_line_tax_ids = None

        vat_tax2_id = None
        invoice_line_tax2_ids = None
        configuracion_id = self.env['liquidacion.config'].browse(1)
        if self.factura_electronica:
            journal_id = self.journal_invoice_use_doc_id
            vat_tax_id = self.vat_tax_id.id
            invoice_line_tax_ids = [(6, 0, [vat_tax_id])]
            # Asignamos el impuesto al cheque que cobramos (NO gravado)
            vat_tax2_id = configuracion_id.vat_tax2_id.id
            invoice_line_tax2_ids = [(6, 0, [vat_tax2_id])]
        else:
            journal_id = self.journal_invoice_id
        if journal_id != False and journal_id != None:
            ail_ids = []
            fiscal_position_id = None
            if self.get_interes() > 0:
                # Create invoice line
                descripcion_cheques = self.get_descripcion_cheques()[0]
                ail = {
                    'name': "Interes por servicios financieros. "+descripcion_cheques,
                    'quantity':1,
                    'price_unit': self.get_interes(),
                    'vat_tax_id': vat_tax_id,
                    'invoice_line_tax_ids': invoice_line_tax_ids,
                    'account_id': journal_id.default_debit_account_id.id,
                }
                ail_ids.append((0,0,ail))
            if self.get_gasto() > 0:
                # Create invoice line
                ail2 = {
                    'name': "Impuesto a los debitos y creditos bancarios por cuenta del cliente.",
                    'quantity':1,
                    'price_unit': self.get_gasto(),
                    'vat_tax_id': vat_tax2_id,
                    'invoice_line_tax_ids': invoice_line_tax2_ids,
                    'account_id': journal_id.default_debit_account_id.id,
                }
                ail_ids.append((0,0,ail2))
                fiscal_position_id = configuracion_id.fiscal_position_id.id
            if len(ail_ids) > 0:
                account_invoice_customer0 = {
                    # 'name': "Liquidacion #" + str(self.id).zfill(8) + " - Intereses",
                    'description_financiera': "Liquidacion #" + str(self.id).zfill(8) + " - Intereses",
                    'account_id': self.account_id.id,
                    'partner_id': self.partner_id.id,
                    'journal_id': journal_id.id,
                    'currency_id': self.currency_id.id,
                    'company_id': 1,
                    'date': self.fecha,
                    'date_invoice': self.fecha,
                    'invoice_line_ids': ail_ids,
                    'fiscal_position_id': fiscal_position_id,
                }
                new_invoice_id = self.env['account.invoice'].create(account_invoice_customer0)
                #hacer configuracion de validacion automatica
                if configuracion_id.automatic_validate:
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

    @api.one
    def _compute_mutuo_monto_texto(self):
        self.mutuo_monto_texto = amount_to_text_es_MX.get_amount_to_text(self, self.get_bruto(), 'centavos', 'pesos con ')

    @api.one
    def caclular_importe_cheques(self):
        for cheque_id in self.payment_ids:
            if cheque_id.check_select:
                tf = cheque_id.check_tasa_fija/100
                tv_dias = cheque_id.check_dias * cheque_id.check_tasa_mensual/30/100
                tv_iva_dias = 0
                if cheque_id.check_vat_tax_id != None:
                    tv_iva_dias = cheque_id.check_vat_tax_id.amount/100 * tv_dias
                nuevo_importe_cheque = self.neto_cheque / (1 - tf - tv_dias - tv_iva_dias)
                cheque_id.amount = nuevo_importe_cheque
                cheque_id.check_select = False

    @api.one
    def caclular_tv_cheques(self):
        for cheque_id in self.payment_ids:
            if cheque_id.check_select:
                tf = cheque_id.check_tasa_fija/100
                # tv_dias = cheque_id.check_dias * cheque_id.check_tasa_mensual/30/100
                t_iva = 0
                if cheque_id.check_vat_tax_id != None:
                    t_iva = cheque_id.check_vat_tax_id.amount/100
                nueva_tasa_mensual = (self.neto_cheque - cheque_id.amount + cheque_id.amount * tf) / (-cheque_id.amount * cheque_id.check_dias - cheque_id.amount * cheque_id.check_dias * t_iva)
                cheque_id.check_tasa_mensual = nueva_tasa_mensual * 30 * 100
                cheque_id.check_select = False


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

# Clase Obsoleta - Usamos Wizards
class LiquidacionPagar(models.Model):
    _name = 'liquidacion.pago'

    payment_date = fields.Date('Fecha de pago', required=True)
    payment_journal_id = fields.Many2one('account.journal', 'Metodo de pago', domain="[('type', 'in', ('bank', 'cash'))]")
    payment_amount = fields.Float('Monto')
    payment_communication = fields.Char('Descripcion')
    liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion')


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
    moneda_id = fields.Many2one('res.currency', 'Moneda')

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

    # Reescribimos funcion original
    @api.multi
    def action_create_debit_note(
            self, operation, partner_type, partner, account):
        self.ensure_one()
        action_date = self._context.get('action_date')
        if operation == 'rejected':
            # Recalculamos si es cuenta cliente o proveedor
            # Ver que tipo de pago participo el cheque en cuestion
            # Para ello tomar el origen de la ultima operacion
            ultima_operacion = self.operation_ids[len(self.operation_ids)-2]
            origen_id = ultima_operacion.origin
            origen_tipo = origen_id._name
            if origen_tipo == 'account.payment':
                # Asignamos el tipo recibo ya que de eso depende
                # si el cheque fue a la cuenta como cliente o proveedor
                partner_type = origen_id.receiptbook_id.partner_type

        if partner_type == 'supplier':
            invoice_type = 'in_invoice'
            journal_type = 'purchase'
            view_id = self.env.ref('account.invoice_supplier_form').id
        else:
            invoice_type = 'out_invoice'
            journal_type = 'sale'
            view_id = self.env.ref('account.invoice_form').id

        # journal = self.env['account.journal'].search([
        #     ('company_id', '=', self.company_id.id),
        #     ('type', '=', journal_type),
        # ], limit=1)
        configuracion_id = self.env['liquidacion.config'].browse(1)
        journal = configuracion_id.journal_cartera_id

        # si pedimos rejected o reclamo, devolvemos mensaje de rechazo y cuenta
        # de rechazo
        if operation in ['rejected', 'reclaimed']:
            name = 'Rechazo cheque "%s"' % (self.name)
        # si pedimos la de holding es una devolucion
        elif operation == 'returned':
            name = 'Devolución cheque "%s"' % (self.name)
        else:
            raise ValidationError(_(
                'Debit note for operation %s not implemented!' % (
                    operation)))

        inv_line_vals = {
            # 'product_id': self.product_id.id,
            'name': name,
            'account_id': account.id,
            'price_unit': self.amount,
            # 'invoice_id': invoice.id,
        }

        inv_vals = {
            # this is the reference that goes on account.move.line of debt line
            # 'name': name,
            # this is the reference that goes on account.move
            'rejected_check_id': self.id,
            'reference': name,
            'date_invoice': action_date,
            'origin': _('Check nbr (id): %s (%s)') % (self.name, self.id),
            'journal_id': journal.id,
            # this is done on muticompany fix
            # 'company_id': journal.company_id.id,
            'partner_id': partner.id,
            'type': invoice_type,
            'invoice_line_ids': [(0, 0, inv_line_vals)],
        }
        if operation == 'rejected' and origen_tipo == 'account.payment':
            inv_vals['name'] = name
            if partner_type == 'customer':
                inv_line_vals['price_unit'] = -self.amount
        if self.currency_id:
            inv_vals['currency_id'] = self.currency_id.id
        # we send internal_type for compatibility with account_document
        invoice = self.env['account.invoice'].with_context(
            internal_type='debit_note').create(inv_vals)
        self._add_operation(operation, invoice, partner, date=action_date)

        return {
            'name': name,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.invoice',
            'view_id': view_id,
            'res_id': invoice.id,
            'type': 'ir.actions.act_window',
        }
