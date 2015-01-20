#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

import zope.intid

from zope import component
from zope.location.location import locate
from zope.component.hooks import site as current_site

from zope.catalog.interfaces import ICatalog

from ZODB.interfaces import IConnection

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from ..grades import Grade
from ..index import CATALOG_NAME
from ..interfaces import IGradeBook

from .evolve2 import copy_grade
from .evolve2 import pick_course_instructor

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
	intids = lsm.getUtility(zope.intid.IIntIds)
	grade_index = catalog = lsm.getUtility(ICatalog, name=CATALOG_NAME)
	
	seen = set()
	total = 0
	sites = dataserver_folder['++etc++hostsites']
	for site in sites.values():
		with current_site(site):
			catalog = component.getUtility(ICourseCatalog)
			for entry in catalog.iterCatalogEntries():
				course = ICourseInstance(entry, None)
				if course is None:
					continue
				if entry.ntiid in seen:
					continue
				seen.add(entry.ntiid)
				instructor = pick_course_instructor(course)
			
				book = IGradeBook(course)
				count = check_book(book, intids, instructor, grade_index)
				total += count

				logger.info('%s grade(s) updated for course %s',
							count, entry.ntiid)

	logger.info('Gradebook evolution %s done; %s grade(s) updated',
				generation, total)
	
	return total
			
def evolve(context):
	"""
	Evolve to generation 3 by checking for non-persisent grades
	"""
	do_evolve(context, generation)
