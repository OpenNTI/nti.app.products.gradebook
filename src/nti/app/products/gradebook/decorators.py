#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various grades pieces.

.. note:: As a namespace, all attributes injected into external
	data should begin with the string `Grade`.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.location.interfaces import ILocation

from pyramid.threadlocal import get_current_request

from nti.assessment.interfaces import IQAssignment
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

	def decorateExternalMapping(self, course, result):
		_links = result.setdefault(LINKS, [])
		book = IGradeBook(course)
		link = Link(book, rel="GradeBook")
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
			if grade is None:
				# Always dummy up a grade (at the right location in
				# the hierarchy) so that we have an 'edit' link if
				# necessary
				grade = Grade()
				grade.__parent__ = entry
				grade.__name__ = user.username

			external['Grade'] = to_external_object(grade)

from .interfaces import ISubmittedAssignmentHistory
from nti.contenttypes.courses.interfaces import is_instructed_by_name
@component.adapter(IQAssignment)
@interface.implementer(IExternalMappingDecorator)
class _InstructorDataForAssignment(object):
	"""
	When an instructor gets access to an assignment,
	they get some extra pieces of information required
	to implement the UI:

	* A count of how many submissions there have been
		for this assignment.
	* A count of how many submissions have been graded.
		(Actually this is disabled now and not sent for
		performance reasons; the design doesn't seem to require
		it.)
	* A link to a view that can access the submissions (history
		items) in bulk.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, assignment, external):
		request = get_current_request()
		if not request:
			return
		username = request.authenticated_userid
		if not username:
			return
		course = ICourseInstance(assignment)
		if not is_instructed_by_name(course, username):
			# We're not an instructor
			return

		book = IGradeBook(course)
		column = book.getColumnForAssignmentId(assignment.__name__)
		if column is None: # pragma: no cover
			# mostly tests
			return

		external['GradeSubmittedCount'] = len(column)

		link_to_bulk_history = Link(ISubmittedAssignmentHistory(column),
									rel='GradeSubmittedAssignmentHistory')
		external.setdefault(LINKS, []).append(link_to_bulk_history)
