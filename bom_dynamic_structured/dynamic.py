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

class StructureStructure(orm.Model):
    """ Model name: StructureStructure
    """
    
    _inherit = 'structure.structure'
        
    def create_dynamic_bom(self, cr, uid, ids, context=None):
        ''' Create BOM if not present
        '''
        bom_pool = self.pool.get('mrp.bom')
        product_pool = self.pool.get('product.product')

        structure_proxy = self.browse(cr, uid, ids, context=context)

        if structure_proxy.dynamic_bom_id:
            dynamic_bom_id = structure_proxy.dynamic_bom_id.id
        else:
            # Create a temp product:
            product_id = product_pool.create(cr, uid, {
                'default_code': 'DYNAMIC.%s' % structure_proxy.id,
                'name': structure_proxy.name,     
                'uom_id': 1,           
                }, context=context)
            product_proxy = product_pool.browse(
                cr, uid, product_id, context=context)
                
            # Create BOM
            dynamic_bom_id = bom_pool.create(cr, uid, {
                'code': product_proxy.default_code,
                'product_tmpl_id': product_proxy.product_tmpl_id.id,
                'product_id': product_proxy.id,
                'product_qty': 1, 
                'product_uom': 1,
                'bom_category': 'dynamic',
                'structure_id': structure_proxy.id,
                }, context=context)
            
            # Update BOM in structure:    
            self.write(cr, uid, ids, {
                'dynamic_bom_id': dynamic_bom_id,
                }, context=context)
    
        return {
            'type': 'ir.actions.act_window',
            'name': _('Structured dynamic BOM'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': dynamic_bom_id,
            'res_model': 'mrp.bom',
            #'view_id': view_id, # False
            'views': [(False, 'form'), (False, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }        
        
    _columns = {
        'dynamic_bom_id': fields.many2one('mrp.bom', 'Dynamic BOM', 
            help='Dynamic BOM with all element masked depend on code struct.'),
        }

class ProductProduct(orm.Model):
    """ Model name: Product bom directly 
    """
    
    _inherit = 'product.product'
        
    def _get_dynamic_bom_line_ids(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate BOM lines
        '''
        line_pool = self.pool.get('mrp.bom.line')        
        res = {}
        for product in self.browse(cr, uid, ids, context=context):
            structure = product.structure_id
            default_code = product.default_code
            
            if not structure or not structure.dynamic_bom_id or not \
                    default_code:
                res[product.id] = []
            else:                
                dynamic_bom_id = structure.dynamic_bom_id.id
                
                # Search dynamic element in BOM
                cr.execute('''
                    SELECT id 
                    FROM mrp_bom_line
                    WHERE 
                        bom_id = %s AND                        
                        %s ilike dynamic_mask;
                    ''', (dynamic_bom_id, default_code))
                
                res[product.id] = [item for item in cr.fetchall()]
        return res

    _columns = {
        'dynamic_bom_line_ids': fields.function(
            _get_dynamic_bom_line_ids, method=True, 
            type='one2many', relation='mrp.bom.line', 
            string='Dynamic BOM line', readonly=True, store=False),                        
        }

class MRPBomLine(orm.Model):
    """ Model name: MRP Bom line
    """
    
    _inherit = 'mrp.bom.line'
    
    
    _columns = {
        'dynamic_mask': fields.char('Dynamic mask', size=20),
        }

class MRPBom(orm.Model):
    """ Model name: MRP Bom new bom_line_ids
    """
    
    _inherit = 'mrp.bom'
        
    # Button event:
    def open_bom_dynamic_lines(self, cr, uid, ids, context=None):
        ''' Open line for dynamic bom with correct mask
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        model_pool = self.pool.get('ir.model.data')
        tree_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 'view_mrp_bom_line_dynamic_tree')[1]
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dynamic lines'),
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'mrp.bom.line',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree')],
            'domain': [('bom_id', '=', ids[0])],
            'context': {'default_bom_id': ids[0]},
            'target': 'current',
            'nodestroy': False,
            }
        
    _columns = {
        'structure_id': fields.many2one('structure.structure', 'Structure', 
            help='Structure reference'),
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
