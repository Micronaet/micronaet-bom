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

class MrpBomIndustrialCost(orm.Model):
    """ Model name: Industrial cost
    """
    
    _name = 'mrp.bom.industrial.cost'
    _description = 'Industrial cost'
    _order = 'name'

    # -------------------------------------------------------------------------    
    # Button event:
    # -------------------------------------------------------------------------    
    def open_load_detail_list(self, cr, uid, ids, context=None):
        ''' Open list in tree view
        '''
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')
        line_ids = line_pool.search(cr, uid, [
            ('cost_id', '=', ids[0]),
            ], context=context)
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detail for cost selected'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'mrp.bom.industrial.cost.line',
            #'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', line_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
            
    def load_detail_from_BOM(self, cr, uid, ids, context=None):
        ''' Load all mask list from bom selected
        '''
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Load current mask selected:
        current_mask = []
        for line in current_proxy.line_ids:
            current_mask.append(line.name)
        
        # Create only new elements:
        mask_ids = product_pool.search(cr, uid, [
            ('bom_selection', '=', True),
            ], context=context)
        if not mask_ids:
            raise osv.except_osv(
                _('Error:'), 
                _('Error product reference selected for BOM'),
                )
        for product in product_pool.browse(cr, uid, mask_ids, context=context):
            mask = '%s%%' % product.default_code
            if mask in current_mask:
                continue
                 
            line_pool.create(cr, uid, {
                'cost_id': current_proxy.id,
                'cost': current_proxy.default_cost,
                'name': mask,
                }, context=context) 
        return True
        
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'unit_cost': fields.float('Costo Unitario', digits=(16, 3),
            help='Default cost used when append imported BOM'),        
        'type': fields.selection([
            ('work', 'Manodopera'),
            ('industrial', 'Costi industriali'),
            ], 'Tipo'),
        'note': fields.text('Note'),
        # TODO REMOVE:
        'default_cost': fields.float('Default cost', digits=(16, 3),
            help='Default cost used when append imported BOM'),        
        }
    
    _defaults = {
        'type': lambda *x: 'industrial',
        }    

class MrpBomIndustrialCostLine(orm.Model):
    """ Model name: Cost line
    """
    
    _name = 'mrp.bom.industrial.cost.line'
    _description = 'Industrial cost line'
    _order = 'name'
    
    def _get_last_cost_info(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):            
            product = line.product_id
            res[line.id] = {}
            res[line.id]['last_cost'] = 0.0
            res[line.id]['last_date'] = False
            if not product:
                continue

            # Loop on sellers and pricelist:
            for seller in product.seller_ids:
                 for pricelist in seller.pricelist_ids: # XXX multi q. probl?
                     if not pricelist.is_active:
                         continue
                         
                     date_quotation = pricelist.date_quotation or False
                     if not res[line.id]['last_cost'] or \
                            date_quotation > res[line.id]['last_date']:
                         res[line.id]['last_cost'] = pricelist.price
                         res[line.id]['last_date'] = date_quotation
        return res
        
    _columns = {
        'name': fields.char('Mask', size=64, required=True, 
            help='Mask for code, use % for all, _ for replace one char'),
        'product_id': fields.many2one('product.product', 'Prodotto'),
        'uom_id': fields.related(
            'product_id', 'uom_id', 
            type='many2one', relation='product.uom', 
            string='UM', readonly=True),
        'cost_id': fields.many2one(
            'mrp.bom.industrial.cost', 'Cost'),            
        'qty': fields.float('Q.', digits=(16, 3), required=True),
        
        # Get product cost info:
        'last_cost': fields.function(
            _get_last_cost_info, method=True, 
            type='float', string='Costo ultimo', 
            store=False, multi=True, readonly=True), 
        'last_date': fields.function(
            _get_last_cost_info, method=True, 
            type='char', string='Data ultimo', 
            store=False, multi=True, readonly=True),
        }

class MrpBomIndustrialCost(orm.Model):
    """ Model name: Industrial cost
    """
    
    _inherit = 'mrp.bom.industrial.cost'
    
    _columns = {
        'line_ids': fields.one2many(
            'mrp.bom.industrial.cost.line', 'cost_id', 'Line'),
        }

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
            
    # -------------------------------------------------------------------------    
    # Utility function:
    # -------------------------------------------------------------------------    
    def get_cost_industrial_for_product(self, cr, uid, ids, context=None):
        ''' Return all list of industrial cost for product passed
            ids: product ids XXX now is one!
        '''
        # Pool used:
        line_pool = self.pool.get('mrp.bom.industrial.cost.line')
        
        product = self.browse(cr, uid, ids, context=context)[0]
        default_code = product.default_code
        if not default_code:
            return {}

        # Update category element priority order len mask
        query = '''
            SELECT id FROM mrp_bom_industrial_cost_line 
            WHERE '%s' ilike name ORDER BY length(name) desc;
            ''' % default_code
        cr.execute(query)

        # XXX 28/10/2017 Changed for report use:
        res = {}
        item_ids = [item[0] for item in cr.fetchall()]
        for item in line_pool.browse(
                cr, uid, item_ids, context=context):
            if item.cost_id in res:
                continue
            res[item.cost_id] = item    
        return res

    # -------------------------------------------------------------------------
    # Button for select
    # -------------------------------------------------------------------------
    def bom_selection_on(self, cr, uid, ids, context=None):
        '''
        '''
        return self.write(cr, uid, ids, {
            'bom_selection': True,          
            }, context=context)

    def bom_selection_off(self, cr, uid, ids, context=None):
        '''
        '''
        return self.write(cr, uid, ids, {
            'bom_selection': False,            
            }, context=context)                
            
    _columns = {
        'bom_selection': fields.boolean('BOM Selection'),
        'from_industrial': fields.float(
            'From industrial cost', digits=(16, 3)),
        'to_industrial': fields.float(
            'To industrial cost', digits=(16, 3)),
        'industrial_missed': fields.boolean('Manca', 
            help='Manca prezzo di alcuni componenti'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
