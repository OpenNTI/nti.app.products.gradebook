#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 2

import zope.intid

from zope import component
from zope.location.location import locate
from zope.security.interfaces import IPrincipal
from zope.component.hooks import site as current_site

from ZODB.interfaces import IConnection

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import SYSTEM_USER_NAME

from ..interfaces import IGradeBook
from ..grades import PersistentGrade
		
def evolve_book(book, intids, instructor=None, ntiid=None):
	
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
				# create new grade
				new_grade = PersistentGrade()
				new_grade.value = grade.value
				new_grade.creator = instructor
				new_grade.username = username
				new_grade.AutoGrade = grade.AutoGrade
				new_grade.createdTime = grade.createdTime
				new_grade.lastModified = grade.lastModified
				
				# add to connection
				connection.add(new_grade)
				
				# remove old entry (no event)
				entry._delitemf(username, event=False)
				
				# add persistent entry (no event)
				entry._setitemf(username, new_grade)
				locate(new_grade, entry, name=username)
				intids.register(new_grade)
				
				# register in metadata catalog
				uid = intids.getId(new_grade)
				if queue is not None:
					try:
						queue.add(uid)
					except TypeError:
						pass
				count += 1
	return count
		
def do_evolve(context, generation=generation):

	conn = context.connection
	dataserver_folder = conn.root()['nti.dataserver']
	
	lsm = dataserver_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)
	total = 0
	sites = dataserver_folder['++etc++hostsites']
	for site in sites.values():
		with current_site(site):
			catalog = component.getUtility(ICourseCatalog)
			for entry in catalog.iterCatalogEntries():
				course = ICourseInstance(entry, None)
				if not course:
					continue
				# pick an instructor
				instructor = None
				instructors = list(course.instructors or ()) + [SYSTEM_USER_NAME]
				for instructor in instructors:
					instructor = IPrincipal(instructor, None)
					if instructor is not None:
						instructor = instructor.id
						break
				book = IGradeBook(course)
				count = evolve_book(book, intids, instructor, entry.ntiid)
				total += count

				logger.info('%s grades(s) for course %s were updated',
							entry.ntiid, count)

	logger.info('Gradebook evolution %s done; %s grades(s) updated',
				generation, total)
			
def evolve(context):
	do_evolve(context, generation)
