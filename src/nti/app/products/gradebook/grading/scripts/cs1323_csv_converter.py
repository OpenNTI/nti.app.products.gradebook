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
import copy
import logging
import argparse
import simplejson
from collections import defaultdict

from zope import component
from zope.configuration import xmlconfig, config

from nti.externalization.externalization import to_external_object

import nti.app.products.gradebook

from ...interfaces import IGradeScheme
from ...interfaces import IIntegerGradeScheme
from ...interfaces import INumericGradeScheme

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
	
def _check_float(value):
	try:
		value = float(value)
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
	cat_assignments = defaultdict(defaultdict)
	categories = defaultdict(CategoryGradeScheme)
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
			cat_name = unicode(cat_name)

			cat_weight = _check_weight(row[1])
			if not cat_weight:
				logger.error("Invalid category weight in row %s,%s", count, row)
				continue
	
			cat_scheme = categories[cat_name]
			if cat_scheme.weight is not None and cat_scheme.weight != cat_scheme.weight:
				logger.warn("category weight change in row %s,%s", count, row)
			cat_scheme.weight = cat_weight
			
			dropLowest = _check_int(row[2] or 0)
			if dropLowest is None:
				logger.error("Invalid drop lowest value in row %s,%s", count, row)
				continue
			if cat_scheme.dropLowest is not None and cat_scheme.dropLowest != dropLowest:
				logger.warn("category drop-lowest change in row %s,%s", count, row)
			cat_scheme.dropLowest = dropLowest

			assignmentId = row[3]
			if not assignmentId:
				logger.error("No assignment found in row %s,%s", count, row)
				continue
			assignmentId = unicode(assignmentId)

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
			
			assignment_penalty = _check_weight(row[5]) if row[5] else 0
			if assignment_penalty is None:
				logger.warn("Invalid assignment penalty in row %s,%s", count, row)
				assignment_penalty = 0
			asg_scheme.penalty = assignment_penalty
			
			name = row[6].lower() if row[6] else 'integer'
			scheme = component.queryUtility(IGradeScheme, name=name)
			if scheme is None:
				logger.error("Invalid assignment grade scheme in row %s,%s", count, row)
				continue
			asg_scheme.scheme = copy.copy(scheme)
			
			if INumericGradeScheme.providedBy(scheme):
				if len(row) < 8:
					logger.error("No max points specififed for assignment in row %s,%s", 
								count, row)
					continue
				elif IIntegerGradeScheme.providedBy(scheme):
					points = _check_int(row[7])
				else:
					points = _check_float(row[7])
		
				if not points:
					logger.error("Invalid assignment max points in row %s,%s", count, row)
					continue
				asg_scheme.scheme.max = points
			
			# ready to add
			cat_assignments[cat_name][assignmentId] = asg_scheme

	for cat_name, cat_scheme in list(categories.items()):
		items = cat_assignments.get(cat_name)
		if not items:
			logger.warn("Nothing to add for category %s", cat_name)
			categories.pop(cat_name, None)
		else:
			items = dict(items)
			cat_scheme.assigments = items
	
	if categories:
		result = CS1323CourseGradingPolicy()
		result.categories = dict(categories)
	else:
		logger.error("Nothing to add for policy")
		result = None
	return result

def externalize(policy, output):
	logger.info("Writing policy to %s", output)
	external = to_external_object(policy)
	with open(output, "wb") as fp:
		simplejson.dump(external, fp, indent=4)

def main():

	context = config.ConfigurationMachine()
	xmlconfig.registerCommonDirectives(context)
	xmlconfig.file("configure.zcml", nti.app.products.gradebook, context=context)
	
	# parse arguments
	arg_parser = argparse.ArgumentParser(description="CS1323 policy CSV converter")
	arg_parser.add_argument('source', help="Source CSV file")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose",
							action='store_true', dest='verbose')
	arg_parser.add_argument('-o', '--output', help="output path", dest='output')
	args = arg_parser.parse_args()
			
	source = args.source
	verbose = args.verbose
	if not os.path.exists(source) or os.path.isdir(source):
		raise IOError("Invalid file")
	source = os.path.expanduser(source)
	
	output = args.output
	output = os.path.expanduser(output) if output else None
	if output and os.path.exists(output) and os.path.isdir(output):
		name = os.path.splitext(os.path.basename(source))[0]
		output = os.path.join(output, '%s.json' % name)
		
	if verbose:
		ei = '%(asctime)-15s %(name)-5s %(levelname)-8s %(message)s'
		logging.basicConfig(level=logging.DEBUG, format=ei)

	policy = process(source)
	if policy is not None and output:
		externalize(policy, output)

if __name__ == '__main__':
	main()
