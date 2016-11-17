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

class MrpBom(orm.Model):
    """ Model name: Mrp bom
    """    
    _inherit = 'mrp.bom'
    
    def set_as_checked(self, cr, uid, ids, context=None): 
        ''' Set as checked the bom and save the date
        '''
        # TODO write message
        return self.write(cr, uid, ids, {
            'checked': True,
            'checked_user_id': uid,
            'check_date': datetime.now().strftime(
                DEFAULT_SERVER_DATETIME_FORMAT),
            }, context=context)
    
    def _get_check_date_test(self, cr, uid, ids, fields, args, context=None):
        ''' Fields function for calculate 
        '''
        res = {}
        for item in self.browse(cr, uid, ids, context=context):
            res[item.id] = item.check_date < item.write_date
        return res    
        
    _columns = {
        'checked': fields.boolean('Checked'),
        'check_user_id': fields.many2one(
            'res.users', 'Checked user'),
        'check_date': fields.date('Check date'),
        'modified_after': fields.function(
            _get_check_date_test, method=True, 
            type='boolean', string='Modified after', store=False),                         
        'check_detail': fields.text('Check detail'),
        }        
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
