# -*- coding: utf-8 -*-
###############################################################################
#
#    Copyright (C) 2001-2014 Micronaet SRL (<http://www.micronaet.it>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
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

class StructureStructure(orm.Model):
    """ Model name: StructureStructure
    """
    
    _inherit = 'structure.structure'
        
    _columns = {
        'dynamic_bom_id': fields.many2one('mrp.bom', 'Dynamic BOM', 
            help='Dynamic BOM with all element masked depend on code struct.'),
        }

class ProductProduct(orm.Model):
    """ Model name: Product bom directly 
    """
    
    _inherit = 'product.product'
        
    def _get_dynamic_bom_line_ids(self, cr, uid, ids, fields, args, 
            context=None):
        ''' Fields function for calculate BOM lines
        '''
        line_pool = self.pool.get('mrp.bom.line')        
        res = {}
        for product in self.browse(cr, uid, ids, context=context):
            res[product.id] = []  # TODO
        return res

    _columns = {
        'dynamic_bom_line_ids': fields.function(
            _get_dynamic_bom_line_ids, method=True, 
            type='one2many', relation='mrp.bom.line', 
            string='Dynamic BOM line', readonly=True, store=False),                        
        }

class MRPBomLine(orm.Model):
    """ Model name: MRP Bom line
    """
    
    _inherit = 'mrp.bom.line'
    
    
    _columns = {
        'dynamic_mask': fields.char('Dynamic mask', size=20),
        }

class MRPBom(orm.Model):
    """ Model name: MRP Bom new bom_line_ids
    """
    
    _inherit = 'mrp.bom'
        
    _columns = {
        'structure_id': fields.many2one('structure.structure', 'Structure', 
            help='Structure reference'),
        }


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
