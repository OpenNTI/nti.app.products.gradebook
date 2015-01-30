#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.metadata.predicates import BasePrincipalObjects

from nti.site.hostpolicy import run_job_in_all_host_sites

from .interfaces import IGradeBook

def gradebook_collector(self):
	for enrollments in component.subscribers( (self.user,), IPrincipalEnrollments):
		for enrollment in enrollments.iter_enrollments():
			course = ICourseInstance(enrollment, None)
			book = IGradeBook(course, None)
			if book is not None:
				yield book
					
@component.adapter(IUser)
class _GradePrincipalObjects(BasePrincipalObjects):

	def iter_objects(self):
		result = []
		def _collector():
			for book in gradebook_collector():
				for grade in book.iter_grades(self.user.username):
					result.append(grade)
		run_job_in_all_host_sites(_collector)
		for obj in result:
			yield obj

@component.adapter(ISystemUserPrincipal)
class _GradeBookPrincipalObjects(BasePrincipalObjects):

	def iter_objects(self):
		result = []
		def _collector():
			for book in gradebook_collector():
				for part in book.values():
					result.append(part)
					for entry in part.values():
						result.append(entry)
		run_job_in_all_host_sites(_collector)
		for obj in result:
			yield obj
