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
from zope.component.hooks import site as current_site

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from ZODB.interfaces import IConnection

from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

from ..interfaces import IGradeBook
from ..grades import PersistentGrade
from ..index import install_grade_catalog

def evolve_book(book, intids, instructor=None, grade_index=None):
	
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
				
				uid = intids.getId(new_grade)
				
				# register in grade catalog
				if grade_index is not None:
					grade_index.index_doc(uid, new_grade)
				
				# register in metadata catalog
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
	
	seen = set()
	
	# install grade catalog
	grade_index = install_grade_catalog(dataserver_folder, intids)
	
	# make grades persistent in all sites	
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
				
				# pick an instructor
				instructor = None
				roles = IPrincipalRoleMap(course, None)
				for principal in course.instructors or ():
					try:
						if 	roles is None or \
							roles.getSetting(RID_INSTRUCTOR, principal.id) is Allow:
							instructor = IUser(principal)
							break
					except (TypeError,IndexError,AttributeError):
						instructor = None
		
				book = IGradeBook(course)
				count = evolve_book(book, intids, instructor, grade_index)
				total += count

				logger.info('%s grades(s) updated for course %s',
							count, entry.ntiid)

	logger.info('Gradebook evolution %s done; %s grades(s) updated',
				generation, total)
	
	return total
			
def evolve(context):
	do_evolve(context, generation)
