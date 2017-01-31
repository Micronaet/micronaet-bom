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
import xlsxwriter
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
from inventory_present import product_present

_logger = logging.getLogger(__name__)

class ResCompany(orm.Model):
    """ Model name: ResCompany
    """
    _inherit = 'res.company'

    def force_first_supplier(self, cr, uid, ids, context=None):
        ''' Force first supplier
        '''
        product_pool = self.pool.get('product.product')        
        product_ids = product_pool.search(cr, uid, [], context=context)            
        first_supplier = {}
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            old_date = False
            supplier_id = False
            for seller in product.seller_ids:
                for pl in seller.pricelist_ids:
                    current_date = pl.write_date
                    if not old_date or old_date < current_date:
                        old_date = current_date
                        supplier_id = seller.name.id
            if supplier_id:
                first_supplier[product.id] = supplier_id
        # Loop for write:
        for product_id, seller_id in first_supplier.iteritems():
            product_pool.write(cr, uid, product_id, {
                'first_suppplier_id': seller_id,
                }, context=context)                
        return True
        
    def export_mailing_list(self, cr, uid, ids, context=None):
        ''' Export mailing list
        '''
        def write_xls_line(line):
            ''' Write line in correct WS with mode selection
            '''
            col = 0
            for item in line:
                self.WS.write(self.counter, col, item)
                col += 1
        
            self.counter += 1
            return 
        
        # XLS generate file:
        xls = '/home/administrator/photo/output/mailing.xlsx'
        _logger.warning('Log file: %s' % xls)
        WB = xlsxwriter.Workbook(xls)

        self.WS = WB.add_worksheet('Partner')
        self.counter = 0
            
        # Write Header line:
        write_xls_line((
            'Ciente', 'Fornitore', 'Azienda', 'Indirizzo', 'Camcard', 'Email',
            'Nome', 'Citta', 'Nazione', 'Email', 'Sito', 'Telefono',
            'Cat. Stat.', 'Newsletter', 'Tipo', 'Zona',
            ))
        
        partner_pool = self.pool.get('res.partner')
        partner_ids = partner_pool.search(cr, uid, 
            [], order='name', context=context)
        for partner in partner_pool.browse(
                cr, uid, partner_ids, context=context):
            write_xls_line((
                'X' if partner.customer else '',
                'X' if partner.supplier else '',
                'X' if partner.is_company else '',
                'X' if partner.is_address else '',
                'X' if partner.camcard_text else '',
                'X' if partner.email else '',
                partner.name,
                partner.city,
                partner.country_id.name,
                partner.email,
                partner.website,
                partner.phone,
                partner.statistic_category_id.name,
                partner.newsletter_category_id.name,
                partner.type_id.name,
                partner.zone_id.name,                
                ))
            
        return True
    def lavoration_inventory_modification(self, cr, uid, ids, context=None):
        ''' Export data from lavoration
        '''
        out_file = '/home/administrator/photo/output/lavoration_problem.csv'
        out_f = open(out_file, 'w')
        _logger.warning('Export lavoration problem: %s' % out_file)
        
        pick_pool = self.pool.get('stock.picking')
        pick_ids = pick_pool.search(cr, uid, [], order='name', context=context)
        
        out_f.write('Doc.|Create|Write|Date|Code|Qty|INV.\n')
        for pick in pick_pool.browse(cr, uid, pick_ids, context=context):
            for line in pick.sl_quants_ids:
                row = '%s|%s|%s|%s|%s|%s|%s\n' % (
                    # Header:
                    pick.name,
                    pick.create_date,
                    pick.write_date,
                    pick.date,
                    
                    # Line:
                    line.product_id.default_code,
                    line.qty,                    
                    line.product_id.mx_start_qty,
                    )
                out_f.write(row.replace('.', ','))
        _logger.warning('End export lavoration')
        out_f.close()
        return True
    
    def inventory_to_reset(self, cr, uid, ids, context=None):
        ''' Check error during operation on bom
        '''
        out_file = '/home/administrator/photo/log/product_to_reset'
        out_file_jump = '/home/administrator/photo/log/product_to_reset_jumped'
        
        out_f = open(out_file, 'w')
        out_jump = open(out_file_jump, 'w')
        
        # Pool used:
        product_pool = self.pool.get('product.product')

        # Check HW bon link:
        product_ids = product_pool.search(cr, uid, [
            ('default_code', 'not in', product_present),                     
            ], context=context)

        for product in product_pool.browse(
                cr, uid, product_ids, context=context):                
            if not product.default_code or product.default_code[:1] not in \
                    '1234567890G':                    
                out_jump.write('%s|0\n' % product.default_code)
                continue     
                    
            out_f.write('%s|0\n' % product.default_code)
        out_f.close()
        out_jump.close()        
