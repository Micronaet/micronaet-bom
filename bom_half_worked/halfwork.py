# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
import os
import sys
import logging
import openerp
import openerp.netsvc as netsvc
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID, api
from openerp import tools
from openerp.tools.translate import _
from openerp.tools.float_utils import float_round as round
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class MrpBomLine(orm.Model):
    """ Model name: Bom line
    """    
    _inherit = 'mrp.bom'
    
    # Used for generate default when start from BOM
    _columns = {
        'halfwork_id': fields.many2one(
            'product.product', 'Halfwork product'),
        }

class MrpBomLine(orm.Model):
    """ Model name: Bom line
    """
    
    _inherit = 'mrp.bom.line'
    
    _columns = {
        'halfwork_id': fields.many2one(
            'product.product', 'Halfwork product'),
        'halfwork': fields.related(
            'product_id', 'halfwork', 
            type='boolean', string='Halfwork'),
        }

    # Button:
    def open_halfwork_form(self, cr, uid, ids, context=None):
        ''' Open component HW for check bom
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        bom_id = line_proxy.product_id.half_bom_id.id
        #model_pool = self.pool.get('ir.model.data')
        #view_id = model_pool.get_object_reference('module_name', 'view_name')[1]
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Halfworked component'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': bom_id,
            'res_model': 'mrp.bom',
            #'view_id': view_id, # False
            'views': [(False, 'form')],
            'domain': [('id', '=', bom_id)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    def create_product_half_bom(self, cr, uid, ids, context=None):
        ''' Create BOM for halfworked         
        '''        
        assert len(ids) == 1, 'Works only with one record a time'
        bom_pool = self.pool.get('mrp.bom')
        
        product_proxy = self.browse(cr, uid, ids, context=context)[0]
        if product_proxy.half_bom_id:
            return True
        else:
            bom_id = bom_pool.create(cr, uid, {
                'product_tmpl_id': product_proxy.product_tmpl_id.id,
                'product_id': product_proxy.id,
                'bom_category': 'half',
                'product_qty': 1.0,
                'code': product_proxy.default_code,
                'type': 'normal',
                'product_uom': product_proxy.uom_id.id,
                'halfwork_id': product_proxy.id,
                }, context=context)
            return self.write(cr, uid, ids, {
                'half_bom_id': bom_id,
                }, context=context)
        
        
    _columns = {
        # TODO remove:
        'halfwork': fields.boolean('Halworked', 
            help='Manage BOM directly in product'),
            
        'half_bom_id': fields.many2one(
            'mrp.bom', 'Half BOM'),
        'half_bom_ids': fields.one2many(
            'mrp.bom.line', 'halfwork_id', 
            'Halfwork component'),
        }
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
