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

class MrpProductionXmlrpcAgent(orm.Model):
    """ Model name: MrpProductionXmlrpcAgent
    """
    
    _name = 'mrp.production.xmlrpc.agent'
    _description = 'XMLRPC Print agent'
    _rec_name = 'hostname'
    _order = 'hostname'
    
    _columns = {
        'hostname': fields.char('IP address', size=64, required=True, 
            help='Use format: 192.168.1.1'),
        'port': fields.integer('Port', required=True),
        'workcenter_id': fields.many2one(
            'mrp.workcenter', 'Workcenter', required=True),
        'note': fields.text('Note'),
        }
        
    _defaults = {
        'port': lambda *x: 8000,
        }    
        
    _sql_constraints = [(
        'name_uniq', 'unique(workcenter_id)', 
        'Every workcenter must have one Agent linked!'
        )]
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
