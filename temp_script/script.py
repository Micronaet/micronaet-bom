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

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    _inherit = 'res.company'

    # Procedure:    
    def create_dynamic_rule(self, cr, uid, ids, context=None):
        ''' Create rule for MT MS
        '''
        log_file = '/home/administrator/photo/log/materassini_MT_MS.log'
        
        # Search dynamic BOM:
        bom_pool = self.pool.get('mrp.bom')
        line_pool = self.pool.get('mrp.bom.line')
        bom_ids = bom_pool.search(cr, uid, [
            ('bom_category', '=', 'dynamic')
            ], context=context)
        if not bom_ids:
            raise osv.except_osv(
                _('BOM Error'), 
                _('No dynamic bom'),
                )    
        dynamic_id = bom_ids[0]        

        # Search category:
        category = 'Materassino'
        category_pool = self.pool.get('mrp.bom.structure.category')
        category_ids = category_pool.search(cr, uid, [
            ('name', '=', category)
            ], context=context)
        if not category_ids:
            raise osv.except_osv(
                _('BOM Error'), 
                _('No category %s' % category),
                )    
        category_id = category_ids[0]        
                
        # Search all MT product    
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('default_code', '=ilike', 'MT%')], context=context)        
        comment = _('Product|Component|Mask|Note\n')

        for product in product_pool.browse(
                cr, uid, product_ids, context=context):   
            # Generate code:    
            default_code = product.default_code
            dynamic_mask = '%s%%' % default_code[:12] # no 13 char (S)
            hw_code = 'MS%s' % default_code[2:]
            
            # Search HW code
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', hw_code)], context=context)
            
            if not product_ids: # Product HW not found!
                comment += '%s|%s|%s|%s\n' % (
                    default_code,
                    hw_code,
                    dynamic_mask,
                    _('No HW component found!'),
                    )
                continue
            product_id = product_ids[0]    
            # more than one raise?    
                
            # Search dynamic rule for product-component:
            line_ids = line_pool.search(cr, uid, [
                ('bom_id', '=', dynamic_id),
                ('dynamic_mask', '=', dynamic_mask),
                ('product_id', '=', product_id),
                ], context=context)
            if line_ids: 
                # rule present
                comment += '%s|%s|%s|%s\n' % (
                    default_code,
                    hw_code,
                    dynamic_mask,
                    _('Yet present!'),
                    )
            else:
                # Create rule
                line_pool.create(cr, uid, {
                    'bom_id': dynamic_id,
                    'product_id': product_id,
                    'dynamic_mask': dynamic_mask,
                    'product_uom': 1, # XXX
                    'product_qty': 1.0,     
                    'category_id': category_id,               
                    }, context=context)
                
                comment += '%s|%s|%s|%s\n' % (
                    default_code,
                    hw_code,
                    dynamic_mask,
                    _('New rule'),
                    )
                    
        # Write log:            
        f_log = open(log_file, 'w')        
        f_log.write(comment)
        return True
        
    def check_bom_half_error_linked(self, cr, uid, ids, context=None):
        ''' Check error during operation on bom
        '''
        # Pool used:
        product_pool = self.pool.get('product.product')

        # Reset selection:
        temp_ids = product_pool.search(cr, uid, [
            ('temp_selection', '=', True)], context=context)
        if temp_ids:  
            product_pool.write(cr, uid, temp_ids, {
                'temp_selection': False}, context=context)
            _logger.warning('Uncheck %s product record' % len(temp_ids))
            
        # Check HW bon link:
        product_ids = product_pool.search(cr, uid, [
            ('relative_type', '=', 'half')], context=context)
        temp_ids = []
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):        
            # XXX Now also empty elements?        
            if product.half_bom_id.halfwork_id.id != product.id:
                temp_ids.append(product.id)
        
        # Update temp selection
        _logger.warning('Check %s product record' % len(temp_ids))
        return product_pool.write(cr, uid, temp_ids, {
            'temp_selection': True}, context=context)
        
    def generate_pipe_from_hw(self, cr, uid, ids, context=None):
        ''' Import hw component, output pipe
        '''
        in_file = '/home/administrator/photo/import_tubi.csv'
        out_file = '/home/administrator/photo/output_tubi.csv'
        separator = '|'
        
        f_in = open(in_file, 'r')
        f_out = open(out_file, 'w')
        
        # Pool used:
        product_pool = self.pool.get('product.product')
        
        i = 0
        _logger.info('Start read: %s' % in_file)
        _logger.info('Start out: %s' % out_file)
        for line in f_in:
            i += 1
            line = line.strip().split(separator)
            if len(line) != 3:
                _logger.error('Column error')
                continue
                
            # Read columns:    
            bom = line[0]
            hw = line[1]  
            quantity = line[2]
            
            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', hw),
                ('relative_type', '=', 'half'),
                ], context=context)
            if not product_ids:
                _logger.error('No HW code: %s' % hw)
                continue    

            if len(product_ids) > 1:
                _logger.warning('More HW code: %s' % hw)
                #continue
            
            product_proxy = product_pool.browse(
                cr, uid, product_ids, context=context)[0]
            f_out.write('%s|%s\n' % (
                product_proxy.half_bom_ids[0].product_id.default_code,
                quantity,
                ))

        _logger.info('End read: %s > %s' % (in_file, out_file))

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'
    
    _columns = {
        'temp_selection': fields.boolean('Temp selection'),
        }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
