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
import erppeek
import ConfigParser
import smtplib
import pdb
from datetime import datetime
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.mime.text import MIMEText
from email import Encoders

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('../openerp.cfg')
now = ('%s' % datetime.now())[:19]

config = ConfigParser.ConfigParser()
config.read([cfg_file])

# ERP Connection:
odoo = {
    'database': config.get('dbaccess', 'dbname'),
    'user': config.get('dbaccess', 'user'),
    'password': config.get('dbaccess', 'pwd'),
    'server': config.get('dbaccess', 'server'),
    'port': config.get('dbaccess', 'port'),
    }

# Mail:
now = now.replace('/', '_').replace('-', '_').replace(':', '_')

text = ''' 
Aggiornamento del %s
Segnalazione dei prodotti che non sono disponibili per le
produzioni cosi come sono pianificate.
La stampa ha visibile solo le righe con problemi.   
''' % now,

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (odoo['server'], odoo['port']),
    db=odoo['database'],
    user=odoo['user'],
    password=odoo['password'],
    )
mailer = odoo.model('ir.mail_server')
model = odoo.model('ir.model.data')

# -----------------------------------------------------------------------------
# SMTP Sent:
# -----------------------------------------------------------------------------
# Get mailserver option:
mailer_ids = mailer.search([])
if not mailer_ids:
    print('[ERR] No mail server configured in ODOO')
    sys.exit()

# First in sequence
odoo_mailer = sorted(mailer.browse(mailer_ids), key=lambda m: m.sequence)[0]

# Open connection:
print('[INFO] Sending using "%s" connection [%s:%s]' % (
    odoo_mailer.name,
    odoo_mailer.smtp_host,
    odoo_mailer.smtp_port,
    ))

if odoo_mailer.smtp_encryption in ('ssl', 'starttls'):
    smtp_server = smtplib.SMTP_SSL(
        odoo_mailer.smtp_host, odoo_mailer.smtp_port)
else:
    print('[ERR] Connect only SMTP SSL server!')
    sys.exit()

# smtp_server.ehlo()  # open the connection
# smtp_server.starttls()
smtp_server.login(odoo_mailer.smtp_user, odoo_mailer.smtp_pass)

# filename = u'MRP fattib. produzioni schedulate %s.xlsx' % now
# fullname = os.path.expanduser(
#    os.path.join(smtp['folder'], filename))
# context = {
#    'save_mode': fullname,
#    }

# Setup context for MRP:
# odoo.context = context
bom = odoo.model('mrp.bom')

# Launch extract procedure for this mode:
# fullname = bom.report_mrp_status_component_excel_file()
fullname = '/tmp/mrp_2023-02-08_15_26_49.xlsx'  # todo remove
filename = 'MRP Fattibili.xlsx'
to_address = 'nicola.riolini@gmail.com'.replace(' ', '')  # todo

for to in to_address.split(','):
    print('Sending mail to %s ...' % to)
    # Header:
    msg = MIMEMultipart()
    msg['Subject'] = 'Stampa fattibilita\' produzioni schedulate: %s' % now
    msg['From'] = odoo_mailer.smtp_user
    msg['To'] = to   # _address
    # msg.attach(MIMEText(text, 'html'))

    # Attachment:
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(open(fullname, 'rb').read())
    Encoders.encode_base64(part)
    part.add_header(
        'Content-Disposition', 'attachment; filename="%s"' % filename)
    msg.attach(part)

    # Send mail:
    smtp_server.sendmail(odoo_mailer.smtp_user, to, msg.as_string())
smtp_server.quit()
