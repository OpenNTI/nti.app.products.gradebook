#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various grades pieces.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.location.interfaces import ILocation

from pyramid.threadlocal import get_current_request

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.links import Link
from nti.dataserver.interfaces import IUser

from nti.externalization.externalization import to_external_object
from nti.externalization.singleton import SingletonDecorator
from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import StandardExternalFields

from .interfaces import IGradeBook

LINKS = StandardExternalFields.LINKS

@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceLinkDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel="GradeBook", elements=('GradeBook'))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceEnrollmentLinkDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		request = get_current_request()
		username = request.authenticated_userid if request else None
		if username:
			course = context.CourseInstance
			_links = result.setdefault(LINKS, [])
			link = Link(course, rel="Grades", elements=('Grades', username))
			interface.alsoProvides(link, ILocation)
			link.__name__ = ''
			link.__parent__ = context
			_links.append(link)

@component.adapter(IUsersCourseAssignmentHistoryItem)
@interface.implementer(IExternalObjectDecorator)
class _UsersCourseAssignmentHistoryItemDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, item, external):
		course = ICourseInstance(item)
		user = IUser(item)
		book = IGradeBook(course)
		assignmentId = item.Submission.assignmentId

		entry = book.getColumnForAssignmentId(assignmentId)
		if entry is not None:
			grade = entry.get(user.username)
			if grade is not None:
				external['Grade'] = to_external_object(grade)
			else:
				external['Grade'] = None
