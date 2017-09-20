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
import xlrd
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

class PurchaseOrderXLSX(orm.Model):
    """ Model name: PurchaseOrderXLSX
    """    
    _name = 'purchase.order.xlsx'
    _description = 'Imported order'
    _rec_name = 'name'
    _order = 'name'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_import_order(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        # Pool used:
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('purchase.order.xlsx.line') 
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        xslx_id = current_proxy.id
        month_db = {
            # Previous year:
            2: '09', 3: '10', 4: '11', 5: '12',
            
            # Next year:
            6: '01', 7: '02', 8: '03', 9: '04', 10: '05', 11: '06', 
            12: '07', 13: '08',
            }
            
        # Parameters:    
        row_start = 0            
        month_current = datetime.now().month
        year_current =  datetime.now().year
        if month_current in [9, 10, 11, 12]:
            year_a = year_current
            year_b = year_current + 1
        else: # 1 > 8
            year_a = year_current - 1
            year_b = year_current
            
        # TODO import procedure
        filename = '/home/thebrush/Scrivania/Stato_tessuti_inventario_parziale.xlsx' # TODO save from binary
        
        # ---------------------------------------------------------------------
        # Load force name (for web publish)
        # ---------------------------------------------------------------------
        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )
                
        WS = WB.sheet_by_index(0)        

        pos = -1
        for row in range(row_start, WS.nrows):
            pos += 1
            if pos == 1: 
                # -------------------------------------------------------------
                # Read product code:
                # -------------------------------------------------------------
                default_code = WS.cell(row, 0).value
                _logger.info('Find material: %s' % default_code)

                product_id = False           
                  
                # Manage code error:
                if not default_code:
                    _logger.error('No material code')
                    continue

                # Search product:
                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', default_code)
                    ], context=context)
                    
                # Manage product error:
                if not product_ids: 
                    _logger.error('No product with code: %s' % default_code)
                    continue
                    
                # TODO manage warning more than one product
                elif len(product_ids) > 1:
                    _logger.error('More material code: %s' % default_code)
                    pass # TODO multi code
                
                product_id = product_ids[0]    
                product_proxy = product_pool.browse(cr, uid, product_id, 
                    context=context)

                # -------------------------------------------------------------
                # Search supplier:
                # -------------------------------------------------------------
                # 1. Procurements:
                if product_proxy.seller_ids:
                    partner_id = product_proxy.seller_ids[0].name.id
                
                # 2. First supplier
                elif product_proxy.first_supplier_id:
                    partner_id = product_proxy.first_supplier_id.id
                else:   
                    partner_id = False                    
                    
            elif pos == 6: # order qty                
                # -------------------------------------------------------------
                # Read quantity and get deadline:
                # -------------------------------------------------------------
                for col in range(2, 14):
                    quantity = WS.cell(row, col).value
                    if not quantity:
                        continue
                    
                    month = month_db[col]
                    day = '01' # TODO Parameterize (wizard data)
                    if month in ['09', '10', '11', '12']:
                        year = year_a
                    else:
                        year = year_b    
                    
                    line_pool.create(cr, uid, {
                        'xlsx_id': ids[0],
                        'product_id': product_id,
                        'partner_id': partner_id,
                        'quantity': quantity,
                        'deadline': '%s-%s-%s' % (year, month, day),
                        }, context=context)
            elif pos in (7, 8) and not WS.cell(row, 0).value:
                _logger.warning('Reset pos, row: %s' % row)
                pos = -1            

        # Update status of import record
        return self.write(cr, uid, ids, {
            'mode': 'imported',
            }, context=context)
    
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'file': fields.binary('XLSX file', filters=None),
        'mode': fields.selection([
            ('draft', 'Draft'),
            ('imported', 'Imported'),
            ('created', 'Created'),            
            ], 'Mode'),
        }
    
    _defaults = {
       'name': lambda *a: _('Imported: %s') % datetime.now().strftime(
            DEFAULT_SERVER_DATE_FORMAT),
        'mode': lambda *x: 'draft',
        }

class PurchaseOrderXLSXLine(orm.Model):
    """ Model name: PurchaseOrderXLSX Line
    """
    
    _name = 'purchase.order.xlsx.line'
    _description = 'Imported order line'
    _rec_name = 'product_id'
    _order = 'sequence'
    
    _columns = {
        'sequence': fields.integer('Sequence'),
        'product_id': fields.many2one(
            'product.product', 'Product'),
        'deadline': fields.date('Deadline'),
        'partner_id': fields.many2one('res.partner', 'Supplier'),
        'quantity': fields.float('Q.ty', digits=(16, 3)),
        'xlsx_id': fields.many2one(
            'purchase.order.xlsx', 'Import wizard', 
            required=False),
        }
    
class PurchaseOrderXLSX(orm.Model):
    """ Model name: PurchaseOrderXLSX
    """    
    _inherit = 'purchase.order.xlsx'
    
    _columns = {
        'line_ids': fields.one2many(
            'purchase.order.xlsx.line', 'xlsx_id', 'Line'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
