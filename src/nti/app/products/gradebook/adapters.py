#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook adapters

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.assessment.common.history import get_most_recent_history_item

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItemContainer

from nti.app.products.gradebook.grades import PersistentGrade

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeBookEntry

from nti.appserver.interfaces import ITrustedTopLevelContainerContextProvider

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IStreamChangeEvent

from nti.dataserver.users.users import User

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(IGrade)
@interface.implementer(IGradeBookEntry)
def _GradeToGradeEntry(grade):
    return grade.__parent__


@interface.implementer(IGradeBookEntry)
@component.adapter(IUsersCourseAssignmentHistoryItem)
def _AssignmentHistoryItem2GradeBookEntry(item):
    assignmentId = item.__name__  # by definition
    course = ICourseInstance(item, None)
    # get gradebook entry definition
    gradebook = IGradeBook(course, None)
    if gradebook is not None:
        # pylint: disable=too-many-function-args
        return gradebook.getColumnForAssignmentId(assignmentId)
    return None


@interface.implementer(ICourseInstance)
def _as_course(context):
    """
    Registered as an adapter for things we expect to be a descendant of a course
    """
    return find_interface(context, ICourseInstance,
                          # Don't be strict so that we can still find it
                          # if some parent object has already had its
                          # __parent__ set to None, as
                          # during object removal
                          strict=False)


@interface.implementer(ICourseCatalogEntry)
def _as_catalog_entry(context):
    course = ICourseInstance(context, None)
    return ICourseCatalogEntry(course, None)


def _no_pickle(*unused_args):
    raise TypeError("This object cannot be pickled")


@interface.implementer(IGrade)
def grade_for_history_item(item):
    """
    Registered as an adapter for both history item and summary
    """
    course = ICourseInstance(item, None)
    if course is None:  # during tests
        return
    user = IUser(item, None)  # Can we do this with just the item? item.creator?
    book = IGradeBook(course)
    assignmentId = item.Submission.assignmentId
    # pylint: disable=too-many-function-args
    entry = book.getColumnForAssignmentId(assignmentId)
    if entry is not None and user is not None:
        grade = entry.get(user.username)
        if grade is None:
            # Always dummy up a grade (at the right location in
            # the hierarchy) so that we have an 'edit' link if
            # necessary
            grade = PersistentGrade()
            grade.createdTime = 0
            grade.lastModified = 0
            grade.__parent__ = entry
            grade.__name__ = user.username
        return grade


@component.adapter(IGrade)
@interface.implementer(IUsersCourseAssignmentHistoryItem)
def history_item_for_grade(grade):
    user = IUser(grade, None)
    course = ICourseInstance(grade, None)
    # FIXME: Need a different way to do this with multiple submissions
    return get_most_recent_history_item(user, course, grade.__parent__.AssignmentId)


@component.adapter(IGrade)
@interface.implementer(IUsersCourseAssignmentHistoryItemContainer)
def history_item_container_for_grade(grade):
    history_item = IUsersCourseAssignmentHistoryItem(grade)
    return history_item.__parent__


@component.adapter(IGrade)
@interface.implementer(IUser)
def grade_to_user(grade):
    return User.get_user(grade.__name__)


@component.adapter(IGrade)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _trusted_context_from_grade(obj):
    results = ()
    course = _as_course(obj)
    if course is not None:
        entry = ICourseCatalogEntry(course, None)
        results = (entry,) if entry is not None else ()
    return results


@component.adapter(IStreamChangeEvent)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _trusted_context_from_change(obj):
    obj = getattr(obj, 'object', None)
    return _trusted_context_from_grade(obj)
