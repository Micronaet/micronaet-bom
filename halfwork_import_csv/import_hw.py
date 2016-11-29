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
    _name = 'import.halfworked.product.component.wizard'

    _columns = {
        'start_with': fields.boolean('Start with'),
        }
        
    def import_halfworked_product_and_component(self, cr, uid, ids, 
            context=None):
        ''' Migrate bom in dynamic way
            Create half work element
            Create BOM 
            Create move in dynamic
        '''
        assert len(ids) == 1, 'Works only with one record a time'

        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # Pool used
        line_pool = self.pool.get('mrp.bom.line')
        product_pool = self.pool.get('product.product')
        structure_id = 1 # XXX

        file_csv = '/home/administrator/photo/hw/hw.csv'    
        file_log = '/home/administrator/photo/hw/hw.log'
        
        try:
            csv = open(file_csv, 'r')
        except:
            raise osv.except_osv(
                _('Open file'), 
                _('Error opening file: %s' % file_csv),
                )
        log = open(file_log, 'w')
                
        ean13_auto = False # TODO
        
        # UOM database:
        cr.execute('select min(id), name from product_uom group by name;')
        uom_db = {}
        for item in cr.fetchall():
            uom_db[item[1].upper()] = item[0]
            
        i = 0
        hw_selected = []

        for row in csv:
            i += 1
            item = row.split('|')            
            if len(item) != 7:
                log.write('%s. Different colums\n' % i)
                continue
            
            # Read line parameter:
            hw_code = item[0].upper().strip()
            hw_name = item[1].strip()
            hw_uom_id = uom_db.get(item[2].upper(), 1) # XXX default 1
            cmpt_code = item[3].upper().strip()
            cmpt_name = item[4].strip()
            cmpt_uom_id = uom_db.get(item[5].upper(), 1) # XXX default 1
            product_qty = float(item[6].replace(',', '.'))
            
            # Mandatory fields:
            if not cmpt_uom_id:
                log.write('%s UOM non correct for component: %s\n' % (
                    i, item[5]))
                continue
            # -----------------------------------------------------------------
            #                      Create component:
            # -----------------------------------------------------------------
            cmpt_ids = product_pool.search(cr, uid, [
                ('default_code', '=', cmpt_code)], context=context)
                
            if cmpt_ids:
                cmpt_id = cmpt_ids[0]
                if len(cmpt_ids) > 1:
                    log.write('%s More than one cmpt: %s %s\n' % (
                        i, cmpt_code))
            else:
                if not cmpt_code:
                    log.write('%s Code component empty\n' % i)
                    continue
                cmpt_id = product_pool.create(cr, uid, {
                    'name': cmpt_name,
                    'uom_id': cmpt_uom_id,
                    'uos_id': cmpt_uom_id,
                    'uom_po_id': cmpt_uom_id,
                    'default_code': cmpt_code,
                    'ean13_auto': ean13_auto,
                    }, context=context)
                log.write('%s Create component: %s\n' % (i, cmpt_code))
                
            # -----------------------------------------------------------------
            #                      Create HW element:
            # -----------------------------------------------------------------
            if not hw_code:
                log.write('%s Code hw empty\n' % i)
                continue

            domain = [
                ('relative_type', '=', 'half'),
                ]
            if wiz_proxy.start_with:
                domain.append(
                    ('default_code', '=ilike', '%s%%' % hw_code),
                    )
            else:        
                domain.append(
                    ('default_code', '=', hw_code),
                    )
            
            hw_ids = product_pool.search(cr, uid, domain, context=context)

            if hw_ids:
                if not wiz_proxy.start_with and len(hw_ids) > 1:
                    log.write('%s More than one hw: %s\n' % (i, hw_code))
            else:
                if wiz_proxy.start_with:
                    # No creation
                    continue
                    
                hw_ids = [product_pool.create(cr, uid, {
                    'name': hw_name,
                    'default_code': hw_code,
                    'relative_type': 'half',       
                    'structure_id': structure_id,
                    'uom_id': hw_uom_id,
                    'ean13_auto': ean13_auto,
                    }, context=context),
                    ]
                    
            _logger.warning('# product %s > %s: %s' % (
                hw_code, cmpt_code, len(hw_ids)))
            for hw_id in hw_ids:
                if hw_id not in hw_selected:
                    hw_selected.append(hw_id) # for show esit                    
            
                # Read current HW:
                HW_proxy = product_pool.browse(
                    cr, uid, hw_id, context=context)  
                _logger.info('Manage product %s' % HW_proxy.default_code)    
             
                # Check yet present material:
                exist = line_pool.search(cr, uid, [
                    ('bom_id', '=', HW_proxy.half_bom_id.id),
                    ('halfwork_id', '=', HW_proxy.id),
                    ('product_id', '=', cmpt_id),
                    ('product_qty', '=', product_qty),
                    ], context=context)
                
                # Create HW Bom with button:
                if exist:
                    log.write('%s Exist: %s > %s\n' % (
                        i, hw_code, cmpt_code))
                else:
                    # Generate linked bom press the button:
                    product_pool.create_product_half_bom(
                        cr, uid, [hw_id], context=context)
                        
                    # Re-read record    
                    HW_proxy = product_pool.browse(
                        cr, uid, hw_id, context=context)                
                        
                    line_pool.create(cr, uid, {
                        # Link:
                        'bom_id': HW_proxy.half_bom_id.id, # bom link
                        'halfwork_id': HW_proxy.id, # product link
                        
                        # Fabric data:
                        'product_id': cmpt_id, 
                        'product_uom': cmpt_uom_id, 
                        'product_qty': product_qty,
                        }, context=context)
                    log.write('%s Create bom line: %s > %s\n' % (
                        i, hw_code, cmpt_code))

        return {
            'type': 'ir.actions.act_window',
            'name': _('HW created'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'product.product',
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', hw_selected)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
