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
import xmlrpclib
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

class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """
    
    _inherit = 'sale.order.line'
    
    def print_label_from_php(self, cr, uid, sol_id, mode, context=None):
        ''' Print action
        '''
        _logger.warning('Print PHP: ID %s mode %s' % (
            sol_id, mode))
        return True
        
class MrpProductionXmlrpcAgent(orm.Model):
    """ Model name: MrpProductionXmlrpcAgent
    """    
    _name = 'mrp.production.xmlrpc.agent'
    _description = 'XMLRPC Print agent'
    _rec_name = 'hostname'
    _order = 'hostname'

    def _clean_as_ascii(self, value):
        ''' Procedure for clean not ascii char in string
        '''
        res = ''
        for c in value:
            if ord(c) <127:
                res += c
            else:
                res += '#'           
        return res
        
    def _get_xmlrpc_server(self, cr, uid, printer_id, context=None):
        ''' Connect with server and return obj
        '''
        server_proxy = self.browse(cr, uid, printer_ids, context=context)
        
        try:
            xmlrpc_server = 'http://%s:%s' % (
                server_proxy.hostname, server_proxy.port)
        except:
            return False
        return xmlrpclib.ServerProxy(xmlrpc_server)
    
    def launch_operation_printer(self, cr, uid, ids, context=None):
        ''' Generate report and launch command:
        '''
        # Reload data for report
        
        # Generate PDF
        
        # Generate batch file
        
        # Generate command to lauch:
        print_report = 'prova.bat' # TODO Change
        
        # Launch with agent:
        xmlrpc_server = self._get_xmlrpc_server(
            cr, uid, ids[0], context=context)
        
        res = xmlrpc_server.execute(print_report)
        if res == 'OK':
            return True
        else:
            return False    
        return 
        
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
