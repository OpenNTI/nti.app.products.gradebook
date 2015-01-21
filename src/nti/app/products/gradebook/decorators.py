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
from zope import component

from zope.security.management import NoInteraction
from zope.security.management import checkPermission

from ZODB import loglevels

from nti.app.products.courseware.utils import is_course_instructor

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.links import Link
from nti.dataserver.users import User
from nti.dataserver.traversal import find_interface

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import SingletonDecorator
from nti.externalization.externalization import to_external_object

from .interfaces import IGrade
from .interfaces import IGradeBook
from .interfaces import IExcusedGrade
from .interfaces import ACT_VIEW_GRADES

LINKS = StandardExternalFields.LINKS

def gradebook_readable(context, interaction=None):
	book = IGradeBook(context)
	try:
		return checkPermission(ACT_VIEW_GRADES.id, book, interaction=interaction)
	except NoInteraction:
		return False

def _grades_readable(grades, interaction=None):
	# We use check permission here specifically to avoid the ACLs
	# which could get in our way if we climebed the parent tree
	# up through legacy courses. We want this all to come from the gradebook
	grades = ICourseInstance(grades) if ICourseCatalogEntry.providedBy(grades) else grades
	return gradebook_readable(grades)
grades_readable = _grades_readable

def _find_course_for_user(data, user):
	if user is None:
		return None

	if ICourseCatalogEntry.providedBy(data):
		data = ICourseInstance(data)

	if ICourseInstance.providedBy(data):
		# Yay, they gave us one directly!
		course = data
	else:
		# Try to find the course within the context of the user;
		# this takes into account the user's enrollment status
		# to find the best course (sub) instance
		course = component.queryMultiAdapter( (data, user), ICourseInstance)

	if course is None:
		# Ok, can we get there genericlly, as in the old-school
		# fashion?
		course = ICourseInstance(data, None)
		if course is None:
			# Hmm, maybe we have an assignment-like object and we can
			# try to find the content package it came from and from there
			# go to the one-to-one mapping to courses we used to have
			course = ICourseInstance(find_interface(data, IContentPackage, strict=False),
									 None)
		if course is not None:
			# Snap. Well, we found a course (good!), but not by taking
			# the user into account (bad!)
			logger.debug("No enrollment for user %s in course %s found "
						 "for data %s; assuming generic/global course instance",
						 user, course, data)

	return course

find_course_for_user=_find_course_for_user

@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceGradebookLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	course = None

	def _predicate(self, context, result):
		self.course = _find_course_for_user(context, self.remoteUser)
		return self.course is not None and _grades_readable(self.course)

	def _do_decorate_external(self, course, result):
		course = self.course
		gradebook_shell = {}
		result['GradeBook'] = gradebook_shell
		gradebook_shell['Class'] = "GradeBook"
		_links = gradebook_shell.setdefault(LINKS, [])
		book = IGradeBook( course )
		for name in ('GradeBookSummary','GradeBookByAssignment','GradeBookByUser'):
			link = Link(book, rel=name, elements=(name,))
			_links.append(link)

		return result

@interface.implementer(IExternalMappingDecorator)
class _GradebookLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return self._is_authenticated and _grades_readable(context)

	def _do_decorate_external(self, book, result):
		rel_map = {	'ExportContents': 'contents.csv',
					'GradeBookByUser': 'GradeBookByUser',
					'GradeBookSummary': 'GradeBookSummary',
					'GradeBookByAssignment': 'GradeBookByAssignment'}
		_links = result.setdefault(LINKS, [])
		for rel, element in rel_map.items():
			link = Link(book, rel=rel, elements=(element,))
			_links.append(link)

@interface.implementer(IExternalObjectDecorator)
class _UsersCourseAssignmentHistoryItemDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, item, external):
		grade = IGrade(item, None)
		if grade is not None:
			external['Grade'] = to_external_object(grade)

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

@component.adapter(IGrade)
@interface.implementer(IExternalMappingDecorator)
class _GradeHistoryItemLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return bool(self._is_authenticated and context.AssignmentId)

	def _do_decorate_external(self, context, result):
		user = User.get_user(context.Username) if context.Username else None
		course = find_interface(context, ICourseInstance, strict=False)
		user_history = component.queryMultiAdapter(	(course, user),
													IUsersCourseAssignmentHistory )

		if not user_history:
			return

		for item in user_history.values():
			if item.assignmentId == context.AssignmentId:
				links = result.setdefault(LINKS, [])
				link = Link(item, rel='AssignmentHistoryItem')
				links.append(link)
				return

@component.adapter(IGrade)
@interface.implementer(IExternalMappingDecorator)
class _ExcusedGradeDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return bool(self._is_authenticated)

	def _do_decorate_external(self, context, result):
		user = self.remoteUser
		course = find_interface(context, ICourseInstance, strict=False)
		result['IsExcused'] = bool(IExcusedGrade.providedBy(context))
		if is_course_instructor(course, user):
			links = result.setdefault(LINKS, [])
			rel = 'excuse' if not IExcusedGrade.providedBy(context) else 'unexcuse'
			link = Link(context, elements=(rel,), rel=rel, method='POST')
			links.append(link)

from .interfaces import ISubmittedAssignmentHistory
from .interfaces import ISubmittedAssignmentHistorySummaries

@interface.implementer(IExternalMappingDecorator)
class _InstructorDataForAssignment(AbstractAuthenticatedRequestAwareDecorator):
	"""
	When an instructor gets access to an assignment,
	they get some extra pieces of information required
	to implement the UI:

	* A count of how many submissions there have been
		for this assignment (this is a performance problem).
	* A count of how many submissions have been graded
		(this is cheap).
	* A link to a view that can access the submissions (history
		items) in bulk.
	"""

	course = None

	def _predicate(self, context, result):
		# Take either the course in our context lineage (e.g,
		# .../Courses/Fall2013/CLC3403_LawAndJustice/AssignmentsByOutlineNode)
		# or that we can find mapped to the assignment. This lets us
		# generate correct links for the same assignment instance used
		# across multiple sections; it does fall down though if the
		# assignment actually isn't in that course...but I don't know
		# how that could happen
		# XXX Need a specific unit test for this
		self.course = find_interface(self.request.context, ICourseInstance,
									 strict=False)
		if self.course is not None:
			logger.log(loglevels.TRACE,
					   "Using course instance from request %r for context %s",
					   self.request.context, context)
		if self.course is None:
			self.course = _find_course_for_user(context, self.remoteUser)
		return self.course is not None and _grades_readable(self.course)

	def _do_decorate_external(self, assignment, external):
		course = self.course

		book = IGradeBook(course)
		column = book.getColumnForAssignmentId(assignment.__name__)
		if column is None: # pragma: no cover
			# mostly tests
			return

		external['GradeSubmittedCount'] = len(column)

		asg_history = ISubmittedAssignmentHistory(column)
		external['GradeAssignmentSubmittedCount'] = len(asg_history)

		link_to_bulk_history = Link(asg_history,
									rel='GradeSubmittedAssignmentHistory')
		link_to_summ_history = Link(ISubmittedAssignmentHistorySummaries(column),
									rel='GradeSubmittedAssignmentHistorySummaries')

		ext_links = external.setdefault(LINKS, [])
		ext_links.append(link_to_bulk_history)
		ext_links.append(link_to_summ_history)
