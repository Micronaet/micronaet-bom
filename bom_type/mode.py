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

class ProductProduct(orm.Model):
    """ Model name: ProductProduct
    """    
    _inherit = 'product.product'
    
    # Button events:
    def used_in_bom(self, cr, uid, ids, context=None):
        """ Product check bom
        """
        line_pool = self.pool.get('mrp.bom.line')
        bom_pool = self.pool.get('mrp.bom')
        
        line_ids = line_pool.search(cr, uid, [
            ('product_id', '=', ids[0])], context=context)
        bom_ids = list(set([item.bom_id.id for item in line_pool.browse(
            cr, uid, line_ids, context=context)]))

        if not bom_ids:
            raise osv.except_osv(
                _('Error'), 
                _('No BOM found where this product was used!'),
                )
                
        # TODO return also product?
        return {
            'type': 'ir.actions.act_window',
            'name': _('BOM used'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            #'res_id': 1,
            'res_model': 'mrp.bom',
            #'view_id': view_id, # False
            'views': [(False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', bom_ids)],
            'context': context,
            'target': 'current', # 'new'
            'nodestroy': False,
            }
        
    _columns = {
        'relative_type': fields.selection([
            ('none', 'None'),
            ('half', 'Halfworked BOM'),
            ('parent', 'Parent BOM'),
            ], 'Relative BOM type'),
        }
        
    _defaults = {
       'relative_type': lambda *x: 'none',
       }
