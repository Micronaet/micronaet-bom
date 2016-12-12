#!/usr/bin/python
# -*- coding: utf-8 -*-
##############################################################################
#
#   Copyright (C) 2010-2012 Associazione OpenERP Italia
#   (<http://www.openerp-italia.org>).
#   Copyright(c)2008-2010 SIA "KN dati".(http://kndati.lv) All Rights Reserved.
#                   General contacts <info@kndati.lv>
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import os
import sys
import logging
import erppeek
import pickle
from datetime import datetime
from openerp.report import report_sxw
from openerp.report.report_sxw import rml_parse
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)

_logger = logging.getLogger(__name__)

class Parser(report_sxw.rml_parse):
    # Constructor:
    def __init__(self, cr, uid, name, context):        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_products': self.get_products,
            })

    # Method
    def get_products(self, data):
        ''' Get filter from data and return produc_ids list
        '''
        if data is None:
            data = {}
        
        cr = self.cr
        uid = self.uid
        context = {}
        
        product_pool = self.pool.get('product.product')
        cr.execute('''
            SELECT id 
            FROM product_product 
            WHERE 
                id NOT in (
                    SELECT l.product_id 
                    FROM mrp_bom_line l JOIN mrp_bom b ON (l.bom_id = b.id)
                    WHERE 
                        b.bom_category IN ('half', 'dynamic', 'parent')
                    )
            ORDER BY 
                default_code;
            ''')
        product_ids = [item[0] for item in cr.fetchall()]
        res = []
        for product in product_pool.browse(
                cr, uid, product_ids, context=context):
                
            # Jump product code start with 3 number    
            default_code = product.default_code
            if not default_code or default_code[:3].isdigit():
                continue
                
            # Jump no stock product:    
            net = product.mx_net_qty
            if net:
                res.append((product, net, product.mx_lord_qty))
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
