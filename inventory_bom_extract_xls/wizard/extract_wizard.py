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
            1. First get data from ODOO product and update fields
            2. After override values from file CSV present
        '''    
        product_pool = self.pool.get('product.product')
        csv_file = '/home/administrator/photo/xls/stock/costrevenue.csv'
        _logger.info('Import cost and revenue in product: %s' % csv_file)
        
        # Before load original:
        product_ids = product_pool.search(cr, uid, [], context=context)
        for product in product_pool.browse(cr, uid, product_ids, 
                context=context):
                
            # Store in new fields for fast search during report:    
            data = {
                'inv_first_supplier': 
                    product.first_supplier_id.id \
                        if product.first_supplier_id else False,        
                'inv_revenue_account': 
                    product.property_account_income.account_ref \
                        if product.property_account_income else False,
                'inv_cost_account': 
                    product.property_account_expense.account_ref \
                        if product.property_account_expense else False,
                }                    
            
            # Get also cost:
            cost = 0.0
            date = False
            for supplier in product.seller_ids:
                for price in supplier.pricelist_ids:
                    if not price.is_active:
                        continue
                    if date == False or price.date_quotation > date:
                        date = price.date_quotation
                        cost = price.price
            if cost:
                data['inv_cost_value'] = cost
            product_pool.write(cr, uid, product.id, data, context=context)
            
        # Update with file:
        self.import_csv_inventory_cost_revenue(
            cr, uid, csv_file, context=context)

        # Call XLSX produce functiocn:    
        return self.action_extract(cr, uid, ids, context=context)
        
    def action_extract(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        # ---------------------------------------------------------------------
        #                             UTILITY: 
        # ---------------------------------------------------------------------
        # Excel:
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
        
        # ---------------------------------------------------------------------
        # BOM
        def load_bom_template(self, cr, uid, context=None):
            ''' Load template bom return code[:6] with element
            '''    
            res = {}
            product_pool = self.pool.get('product.product')
            product_ids = product_pool.search(cr, uid, [
                ('bom_selection', '=', True),
                ], context=context)
            for product in product_pool.browse(
                    cr, uid, product_ids, context=context):
                res[product.default_code[:6].strip()] = (
                    product.dynamic_bom_line_ids, # BOM
                    product_pool.get_cost_industrial_for_product( # Industrial
                        cr, uid, [product.id], context=context),
                    )
            return res
            
        def clean_float(value):
            ''' Clean float value
            '''    
            try: 
                res = float(value)
                return res
            except:
                return 0.0
        
        def not_in_inventory_selection(product, jumped, costs):
            ''' Check if the product need to be used:
                Add in jumped list
            '''
            ledger_selection = (
                '37.00101', # Tessuto c/acquisti
                #'37.00102', # Materie varie prime c/acquisti
                '37.00103', # Ferro c/acquisti
                '37.00105', # Cartoni c/acquisti
                '37.00106', # Cellophan c/acquisti
                '37.00108', # Copriteste e pinze c/acquisti
                )
            supplier_selection = (
                31401,   #'20.01330', # La Industrial Algodonera
                '31401', #'20.01330', # La Industrial Algodonera
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
                        get_cost(product, costs),            
                        )
            return not_selected            
        
        def get_cost(product, costs):
            ''' Check cost for this product
            '''
            # TODO write a better method
            default_code = product.default_code
            if default_code and default_code in costs and costs[default_code]:
                if default_code == 'ANG22':
                    print default_code, costs[default_code]
                return costs[default_code]
            else:     
                if default_code == 'ANG22':
                    print default_code, product.inv_cost_value or product.standard_price 
                #return product.standard_price
                return product.inv_cost_value or product.standard_price 

        def setup_materials(product, materials, costs):
            ''' Utility for append product in material list (initial setup)
            '''
            price = get_cost(product, costs)
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
            
        def setup_materials_q(product, col, qty, materials, costs):
            ''' Add data for product passed in right column with right cost
            '''
            price = get_cost(product, costs)
            
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
        _logger.info('Check cost for product')
        product_pool = self.pool.get('product.product')
        costs = product_pool.get_purchase_cost_value(cr, uid, context=context)

        # ---------------------------------------------------------------------
        # Template bom:
        # ---------------------------------------------------------------------
        template_bom = load_bom_template(self, cr, uid, context=context)    

        # ---------------------------------------------------------------------            
        # XLS output file:
        # ---------------------------------------------------------------------            
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
        materials = {}
        jumped = {} # Material not managed
        no_bom6 = {}
        for default_code, unload_list in inventory_product.iteritems():
            _logger.info('Extract material for code: %s' % default_code)
            
            # ------------------------------
            # Product data information used:
            # ------------------------------
            # Normal product (check in BOM template):
            product = products[default_code] # Browse obj
            code6 = default_code[:6].strip()
            industrial_ids = {}
            dynamic_ids = []
            # TODO choose another template instead
            
            if code6 in template_bom:
                (dynamic_ids, industrial_ids) = template_bom[code6]
                # TODO manage industrial
            else:
                if code6 not in no_bom6:
                    no_bom6[code6] = []
                if default_code not in no_bom6[code6]: # Log no bom product
                    no_bom6[code6].append(default_code)
                
            # Halfworked product:
            half_line_ids = product.half_bom_ids # bom_ids            
            
            # -----------------------------------------------------------------
            # I. Raw material (Invoice direct sale for material):
            # -----------------------------------------------------------------
            if not dynamic_ids and not half_line_ids:                
                if not_in_inventory_selection(# Not used:
                        product, jumped, costs):
                    continue # jump not used (update the list)!
                    
                # Add in inventory:
                setup_materials(product, materials, costs)
                
                # Loop on all period:
                for col in range (0, 12):
                    product_qty = unload_list[col]
                    if not product_qty: # nothing to do, is empty
                        continue
                        
                    setup_materials_q(product, col, product_qty, materials, 
                        costs)
                continue
            # -----------------------------------------------------------------

            # -----------------------------------------------------------------
            # II. Halfwork explose (Halfwork explosed with material present):
            # -----------------------------------------------------------------
            for line in half_line_ids:
                component = line.product_id
                component_code = component.default_code
                
                # Component not used:
                if not_in_inventory_selection(component, jumped, costs):
                    continue

                # Add to inventory:
                setup_materials(component, materials, costs)
                
                # Loop on all period:
                for col in range (0, 12):
                    product_qty = unload_list[col]
                    if not product_qty: # nothing to do, is empty
                        #_logger.info('Jumped 0: %s' % default_code)
                        continue
                
                    setup_materials_q(
                        component, col, 
                        product_qty * line.product_qty, 
                        materials,
                        costs
                        )
                continue
            # -----------------------------------------------------------------

            # -----------------------------------------------------------------
            # III. Product explose (Explode product, first level, raw mat.):
            # -----------------------------------------------------------------
            for line in dynamic_ids: # has bom
                # TODO change product_qty
                component = line.product_id
                component_code = component.default_code

                # -------------------------------------------------------------
                # a. HW in product explose:
                # -------------------------------------------------------------
                # Explode material in halfworked level:
                # TODO save also halfwork material
                if component.half_bom_ids:
                    for hw_line in component.half_bom_ids:
                        hw_product = hw_line.product_id
                        hw_product_code = hw_product.default_code
                        
                        # Not used:
                        if not_in_inventory_selection(hw_product, jumped, 
                                costs):                                
                            continue # jump not used!
                        
                        # Add to inventory:
                        setup_materials(hw_product, materials, costs)

                        for col in range (0, 12):
                            product_qty = unload_list[col]
                            if not product_qty: # nothing to do, is empty
                                #_logger.info('Jumped 0: %s' % default_code)
                                continue

                            setup_materials_q(
                                hw_product, col, 
                                product_qty * hw_line.product_qty, # q.
                                materials,
                                costs,
                                )
                    continue # no other material        

                # -------------------------------------------------------------
                # b. Prime material in product explose:
                # -------------------------------------------------------------
                # Take material in first level                
                if not_in_inventory_selection(component, jumped, costs):
                    continue # Not used jumped
                                    
                for col in range (0, 12):
                    product_qty = unload_list[col]
                    if not product_qty: # nothing to do, is empty
                        continue
                        
                    if component_code not in materials: # Add to inventory:
                        setup_materials(component, materials, costs)
                    setup_materials_q(
                        component, col, 
                        product_qty * line.product_qty, 
                        materials,
                        costs,
                        )

        xls_sheet_write(
            WB, '5. Materiali utilizzati', materials, material_product)
        xls_sheet_write_table(
            WB, '6. Materiali saltati', jumped, (
                'Codice materiale', 'Nome', 'Costo', 'Ricavo', 'Fornitore', 
                'Prezzo',
                ))
                
        # Write extra page for BOM not found from product template:
        WS = WB.add_worksheet('7. Prodotti senza modello DB')
        row = 0
        WS.write(row, 0, 'Codice padre (template)')
        WS.write(row, 1, 'Elenco prodotti')
        for code6 in sorted(no_bom6):
            row += 1
            WS.write(row, 0, code6)
            WS.write(row, 1, ', '.join(no_bom6[code6]))
                        
    _columns = {
        'year': fields.integer('Year', required=True),
        }
        
    _defaults = {
        'year': lambda *x: int(datetime.now().strftime('%Y')),
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
