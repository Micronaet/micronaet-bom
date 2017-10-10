# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
# Developer: Nicola Riolini @thebrush (<https://it.linkedin.com/in/thebrush>)
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. 
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

import os
import sys
import logging
import openerp
import xlsxwriter
import xlrd
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)

class ProductInventoryExtractXLSWizard(orm.TransientModel):
    ''' Wizard for extracting inventory wizard
    '''
    _name = 'product.inventory.extract.xls.wizard'

    def import_csv_inventory_cost_revenue(
            self, cr, uid, filename, context=None):
        ''' Import CSV data for inventory
        '''
        product_pool = self.pool.get('product.product')
        i = 0
        for line in open(filename, 'r'):
            i += 1
            if i % 50 == 0:
                _logger.info('Update cost / revenue: %s' % i)
            fields = line.split(';')
            
            # Read parameters:
            default_code = fields[0].strip()
            description = fields[1].strip()
            revenue = fields[2].strip()
            cost = fields[3].strip()
            supplier = fields[4].strip()

            product_ids = product_pool.search(cr, uid, [
                ('default_code', '=', default_code),
                ], context=context)
                
            if product_ids: # exist:
                product_pool.write(cr, uid, product_ids, {
                    'inv_revenue_account': revenue,
                    'inv_cost_account': cost,
                    'inv_first_supplier': supplier,
                    }, context=context)
        else:
            _logger.error('Product code not found: %s' % default_code)               
        return True
        
    # --------------------
    # Wizard button event:
    # --------------------
    def action_extract_reload(self, cr, uid, ids, context=None):
        ''' Reload cost / revenut before launch normal procedure        
        '''    
        csv_file = '/home/administrator/photo/xls/stock/costrevenue.csv'
        _logger.info('Import cost and revenue in product: %s' % csv_file)
        self.import_csv_inventory_cost_revenue(
            cr, uid, csv_file, context=context)
        return self.action_extract(cr, uid, ids, context=context)
        
    def action_extract(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        # ---------------------------------------------------------------------
        # Utility:
        # ---------------------------------------------------------------------
        def xls_write_row(WS, row, line, title=False):
            ''' Write row in a file
            '''
            print 'Write sheet: %s' % title
            
            if title: # data line
                WS.write(row, 0, title)
                col = 0
            else: # header line:
                col = -1
                
            for item in line:
                col += 1
                WS.write(row, col, item)
            return
        
        def xls_sheet_write(WB, name, inventory, header):
            ''' Add new sheet and write inventory data
                WB: Excel Workbook
                name: Sheet name
                inventory: database to write
                header: title list
            '''
            WS = WB.add_worksheet(name)
            xls_write_row(WS, 0, header)
            
            row = 0
            for code in sorted(inventory):
                row += 1
                xls_write_row(WS, row, inventory[code], code)
            _logger.info('End extract %s sheet: %s' % (xls_file, name))
            return            

        def xls_sheet_write_table(WB, name, value, title):
            ''' Write a simple list on Excel file
                WB: Excel workbook
                name: Sheet name
                value: dict with data
                title: string for title
            '''
            # Write name of sheet:
            WS = WB.add_worksheet(name)
            
            # Write header:
            for col in range(0, len(title)):
                WS.write(0, col, title[col])
                
            # Write data lines:    
            row = 0
            for item in sorted(value):
                row += 1
                WS.write(row, 0, item) # code
                data = value[item]
                for col in range(0, len(data)):
                    WS.write(row, col + 1, data[col])
            return    
            
        def clean_float(value):
            ''' Clean float value
            '''    
            try: 
                res = float(value)
                return res
            except:
                #_logger.warning('Float value not present: %s' % value)
                return 0.0
        
        def not_in_inventory_selection(product, jumped):
            ''' Check if the product need to be used:
                Add in jumped list
            '''
            ledger_selection = (
                '37.00101', # Tessuto c/acquisti
                '37.00103', # Ferro c/acquisti
                '37.00105', # Cartoni c/acquisti
                '37.00106', # Cellophan c/acquisti
                '37.00108', # Copriteste e pinze c/acquisti
                )
            supplier_selection = (
                '20.01330', # La Industrial Algodonera
                )

            # cost, revenue, supplier all different:
            not_selected = product.inv_revenue_account not in ledger_selection\
                and product.inv_cost_account not in ledger_selection\
                and product.inv_first_supplier not in supplier_selection
                
            if not_selected:
                if product.default_code not in jumped: 
                    # log jumped material (with useful information)
                    jumped[product.default_code] = ( 
                        product.name,
                        product.inv_revenue_account,
                        product.inv_cost_account,
                        product.inv_first_supplier,
                        get_cost(product),            
                        )
            return not_selected            
        
        def get_cost(product):
            ''' Check cost for this product
            '''
            # TODO write a better method
            default_code = product.default_code
            if default_code and default_code in of_cost:
                return of_cost[default_code]
            else:     
                return product.standard_price

        def setup_materials(product, materials):
            ''' Utility for append product in material list (initial setup)
            '''
            price = get_cost(product)
            if product.default_code not in materials:
                materials[product.default_code] = [
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    product.inv_revenue_account,
                    product.inv_cost_account,
                    product.inv_first_supplier,
                    price, 
                    ]            
            return
            
        def setup_materials_q(product, col, qty, materials):
            ''' Add data for product passed in right column with right cost
            '''
            price = get_cost(product)
            
            default_code = product.default_code
            # Add q:
            materials[default_code][col] += qty
            # Add total TODO change cost value:
            materials[default_code][col + 12] += qty * price
            return
            
        if context is None: 
            context = {}    

        # ---------------------------------------------------------------------            
        # Parameters:        
        # ---------------------------------------------------------------------            
        code_part = 6
        xls_file = '/home/administrator/photo/xls/stock/inventory_%s.xlsx'
        xls_infile = '/home/administrator/photo/xls/stock/use_inv_%s.xlsx'
        start_row = 2 # first data row (start from 0)
                
        # Read parameter from wizard:
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]
        year = wiz_browse.year

        # ---------------------------------------------------------------------            
        # Load cost from order:
        # ---------------------------------------------------------------------            
        of_cost = {}
        po_pool = self.pool.get('purchase.order')
        po_ids = po_pool.search(cr, uid, [
            ('state', 'in', ('approved', )),
            ('date_order', '>=', '%s-01-01' % year),
            ('date_order', '<=', '%s-12-31' % year),
            ], context=context)
        for po in po_pool.browse(cr, uid, po_ids, context=context):
            for line in po.order_line:
                if not line.price_unit:
                    continue # jump no price line
                product = line.product_id
                default_code = product.default_code
                if default_code and default_code not in of_cost:                    
                    of_cost[default_code] = line.price_unit
        
        # Insert year in filename:
        xls_file = xls_file % year
        xls_infile = xls_infile % year

        # Open XLS file:
        _logger.info('Create extract %s file' % xls_file)
        WB = xlsxwriter.Workbook(xls_file)

        # Header:
        header_product = [
            'Codice', 'Gen.', 'Feb.', 'Mar.', 'Apr.', 'Mag.', 'Giu.', 'Lug.', 
            'Ago.', 'Set.', 'Ott.', 'Nov.', 'Dic.',
            ]
        header = [
            'Codice', 'Inv. iniz.', 'Gen.', 'Feb.', 'Mar.', 'Apr.', 
            'Mag.', 'Giu.', 'Lug.', 'Ago.', 'Set.', 'Ott.', 'Nov.', 
            'Dic.', 'Inv. fin.'
            ]
        material_product = [
            'Codice', 'Gen.', 'Feb.', 'Mar.', 'Apr.', 'Mag.', 'Giu.', 'Lug.', 
            'Ago.', 'Set.', 'Ott.', 'Nov.', 'Dic.',
            'Gen.', 'Feb.', 'Mar.', 'Apr.', 'Mag.', 'Giu.', 'Lug.', 
            'Ago.', 'Set.', 'Ott.', 'Nov.', 'Dic.',
            'Costo', 'Ricavo', 'Fornitore', 'Costo',
            ]

        # ---------------------------------------------------------------------
        # A. Read parent code in invoice and default code in invoice
        # ---------------------------------------------------------------------
        # Domain filter invoice:
        _logger.info('Start extract sale from invoice, year %s' % year)
        line_pool = self.pool.get('account.invoice.line')
        line_ids = line_pool.search(cr, uid, [
            ('invoice_id.date_invoice', '>=', '%s-01-01' % year),
            #('invoice_id.date_invoice', '<', '%s-02-01' % year),
            ('invoice_id.date_invoice', '<', '%s-01-01' % (year + 1)),
            ('invoice_id.state', '=', 'open'),
            ], context=context)
                
        # Database:    
        inventory_product = {}
        inventory = {}        
        products = {}
        _logger.info('Read %s invoice line' % len(line_ids))        
        for line in line_pool.browse(
                cr, uid, line_ids, context=context):
            default_code = line.product_id.default_code
            if not default_code:
                _logger.error('No default code')
                continue
            parent_code = default_code[:code_part].strip()
                
            quantity = line.quantity
            date_invoice = line.invoice_id.date_invoice
            
            if default_code not in inventory_product:
                inventory_product[default_code] = [
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    ]
                products[default_code] = line.product_id     
            if parent_code not in inventory:
                inventory[parent_code] = [
                    0, # Start inv.
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, # End inv.
                    ]
            month = int(date_invoice[5:7])
            inventory_product[default_code][month - 1] += quantity   
            inventory[parent_code][month] += quantity   

        # Export in XLSX file:
        xls_sheet_write(WB, '1. Vendite prodotti', inventory_product, 
            header_product)
        xls_sheet_write(WB, '2. Vendite padre', inventory, header)
        
        # ---------------------------------------------------------------------
        # B. Integrate unload inventory:
        # ---------------------------------------------------------------------
        _logger.info('Read inventory adjust file: %s' % xls_infile),
        # Open file:
        try:
            # from xlrd.sheet import ctype_text   
            WB_inv = xlrd.open_workbook(xls_infile)
            WS_inv = WB_inv.sheet_by_index(0)
        except:
            raise osv.except_osv(
                _('Open file error'), 
                _('Cannot open file: %s' % xls_infile),
                )

        for i in range(start_row, WS_inv.nrows):
            row = WS_inv.row(i)
            parent_code = row[0].value
            if not parent_code: # end import
                _logger.info('End import at line: %s' % i)
                break
            
            if parent_code not in inventory:
                _logger.warning('Code not found: %s' % parent_code)
                inventory[parent_code] = [
                    0, # Start inv.
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, # End inv.
                    ]                    

            for col in range(1, 15):
                inventory[parent_code][col - 1] += clean_float(row[col].value)
        _logger.info('End inventory adjust file: %s' % xls_infile),

        # Export in XLSX file:
        xls_sheet_write(WB, '3. Correzione padre', inventory, header)

        # ---------------------------------------------------------------------
        # C. Assign product unload depend on inventory database
        # ---------------------------------------------------------------------
        for default_code, unload_list in inventory_product.iteritems():
            parent_code = default_code[:code_part].strip()
            # loop on month:
            for col in range(0, 12):
                product_qty = inventory_product[default_code][col]
                parent_qty = inventory[parent_code][col + 1]
                
                # 3 case:
                if not parent_qty:
                    inventory_product[default_code][col] = 0.0
                elif product_qty <= parent_qty: 
                    inventory[parent_code][col + 1] -= product_qty                     
                else: # product qty > parent_qty
                    inventory_product[default_code][col] = parent_qty
                    inventory[parent_code][col + 1] = 0.0
        # Export in XLSX file:
        xls_sheet_write(WB, '4. Correzione prodotti', inventory_product, 
            header_product)

        # ---------------------------------------------------------------------
        # D. Extra material from sales
        # ---------------------------------------------------------------------
        import pdb; pdb.set_trace()
        materials = {}
        jumped = {} # Material not managed
        temp = 0 # TODO remove
        for default_code, unload_list in inventory_product.iteritems():
            _logger.info('Extract material for code: %s' % default_code)
            temp += 1 # TODO remove
            
            # ------------------------------
            # Product data information used:
            # ------------------------------
            # Normal product:
            dynamic_ids = products[default_code].dynamic_bom_line_ids
            # Halfworked product:
            half_line_ids = products[default_code].half_bom_ids # bom_ids
            # relative_type = half
            
            for col in range (0, 12):
                product_qty = unload_list[col]
                if not product_qty: # nothing to do, is empty
                    #_logger.info('Jumped 0: %s' % default_code)
                    continue
                                    
                # -------------------------------------------------------------
                # I. Prime material:
                # -------------------------------------------------------------
                if not dynamic_ids and not half_line_ids:
                    # Not used:
                    if not_in_inventory_selection(
                            products[default_code], jumped):
                        continue # jump not used (update the list)!
                        
                    # Add in inventory:
                    setup_materials(products[default_code], materials)
                    setup_materials_q(
                        products[default_code], col, product_qty, materials)
                    continue

                # -------------------------------------------------------------
                # II. Halfwork explose:                
                # -------------------------------------------------------------
                for line in half_line_ids:
                    component = line.product_id
                    component_code = component.default_code
                    
                    # Not used:
                    if not_in_inventory_selection(component, jumped):
                        continue

                    # Add to inventory:
                    setup_materials(component, materials)
                    setup_materials_q(
                        component, col, 
                        product_qty * line.product_qty, 
                        materials,
                        )
                    continue

                # -------------------------------------------------------------
                # III. Product explose:
                # -------------------------------------------------------------
                for line in dynamic_ids: # has bom
                    # TODO change product_qty
                    component = line.product_id
                    component_code = component.default_code

                    # ---------------------------------------------------------
                    # a. HW in product explose:
                    # ---------------------------------------------------------
                    if component.half_bom_ids:
                        for hw_line in component.half_bom_ids:
                            hw_product = hw_line.product_id
                            hw_product_code = hw_product.default_code
                            
                            # Not used:
                            if not_in_inventory_selection(hw_product, jumped):                                
                                continue # jump not used!
                            
                            # Add to inventory:
                            setup_materials(hw_product, materials)
                            setup_materials_q(
                                hw_product, col, 
                                product_qty * hw_line.product_qty, # q.
                                materials,
                                )
                        continue # no other material        

                    # ---------------------------------------------------------
                    # b. Prime material in product explose:
                    # ---------------------------------------------------------
                    # Not used:
                    if not_in_inventory_selection(component, jumped):
                        continue # jump not used

                    # Add to inventory:
                    if component_code not in materials:
                        setup_materials(component, materials)
                    setup_materials_q(
                        component, col, 
                        product_qty * line.product_qty, 
                        materials,
                        )

            #if temp > 1000:
            #    break # TODO remove    

        xls_sheet_write(
            WB, '5. Materiali utilizzati', materials, material_product)
        xls_sheet_write_table(
            WB, '6. Materiali saltati', jumped, (
                'Codice materiale', 'Nome', 'Costo', 'Ricavo', 'Fornitore', 
                'Prezzo',
                ))
                        
    _columns = {
        'year': fields.integer('Year', required=True),
        }
        
    _defaults = {
        'year': lambda *x: int(datetime.now().strftime('%Y')),
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
