# -*- coding: utf-8 -*-

from openerp import models, fields, api
from datetime import datetime, timedelta
from dateutil import relativedelta
from openerp.exceptions import UserError, ValidationError
import time

class ChequeOpcionesWizard(models.TransientModel):
    _name = 'cheque.opciones.wizard'

    cheque_id = fields.Many2one('account.payment', string='Liquidacion')
    date = fields.Date('Fecha', default=lambda *a: time.strftime('%Y-%m-%d'))
    neto = fields.Monetary("neto")
    currency_id = fields.Many2one('res.currency', 'Moneda')

    @api.one
    def confirm_payment(self):
        if self.type_operation == 'compra':
            self.liquidacion_id.pagar_liquidacion(self.date, self.amount,self.journal_payment_out_id)
        elif self.type_operation == 'venta':
            self.liquidacion_id.cobrar_liquidacion(self.date, self.amount,self.journal_payment_in_id)
