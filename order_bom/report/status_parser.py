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
            'load_objects': self.load_objects,
            'load_parent_objects': self.load_parent_objects,
            'get_db': self.get_db,
            'ok_modal': self.ok_modal,
            })

    # Method
    def get_db(self, name):
        res = self.master.get(name, [])
        res.sort(key=lambda x: (x.default_code, x.name))
        return res

    def load_objects(self, data):
        ''' Master function for generate data
        '''
        if data is None:
            data = {}
        
        cr = self.cr
        uid = self.uid
        context = {}
        
        sale_order = self.pool.get('sale.order')
        self.master = sale_order.get_component_in_product_order_open(
            cr, uid, context=context)
        
        self.master['table'] = {}
        return ''

    def ok_modal(self, hw, data):
        ''' Check modal selection and pipe hw elements
        '''
        if data is None:
            data = {}
        if data.get('modal', False) != 'pipe':
            return True # always print if not pipe
        if hw.product_id.half_bom_ids and \
                hw.product_id.half_bom_ids[0].product_id.is_pipe:
            return True
        else:    
            return False
            
    def load_parent_objects(self, data):
        ''' Master function for generate data parent report
        '''
        if data is None:
            data = {}
        
        cr = self.cr
        uid = self.uid
        context = {}
        
        start_code = data.get('start_code', False)
        domain = [('bom_category', '=', 'parent')]
        if start_code:
            domain.append(('code', '=ilike', start_code))
        bom_pool = self.pool.get('mrp.bom')
        bom_ids = bom_pool.search(
            cr, uid, domain, order='code', context=context)
        return bom_pool.browse(cr, uid, bom_ids, context=context)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
