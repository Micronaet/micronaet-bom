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

class MrpBomCategoryStructureCategory(orm.Model):
    """ Model name: Mrp Bom Category structure
    """
    
    _name = 'mrp.bom.structure.category'
    _description = 'BOM structure category'
    
    _columns = {
        'name': fields.char('Category element', size=40, required=True,
            help='Category element (for BOM structure)'),
        'speech_structure_id': fields.many2one(
            'structure.structure', 'Default speech code', required=False),
        'note': fields.text('Note'),        
        }
    
    
class MrpBomCategory(orm.Model):
    """ Model name: Mrp Bom Category
    """
    
    _name = 'mrp.bom.structure'
    _description = 'BOM Structure'
    
    _columns = {
        'name': fields.char('Code', size=10, required=True),
        'note': fields.text('Note'),
        }

class MrpBomCategoryLine(orm.Model):
    """ Model name: Mrp Bom Category Items
    """
    
    _name = 'mrp.bom.structure.line'
    _description = 'BOM category line'
    _rec_name = 'category_id'
    _order = 'sequence,category_id'
    
    _columns = {
        'sequence': fields.integer('Sequence', required=True),
        'category_id': fields.many2one(
            'mrp.bom.structure.category', 'Category', required=False),
        'structure_id': fields.many2one('mrp.bom.structure', 'Structure'),
        'product_id': fields.many2one(
            'product.product', 'Default product', required=False),
        'quantity': fields.integer('Q.ty', required=True),
        'uom_id': fields.related(
            'product_id', 'uom_id', type='many2one', relation='product.uom', 
            string='UOM', readonly=True),        
        }
        
    _defaults = {
        'sequence': lambda *x: 10,
        'total': lambda *x: 1,        
        }    

