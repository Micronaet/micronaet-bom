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
from openerp.tools import (
    DEFAULT_SERVER_DATE_FORMAT, 
    DEFAULT_SERVER_DATETIME_FORMAT, 
    DATETIME_FORMATS_MAP, 
    float_compare)


_logger = logging.getLogger(__name__)


class SaleOrderLine(orm.Model):
    """ Model name: SaleOrderLine
    """
    
    _inherit = 'sale.order.line'
    
    def print_label_from_php(self, cr, uid, sol_id, mode, total, context=None):
        ''' Print action
        '''
        _logger.warning('Print PHP: ID %s mode %s [Total: %s]' % (
            sol_id, mode, total))
            
        # TODO Be moved!!!!!
        # Pool used:
        mrp_pool = self.pool.get('mrp.production')
        agent_pool = self.pool.get('mrp.production.xmlrpc.agent')
        
        if context is None:
            context = {}

        # Get used elements:        
        current_proxy = self.browse(cr, uid, sol_id, context=context)
        mrp = current_proxy.mrp_id
        job = current_proxy.working_line_id
                
        # Get launch agent for line:
        agent_ids = agent_pool.search(cr, uid, [
            ('workcenter_id', '=', job.workcenter_id.id)], context=context)
        if not agent_ids:
            _logger.error('Error no agent for current line')
        agent_id = agent_ids    

        # Select job line with q. for label printing:
        ctx = dict.copy(context)
        ctx['sol_job'] = {}
        ctx['sol_job_mode'] = mode
        ctx['collect_label'] = True # for return structure of label 

        if total: # Only the current line with total passed:
            ctx['sol_job'][sol_id] = total
        else: # all remain qty                
            for line in job.working_ids:
                if line.working_qty:
                    ctx['sol_job'][line.id] = line.working_qty

        _logger.warning('Generate remain job label:')
        mrp_pool.generate_label_job(cr, uid, [mrp.id], context=ctx)
        
        _logger.warning('Generate print job label in PDF:')
        collect_label_db = mrp_pool.merge_pdf_mrp_label_jobs(
            cr, uid, [mrp.id], context=ctx)

        # XXX Note: for now the dabase is full of data (for print also one label
        # now we use only print all function
        
        # Generate command for print the label generated:
        print_all_label = collect_label_db.values()
        print_command = ''
        for seq, command in sorted(print_all_label):
            print_command += '%s\n\r' % command

        # Launch operation from remote agent:
        _logger.info('Launch print command remotely')
        agent_pool.launch_operation_printer(
            cr, uid, agent_id, print_command, context=context)
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
        
    def _get_xmlrpc_server(self, cr, uid, agent_id, context=None):
        ''' Connect with server and return obj
        '''
        server_proxy = self.browse(cr, uid, agent_id, context=context)
        
        try:
            xmlrpc_server = 'http://%s:%s' % (
                server_proxy.hostname, server_proxy.port)
        except:
            return False
        return xmlrpclib.ServerProxy(xmlrpc_server)
    
    def launch_operation_printer(self, cr, uid, agent_id, command, context=None):
        ''' Generate report and launch command:
        '''
        # Launch with agent:
        xmlrpc_server = self._get_xmlrpc_server(
            cr, uid, agent_id, context=context)
        
        res = xmlrpc_server.execute(command)
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
