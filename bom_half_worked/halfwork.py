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
        # TODO remove? yet used?    
        'halfwork': fields.related(
            'product_id', 'halfwork', 
            type='boolean', string='Halfwork'),
            
        # Add for layout button:
        'relative_type': fields.related(
            'product_id', 'relative_type', 
            selection=[
                ('none', 'None'),
                ('half', 'Halfworked BOM'),
                ('parent', 'Parent BOM'),
                ], 
            type='selection', string='Relative type'),
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
    
    def unlink_product_half_bom(self, cr, uid, ids, context=None):
        ''' Remove BOM if linked is not for this product
        '''
        import pdb; pdb.set_trace()
        assert len(ids) == 1, 'Works only with one record a time'
        line_pool = self.pool.get('mrp.bom.line')
        
        product_proxy = self.browse(cr, uid, ids, context=context)[0]

        if not product_proxy.half_bom_id: # XXX just for sure behaviour!
            return True
            
        if product_proxy.half_bom_id.halfwork_id == product_proxy.id:
            raise osv.except_osv(
                _('Error'), 
                _('Cannot unlink, correct assigned to bom also for back link'),
                )

        # Clean BOM:
        self.write(cr, uid, product_proxy.id, {
            'half_bom_id': False,            
            }, context=context)
        
        # Click regenerate button:
        self.create_product_half_bom(cr, uid, ids, context=context)
        
        # Read record again:
        product_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Update Rows:
        row_ids = [item.id for item in product_proxy.half_bom_ids]
        if row_ids:
            return line_pool.write(cr, uid, row_ids, {
                'bom_id': product_proxy.half_bom_id.id,
                }, context=context) 
        
        return True
                
    def relink_product_half_bom(self, cr, uid, ids, context=None):
        ''' Relink if linked BOM has empty halfwork_id
        ''' 
        assert len(ids) == 1, 'Works only with one record a time'
        bom_pool = self.pool.get('mrp.bom')
        
        product_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        if not product_proxy.half_bom_id:
            return True
            
        if product_proxy.half_bom_id.halfwork_id:
            _logger.warning('No update, yet present')
            return True           
            
        return bom_pool.write(cr, uid, product_proxy.half_bom_id.id, {
            'halfwork_id': product_proxy.id}, context=context)    
        
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
            'mrp.bom', 'Half BOM', copy=False),
        'half_bom_ids': fields.one2many(
            'mrp.bom.line', 'halfwork_id', 
            'Halfwork component'),
        }
        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
