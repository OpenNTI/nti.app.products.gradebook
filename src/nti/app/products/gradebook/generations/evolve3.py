#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

from zope.intid.interfaces import IIntIds

from zope.location.location import locate

from zope.catalog.interfaces import ICatalog

from ZODB.interfaces import IConnection

from nti.app.products.gradebook.generations.evolve2 import copy_grade
from nti.app.products.gradebook.generations.evolve2 import iter_courses
from nti.app.products.gradebook.generations.evolve2 import pick_course_instructor

from nti.app.products.gradebook.grades import Grade

from nti.app.products.gradebook.index import CATALOG_NAME

from nti.app.products.gradebook.interfaces import IGradeBook

def check_book(book, intids, instructor, grade_index):

	try:
		from nti.metadata import metadata_queue
		queue = metadata_queue()
	except ImportError:
		queue = None

	count = 0
	connection = IConnection(book)
	for part in book.values():
		for entry in part.values():
			for username, grade in list(entry.items()):
				if type(grade) == Grade:
					new_grade = copy_grade(grade, instructor, username)

					entry._delitemf(username, event=False)
					connection.add(new_grade)

					entry._setitemf(username, new_grade)
					locate(new_grade, entry, name=username)
					intids.register(new_grade)

					uid = intids.getId(new_grade)
					grade_index.index_doc(uid, new_grade)

					if queue is not None:
						try:
							queue.add(uid)
						except TypeError:
							pass
					count += 1
	return count

def do_evolve(context, generation=generation):
	logger.info("Gradebook evolution %s started", generation);

	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)
	grade_index = lsm.getUtility(ICatalog, name=CATALOG_NAME)

	total = 0
	for entry, course in iter_courses(dataserver_folder):
		book = IGradeBook(course)
		instructor = pick_course_instructor(course)
		count = check_book(book, intids, instructor, grade_index)
		total += count
		if count > 0:
			logger.info('%s grade(s) updated for course %s', count, entry.ntiid)

	logger.info('Gradebook evolution %s done; %s grade(s) updated',
				generation, total)

	return total

def evolve(context):
	"""
	Evolve to generation 3 by checking for non-persisent grades
	"""
	do_evolve(context, generation)
