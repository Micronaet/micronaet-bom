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
    # Property:
    table = []
    product = {}
    component = {}
    no_structure = {}
    no_product = {}
    no_component = {}
    
    # Constructor:
    def __init__(self, cr, uid, name, context):        
        super(Parser, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'get_objects': self.get_objects,
            'get_db': self.get_db,
            })

    # Method
    def get_db(self, name):
        return self.__getattribute__(name)

    def get_objects(self, data):
        ''' Master function for generate data
        '''
        if data is None:
            data = {}
        
        cr = self.cr
        uid = self.uid
        context = {}
        
        sale_order = self.pool.get('sale.order')
        data = sale_order.get_component_in_product_order_open(
            cr, uid, context=context)
        
        # Save in object:    
        self.product = data.get('product')    
        self.component = data.get('component')
        
        # Error
        self.no_structure = data.get('no_structure')
        self.no_product = data.get('no_product')
        self.no_component = data.get('no_component')
        
        for key, value in self.product.iteritems():
            self.table.append([
                0.0, # INV
                0.0, # TCAR
                0.0, # TSCAR
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], # MM
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], # OC
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], # OF
                [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], # SAL
                key, # Browse product
                ])
        return ''

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
