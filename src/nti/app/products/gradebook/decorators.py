#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various grades pieces.

.. note:: As a namespace, all attributes injected into external
	data should begin with the string `Grade`.

.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from pyramid.threadlocal import get_current_request

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.links import Link

from nti.externalization.singleton import SingletonDecorator
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.externalization import to_external_object

from .interfaces import IGrade
from .interfaces import IGradeBook

LINKS = StandardExternalFields.LINKS

from nti.contenttypes.courses.interfaces import is_instructed_by_name
def _course_when_instructed_by_current_user(data, request=None):
	request = request or get_current_request()
	if not request:
		return
	username = request.authenticated_userid
	if not username:
		return
	course = ICourseInstance(data, None)
	if course is None or not is_instructed_by_name(course, username):
		# We're not an instructor
		return

	return course

@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceGradebookLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return _course_when_instructed_by_current_user(context, self.request) is not None

	def _do_decorate_external(self, course, result):
		course = ICourseInstance(course, None)
		if course is not None:
			_links = result.setdefault(LINKS, [])
			book = IGradeBook(course)
			link = Link(book, rel="GradeBook")
			_links.append(link)

@interface.implementer(IExternalMappingDecorator)
class _GradebookLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return _course_when_instructed_by_current_user(context, self.request) is not None

	def _do_decorate_external(self, book, result):
		_links = result.setdefault(LINKS, [])
		link = Link(book, rel='ExportContents', elements=('contents.csv',))
		_links.append(link)

@interface.implementer(IExternalObjectDecorator)
class _UsersCourseAssignmentHistoryItemDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, item, external):
		grade = IGrade(item, None)
		if grade is not None:
			external['Grade'] = to_external_object(grade)

from .interfaces import ISubmittedAssignmentHistory
from .interfaces import ISubmittedAssignmentHistorySummaries

@interface.implementer(IExternalMappingDecorator)
class _InstructorDataForAssignment(AbstractAuthenticatedRequestAwareDecorator):
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

	def _predicate(self, context, result):
		return _course_when_instructed_by_current_user(context, self.request) is not None

	def _do_decorate_external(self, assignment, external):
		course = ICourseInstance(assignment, None)
		if course is None:
			return

		book = IGradeBook(course)
		column = book.getColumnForAssignmentId(assignment.__name__)
		if column is None: # pragma: no cover
			# mostly tests
			return

		external['GradeSubmittedCount'] = len(column)

		link_to_bulk_history = Link(ISubmittedAssignmentHistory(column),
									rel='GradeSubmittedAssignmentHistory')
		link_to_summ_history = Link(ISubmittedAssignmentHistorySummaries(column),
									rel='GradeSubmittedAssignmentHistorySummaries')

		ext_links = external.setdefault(LINKS, [])
		ext_links.append(link_to_bulk_history)
		ext_links.append(link_to_summ_history)
