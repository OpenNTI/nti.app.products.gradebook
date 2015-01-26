#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import csv
import logging
import argparse
from collections import defaultdict

from zope.configuration import xmlconfig, config

import nti.app.products.gradebook

from ..policies import CategoryGradeScheme
from ..policies import AssigmentGradeScheme
from ..policies import CS1323CourseGradingPolicy

def _check_int(value):
	try:
		value = int(value)
		assert value >= 0 
		return value
	except (TypeError, ValueError, AssertionError):
		return None
	
def _check_weight(value):
	try:
		value = float(value)
		assert value >= 0 and value <=100
		value = value/100.0 if value > 1 else value
		return value
	except (TypeError, ValueError, AssertionError):
		return None

def process(source):
	"""
	read a csv to produce a CS1323 policy object
	
	the columns of the file goes as follow
	1) Category Name; Category nane
	2) Category Weigh%: Category percentage weight
	3) Drop lowest: Drop the lowest assignments
	4) Assignment Identifier: Assigment id/name
	5) Assignment Weight %: Assignment percentage weight relative to category
	6) Assignment Late Penalty %: Assignment late penalty  discount percentage
	7) Assignment Grading Scheme: Assignment grading scheme
	8) Max Points: Max points for assignemt if Scheme is integer
	"""

	assignments = set()
	cat_assignment = defaultdict(defaultdict)
	categories = defaultdict(CategoryGradeScheme)
	result = CS1323CourseGradingPolicy()
	with open(source, 'rU') as fp:
		count = 0
		rdr = csv.reader(fp)
		for row in rdr:
			count += 1
			if not row or row[0].startswith('#'):
				continue

			if len(row) < 4:
				logger.warn("Invalid entry in row %s,%s", count, row)
				continue

			cat_name = row[0]
			if not cat_name:
				logger.error("No category name specified in row %s,%s", count, row)
				continue

			cat_weight = _check_weight(row[1])
			if not cat_weight:
				logger.error("Invalid category weight in row %s,%s", count, row)
				continue
	
			cat_scheme = categories[cat_name]
			if cat_scheme.weight is not None and cat_scheme.weight != cat_scheme.weight:
				logger.warn("category weight change in row %s,%s", count, row)
				
			dropLowest = row[2]
			if dropLowest is not None and not _check_int(dropLowest):
				logger.error("Invalid drop lowest value in row %s,%s", count, row)
				continue
			if cat_scheme.dropLowest != dropLowest:
				logger.warn("category drop-lowest change in row %s,%s", count, row)
			cat_scheme.dropLowest = dropLowest

			assignmentId = row[3]
			if not assignmentId:
				logger.error("No assignment found in row %s,%s", count, row)
				continue
			
			assignment_weight = _check_weight(row[4])
			if not assignment_weight:
				logger.error("Invalid assignment weight in row %s,%s", count, row)
				continue
			
			if assignmentId in assignments:
				logger.error("Duplicate assignment in row %s,%s", count, row)
				continue
			
			assignments.add(assignmentId)
			asg_scheme = AssigmentGradeScheme()
			asg_scheme.weight = assignment_weight
			
	return result

def main():

	context = config.ConfigurationMachine()
	xmlconfig.registerCommonDirectives(context)
	xmlconfig.file("configure.zcml", nti.app.products.gradebook, context=context)
	
	# parse arguments
	arg_parser = argparse.ArgumentParser(description="CS1323 policy CSV converter")
	arg_parser.add_argument('source', help="Source CSV file")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose",
							action='store_true', dest='verbose')
	args = arg_parser.parse_args()
	
	source = args.source
	verbose = args.verbose
	if not os.path.exists(source) or os.path.isdir(source):
		raise IOError("Invalid file")

	if verbose:
		ei = '%(asctime)-15s %(name)-5s %(levelname)-8s %(message)s'
		logging.basicConfig(level=logging.DEBUG, format=ei)

if __name__ == '__main__':
	main()
