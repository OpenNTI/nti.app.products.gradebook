#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.intid

from zope import component
from zope import interface

from ZODB.interfaces import IBroken
from ZODB.POSException import POSError

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IPrincipalMetadataObjectsIntIds

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.utils.property import Lazy

from .interfaces import IGradeBook

def get_uid(obj, intids=None):
	intids = component.getUtility(zope.intid.IIntIds) if intids is None else intids
	try:
		if IBroken.providedBy(obj):
			logger.warn("ignoring broken object %s", type(obj))
		else:
			uid = intids.queryId(obj)
			if uid is None:
				logger.warn("ignoring unregistered object %s", obj)
			else:
				return uid
	except (TypeError, POSError):
		logger.error("ignoring broken object %s", type(obj))
	return None

@component.adapter(IUser)
@interface.implementer(IPrincipalMetadataObjectsIntIds)
class _GradePrincipalObjectsIntIds(object):

	def __init__(self, user):
		self.user = user

	@Lazy
	def _intids(self):
		return component.getUtility(zope.intid.IIntIds)

	def course_collector(self):
		for enrollments in component.subscribers( (self.user,), IPrincipalEnrollments):
			for enrollment in enrollments.iter_enrollments():
				course = ICourseInstance(enrollment, None)
				if course is not None:
					yield course
			
	def iter_intids(self, intids=None):
		result = set()
		intids = self._intids if intids is None else intids
		def _collector():
			for course in self.course_collector():
				book = IGradeBook(course, None)
				if book is None:
					continue
				for grade in book.iter_grades(self.user.username):
					uid = get_uid(grade, intids)
					if uid is not None:
						result.add(uid)
		run_job_in_all_host_sites(_collector)
		for uid in result:
			yield uid
