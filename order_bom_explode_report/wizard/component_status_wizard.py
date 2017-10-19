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
            }

        if wiz_browse.mode == 'mrp':
            report_name = 'mrp_status_explode_report'            
        elif wiz_browse.mode == 'todo':
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
            'res.partner', 'First supplier'),
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

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
