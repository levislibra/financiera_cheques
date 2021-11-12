# -*- coding: utf-8 -*-

from openerp import models, fields, api

class ExtendsResCompany(models.Model):
	_inherit = 'res.company'

	liquidacion_config_id = fields.Many2one('liquidacion.config', 'Configuracion liquidaciones')