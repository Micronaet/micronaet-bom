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
            'get_objects': self.get_objects,
            'get_totals': self.get_totals,
            })
        
    def get_totals(self, ):
        ''' Total for report 
        '''
        return self.totals
        
    def get_objects(self, o, data=None):
        ''' Master function for generate data
        '''
        if data is None:
            data = {}
        
        self.totals = [
            0.0, # min
            0.0, # max
            ]
        cr = self.cr
        uid = self.uid
        context = {}
        
        res = []
        
        for item in o.dynamic_bom_line_ids:
            record = [
                # Component info:
                item.product_id.code, #0 
                item.product_id.name, #1
                item.product_uom.name, #2
                item.product_qty or 0.0, #3
                [], #4 Supplier 
                [], #5 Unit price
                0.0, #6 Min price
                0.0, #7 Max price
                0.0, #8 Min subtotal
                0.0, #9 Max subtotal                 
                ]
                
            for supplier in item.product_id.seller_ids:
                if supplier.name.name not in record[4]:
                    record[4].append(supplier.name.name)
                for pricelist in supplier.pricelist_ids:
                    record[5].append(pricelist.price)
            if record[5]: # If no price no calc:
                record[6] = min(record[5])
                record[7] = max(record[5])
                record[8] = record[6] * record[3]
                record[9] = record[7] * record[3]
            
                self.totals[0] += record[8]
                self.totals[1] += record[9]                    
            res.append(record)
        return res

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
