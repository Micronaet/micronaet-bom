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

class MRPBom(orm.Model):
    """ Model name: MRPBom
    """    
    _inherit = 'mrp.bom'

    # EXTRA BLOCK -------------------------------------------------------------
    def migrate_assign_parent_bom(self, cr, uid, ids, context=None):
        ''' Migrate bom in dynamic way
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        line_pool = self.pool.get('mrp.bom.line')
        
        # Create rule in dynamic:
        bom_proxy = self.browse(cr, uid, ids, context=context)[0]
        structure = bom_proxy.product_id.structure_id
        
        for line in bom_proxy.bom_line_ids:
            line_pool.create(cr, uid, {
                'bom_id': structure.dynamic_bom_id.id,
                'product_id': line.product_id.id,
                'dynamic_mask': '%s%s' % (bom_proxy.product_id.code, '%'),
                'product_qty': line.product_qty,
                'product_uom': line.product_uom.id,                                
                }, context=context)
        
        # Move in to be remove category
        self.write(cr, uid, ids, {
            'bom_category': 'remove',
            }, context=context)
        return True

    def migrate_assign_product_bom_product(self, cr, uid, ids, context=None):
        ''' Loop button:
        '''
        product_pool = self.pool.get('product.product')
        
        product_ids = self.search(cr, uid, [
            ('bom_category', '=', 'product')], context=context)

        # LOG operation (TODO remove)
        log_f = open(os.path.expanduser('~/bom.csv'), 'w')

        dimension_db = {}        
        for item in product_ids:
            message = self.migrate_assign_product_bom_product1(
                cr, uid, [item], dimension_db, context=context)
            log_f.write(message)    
        log_f.close()        
        return True    
        
    def migrate_assign_product_bom_product1(self, cr, uid, ids, dimension_db, 
            context=None):
        ''' Migrate bom in dynamic way
            Create half work element
            Create BOM 
            Create move in dynamic
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        line_pool = self.pool.get('mrp.bom.line')
        product_pool = self.pool.get('product.product')
        
        bom_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        log = ''
        # ---------------------------------------------------------------------
        # Create dynamic mask from code:
        # ---------------------------------------------------------------------
        if not bom_proxy.product_id:
            pr_ids = product_pool.search(cr, uid, [
                ('product_tmpl_id', '=', bom_proxy.product_tmpl_id.id),
                ], context=context)
            if pr_ids:
                default_code = product_pool.browse(
                    cr, uid, pr_ids, context=context)[0]
        default_code = bom_proxy.product_id.default_code
        if not default_code:
            log += '\n???|%s||%s|No codice x BOM\n' % ( 
                len(bom_proxy.bom_line_ids),
                bom_proxy.name,
                )
            return log
        
        # Set mask for unique element S and no S are the same
        if default_code[12:13] == 'S':
            dynamic_mask = default_code[:12] + '%'
        else:
            dynamic_mask = default_code + '%'
        log += '\n%s|%s|%s|%s\n' % (
            default_code, 
            len(bom_proxy.bom_line_ids),
            dynamic_mask, 
            bom_proxy.name or '???', # or bom_proxy.product_tmpl_id.name, 
            )
        
        # TODO Check if dynamic and product are jet present
        
        # ---------------------------------------------------------------------
        # Create TL element:
        # ---------------------------------------------------------------------
        for line in bom_proxy.bom_line_ids:
            component_code = line.product_id.default_code
            if not component_code:
                log += '|||%s||No codice componente\n' % bom_proxy.name
                return log
                
            TL_code = 'TL%s%s%s' % (
                default_code[:3],
                default_code[3:6],
                default_code[8:12],
                )
            component_ids = product_pool.search(cr, uid, [
                ('default_code', '=', TL_code)], context=context)
            
            # check dimemnsion:
            product_qty = line.product_qty
            if TL_code not in dimension_db:
               dimension_db[TL_code] = product_qty
            
            if product_qty != dimension_db[TL_code]:
                comment = 'Differenze di metratura!!!!'
            else:
                comment = ''
            if component_ids:
                if len(component_ids) > 1:
                    log += '||||%s|%s|%s|Piu componenti|NO|%s\n' % (
                        component_code, TL_code, product_qty, comment)
                else:
                    log += '||||%s|%s|%s||SI|%s\n' % (
                        component_code, TL_code, product_qty, comment)
            else:        
                log += '||||%s|%s|%s|Non trovato in ODOO|%s|NO\n' % (
                    component_code, TL_code, product_qty, comment)
        print log        
        return log            

        # ---------------------------------------------------------------------
        # Create TL BOM:
        # ---------------------------------------------------------------------
        
        
        # ---------------------------------------------------------------------
        # Create rule in dynamic:
        # ---------------------------------------------------------------------
        structure = bom_proxy.product_id.structure_id
                
        #for line in bom_proxy.bom_line_ids:
        #    line_pool.create(cr, uid, {
        #        'bom_id': structure.dynamic_bom_id.id,
        #        'product_id': line.product_id.id,
        #        'dynamic_mask': '%s%s' % (bom_proxy.product_id.code, '%'), # TODO remove S finale
        #        'product_qty': line.product_qty,
        #        'product_uom': line.product_uom.id,                                
        #        }, context=context)
        
        # Move in to be remove category
        #self.write(cr, uid, ids, {
        #    'bom_category': 'remove',
        #    }, context=context)
        return True
    # EXTRA BLOCK -------------------------------------------------------------
        
    def get_config_parameter_list(self, cr, uid, context=None):
        ''' Read parameter: 
        '''    
        key = 'product.default.product.parent.bom'
        config_pool = self.pool.get('ir.config_parameter')
        config_ids = config_pool.search(cr, uid, [
            ('key', '=', key)], context=context)
        if not config_ids:
            _logger.warning('Parameter not found: %s' % key)
            return []
        config_proxy = config_pool.browse(
            cr, uid, config_ids, context=context)[0]
        return eval(config_proxy.value)    
    
    def assign_parent_bom(self, cr, uid, ids, context=None):
        ''' Assign bom depend on code format
        '''    
        bom_code_split = self.get_config_parameter_list(
            cr, uid, context=context)
        if not bom_code_split:
            raise osv.except_osv(
                _('Error'), 
                _('Setup config paremeter!'))
            
        bom_proxy = self.browse(cr, uid, ids, context=context)[0]
        default_code = bom_proxy.product_id.default_code
        if not default_code:
            raise osv.except_osv(
                _('Error'), 
                _('No default code in product!'))

        bom_ids = False        
        for to in bom_code_split:  
            if len(default_code) <= to:
                continue
            partial = default_code[0:to]
            bom_ids = self.search(cr, uid, [
                ('bom_category', '=', 'half'), 
                ('product_id.default_code', '=', partial),
                ], context=context)
            if bom_ids:
                break
                
        if not bom_ids:
            raise osv.except_osv(
                _('Error'), 
                _('No default code in product!'))
                
        if len(bom_ids) > 1:
            _logger.error('Found more parent bom!')
                
        return self.write(cr, uid, ids, {
            'subparent_id': bom_ids[0],
            }, context=context)        
    
    _columns = {
        'subparent_id': fields.many2one(
            'mrp.bom', 'Sub parent bom'),        
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
