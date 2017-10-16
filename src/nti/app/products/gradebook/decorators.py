#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various grades pieces.

.. note:: As a namespace, all attributes injected into external
    data should begin with the string `Grade`.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.security.management import NoInteraction
from zope.security.management import checkPermission

from nti.app.assessment.common.submissions import get_submissions

from nti.app.products.gradebook.interfaces import ACT_VIEW_GRADES

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IExcusedGrade
from nti.app.products.gradebook.interfaces import ISubmittedAssignmentHistory
from nti.app.products.gradebook.interfaces import ISubmittedAssignmentHistorySummaries

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contentlibrary.interfaces import IContentPackage

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

from nti.mimetype.mimetype import MIME_BASE

from nti.traversal.traversal import find_interface

LINKS = StandardExternalFields.LINKS
CLASS = StandardExternalFields.CLASS
MIME_TYPE = StandardExternalFields.MIMETYPE

logger = __import__('logging').getLogger(__name__)


def gradebook_readable(context, interaction=None):
    book = IGradeBook(context)
    try:
        return checkPermission(ACT_VIEW_GRADES.id, book, interaction=interaction)
    except NoInteraction:
        return False


def grades_readable(grades, unused_interaction=None):
    # We use check permission here specifically to avoid the ACLs
    # which could get in our way if we climebed the parent tree
    # up through legacy courses. We want this all to come from the gradebook
    grades = ICourseInstance(
        grades) if ICourseCatalogEntry.providedBy(grades) else grades
    return gradebook_readable(grades)
_grades_readable = grades_readable  # BWC


def find_course_for_user(data, user):
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
        course = component.queryMultiAdapter((data, user), ICourseInstance)

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
_find_course_for_user = find_course_for_user  # BWC


@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceGradebookLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    course = None

    def _predicate(self, context, unused_result):
        self.course = find_course_for_user(context, self.remoteUser)
        return self.course is not None and grades_readable(self.course)

    def _do_decorate_external(self, unused_course, result):
        course = self.course
        # For backwards compatibility
        _links = result.setdefault(LINKS, [])
        link = Link(IGradeBook(course), rel="GradeBook")
        _links.append(link)

        gradebook_shell = {}
        result['GradeBook'] = gradebook_shell
        gradebook_shell[CLASS] = "GradeBook"
        gradebook_shell[MIME_TYPE] = MIME_BASE + '.gradebookshell'
        _links = gradebook_shell.setdefault(LINKS, [])
        gradebook = IGradeBook(course)

        rel_map = {
            'ExportContents': 'contents.csv',
            'GradeBookSummary': 'GradeBookSummary',
            'SetGrade': 'SetGrade'
        }
        for rel, element in rel_map.items():
            link = Link(gradebook, rel=rel, elements=(element,))
            _links.append(link)
        return result


@interface.implementer(IExternalObjectDecorator)
class _UsersCourseAssignmentHistoryItemDecorator(Singleton):

    def decorateExternalObject(self, item, external):
        grade = IGrade(item, None)
        if grade is not None:
            external['Grade'] = to_external_object(grade)


from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory


@component.adapter(IGrade)
@interface.implementer(IExternalMappingDecorator)
class _GradeHistoryItemLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, unused_result):
        return bool(self._is_authenticated and context.AssignmentId)

    def _do_decorate_external(self, context, result):
        user = User.get_user(context.Username) if context.Username else None
        course = find_interface(context, ICourseInstance, strict=False)
        user_history = component.queryMultiAdapter((course, user),
                                                   IUsersCourseAssignmentHistory)
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

    def _predicate(self, unused_context, unused_result):
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


@component.adapter(IGrade)
@interface.implementer(IExternalMappingDecorator)
class _GradeEditLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        return bool(self._is_authenticated)

    def _do_decorate_external(self, context, result):
        course = find_interface(context, ICourseInstance, strict=False)
        if is_course_instructor(course, self.remoteUser):
            links = result.setdefault(LINKS, [])
            link = Link(context, rel='edit', method='POST')
            links.append(link)


@component.adapter(IGrade)
@interface.implementer(IExternalMappingDecorator)
class _GradeCatalogEntryDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self,  unused_context,  unused_result):
        return bool(self._is_authenticated)

    def _do_decorate_external(self, context, result):
        entry = ICourseCatalogEntry(context, None)
        if entry is not None:
            result['CatalogEntryNTIID'] = entry.ntiid


@interface.implementer(IExternalMappingDecorator)
class _InstructorDataForAssignment(AbstractAuthenticatedRequestAwareDecorator):
    """
    When an instructor gets access to an assignment,
    they get some extra pieces of information required
    to implement the UI:

    * A count of how many submissions there have been
            for this assignment.
    * A count of how many submissions have been graded
            (this is cheap).
    * A link to a view that can access the submissions (history
            items) in bulk.
    * A link to the gradebook summary view for this assignment.
    """

    course = None

    def _predicate(self, context,  unused_result):
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
        if self.course is None:
            self.course = find_course_for_user(context, self.remoteUser)
        return self.course is not None and grades_readable(self.course)

    def _get_student_population_count(self, course, assignment):
        """
        The number of students who could possibly take this assignment.
        """
        enrollments = ICourseEnrollments(course)
        if assignment.is_non_public:
            result = enrollments.count_legacy_forcredit_enrollments()
        else:
            result = enrollments.count_enrollments()
        return result

    def _do_decorate_external(self, assignment, external):
        course = self.course

        book = IGradeBook(course)
        column = book.getColumnForAssignmentId(assignment.__name__)
        if column is None:  # pragma: no cover
            # mostly tests
            return

        external['GradeSubmittedCount'] = len(column)

        submissions = get_submissions(assignment, course)
        external['GradeAssignmentSubmittedCount'] = len(submissions or ())
        student_pop_count = self._get_student_population_count(course, assignment)
        external['GradeSubmittedStudentPopulationCount'] = student_pop_count

        asg_history = ISubmittedAssignmentHistory(column)
        link_to_bulk_history = Link(asg_history,
                                    rel='GradeSubmittedAssignmentHistory')

        link_to_summ_history = Link(ISubmittedAssignmentHistorySummaries(column),
                                    rel='GradeSubmittedAssignmentHistorySummaries')

        gradebook_summary_link = Link(column,
                                      rel='GradeBookByAssignment', 
                                      elements=('Summary',))

        ext_links = external.setdefault(LINKS, [])
        ext_links.append(link_to_bulk_history)
        ext_links.append(link_to_summ_history)
        ext_links.append(gradebook_summary_link)
