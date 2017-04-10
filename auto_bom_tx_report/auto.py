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

class MrpProduction(orm.Model):
    """ Model name: MrpProduction
    """
    
    _inherit = 'mrp.production'
    
    def send_fabric_mrp_report_scheduler(self, cr, uid, context=None):
        ''' Generate PDF with data and send mail
        '''
        #filename = 'tmp.pdf' # TODO change
        report_name = 'stock_status_explode_report'
        datas = {
            # Report setup:
            #'record_ids': [job.id],
            'model': 'mrp.production',
            'active_id': False,
            'active_ids': [],
            'context': context,

            # Datas setup:
            'mp_mode': 'fabric', 
            'only_negative': False, # TODO
            'without_type_ids': [], 
            'mode': 'component', 
            'type_id': False,
            'with_deadline': False, 
            'days': 30, 
            'first_supplier_id': False, 
            'with_type_ids': []
            }
    
        # -----------------------------------------------------------------
        # Call report:            
        # -----------------------------------------------------------------
        try:
            result, extension = openerp.report.render_report(
                cr, uid, [], report_name, datas, context)
        except:
            _logger.error('Error generation TX report [%s]' % (
                sys.exc_info(),))
            return False
            
        #file_pdf = open(filename, 'w') # XXX binary?
        #file_pdf.write(result)
        #file_pdf.close()

        # -----------------------------------------------------------------
        # Send report:
        # -----------------------------------------------------------------
        # Send mail with attachment:
        group_pool = self.pool.get('res.groups')
        model_pool = self.pool.get('ir.model.data')
        thread_pool = self.pool.get('mail.thread')
        group_id = model_pool.get_object_reference(
            cr, uid, 'textilene_status', 'group_textilene_admin')[1]    
        partner_ids = []
        for user in group_pool.browse(
                cr, uid, group_id, context=context).users:
            partner_ids.append(user.partner_id.id)
            
        thread_pool = self.pool.get('mail.thread')
        thread_pool.message_post(cr, uid, False, 
            type='email', 
            body='Stato tessuti settimanale', 
            subject='Invio automatico stato tessuto: %s' % date,
            partner_ids=[(6, 0, partner_ids)],
            attachments=[('Completo.pdf', result)], 
            context=context,
            )
        return True            

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