class MrpBomCategory(orm.Model):
    """ Model name: Mrp Bom Category
    """
    
    _inherit = 'mrp.bom.structure'
    
    _columns = {
        'category_ids': fields.one2many(
            'mrp.bom.structure.line', 'structure_id', 
            'Category'),
        }
    
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
    
        model_pool = self.pool.get('ir.model.data')

        form_view_id = model_pool.get_object_reference(cr, uid,
            'bom_dynamic_structured', 'view_mrp_bom_dynamic_new_form')[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Structured dynamic BOM'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': dynamic_bom_id,
            'res_model': 'mrp.bom',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form'), (False, 'tree')],
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
        
    #def open_dynamic_bom(self, cr, uid, ids, context=None):
    #    ''' Open dynamic structure
    #    '''    
    #    product_proxy = self.browse(cr, uid, ids, context=context)[0]
    #    return self.pool.get('structure.structure').create_dynamic_bom(
    #        cr, uid, [product_proxy.structure_id.id], context=context)
    #    return True

    def open_dynamic_bom(self, cr, uid, ids, context=None):
        ''' Open dynamic structure
        '''    
        product_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        structure = product_proxy.structure_id
        if structure.dynamic_bom_id:
            return self.pool.get('mrp.bom').open_bom_dynamic_lines(
                cr, uid, [structure.dynamic_bom_id.id], context=context)        
        else: # First time:
            return self.pool.get('structure.structure').create_dynamic_bom(
                cr, uid, [structure_id.id], context=context)

    def open_current_dynamic_bom(self, cr, uid, ids, context=None):
        ''' Open current BOM with dynamic rule
        '''
        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_product_product_dynamic_bom_form',
            )[1]
        tree_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_product_product_dynamic_bom_tree',
            )[1]
 
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dynamic BOM'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_id': ids[0],
            'res_model': 'product.product',
            'view_id': form_view_id,
            'views': [(form_view_id, 'form'), (tree_view_id, 'tree')],
            'domain': [],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }
       
    def check_mask_parameter_structure(self, dynamic_mask, structure):
        ''' 
        '''
        default_code = dynamic_mask.replace('%', '').replace('_', ' ').rstrip()
        
        error = '' 
        for block in structure.block_ids:
            part = default_code[block.from_char-1: block.to_char].strip()
            if part:
                not_found = True
                for v in block.value_ids:
                    if v.code == part:
                        not_found = False
                        break
                if not_found:
                    return _('Part %s not found in %s block') % (
                        part, block.name)
        return False
        
    def _get_dynamic_bom_line_ids(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate BOM lines
        '''
        _logger.error('Dynamic line calculation! JUST FOR TEST')
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
                res[product.id] = [item[0] for item in cr.fetchall()]
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

    def get_this_component_line(self, cr, uid, ids, context=None):
        ''' Utility for search lines with this product on this bom:
        '''
        line_proxy = self.browse(cr, uid, ids, context=context)[0]
        return self.search(cr, uid, [
            ('bom_id', '=', line_proxy.bom_id.id),            
            ('product_id', '=', line_proxy.product_id.id),
            ], context=context)        
            
        
    def component_use_this(self, cr, uid, ids, context=None):
        ''' List all line that has this compoment (for check rules)
        '''
        line_ids = self.get_this_component_line(cr, uid, ids, context=context)

        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_product_product_dynamic_button_bom_form',
            )[1]
        tree_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_mrp_bom_line_dynamic_tree',
            )[1]
        if len(line_ids) == 1:
            raise osv.except_osv(
                _('Warning'), 
                _('This is the only rule that use this component'),
                )
                
        return {
            'type': 'ir.actions.act_window',
            'name': _('Dynamic BOM component'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'mrp.bom.line',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }        

    def component_product_use_this(self, cr, uid, ids, context=None):
        ''' Search this compoment after all product with those masks
        ''' 
        # Search rule that use this component:
        line_ids = self.get_this_component_line(cr, uid, ids, context=context)
        # Search product that use those masks:
        return self.product_use_this_mask(cr, uid, line_ids, context=context)
        
    def product_use_this_mask(self, cr, uid, ids, context=None):
        ''' Check product that work with this rule
        '''
        #XXX  Used also for all product search (not only button event!)
        where = ''        
        for line_proxy in self.browse(cr, uid, ids, context=context):
            if not line_proxy.dynamic_mask:
                continue
            where += '%s%s' % (
                ' or ' if where else '',
                'default_code ilike \'%s\'' % line_proxy.dynamic_mask
                )
        if not where:
            raise osv.except_osv(
                _('Error!'), 
                _('No product with mask selected!'),
                )
                    
        cr.execute('''
            SELECT distinct id 
            FROM product_product 
            WHERE %s
            ''' % where)
        product_ids = [item[0] for item in cr.fetchall()]

        if not product_ids:
            raise osv.except_osv(
                _('Error!'), 
                _('No product with mask selected!'),
                )

        model_pool = self.pool.get('ir.model.data')
        form_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_product_product_dynamic_bom_form',
            )[1]
        tree_view_id = model_pool.get_object_reference(cr, uid, 
            'bom_dynamic_structured', 
            'view_product_product_dynamic_bom_tree',
            )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Dynamic BOM'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'product.product',
            'view_id': tree_view_id,
            'views': [(tree_view_id, 'tree'), (form_view_id, 'form')],
            'domain': [('id', 'in', product_ids)],
            'context': context,
            'target': 'current',
            'nodestroy': False,
            }
        
    def onchange_dynamic_mask(self, cr, uid, ids, dynamic_mask, bom_id,
            context=None):
        ''' Check mask if correct
        '''        
        bom_pool = self.pool.get('mrp.bom')
        product_pool = self.pool.get('product.product')

        res = {}
        if not dynamic_mask or not bom_id:
            return res
            
        bom_proxy = bom_pool.browse(cr, uid, bom_id, context=context)
        
        error = product_pool.check_mask_parameter_structure(
            dynamic_mask, bom_proxy.structure_id)
        if error:
            res['warning'] = {
                'title': _('Code error:'), 
                'message': _('Error parsing code: %s') % error,
                }
        return res
    
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
        search_view_id = model_pool.get_object_reference(cr, uid, 
           'bom_dynamic_structured', 
           'view_mrp_bom_line_search',
           )[1]

        return {
            'type': 'ir.actions.act_window',
            'name': _('Dynamic lines'),
            'view_type': 'form',
            'view_mode': 'tree',
            'res_model': 'mrp.bom.line',
            'view_id': tree_view_id,
            'search_view_id': search_view_id,
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
