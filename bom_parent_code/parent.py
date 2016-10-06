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
        import pdb; pdb.set_trace()
        line_pool = self.pool.get('mrp.bom.line')
        
        # Create rule in dynamic:
        bom_proxy = self.browse(cr, uid, ids, context=context)[0]
        structure_id = bom_proxy.product_id.structure_id.id or 1 # XXX
        
        for line in bom_proxy.bom_line_ids:
            line_pool.create(cr, uid, {
                'bom_id': structure_id.dynamic_bom_id.id,
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
