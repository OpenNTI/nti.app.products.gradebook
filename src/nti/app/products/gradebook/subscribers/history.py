#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from nti.app.assessment.interfaces import IObjectRegradeEvent
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItemContainer

from nti.app.products.gradebook.autograde_policies import find_autograde_policy

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeBookEntry

from nti.app.products.gradebook.utils import remove_from_container

from nti.app.products.gradebook.utils.gradebook import set_grade_by_assignment_history_item

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.users.users import User

logger = __import__('logging').getLogger(__name__)


@component.adapter(IGrade, IObjectModifiedEvent)
def _grade_modified(grade, unused_event=None):
    """
    When a grade is modified, make sure that the history item that
    conceptually contains it is updated too.
    """
    grade_container = grade.__parent__
    if grade_container is None or not grade_container.AssignmentId:
        # not yet
        return
    user = User.get_user(grade.username)
    if user is None:
        return
    course = ICourseInstance(grade, None)
    if course is None:
        # not yet
        return
    # MetaGrades will not have history item associated with them
    history_item = IUsersCourseAssignmentHistoryItem(grade, None)
    if history_item is not None:
        history_item.updateLastModIfGreater(grade.lastModified)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, unused_event=None):
    set_grade_by_assignment_history_item(item)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectModifiedEvent)
def _assignment_history_item_modified(item, unused_event=None):
    set_grade_by_assignment_history_item(item)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRemovedEvent)
def _assignment_history_item_removed(item, unused_event=None):
    """
    Remove associated grade with this history item.
    """
    grade = IGrade(item, None)
    if grade is not None:
        try:
            del grade.__parent__[grade.__name__]
        except KeyError:
            pass


@component.adapter(IUsersCourseAssignmentHistoryItemContainer, IObjectRemovedEvent)
def _assignment_history_item_container_removed(item_container, unused_event=None):
    """
    Remove all grades for this user and assignment when the history item container
    goes away (reset).
    """
    entry = IGradeBookEntry(item_container, None)
    if entry is not None:
        try:
            remove_from_container(entry, item_container.__name__)
        except KeyError:
            pass


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRegradeEvent)
def _regrade_assignment_history_item(item, unused_event=None):
    assignmentId = item.assignmentId
    course = ICourseInstance(item, None)
    policy = find_autograde_policy(course, assignmentId)
    if policy is not None:
        set_grade_by_assignment_history_item(item)
