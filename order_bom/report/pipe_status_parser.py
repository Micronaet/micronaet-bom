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
            'load_pipe_bom': self.load_pipe_bom,
            'get_filter': self.get_filter,
            })

    # Method
    def get_filter(self, data):
        if data is None:
            data = {}

        description = _('All halfwork')
        return description
        
    def load_pipe_bom(self, data):
        ''' Master function for generate data
        '''
        if data is None:
            data = {}
        
        cr = self.cr
        uid = self.uid
        context = {}
        
        product_pool = self.pool.get('product.product')
        product_ids = product_pool.search(cr, uid, [
            ('relative_type', '=', 'half'),
            ], context=context)
        
        res = {}        
        for item in product_pool.browse(cr, uid, product_ids, context=context):
            for component in item.half_bom_ids:
                product = component.product_id
                if not product.is_pipe:
                    continue
                if product.default_code not in res:
                    res[product.default_code] = []
                res[product.default_code].append(item.default_code)
        res = sorted(res)
        return res.iteritems()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
