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
            'load_bom': self.load_bom,
            'get_filter': self.get_filter,
            })

    # Method
    def get_filter(self, data):
        if data is None:
            data = {}

        start_code = data.get('start_code', '')
        
        description = _('Line: %s') % only
        if start_code:
            description += _('Code start with: %s') % start_code
        return description
        
    def load_bom(self, data):
        ''' Master function for generate data list of product in 
            parent bom and dynamic bom, half bom
        '''
        if data is None:
            data = {}
        
        cr = self.cr
        uid = self.uid
        context = {}

        line_pool = self.pool.get('mrp.bom.line')
        start_code = data.get('start_code', '')        
        
        # Create dynamic domain:
        domain = [('bom_id.bom_category', 'in', ('half', 'parent', 'dynamic')]
        if start_code:
            domain.append(
                ('product_id.default_code', '=ilike', '%s%%' % start_code))
                
        line_ids = line_poo.search(cr, uid, domain, context=context)
        products = {}
        
        for line in line_pool.browse(cr, uid, line_ids, context=context):
            product = line.product_id
            if line.product_id.default_code not in products:
                products[product.default_code] = []
            products[product.default_code].append(line)        
        return sorted(products.iteritems())

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
