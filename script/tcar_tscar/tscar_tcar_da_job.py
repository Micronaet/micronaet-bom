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
import pdb
import sys
import xlrd
import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
# Parameters:
# -----------------------------------------------------------------------------
# Stagione attuale: 2024-25
from_date = '2023-09-01'
to_date = '2024-08-31'

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
cfg_file = os.path.expanduser('../openerp.fia')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint


# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (
        server, port),
    db=dbname,
    user=user,
    password=pwd,
    )

# Pool used:
picking_pool = odoo.model('stock.picking')
move_pool = odoo.model('stock.move')
product_pool = odoo.model('product.product')

log_f = open('./fabric_log.csv', 'w')
product_update = {}

# -----------------------------------------------------------------------------
# Load TCAR / TSCAR:
# -----------------------------------------------------------------------------
in_ids = move_pool.search([
    ('picking_id', '!=', False),
    ('picking_id.origin', '=ilike', 'OF%'),
    ('picking_id.date', '>=', '%s 00:00:00' % from_date),
    ('picking_id.date', '<=', '%s 23:59:59' % to_date),
    ('product_id.inventory_category_id.name', '=', 'Tessuti'),
    ])

out_ids = move_pool.search([
    ('picking_id', '!=', False),
    ('picking_id.dep_mode', '=', 'cut'),
    ('picking_id.date', '>=', '%s 00:00:00' % from_date),
    ('picking_id.date', '<=', '%s 23:59:59' % to_date),
    ('product_id.inventory_category_id.name', '=', 'Tessuti'),
    ])

# move.picking_id.location_dest_id.name == 'Stock'
loop = [
    (1, 'in', in_ids),
    (0, 'out', out_ids),
    ]

print('Collect TSCAR from picking job TCAR from OF')
for pos, mode, move_ids in loop:
    counter = 0
    total = len(move_ids)
    for move in move_pool.browse(move_ids):
        counter += 1
        product = move.product_id
        default_code = (product.default_code or '').upper()
        quantity = move.product_qty
        picking = move.picking_id
        if not picking:
            print('%s su %s [WARNING] Mode %s no picking' % (
                counter, total, move.id))
            continue

        picking_name = '%s - %s' % (picking.name, picking.origin or '')
        if not default_code:
            print('%s su %s [ERROR] %s' % (counter, total, default_code))
            log_f.write('%s|%s|%s|%s|%s|%s\n' % (
                default_code, mode, quantity, picking_name, picking.date,
                'ERROR'))
            log_f.flush()
            continue

        print('%s su %s [INFO] %s' % (counter, total, default_code))
        log_f.write('%s|%s|%s|%s|%s|%s\n' % (
            default_code, mode, quantity, picking_name, picking.date, 'OK'))
        log_f.flush()
        product_id = product.id
        if product_id not in product_update:
            product_update[product_id] = [0.0, 0.0]  # tcar, tscar
        product_update[product_id][pos] += quantity

print('Continua se vuoi aggiornare')
pdb.set_trace()
# -----------------------------------------------------------------------------
# Clean TSCAR TCAR data:
# -----------------------------------------------------------------------------
print('Clean TSCAR TCAR in all Tessuti')
product_ids = product_pool.search([
    ('inventory_category_id.name', '=', 'Tessuti'),
    ])

for product in product_pool.browse(product_ids):
    product_pool.write([product.id], {
        'tscar': 0.0,
        'tcar': 0.0,
        })

# -----------------------------------------------------------------------------
# Update product:invent
# -----------------------------------------------------------------------------
print('Update TSCAR TCAR in all Tessuti')
for product_id in product_update:
    tcar, tscar = product_update[product_id]
    # print('ID: %s [SCAR %s] [TCAR %S]' % (product_id, tscar, tcar))

    product_pool.write([product_id], {
        'tcar': tcar,
        'tscar': tscar,
        })
