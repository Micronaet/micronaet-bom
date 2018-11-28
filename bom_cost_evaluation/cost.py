#!/usr/bin/python
# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<https://micronaet.com>)
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

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """
    
    _inherit = 'product.product'

    # -------------------------------------------------------------------------
    # Utility:
    # -------------------------------------------------------------------------
    # Raw Material price list:
    def _get_last_material_price_from_check(self, cr, uid, ids, context=None):
        ''' Return product requested last price
        '''
        res = {}
        for product in self.browse(cr, uid, ids, context=context):
            last_date = False
            last_price = 0.0
            #last_seller = False
            for seller in product.seller_ids:
                for price in seller.pricelist_ids:
                    if not last_date or last_date < price.date_quotation:
                        last_price = price.price
                        last_date = price.date_quotation
                        #last_seller = price.
            if last_price:
                res[product.id] = (last_price, last_date)
            else:
                res[product.id] = (0.0, '')
        return res

    # Raw Material price browse:
    def _get_last_material_price(self, cr, uid, product, store, 
            context=None):
        ''' Return product requested last price with browse
            store: cache database
            return (price, date, error)
        '''
        if product.id in store['material']:
            return store['material'][product.id]

        if product.is_pipe: # Metal:
            weight = product.weight
            material = product.pipe_material_id.last_price
            unit = material * weight
            record = (
                unit, 
                u'(%sKg x %s€/kg=%s)' % (
                    weight, 
                    material,
                    unit,
                    ), 
                not unit,
                )
        else: # Material
            last_date = False
            last_price = 0.0
            for seller in product.seller_ids:
                for price in seller.pricelist_ids:
                    if not last_date or last_date < price.date_quotation:
                        last_price = price.price
                        last_date = price.date_quotation
            if last_price:
                record = (
                    last_price,
                    u'(%s€ [%s])' % (
                        last_price, last_date or '/'), 
                    False,
                    )
            else:
                record = (0.0, '', True)

        store['material'][product.id] = record
        return record

    # Raw Material price:
    def _get_hw_price(self, cr, uid, product_id, hw_ids, 
            store, context=None):
        ''' Calculate cost for HW BOM
        '''
        if product_id in store['hw']:
            return store['hw'][product_id]
        
        total = 0
        error = False
        calc = ''
        for item in hw_ids:
            cmpt = item.product_id
            qty = item.product_qty               
            cmpt_code = cmpt.default_code
            
            calc += u'[%s: N. %s x ' % (cmpt_code, qty)
            if cmpt.is_pipe: # Metal:
                weight = cmpt.weight
                material = cmpt.pipe_material_id.last_price
                unit = material * weight
                calc += u'(%s Kg x %s EUR/kg=%s)' % (
                    weight, 
                    material,
                    unit,
                    )

            else: # Other materials:
                record = self._get_last_material_price(
                    cr, uid, cmpt, store, context=context)
                unit = record[0]
                calc += record[1] #u'(%s EUR/unit.)' % unit

            if not unit:
                # TODO Add missed element (no price):
                error = True

            # Total part:
            subtotal = qty * unit    
            calc += u' = %s]   ' % subtotal
            total += subtotal
        
        record = (total, calc, error) # total, description
        store['hw'][product_id] = record
        return record

    def _get_product_bom_template(self, cr, uid, parent_code, store, 
            context=None):
        ''' Get template for industrial cost
        '''   
        if parent_code in store['template']:
            return store['template'][parent_code]
        if not parent_code:
            return False
            
        product_ids = self.search(cr, uid, [
            ('bom_selection', '=', True),
            ('default_code', '=ilike', '%s%%' % parent_code),
            ])
        if not product_ids:
            return False
    
        #product = self.browse(product_ids)[0]
        store['template'][parent_code] = product_ids[0]
        return product_ids[0]
        #product_cost[parent_code] = product.from_industrial

    def _get_bom_total_cost(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        if context is None:
            enable = False
        else:
            enable = context.get('enable_bom_cost', False)
            
        res = {}
        if not enable:
            _logger.warning('No enable_bom_cost activated in context')
            return res
        
        # cache database:
        store = {
            'material': {},
            'hw': {},
            'template': {},
            }

        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = {
                'bom_total_cost': 0.0,
                'bom_cost_mode': 'material', # default
                'bom_total_cost_text': '',
                'bom_total_cost_error': False,
                'bom_template_id': False,
                }
                
            if product.bom_alternative or product.bom_placeholder:
                # -------------------------------------------------------------
                # Placeholder:
                # -------------------------------------------------------------
                res[product.id]['bom_cost_mode'] = 'placeholder'
                continue
                
            dynamic_bom = product.dynamic_bom_line_ids
            if dynamic_bom:
                default_code = product.default_code or ''
                parent_code = '%-6s' % default_code[:6]

                # -------------------------------------------------------------
                # Dynamic bom:
                # -------------------------------------------------------------
                res[product.id]['bom_cost_mode'] = 'final'          
                total = 0.0
                res[product.id]['bom_template_id'] = \
                    self._get_product_bom_template(
                        cr, uid, parent_code, store, context=context)
                
                for item in sorted(
                        dynamic_bom, key=lambda x: x.product_id.default_code):
                    cmpt = item.product_id
                    if cmpt.bom_alternative or cmpt.bom_placeholder:
                        continue
                    
                    qty = item.product_qty               
                    cmpt_hw_ids = cmpt.half_bom_ids
                    if cmpt_hw_ids: # HW
                        (cmpt_unit, cmpt_detail, cmpt_error) = \
                            self._get_hw_price(cr, uid, cmpt.id, 
                                cmpt_hw_ids, store, context=context)
                        subtotal = cmpt_unit * qty        
                        res[product.id]['bom_total_cost_text'] += \
                            u'[HW:%s] N. %s x %s EUR=%s  ' % (
                                cmpt.default_code, qty, cmpt_unit, subtotal)
                    else: # Material 
                        (cmpt_unit, cmpt_detail, cmpt_error) = \
                            self._get_last_material_price(
                                cr, uid, cmpt, store, 
                                context=context)
                        subtotal = cmpt_unit * qty        
                        res[product.id]['bom_total_cost_text'] += \
                            u'[MP:%s] N. %s x %s EUR=%s  ' % (
                                cmpt.default_code, qty, cmpt_unit, subtotal)
                    total += subtotal
                res[product.id]['bom_total_cost'] = total
            else:
                # -------------------------------------------------------------
                # Half processed bom:
                # -------------------------------------------------------------
                hw_ids = product.half_bom_ids            
                if hw_ids:
                    res[product.id]['bom_cost_mode'] = 'half'   
                    (
                        res[product.id]['bom_total_cost'], 
                        res[product.id]['bom_total_cost_text'],
                        res[product.id]['bom_total_cost_error'],
                        ) = self._get_hw_price(
                            cr, uid, product.id, hw_ids, 
                            store, context=context)

                else:    
                    # ---------------------------------------------------------
                    # Raw material:
                    # ---------------------------------------------------------
                    (
                        res[product.id]['bom_total_cost'], 
                        res[product.id]['bom_total_cost_text'],
                        res[product.id]['bom_total_cost_error'],
                        ) = self._get_last_material_price(
                            cr, uid, product, store, 
                            context=context)
        return res
        
    _columns = {
        'bom_total_cost': fields.function(
            _get_bom_total_cost, method=True, 
            type='float', string='BOM Cost', 
            store=False, multi=True), 
        'bom_total_cost_text': fields.function(
            _get_bom_total_cost, method=True, 
            type='text', string='BOM Cost explode', 
            store=False, multi=True),                        
        'bom_total_cost_error': fields.function(
            _get_bom_total_cost, method=True, 
            type='boolean', string='BOM error', 
            store=False, multi=True),                        
        'bom_cost_mode': fields.function(
            _get_bom_total_cost, method=True, 
            type='text', string='BOM Cost explode', selection=[
                ('raw', 'Raw material'),
                ('half', 'Half processed'),
                ('final', 'Final product'),
                ('placeholder', 'Placeholder'),
                ],
            store=False, multi=True),                        
        'bom_template_id': fields.function(
            _get_bom_total_cost, method=True, 
            type='many2one', string='Template', relation='product.product',
            store=False, multi=True),            
        }
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
