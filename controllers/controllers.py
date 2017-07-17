# -*- coding: utf-8 -*-
from openerp import http

#class Librasoft-financiera-cheques(http.Controller):
#	@http.route('/librasoft-financiera-cheques/librasoft-financiera-cheques/', auth='public')
#	def index(self, **kw):
#		return "Hello, world"

#     @http.route('/librasoft-financiera-cheques/librasoft-financiera-cheques/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('librasoft-financiera-cheques.listing', {
#             'root': '/librasoft-financiera-cheques/librasoft-financiera-cheques',
#             'objects': http.request.env['librasoft-financiera-cheques.librasoft-financiera-cheques'].search([]),
#         })

#     @http.route('/librasoft-financiera-cheques/librasoft-financiera-cheques/objects/<model("librasoft-financiera-cheques.librasoft-financiera-cheques"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('librasoft-financiera-cheques.object', {
#             'object': obj
#         })