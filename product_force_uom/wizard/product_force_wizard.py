# -*- coding: utf-8 -*-
###############################################################################
#
# ODOO (ex OpenERP) 
# Open Source Management Solution
# Copyright (C) 2001-2015 Micronaet S.r.l. (<http://www.micronaet.it>)
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
import openerp.addons.decimal_precision as dp
from openerp.osv import fields, osv, expression, orm
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from openerp import SUPERUSER_ID
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import (DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class ProductProductUomForceWizard(orm.TransientModel):
    ''' Wizard for
    '''
    _name = 'product.product.uom.force.wizard'

    # --------------------
    # Wizard button event:
    # --------------------
    def force_uom(self, cr, uid, ids, context=None):
        ''' Force uom in product
        '''
        product_pool = self.pool.get('product.product')
        
        if context is None:
            context = {}
        active_id = context.get('active_id', False)
        if not active_id:
            raise osv.except_osv(
                _('No product'), 
                _('Error reading product to force'),
                )
        product_proxy = product_pool.browse(
            cr, uid, active_id, context=context)    
        previous_uom = product_proxy.uom_id.name    
            
        wiz_proxy = self.browse(cr, uid, ids, context=context)[0]
        
        current_uom = wiz_proxy.uom_id.name
        uom_id = wiz_proxy.uom_id.id
        cr.execute('''
            UPDATE product_template 
            SET uom_id=%s, uos_id=%s, uom_po_id=%s
            WHERE id in (
                SELECT product_tmpl_id 
                FROM product_product 
                WHERE id=%s);            
            ''', (uom_id, uom_id, uom_id, active_id))

        # log message for force
        self.pool.get('product.product').message_post(cr, uid, active_id, 
            type='email', 
            body=_('Forced UOM from %s to %s') % (
                previous_uom, current_uom), 
            subject='Change UOM product: %s' % product_proxy.default_code,
            partner_ids=[(6, 0, (1, ))],
            attachments=[], context=context
            )
        return True

    _columns = {
        'uom_id': fields.many2one(
            'product.uom', 'Force UOM', required=True),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
