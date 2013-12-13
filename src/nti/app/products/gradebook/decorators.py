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

from nti.app.assessment import interfaces as appa_interfaces

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.links import Link
from nti.dataserver import interfaces as nti_interfaces

from nti.externalization import externalization
from nti.externalization.singleton import SingletonDecorator
from nti.externalization import interfaces as external_interfaces
from nti.externalization.interfaces import StandardExternalFields

from . import interfaces as grade_interfaces

LINKS = StandardExternalFields.LINKS

@component.adapter(ICourseInstance)
@interface.implementer(external_interfaces.IExternalMappingDecorator)
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
@interface.implementer(external_interfaces.IExternalMappingDecorator)
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

@component.adapter(appa_interfaces.IUsersCourseAssignmentHistoryItem)
@interface.implementer(external_interfaces.IExternalObjectDecorator)
class _UsersCourseAssignmentHistoryItemDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		entry = grade_interfaces.IGradeBookEntry(original, None)
		if entry is not None:
			course = ICourseInstance(original)
			user = nti_interfaces.IUser(original)
			course_grades = grade_interfaces.IGrades(course)
			grade = course_grades.find_grade(entry.NTIID, user.username)
			if grade is None:
				external['Grade'] = externalization.to_external_object(grade)
