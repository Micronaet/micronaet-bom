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
    """ Model name: ProductProduct add utility for report
    """    
    _inherit = 'product.product'

    def report_get_objects_bom_industrial_cost(self, cr, uid, datas=None, 
            context=None):
        ''' Integration report
        '''
        _logger.info('Start extracting...')
        # TODO reactivate
        #data =  {
        #    'active_ids': False, # Load all template
        #    'model': 'product.product', 
        #    'wizard': True,
        #   }
        res = super(
            ProductProduct, self).report_get_objects_bom_industrial_cost(
                cr, uid, datas=datas, context=context)
        _logger.info('Start reporting...')
        # removed
        return res
        
        # ---------------------------------------------------------------------
        # NEW VERSIONE:
        # ---------------------------------------------------------------------
        f_bom = open('/home/odoo/0.bom_report.csv', 'w')

        header = u'Componente|Q.|UM|Prezzo|Totale\n'
        for item in res:
            (min, max, error, components, extra1, extra2, index, total, 
                product, parameter, total_text, pipe_total_weight) = item
            f_bom.write(u'%s|%s' % (
                product.default_code, 
                product.name,
                ))
            
            # -----------------------------------------------------------------
            # Component line:
            # -----------------------------------------------------------------
            f_bom.write(header)
            for line in components:
                (name, q, um, price, total, list_detail, hw, element, 
                    red_price, fabric_text) = line
                if hw:
                    block1 = u'%s %s' % (
                        name,
                        #list_ids,
                        hw.default_code,                
                        )  
                else:
                    block1 = name              
                    
                f_bom.write(u'%s|%s|%s|%s|%s\n' % (
                    block1,
                    q,
                    um,
                    price,
                    total,            
                    ))
                
            # -----------------------------------------------------------------
            # Work
            # -----------------------------------------------------------------
            f_bom.write(u'Manodopera|Prodotto|Totale\n')
            for item, details, time_qty in extra1:
                f_bom.write('%s (unit. %s)||%s|%s\n' % (
                    item.cost_id.name,
                    item.cost_id.unit_cost,
                    item.product_id.default_code or '/',
                    details,            
                    ))

            # -----------------------------------------------------------------
            # Industrial
            # -----------------------------------------------------------------
            f_bom.write(u'Costi industriali|Prodotto|Totale\n')
            for item, details, time_qty in extra2:
                f_bom.write('%s (unit. %s)||%s|%s\n' % (
                    item.cost_id.name,
                    item.cost_id.unit_cost,
                    item.product_id.default_code or '/',
                    details,            
                    ))

            # -----------------------------------------------------------------
            # Total:
            # -----------------------------------------------------------------
            f_bom.write(u'Subtotali|%s|Costo|%s-%s\n' % (
                total_text, min, max
                ))
            #f_bom.write('Indici|%s|Vendita|%s-%s\n' % (
            #    total['index'],
            #    total['margin']
            #    ))
            
        f_bom.close()
        return res
            
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
