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
import xlrd
import xlsxwriter
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

    def publish_image_web1_xls(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None:
            context = {}        
        
        # Pool:
        product_pool = self.pool.get('product.product')
        connector_pool = self.pool.get('product.product.web.server')

        # Read excel for product:
        filename = '/home/administrator/photo/xls/web/code.xls'
        mode = 'selection'
        published = True
        product_ids = []        
        try:
            WB = xlrd.open_workbook(filename)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Cannot read XLS file: %s' % filename),
                )                
        WS = WB.sheet_by_index(0)
        try:
            webserver_id = int(WS.cell(0, 0).value)
        except:
            raise osv.except_osv(
                _('Error XLSX'), 
                _('Prima riga deve essere codice web connect!'),
                )                
                     
        for row in range(1, WS.nrows):
            try:
                default_code = WS.cell(row, 0).value
                #_logger.info('Product: %s' % default_code)
            except:
                continue
            try:
                p_ids = product_pool.search(cr, uid, [
                    ('default_code', '=', default_code),
                    ], context=context)
                if not p_ids:
                    _logger.error('Not found %s' % default_code)
                    continue
                product_ids.append(p_ids[0])
            except:
                continue
        
        
        # Create record if not present in product
        publish_ids = []
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            for server in product.web_server_ids:
                if server.connector_id.id == webserver_id:
                    publish_ids.append(server.id)
                    break
            else: # only if not found:
                publish_ids.append(
                    connector_pool.create(cr, uid, {
                        'connector_id': webserver_id,
                        'product_id': product.id,
                        'published': True,
                        }, context=context))
            
        #if publish_ids:
        #    # Set all record for publish:                    
        #    connector_pool.write(cr, uid, publish_ids, {
        #        'published': published,                
        #        }, context=context)
        return True

    # Procedure:    
    def export_partner_pricelist(self, cr, uid, ids, context=None):
        ''' Export property pricelist for partner
        '''
        def clean_ascii(value):
            ''' Clean non ascii char
            '''
            res = ''
            if not value:
                return res               
            for c in value:
                if ord(c) < 128:
                    res += c
                else:
                    res += '*'
            return res

        pricelist_file = '/home/administrator/photo/output/partner_pricelist.csv'
        pl_file = open(pricelist_file, 'w')

        partner_pool = self.pool.get('res.partner')
        partner_ids = partner_pool.search(cr, uid, [
            ('is_address', '=', False)
            ], context=None)
        for partner in partner_pool.browse(
                cr, uid, partner_ids, context=context):
            pl_file.write('%s|%s|%s|%s|%s|%s|%s\n' % (
                'X' if partner.customer else '',
                'X' if partner.supplier else '',
                partner.create_date,
                clean_ascii(partner.name),
                clean_ascii(partner.city),
                clean_ascii(partner.country_id.name if \
                    partner.country_id else ''),
                partner.property_product_pricelist.name if \
                    partner.property_product_pricelist else ''
                ))    
        pl_file.close()
        return True        
        
    def export_product_status_for_inventory(self, cr, uid, ids, context=None):
        ''' Export inventory data from order and picking
        '''
        # Output file:
        log_file = '/home/administrator/photo/output/C01_inventory.csv'
        f_log = open(log_file, 'w')

        # Pool used:
        product_pool = self.pool.get('product.product')
        line_pool = self.pool.get('purchase.order.line')
        move_pool = self.pool.get('stock.move')
        
        # Database:
        move_db = {}
        line_db = {}
        
        # Search only product in cat. stat: C01:
        _logger.warning('Start select product')
        product_ids = product_pool.search(cr, uid, [
            ('statistic_category', '=', 'C01'),
            ], context=context)
        _logger.warning('End select, total: %s' % len(product_ids))
        
        # Check purchase line for price:    
        _logger.warning('Start select product')
        line_ids = line_pool.search(cr, uid, [
            ('product_id', 'in', product_ids),
            ('order_id.state', 'not in', ('draft', 'cancel')),
            ], context=context)
        _logger.warning('End select purchase, total: %s' % len(line_ids))
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            if line.product_id.id not in line_db:
                line_db[line.product_id.id] = []
            line_db[line.product_id.id].append(line)
            
        # Check stock move for sold in year    
        _logger.warning('Start select product')
        move_ids = move_pool.search(cr, uid, [
            ('product_id', 'in', product_ids),
            ('state', '=', 'done'),
            ], context=context)
        _logger.warning('End select move, total: %s' % len(move_ids))
        for move in move_pool.browse(cr, uid, move_ids, context=context):
            if move.product_id.id not in move_db:
                move_db[move.product_id.id] = []
            move_db[move.product_id.id].append(move)
       
        # Create database list for product:
        _logger.warning('Start export product')
        f_log.write('Codice|INV|Costo azienda|Pz. camion|Prezzo diff.|Movimentato 2016|Fatt.|OF|MM\n')
        
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            # OF status    
            of_status = ''
            price_unit = 0.0        
            price_difference = False
            of_name = ''
            for line in line_db.get(product.id, []):
                if line.order_id.name.startswith('INV'):
                    continue
                if not price_unit:
                    price_unit = line.price_unit
                elif price_unit != line.price_unit:
                    price_difference = True
                of_name += '%s ' % line.order_id.name
                of_status += '[ %s doc. %s ]' % (
                    line.price_unit,
                    line.order_id.date_order[:10],
                    )
            
            # MM status
            mm_status = ''
            move_date = '' # TODO
            moved = False
            for line in move_db.get(product.id, []):
                if line.picking_id.name.startswith('WH/IN/00005'):
                    continue
            
                if not line.picking_id.name.startswith('WH/IN'):
                    continue
                if line.create_date > '2016-01-01':
                    moved = True
                mm_status += '[ %s doc. %s ]' % (
                    line.create_date[:10],
                    line.picking_id.name, # date_done
                    )
            
            f_log.write('%s|%s|%s|%s|%s|%s|%s|%s|%s\n' % (
                product.default_code, 
                product.mx_start_qty,
                product.company_cost,
                '%s' % ([item.quantity for item in product.transport_ids], ),
                'X' if price_difference else '',
                'X' if moved else '',
                of_name,
                of_status,
                mm_status,
                ))
                
        f_log.close()
        _logger.warning('End export product')
        return True
    
    def save_cost_in_cost_method(self, cr, uid, ids, context=None):
        ''' Migrate 3 cost from old part in new cost management
        '''
        # Log operation
        log_file = '/home/administrator/photo/output/indoor_cost_migration.csv'
        f_log = open(log_file, 'w')
        _logger.warning('Start migrate cost log on: %s' % log_file)
        
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('statistic_category', 'in', (
                'I01', 'I02', 'I03', 'I04', 'I05', 'I06')),
            ], context=context)
            
        f_log.write(
            'Codice|INV|Cat. Stat.|Costo fornitore|Azienda Da|A|Cliente Da|A\n')
        res = {}    
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
            f_log.write(
                '%s|%s|%s|%s|%s|%s|%s\n' % (
                    product.default_code,
                    product.statistic_category,
                    product.standard_price,
                    product.cost_in_stock,
                    product.company_cost,
                    product.cost_for_sale,
                    product.customer_cost,
                ))
            res[product.id] = {
                'company_cost': product.cost_in_stock,
                'customer_cost': product.cost_for_sale,
                }
                
        for product_id, data in res.iteritems():
            product_pool.write(cr, uid, product_id, data, context=context)
        _logger.info('Migrated data!')
        f_log.close()
        return True        
    
