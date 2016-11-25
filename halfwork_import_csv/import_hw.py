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

class ImportHalfworkedProductComponent(orm.TransientModel):
    """ Model name: Import wizard
    """    
    _inherit = 'import.halfworked.product.component.wizard'

    def import_halfworked_product_and_component(self, cr, uid, ids, 
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

        csv = open('/home/administrator/photo/hw.csv', 'r')
        ean_13_auto = False # TODO
        
        # UOM database:
        cr.execute('select min(id), name from product_uom group by name;')
        uom_db = {}
        import pdb; pdb.set_trace()
        for item in cr.fetchall():
            uom_db[item[1]] = item[0]
            
        i = 0
        for row in csv:
            i += 1
            item = row.split('|')            
            if len(item) != 6:
                _logger.error('Different colums')
                continue
            
            # Read line parameter:
            hw_code = item[0].upper().strip()
            hw_name = item[1].strip()
            hw_uom_id = 1 # XXX
            cmpt_code = item[2].upper().strip()
            cmpt_name = tem[3].strip()
            cmpt_uom_id = item[4].strip()
            product_qty = float(item[5].replace(',', '.'))

            # -----------------------------------------------------------------
            #                      Create component:
            # -----------------------------------------------------------------
            if not cmpt_code:
                _logger.error('%s Code component empty' % i)
                continue

            cmpt_ids = product_pool.search(cr, uid, [
                ('default_code', '=', cmpt_code)], context=context)
            if cmpt_ids:
                cmpt_id = cmpt_ids[0]
                if len(cmpt_ids) > 1:
                    _logger.error('More than one cmpt: %s' % cmpt_code)
            else:
                cmpt_id = product_pool.create(cr, uid, {
                    'name': cmpt_name,
                    'uom_id': cmpt_uom_id,
                    'uos_id': cmpt_uos_id,
                    'uom_po_id': cmpt_uom_po_id,
                    'default_code': cmpt_code,
                    'ean_13_auto': ean_13_auto,
                    }, context=context)
                _logger.warning('Create component: %s' % cmpt_code)
                
            # -----------------------------------------------------------------
            #                      Create HW element:
            # -----------------------------------------------------------------
            if not hw_code:
                _logger.error('%s Code hw empty' % i)
                continue
            
            hw_ids = product_pool.search(cr, uid, [
                ('default_code', '=', hw_code),
                ('relative_type', '=', 'half'),
                ], context=context)

            if hw_ids:
                if len(hw__ids) > 1:
                    _logger.error('More than one hw_: %s' % hw__code)
                HW_id = component_ids[0]
            else:    
                HW_id = product_pool.create(cr, uid, {
                    'name': hw_code,
                    'default_code': hw_code,
                    'relative_type': 'half',       
                    'structure_id': structure_id,
                    'uom_id': hw_uom_id,
                    'ean13_auto': ean13_auto,
                    }, context=context)

            # Read current HW:
            HW_proxy = product_pool.browse(
                cr, uid, HW_id, context=context)  
         
            # Check yet present material:
            exist = line_pool.search(cr, uid, [
                ('bom_id', '=', HW_proxy.half_bom_id.id),
                ('halfwork_id', '=', HW_proxy.id),
                ('product_id', '=', cmpt_id),
                ('product_qty', '=', product_qty),
                ], context=context)
            
            # Create HW Bom with button:
            if exist: 
                _logger.warning('%s Esist: %s' % (i, cmpt_code))
            else:
                # Generate linked bom press the button:
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
                    'product_id': cmpt_id, 
                    'product_uom': cmpt_uom_id, 
                    'product_qty': product_qty,
                    }, context=context)
        return True
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
