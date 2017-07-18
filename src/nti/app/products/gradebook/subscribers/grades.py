#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import time

from zope import component

from zope.annotation.interfaces import IAnnotations

from zope.event import notify

from zope.lifecycleevent import ObjectModifiedEvent

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectRemovedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.app.products.gradebook.interfaces import IGrade

from nti.containers.containers import CaseInsensitiveLastModifiedBTreeContainer

from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.activitystream_change import Change

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

_CHANGE_KEY = 'nti.app.products.gradebook.subscribers.ENTRY_CHANGE_KEY'


def _get_user(user):
    if not IUser.providedBy(user) and user:
        result = User.get_user(str(user))
    else:
        result = user
    return user if result is None else user


def _get_entry_change_storage(entry):
    annotes = IAnnotations(entry)
    changes = annotes.get(_CHANGE_KEY)
    if changes is None:
        changes = CaseInsensitiveLastModifiedBTreeContainer()
        changes.__name__ = _CHANGE_KEY
        changes.__parent__ = entry
        annotes[_CHANGE_KEY] = changes
    return annotes[_CHANGE_KEY]


def _do_store_grade_created_event(grade, _):
    storage = _get_entry_change_storage(grade.__parent__)
    if grade.Username in storage:
        change_event = storage[grade.Username]
        change_event.updateLastMod()
        notify(ObjectModifiedEvent(change_event))
        return
    change = Change(Change.CREATED, grade)
    # Set the time to now. Since grades are created
    # at assignment submission time, we rely on the
    # change times for more accurate reporting.
    now = time.time()
    change.lastModified = now
    change.createdTime = now
    if grade.creator is not None:
        change.creator = _get_user(grade.creator)
    else:
        # If we can get to a course, we arbitrarily assume
        # it's from the first instructor in the list
        try:
            instance = ICourseInstance(grade)
            roles = IPrincipalRoleMap(instance)
            for instructor in instance.instructors:
                if roles.getSetting(RID_INSTRUCTOR, instructor.id) is Allow:
                    grade.creator = instructor.id
                    change.creator = IUser(instructor)
                    break
        except (TypeError, IndexError, AttributeError):
            pass
    # Give the change a sharedWith value of the target
    # username; that way it gets indexed cheaply as directed
    # to the user.
    # NOTE: See __acl__ on the grade object; this
    # may change if we have a richer publishing workflow
    change.sharedWith = (grade.Username,)
    change.__copy_object_acl__ = True
    # Now store it, firing events to index, etc. Remember this
    # only happens if the name and parent aren't already
    # set (which they will be because they were copied from grade)
    del change.__name__
    del change.__parent__
    # Define it as top-level content for indexing purposes
    change.__is_toplevel_content__ = True
    storage[grade.Username] = change
    assert change.__parent__ is _get_entry_change_storage(grade.__parent__)
    assert change.__name__ == grade.Username
    return change


@component.adapter(IGrade, IObjectAddedEvent)
@component.adapter(IGrade, IObjectModifiedEvent)
def _store_grade_created_event(grade, event):
    # We're registered for both added and modified events,
    # and we only store a change when the grade actually
    # gets a value for the first time.
    if grade.value is not None:
        _do_store_grade_created_event(grade, event)


@component.adapter(IGrade, IObjectRemovedEvent)
def _remove_grade_event(grade, event):
    try:
        storage = _get_entry_change_storage(grade.__parent__)
        del storage[grade.Username]
    except KeyError:
        pass
