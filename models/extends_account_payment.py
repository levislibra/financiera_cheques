# -*- coding: utf-8 -*-

from openerp import models, fields, api
import time
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.tools.translate import _
import logging
from openerp.osv import orm
_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    # This OpenERP object inherits from cheques.de.terceros
    # to add a new float field
    _inherit = 'account.payment'
    _name = 'account.payment'
    _description = 'Opciones extras de cheques para calculo de financiera'

    check_liquidacion_id = fields.Many2one('liquidacion', 'Liquidacion id')
    check_select = fields.Boolean('Seleccionar')
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

    @api.multi
    def wizard_opciones_cheque(self):
        params = {
            'cheque_id': self.id,
        }
        view_id = self.env['cheque.opciones.wizard']
        new = view_id.create(params)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Opciones cheque',
            'res_model': 'cheque.opciones.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id'    : new.id,
            'view_id': self.env.ref('financiera_cheques.cheque_opciones_wizard', False).id,
            'target': 'new',
        }