#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import sys
import argparse

from zope import component

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistories

from nti.app.products.gradebook.utils import set_grade_by_assignment_history_item

from nti.assessment.interfaces import IQAssignment

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid

def get_course(ntiid):
	obj = find_object_with_ntiid(ntiid)
	course = ICourseInstance(obj, None)
	if course is None or ILegacyCourseInstance.providedBy(course):
		raise ValueError("Could not find course with NTIID %s", ntiid)
	return course

def get_assignment(ntiid):
	result = component.queryUtility(IQAssignment, name=ntiid)
	if result is None:
		raise ValueError("Could not find assignment with NTIID %s", ntiid)
	return result

def _process_args(args):
	set_site(args.site)
	course = get_course(args.course)
	_ = get_assignment(args.assignment)
	histories = IUsersCourseAssignmentHistories(course)
	if not args.users:
		users = list(histories.keys())
	else:
		users = set(args.users)

	assignmentId = args.assignment
	for username in users:
		history = histories[username]
		if assignmentId not in history:
			continue
		item = history[assignmentId]
		submission = item.Submission
		if not submission: # empty -> manual grades
			continue
		grade = set_grade_by_assignment_history_item(item, args.overwrite)
		if args.verbose and grade is not None:
			logger.info("Setting grade for user %s to %s", username, grade.value)

def main():
	arg_parser = argparse.ArgumentParser(description="Grade course assignment submissions")
	arg_parser.add_argument('-v', '--verbose', help="Be Verbose", action='store_true',
							dest='verbose')
	
	arg_parser.add_argument('-o', '--overwrite', help="Overwrite grades", action='store_true',
							dest='overwrite')

	arg_parser.add_argument('-s', '--site',
							dest='site',
							help="Application SITE.")

	arg_parser.add_argument('-c', '--course',
							dest='course',
							help="Course NTIID.")

	arg_parser.add_argument('-a', '--assignment',
							dest='assignment',
							help="Assignment NTIID.")

	arg_parser.add_argument('-u', '--users',
							 dest='users',
							 nargs="+",
							 default=(),
							 help="The usernames")

	args = arg_parser.parse_args()
	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	if not args.site:
		raise ValueError("Application site not specified")

	if not args.course:
		raise ValueError("Course not specified")

	if not args.assignment:
		raise ValueError("Assignment not specified")

	conf_packages = ('nti.appserver',)
	context = create_context(env_dir, with_library=True)

	run_with_dataserver(environment_dir=env_dir,
						verbose=args.verbose,
						xmlconfig_packages=conf_packages,
						context=context,
						minimal_ds=True,
						function=lambda: _process_args(args))
	sys.exit(0)

if __name__ == '__main__':
	main()
