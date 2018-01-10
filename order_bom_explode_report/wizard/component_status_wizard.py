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


class CcomponentStatusReportWizard(orm.TransientModel):
    ''' Wizard for print status
    '''
    _name = 'component.status.report.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def action_open_report(self, cr, uid, ids, context=None):
        ''' Event for button done
        '''
        if context is None: 
            context = {}        
        
        wiz_browse = self.browse(cr, uid, ids, context=context)[0]        
        datas = {
            'mode': wiz_browse.mode,
            'mp_mode': wiz_browse.mp_mode,
            'days': wiz_browse.days,
            'first_supplier_id': wiz_browse.first_supplier_id.id or False,
            #'negative_start': wiz_browse.negative_start,
            'type_id': False, # TODO remove ex. wiz_browse.type_id.id or
            'with_type_ids': 
                [item.id for item in wiz_browse.with_type_ids],
            'without_type_ids': 
                [item.id for item in wiz_browse.without_type_ids],
            'with_deadline': wiz_browse.with_deadline,    
            'only_negative': wiz_browse.only_negative,
            'exclude_inventory_category': 
                wiz_browse.exclude_inventory_category,
            }

        if wiz_browse.mode == 'mrp':
            report_name = 'mrp_status_explode_report'            
        elif wiz_browse.mode == 'todo':
            # Create simulation order:
            if wiz_browse.line_ids:
                # Create fake order and put product for simulation:
                sale_pool = self.pool.get('sale.order')
                sol_pool = self.pool.get('sale.order.line')
                partner_id = 1 # XXX company partner
                data = sale_pool.onchange_partner_id(
                    cr, uid, False, partner_id, context=context).get(
                        'value', {})
                data['simulation'] = True
                data['partner_id'] = partner_id
                data['date_order'] = datetime.now().strftime(
                    DEFAULT_SERVER_DATE_FORMAT)
                order_id = sale_pool.create(cr, uid, data, context=context)
                
                for line in wiz_browse.line_ids:
                    product_id = line.product_id.id
                    data_line = sol_pool.product_id_change_with_wh(
                        cr, uid, False,
                        data.get('pricelist_id', False),
                        product_id,
                        line.quantity,
                        line.product_id.uom_id.id,
                        0, # uos qty
                        line.product_id.uos_id.id,
                        '', # name
                        partner_id,
                        False, #'IT_it',
                        True, # update tax
                        data.get('date_order', False),
                        False, # packaging
                        data.get('fiscal_position', False),
                        False, # flag
                        data.get('warehouse_id', False),
                        context=context).get('value', {})
                        
                    if data_line.get('tax_id', False):
                        data_line['tax_id'] = (
                            (6, 0, data_line.get('tax_id')),
                            )
                    data_line['order_id'] = order_id
                    data_line['product_id'] = product_id
                    data_line['product_uom_qty'] = line.quantity
                    # TODO onchange product_uom_qty?                    
                    sol_pool.create(cr, uid, data_line, context=context)                    
                datas['simulation_order_ids'] = order_id
            report_name = 'mrp_status_hw_cmp_report'
        else: # halfwork, component
            report_name = 'stock_status_explode_report'

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            }

    # -------------------------------------------------------------------------
    # Fields function:
    # -------------------------------------------------------------------------
    def _get_excluded_inventory(self, cr, uid, context=None):
        ''' Fields function for calculate 
        '''
        inventory_pool = self.pool.get(
            'product.product.inventory.category')
        inventory_ids = inventory_pool.search(cr, uid, [
            ('not_in_report', '=', True),
            ], context=context)
        res = ''
        for category in inventory_pool.browse(cr, uid, inventory_ids, 
                context=context):
            res += '[%s] ' % category.name               
        return res
        
    _columns = {
        'mode': fields.selection([
            ('halfwork', 'Halfwork'),
            ('component', 'Final component'),
            ('mrp', 'Scheduled production'),
            ('todo', 'TODO hw and component'),
            ], 'Report mode', required=True),
        'mp_mode': fields.selection([
            ('pipe', 'Pipe *'),
            ('extra', 'Extra material (all) *'),
            ('fabric', 'Fabric'),
            ], 'MP mode'),
        'only_negative': fields.boolean('Only negative'),
        'days': fields.integer('Days', help='Production scheduled now + days'),
        'with_deadline': fields.boolean('With deadline period', 
            help='Add line with parent distribution of remain to produce OC'),
        'negative_start': fields.boolean('Negative start', 
            help='Total check month for negative start'),
        'first_supplier_id': fields.many2one(
            'res.partner', 'Fornitore ultimo acquisto'),
        'type_id': fields.many2one(
            'mrp.bom.structure.category.type', 'Component category type'),
        'with_type_ids': fields.many2many(
            'mrp.bom.structure.category.type', 
            'with_mrp_bom_structure_category_type_rel', 
            'wiz_id', 'type_id', 
            'With type'),    
        'without_type_ids': fields.many2many(
            'mrp.bom.structure.category.type', 
            'without_mrp_bom_structure_category_type_rel', 
            'wiz_id', 'type_id', 
            'Without type'),    
        'type_id': fields.many2one(
            'mrp.bom.structure.category.type', 'Component category type'),
        'exclude_inventory_category': fields.boolean(
            'Escludi categorie inventario'),
        'exclude_inventory_list': fields.char('Esclusi', size=400, 
            readonly=True), 
        }
        
    _defaults = {
        'mode': lambda *x: 'halfwork',
        'days': lambda *x: 30,
        'exclude_inventory_category': lambda *x: True,        
        'exclude_inventory_list':
            lambda s, cr, uid, ctx: s._get_excluded_inventory(cr, uid, ctx),
        }    

class ComponentStatusReportWizard(orm.TransientModel):
    ''' Wizard for print status
    '''
    _name = 'component.status.report.wizard.line'
    _rec_name = 'product_id'    

    _columns = {
        #'parent': fields.char('Cod. padre', size=20, required=True),
        'product_id': fields.many2one('product.product', 'Product', 
            required=True),
        'quantity': fields.float('Q.', digits=(16, 2), required=True),
        'wizard_id': fields.many2one(
            'component.status.report.wizard', 'Wizard'),
        }

class ComponentStatusReportWizard(orm.TransientModel):
    ''' Wizard for print status
    '''
    _inherit = 'component.status.report.wizard'
       
    _columns = {
        'line_ids': fields.one2many(
            'component.status.report.wizard.line', 'wizard_id', 'Linee'),
        }    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
