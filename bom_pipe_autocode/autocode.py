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

    def is_pipe_generate_pipe_data_from_code(
            self, cr, uid, ids, field, context=None):
        ''' from name generate code
        '''    
        return self.generate_pipe_data_from_code(
            cr, uid, ids, 'name', context=context)
            
    def yet_pipe_generate_pipe_data_from_code(
            self, cr, uid, ids, field, context=None):
        ''' from default_code re-generate code
        '''    
        return self.generate_pipe_data_from_code(
            cr, uid, ids, 'default_code', context=context)
    
    def generate_pipe_data_from_code(self, cr, uid, ids, field, context=None):
        ''' Extract data from code:
        '''
        assert len(ids) == 1, 'Works only with one record a time'
        
        part = 4
        product_proxy = self.browse(cr, uid, ids, context=context)
        default_code = product_proxy.__getattribute__(field).upper()        
        code = default_code.split('X')

        if len(code) != 3:
            return False

        # Extract data:        
        material = code[0][:part]
        pipe_diameter = code[0][part:]
        pipe_thick = code[1].replace(',', '.')
        pipe_length = code[2]
        
        material_pool = self.pool.get('product.pipe.material')
        material_ids = material_pool.search(cr, uid, [
            ('code', '=', material)], context=context)
            
        # Default:
        pipe_min_order = False
        pipe_resistence = ''
        first_supplier_id = False
        pipe_material_id = False
        if material_ids:    
            pipe_material_id = material_ids[0]
            material_proxy = material_pool.browse(
                cr, uid, material_ids, context=context)    
            material_name = material_proxy.name

            # Header data:
            pipe_resistence = material_proxy[0].resistence
            first_supplier_id = material_proxy[0].first_supplier_id.id
            
            for lot in material_proxy[0].lot_ids:
                if lot.diameter == float(pipe_diameter):
                    pipe_min_order = lot.order_lot
                    break
                
        else: # not found
            _logger.warning('Material not fount: %s' % material)
            material_name = material
        
        name = _('Tubo %s Diam. %s Spess. %s Lungh. %s') % (
            material_name, # TODO
            pipe_diameter,
            pipe_thick,
            pipe_length,
            )
            
        data = {
            'name': name,
            'default_code': default_code,
            
            'is_pipe': True,
            'pipe_diameter': pipe_diameter,
            'pipe_thick': pipe_thick,
            'pipe_length': pipe_length,
            #'pipe_resistence': pipe_resistence,
            #'pipe_min_order': pipe_min_order,
            'pipe_material_id': pipe_material_id,
            #'first_supplier_id': first_supplier_id, # TODO add dep.
            }               
        if pipe_resistence:       
            data['pipe_resistence'] = pipe_resistence

        if first_supplier_id:
            data['first_supplier_id'] = first_supplier_id
        
        if pipe_min_order:
            data['pipe_min_order'] = pipe_min_order
            
        return self.write(cr, uid, ids, data, context=context)
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
