#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from nti.app.assessment.interfaces import IObjectRegradeEvent
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.app.products.gradebook.autograde_policies import find_autograde_policy

from nti.app.products.gradebook.interfaces import IGrade

from nti.app.products.gradebook.utils import remove_from_container

from nti.app.products.gradebook.utils.gradebook import find_entry_for_item
from nti.app.products.gradebook.utils.gradebook import set_grade_by_assignment_history_item

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User


@component.adapter(IGrade, IObjectModifiedEvent)
def _grade_modified(grade, _):
    """
    When a grade is modified, make sure that the history item that
    conceptually contains it is updated too.
    """
    entry = grade.__parent__
    if entry is None or not entry.AssignmentId:
        # not yet
        return
    user = User.get_user(grade.username)
    if user is None:
        return
    course = ICourseInstance(grade, None)
    if course is None:
        # not yet
        return
    history = component.getMultiAdapter((course, user),
                                        IUsersCourseAssignmentHistory)
    if entry.AssignmentId in history:
        item = history[entry.assignmentId]
        item.updateLastModIfGreater(grade.lastModified)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectAddedEvent)
def _assignment_history_item_added(item, _):
    set_grade_by_assignment_history_item(item)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectModifiedEvent)
def _assignment_history_item_modified(item, _):
    set_grade_by_assignment_history_item(item)


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRemovedEvent)
def _assignment_history_item_removed(item, _):
    entry = find_entry_for_item(item)
    if entry is not None:
        user = IUser(item, None)
        if user is not None:
            try:
                remove_from_container(entry, user.username)
            except KeyError:
                pass


@component.adapter(IUsersCourseAssignmentHistoryItem, IObjectRegradeEvent)
def _regrade_assignment_history_item(item, _):
    assignmentId = item.assignmentId
    course = ICourseInstance(item, None)
    policy = find_autograde_policy(course, assignmentId)
    if policy is not None:
        set_grade_by_assignment_history_item(item)
