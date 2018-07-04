# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time

class FinancieraPaymentWizard(models.TransientModel):
    _name = 'liquidacion.payment.wizard'

    liquidacion_id = fields.Many2one('liquidacion', string='Liquidacion')
    date = fields.Date('Fecha', default=lambda *a: time.strftime('%Y-%m-%d'))
    journal_payment_out_id = fields.Many2one('account.journal', string='Metodo de pago')
    journal_payment_in_id = fields.Many2one('account.journal', string='Metodo de cobro')
    type_operation = fields.Selection(related='liquidacion_id.type_operation', string='Tipo de operacion', readonly=True)
    amount = fields.Monetary("Monto")
    currency_id = fields.Many2one('res.currency', 'Moneda')

    @api.one
    def confirm_payment(self):
        print "CONFIRM PAYMENT"
        if self.type_operation == 'compra':
            self.liquidacion_id.pagar_liquidacion(self.date, self.amount,self.journal_payment_out_id)
        elif self.type_operation == 'venta':
            pass

class FinancieraChequeWizard(models.TransientModel):
    _name = 'liquidacion.cheque.wizard'

    cheque_id = fields.Many2one('account.check', "Cheque")
    liquidacion_id = fields.Many2one('liquidaicon', "Liquidaicon")

    @api.one
    def confirm_eliminar_seleccion(self):
        self.cheque_id.eliminar_seleccion()
        self.liquidacion_id.update({})
        return True
