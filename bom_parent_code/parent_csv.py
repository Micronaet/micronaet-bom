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
    """ Model name: MRP Bom
    """    
    _inherit = 'mrp.bom'

    # EXTRA BLOCK -------------------------------------------------------------
    def migrate_assign_product_bom_product_csv(self, cr, uid, ids, 
            context=None):
        ''' Migrate bom in dynamic way
            Create half work element
            Create BOM 
            Create move in dynamic
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        # Pool used
        line_pool = self.pool.get('mrp.bom.line')
        product_pool = self.pool.get('product.product')

        csv = open('/home/administrator/photo/bom.csv', 'r')
        #structure = bom_proxy.product_id.structure_id
        
        i = 0
        HW_codes = []
        fabric_uom = 8 # m.
        structure_id = 1 # TODO needed?
        dynamic_bom_id = 7366 # bom_category = dynamic
        
        for row in csv:
            i += 1
            item = row.split('|')            
            if len(item) != 7:
                _logger.error('Different colums')
                continue
            
            # Read line parameter:
            import pdb; pdb.set_trace()
            bom_id = int(item[0])
            default_code = item[1].upper().strip()
            fabric_id = int(item[2])
            fabric_code = item[3].upper().strip()
            product_qty = float(item[4].replace(',', '.'))
            component_code = item[5].strip()
            category_id = int(item[6]) # always present?

            # Mask for S or not S (same)
            if default_code[12:13] == 'S':
                dynamic_mask = default_code[:12] + '%'
            else:
                dynamic_mask = default_code + '%'

            # -----------------------------------------------------------------
            # Create HW element:
            # -----------------------------------------------------------------
            if not component_code:
                _logger.error('%s Code component empty' % i)
                continue
            
            # TODO Decidere se creare il solo semilavorato oppure continuare
            if component_code in HW_codes:
                _logger.error('%s Code component yet present: %s' % (
                    i, component_code))
                continue

            component_ids = product_pool.search(cr, uid, [
                ('default_code', '=', component_code),
                #XXX('relative_type', '=', 'half'),
                ], context=context)

            if component_ids:
                _logger.error('%s Code component yet present' % (   
                    i, component_code))
                # Update as half    
                product_pool.write(cr, uid, component_ids, {
                    'relative_type': 'half',
                    }, context=context)    
                continue                

            HW_id = product_pool.create(cr, uid, {
                'name': component_code,
                'default_code': component_code,
                'relative_type': 'half',       
                'structure_id': structure_id,
                'uom_id': 1, # XXX NR
                'ean13_auto': False,
                }, context=context)
            HW_codes.append(component_code)
            HW_proxy = product_pool.browse(
                cr, uid, HW_id, context=context)  
             
            # TODO check yet present material:
            #exist = line_pool.search(cr, uid, [
            #    ('bom_id', '=', HW_proxy.half_bom_id.id),
            #    ('halfwork_id', '=', HW_proxy.id),
            #    ('product_id', '=', fabric_id),
            #    ('product_qty', '=', product_qty),
            #    ], context=context)
            # Create HW Bom with button:
            product_pool.create_product_half_bom(
                cr, uid, [HW_id], context=context)
            # Re-read record    
            HW_proxy = product_pool.browse(
                cr, uid, HW_id, context=context)                
                
            line_pool.create(cr, uid, {
                # Link:
                'bom_id': HW_proxy.half_bom_id.id, # bom link
                'halfwork_id': HW_proxy.id, # product link
                
                # Fabric data:
                'product_id': fabric_id, 
                'product_uom': fabric_uom, 
                #'type': line.type,
                'product_qty': product_qty,
                }, context=context)

            # -------------------------------------------------------------
            # Create / Update rule in dynamic:
            # -------------------------------------------------------------
            #line_ids = line_pool.search(cr, uid, [
            #    ('bom_id', '=', dynamic_bom_id), # dynamic bom for structure
            #    ('dynamic_mask', '=', dynamic_mask), # mask
            #    ('category_id', '=', category_id),
            #    ('product_id', '=', HW_proxy.id),
            #    ], context=context)
            #if not line_ids: # Update or check
            line_pool.create(cr, uid, {
                'bom_id': dynamic_bom_id,
                'dynamic_mask': dynamic_mask,
                'category_id': category_id,
                'product_id': HW_proxy.id, 
                'product_uom': HW_proxy.uom_id.id, 
                'product_qty': 1, # always!
                'type': 'normal',
                }, context=context)
            self.write(cr, uid, bom_id, {
                'bom_category': 'remove',
                }, context=context)
        return
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: