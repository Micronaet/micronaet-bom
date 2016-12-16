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
import pickle
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

class ClassNameCamelCase(orm.Model):
    """ Model name: ClassNameCamelCase
    """
    
    _inherit = 'product.product.import.inventory'

    filename = '/home/administrator/photo/xls/inventory' # TODO parametrize
    
    def action_correct_delta_from_csv(self, cr, uid, ids, context=None):
        ''' Generate report status for delta inventory
            Read files for get product
        '''
        if context is None:
            context = {}
            
        # Pool used:
        product_pool = self.pool.get('product.product')
        mrp_pool = self.pool.get('mrp.production')
        error = ''
        note = ''
        
        current_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        # ---------------------------------------------------------------------
        # Read parameters:
        # ---------------------------------------------------------------------
        fullname = current_proxy.fullname
        max_line = current_proxy.max_line
        
        # Pickle part for speedup during debug:
        use_pickle = False # TODO change
        pickle_file = os.path.expanduser('~/pickle.store')

        # Init check:
        if not fullname:
            raise osv.except_osv(
                _('Import error'), 
                _('Need a file name to import in path %s' % fullname),
                )
        
        # Log activity:        
        _logger.info('Start import delta product form: %s' % self.filename)

        # ---------------------------------------------------------------------
        # Generate movement database:
        # ---------------------------------------------------------------------
        if use_pickle:            
            product_movement = pickle.load(
                open(pickle_file, 'wb'))
        else:
            
            _logger.info('Read halfworked data type')    
            
            # Call report for halfwork:
            data = {
                'mode': 'halfwork',
                'for_inventory_delta': True,
                }
            
            product_movement = mrp_pool.get_explode_report_object(
                cr, uid, data=data, context=context)

            # Call report for component:
            _logger.info('Read component data type')    
            data['type'] = 'component'
            product_movement.update(
                mrp_pool.get_explode_report_object(
                    cr, uid, data=data, context=context))
     
            pickle.dump(
                product_movement, 
                open(pickle_file, 'wb'),
                )

        # Read excel filename:
        try:
            filename = os.path.join(self.filename, fullname)
            wb = xlrd.open_workbook(filename)
            ws = wb.sheet_by_index(0)
        except:
            raise osv.except_osv(
                _('Open file error'), 
                _('Cannot found file: %s (or file not in correct format' % \
                    filename),
                )  

        # Loop on line:
        for i in range(0, max_line):
            try:
                row = ws.row(i) # generate error at end
            except:
                # Out of range error ends import:
                note += _('Import end at line: %s\n') % i
                break

            try:
                # Loop on colums (trace)
                try:
                    default_code = str(row[0].value).replace('.0', '')
                except:
                    default = ''
                    
                # Search product with code:
                if not default_code:
                    error += _('%s. No default code on file found\n') % i
                    continue # jump

                try:
                    product_qty = float(row[1].value)
                except:
                    product_qty = 0

                product_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', default_code)], context=context)
                
                if not product_ids:
                    error += _(
                        '%s. Error code not found, code: %s\n') % (
                            i, default_code)
                    continue # jump                

                elif len(product_ids) > 1:
                    error += _(
                        '%s. Warning more code (take first), code: %s\n') % (
                            i, default_code)
                record = product_movement.get(default_code, False)
                if record:                  
                    inventory_delta = product_qty - \
                        sum((
                            record[3], # SAL value
                            - record[1], # negative OC value
                            - record[2], # positive OF value                        
                            
                            #- record[0], # XXX no inventory start (yet delta)
                            )) + record[4] # Delta yet present        
                    note += '%s | %s | %s (previous: %s)\n' % (
                        i, default_code, inventory_delta, 
                        record[4])
                        
                else:
                    inventory_delta = product_qty 
                    note += '%s. %s NO DATA (set as start)!!!\n' % (
                        i, default_code)
                           
                product_pool.write(cr, uid, product_ids[0], {
                    'inventory_delta': inventory_delta,
                    }, context=context)                              
                    
            except:
                error += _('%s. Import error code: %s [%s]\n') % (
                    i, default_code, sys.exc_info())
                    
        self.write(cr, uid, ids, {
            'error': error,
            'note': 'File: %s\n%s' % (
                filename, note),
            }, context=context)

        _logger.info('End import Delta product: %s' % fullname)
        return True        
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
